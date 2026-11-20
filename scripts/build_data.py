#!/usr/bin/env python3
"""Build the bundled boundary data from Overture Maps.

Reads the Overture Maps ``divisions`` theme straight from the public S3 bucket
(DuckDB + the httpfs and spatial extensions), keeps Turkiye's provinces
(``subtype='region'``) and districts (``subtype='county'``), simplifies them and
writes:

    data/iller.geojson     81 provinces
    data/ilceler.geojson   973 districts
    data/il-ilce.json      plate code, ISO code, name and district names per province

Build-time dependency only (the library itself needs nothing):

    pip install duckdb
    python scripts/build_data.py                  # newest Overture release
    python scripts/build_data.py --release 2026-11-18.0 --tolerance 0.0006

Data (c) OpenStreetMap contributors, Overture Maps Foundation, ODbL 1.0.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

try:
    import duckdb
except ImportError:  # pragma: no cover
    sys.exit("duckdb is required to rebuild the data: pip install duckdb")

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"

BUCKET = "s3://overturemaps-us-west-2/release"
DIVISIONS = "theme=divisions/type=division_area"
EXPECTED_IL = 81
# Official district count at the time of writing (TUIK / MERNIS). Printed as a
# check, not enforced: the number changes when a law creates new districts.
EXPECTED_ILCE = 973

DEFAULT_TOLERANCE = 0.0008  # degrees, about 90 m of latitude
COORD_DECIMALS = 4  # about 11 m, well below the simplification tolerance


def latest_release(con) -> str:
    rows = con.execute(f"SELECT file FROM glob('{BUCKET}/*/{DIVISIONS}/*')").fetchall()
    found = set()
    for (path,) in rows:
        m = re.search(r"/release/(\d{4}-\d{2}-\d{2}\.\d+)/", path)
        if m:
            found.add(m.group(1))
    if not found:
        sys.exit("no Overture releases found in " + BUCKET)

    def key(rel):
        date, patch = rel.split(".")
        return date, int(patch)

    return max(found, key=key)


def signed_area(ring):
    s = 0.0
    for i in range(len(ring) - 1):
        x1, y1 = ring[i]
        x2, y2 = ring[i + 1]
        s += x1 * y2 - x2 * y1
    return s / 2.0


def clean_ring(ring, want_ccw):
    """Round, drop repeated points, close the ring and fix its winding (RFC 7946)."""
    pts = []
    for x, y in ring:
        p = (round(x, COORD_DECIMALS), round(y, COORD_DECIMALS))
        if not pts or p != pts[-1]:
            pts.append(p)
    if len(pts) > 1 and pts[0] == pts[-1]:
        pts.pop()
    if len(pts) < 3:
        return None
    pts.append(pts[0])
    if (signed_area(pts) > 0) != want_ccw:
        pts.reverse()
    return [list(p) for p in pts]


def clean_geometry(geom):
    polys = [geom["coordinates"]] if geom["type"] == "Polygon" else geom["coordinates"]
    out = []
    for poly in polys:
        rings = []
        for idx, ring in enumerate(poly):
            r = clean_ring(ring, want_ccw=(idx == 0))
            if r is None:
                if idx == 0:
                    rings = []
                    break
                continue
            rings.append(r)
        if rings:
            out.append(rings)
    if not out:
        return None
    if len(out) == 1:
        return {"type": "Polygon", "coordinates": out[0]}
    return {"type": "MultiPolygon", "coordinates": out}


def write_geojson(path, features):
    fc = {"type": "FeatureCollection", "features": features}
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(fc, fh, ensure_ascii=False, separators=(",", ":"))
        fh.write("\n")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--release", help="Overture release, e.g. 2026-11-18.0 (default: newest)")
    ap.add_argument("--tolerance", type=float, default=DEFAULT_TOLERANCE, help="simplification tolerance in degrees")
    args = ap.parse_args()

    con = duckdb.connect()
    con.execute("INSTALL httpfs; LOAD httpfs; INSTALL spatial; LOAD spatial;")
    con.execute("SET s3_region='us-west-2'; SET enable_progress_bar=false;")

    release = args.release or latest_release(con)
    print("Overture release:", release)
    src = f"{BUCKET}/{release}/{DIVISIONS}/*"

    # class='land' drops the maritime twin that every coastal province carries
    # (81 land + 28 maritime region rows = 109).
    con.execute(
        f"""
        CREATE TABLE raw AS
        SELECT division_id AS id, subtype, region, names.primary AS name,
               ST_Force2D(geometry) AS g,
               list_distinct(list_transform(sources, s -> s.license)) AS licenses
        FROM read_parquet('{src}', hive_partitioning=1)
        WHERE country = 'TR' AND subtype IN ('region', 'county') AND class = 'land'
        """
    )
    n_region_raw, n_county_raw = con.execute(
        "SELECT count(*) FILTER (WHERE subtype='region'), count(*) FILTER (WHERE subtype='county') FROM raw"
    ).fetchone()
    print(f"land rows: {n_region_raw} region, {n_county_raw} county")

    # The geometry of every row is OpenStreetMap (ODbL); other licences only
    # appear on translated names, which this build does not use.
    geom_licenses = con.execute(
        "SELECT DISTINCT unnest(licenses) FROM raw WHERE subtype IN ('region','county')"
    ).fetchall()
    print("source licences present on the rows:", sorted(x[0] for x in geom_licenses))

    # Overture sometimes carries an administrative boundary that is not a
    # district but sits entirely inside one (for example the islet "Kara Ada"
    # inside Bodrum). Drop a county that is >90% covered by another county.
    nested = con.execute(
        """
        SELECT a.id, a.name, a.region, b.name
        FROM raw a JOIN raw b
          ON a.subtype='county' AND b.subtype='county' AND a.id <> b.id
         AND ST_Intersects(a.g, b.g)
        WHERE ST_Area(ST_Intersection(a.g, b.g)) > 0.9 * ST_Area(a.g)
        """
    ).fetchall()
    for _id, name, reg, inside in nested:
        print(f"  dropping nested boundary: {name} ({reg}) lies inside {inside}")
    con.execute("CREATE TABLE drop_ids AS SELECT * FROM (VALUES %s) t(id)" % (
        ",".join("('%s')" % r[0] for r in nested) or "(NULL)"))

    con.execute(
        """
        CREATE TABLE county AS
        SELECT id, region, name, g FROM raw
        WHERE subtype='county' AND id NOT IN (SELECT id FROM drop_ids WHERE id IS NOT NULL)
        ORDER BY region, name, id
        """
    )
    n_county = con.execute("SELECT count(*) FROM county").fetchone()[0]

    # Province list (names + plate codes) comes from the region rows.
    regions = con.execute(
        "SELECT region, name FROM raw WHERE subtype='region' ORDER BY region"
    ).fetchall()
    codes = {}
    for reg, name in regions:
        m = re.fullmatch(r"TR-(\d{2})", reg or "")
        if not m:
            sys.exit(f"unexpected region code {reg!r} for {name!r}")
        plaka = int(m.group(1))
        if plaka in codes:
            sys.exit(f"duplicate plate code {plaka}")
        codes[plaka] = (reg, name)
    if len(codes) != EXPECTED_IL or sorted(codes) != list(range(1, EXPECTED_IL + 1)):
        sys.exit(f"expected provinces 1..{EXPECTED_IL}, got {len(codes)}")
    county_regions = {r[0] for r in con.execute("SELECT DISTINCT region FROM county").fetchall()}
    if county_regions != {v[0] for v in codes.values()}:
        sys.exit("districts and provinces do not cover the same region codes")

    print("coverage valid (no overlaps or gaps in shared edges):",
          con.execute("SELECT ST_CoverageInvalidEdges(list(g)) IS NULL FROM county").fetchone()[0])

    pts_before = con.execute("SELECT sum(ST_NPoints(g)) FROM county").fetchone()[0]
    # Coverage simplification keeps neighbouring districts glued together, so
    # simplifying never opens gaps or overlaps between them.
    con.execute(
        f"""
        CREATE TABLE county_n AS
        SELECT row_number() OVER (ORDER BY region, name, id) AS rn, id, region, name, g FROM county
        """
    )
    # The scalar form simplifies the whole list in one pass (seconds). The
    # window-aggregate form re-runs per row and takes far longer. ST_Dump walks
    # the returned collection in input order, so path[1] is the input row number.
    con.execute(
        f"""
        CREATE TABLE simple AS
        WITH dumped AS (
            SELECT unnest(ST_Dump(ST_CoverageSimplify(list(g ORDER BY rn), {args.tolerance}))) AS x
            FROM county_n
        ),
        parts AS (SELECT x.path[1] AS rn, x.geom AS geom FROM dumped)
        SELECT c.id, c.region, c.name, ST_Collect(list(p.geom)) AS g
        FROM county_n c JOIN parts p ON p.rn = c.rn
        GROUP BY c.id, c.region, c.name
        """
    )
    pts_after = con.execute("SELECT sum(ST_NPoints(g)) FROM simple").fetchone()[0]
    print(f"vertices: {pts_before} -> {pts_after} (tolerance {args.tolerance} deg)")
    empty = con.execute("SELECT count(*) FROM simple WHERE ST_IsEmpty(g)").fetchone()[0]
    if empty:
        sys.exit(f"{empty} districts collapsed to empty geometry; lower --tolerance")

    # Provinces are the union of their simplified districts: the two layers
    # share every edge and always agree.
    con.execute(
        "CREATE TABLE province AS SELECT region, ST_CoverageUnion_Agg(g) AS g FROM simple GROUP BY region"
    )

    ilce_features = []
    for id_, reg, name, gj in con.execute(
        "SELECT id, region, name, ST_AsGeoJSON(g) FROM simple ORDER BY region, name, id"
    ).fetchall():
        plaka = int(reg[3:])
        geom = clean_geometry(json.loads(gj))
        if geom is None:
            sys.exit(f"empty geometry after cleaning: {name}")
        ilce_features.append(
            {
                "type": "Feature",
                "properties": {"il": codes[plaka][1], "plaka": plaka, "iso": reg, "ilce": name},
                "geometry": geom,
            }
        )

    ilce_count = {}
    for f in ilce_features:
        ilce_count[f["properties"]["plaka"]] = ilce_count.get(f["properties"]["plaka"], 0) + 1

    il_features = []
    for reg, gj in con.execute("SELECT region, ST_AsGeoJSON(g) FROM province ORDER BY region").fetchall():
        plaka = int(reg[3:])
        geom = clean_geometry(json.loads(gj))
        il_features.append(
            {
                "type": "Feature",
                "properties": {
                    "il": codes[plaka][1],
                    "plaka": plaka,
                    "iso": reg,
                    "ilce_sayisi": ilce_count[plaka],
                },
                "geometry": geom,
            }
        )

    iller = []
    for plaka in sorted(codes):
        reg, name = codes[plaka]
        names = sorted(f["properties"]["ilce"] for f in ilce_features if f["properties"]["plaka"] == plaka)
        iller.append({"plaka": plaka, "iso": reg, "ad": name, "ilceler": names})

    DATA.mkdir(exist_ok=True)
    write_geojson(DATA / "ilceler.geojson", ilce_features)
    write_geojson(DATA / "iller.geojson", il_features)
    meta = {
        "meta": {
            "overture_release": release,
            "built": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            "il_sayisi": len(iller),
            "ilce_sayisi": len(ilce_features),
            "simplify_tolerance_deg": args.tolerance,
            "coordinate_decimals": COORD_DECIMALS,
            "license": "ODbL-1.0",
            "attribution": "(c) OpenStreetMap contributors, Overture Maps Foundation",
        },
        "iller": iller,
    }
    with open(DATA / "il-ilce.json", "w", encoding="utf-8", newline="\n") as fh:
        json.dump(meta, fh, ensure_ascii=False, indent=1)
        fh.write("\n")

    total = 0
    for name in ("iller.geojson", "ilceler.geojson", "il-ilce.json"):
        size = (DATA / name).stat().st_size
        total += size
        print(f"  {name}: {size / 1e6:.2f} MB")
    print(f"total {total / 1e6:.2f} MB")
    print(f"provinces: {len(iller)} (expected {EXPECTED_IL})")
    print(f"districts: {len(ilce_features)} (official count {EXPECTED_ILCE}; Overture land rows {n_county_raw})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
