"""Point-in-polygon lookup over the bundled district boundaries.

Pure Python, standard library only. A bounding box pre-filter narrows the
973 district polygons down to a handful, then a ray-casting test decides.
"""

from __future__ import annotations

import json
import math
import threading
from pathlib import Path
from typing import Dict, List, Optional, Union

_PKG_DIR = Path(__file__).resolve().parent
# Wheels carry the data next to the code; a source checkout keeps it in <repo>/data.
_DATA_DIRS = (_PKG_DIR / "data", _PKG_DIR.parents[1] / "data")

_lock = threading.Lock()
_index = None  # built lazily, see _load()


def data_path(name: str) -> Path:
    """Path of a bundled data file (``iller.geojson``, ``ilceler.geojson``, ``il-ilce.json``)."""
    for base in _DATA_DIRS:
        candidate = base / name
        if candidate.is_file():
            return candidate
    raise FileNotFoundError(
        "data file %r not found; run scripts/build_data.py or reinstall the package" % name
    )


def _ring_bbox(ring):
    xs = [p[0] for p in ring]
    ys = [p[1] for p in ring]
    return min(xs), min(ys), max(xs), max(ys)


def _prepare_ring(ring):
    # Split into two flat lists: faster to index than a list of pairs.
    return [p[0] for p in ring], [p[1] for p in ring]


def _load():
    global _index
    if _index is not None:
        return _index
    with _lock:
        if _index is not None:
            return _index
        with open(data_path("ilceler.geojson"), "r", encoding="utf-8") as fh:
            fc = json.load(fh)
        with open(data_path("il-ilce.json"), "r", encoding="utf-8") as fh:
            meta = json.load(fh)

        cells = []  # (minx, miny, maxx, maxy, polygons, info)
        for feat in fc["features"]:
            props = feat["properties"]
            info = {
                "il": props["il"],
                "plaka": props["plaka"],
                "iso": props["iso"],
                "ilce": props["ilce"],
            }
            geom = feat["geometry"]
            polys = [geom["coordinates"]] if geom["type"] == "Polygon" else geom["coordinates"]
            prepared = []
            fminx = fminy = math.inf
            fmaxx = fmaxy = -math.inf
            for poly in polys:
                outer = poly[0]
                minx, miny, maxx, maxy = _ring_bbox(outer)
                fminx, fminy = min(fminx, minx), min(fminy, miny)
                fmaxx, fmaxy = max(fmaxx, maxx), max(fmaxy, maxy)
                prepared.append(
                    (
                        minx,
                        miny,
                        maxx,
                        maxy,
                        _prepare_ring(outer),
                        [_prepare_ring(h) for h in poly[1:]],
                    )
                )
            cells.append((fminx, fminy, fmaxx, fmaxy, prepared, info))

        iller_list = []
        by_key: Dict[str, dict] = {}
        for il in meta["iller"]:
            entry = {"il": il["ad"], "plaka": il["plaka"], "iso": il["iso"]}
            iller_list.append(entry)
            ilce_names = sorted(il["ilceler"], key=_sort_key)
            record = {"entry": entry, "ilceler": ilce_names}
            by_key[_fold(il["ad"])] = record
            by_key[str(il["plaka"])] = record
            by_key["%02d" % il["plaka"]] = record
            by_key[il["iso"].lower()] = record
        _index = {"cells": cells, "iller": iller_list, "by_key": by_key, "meta": meta["meta"]}
        return _index


_TR_FOLD = str.maketrans(
    {
        "ç": "c",
        "ğ": "g",
        "ö": "o",
        "ş": "s",
        "ü": "u",
        "â": "a",
        "î": "i",
        "û": "u",
    }
)


def _fold(text: str) -> str:
    """Case and diacritic insensitive key: 'İstanbul', 'ISTANBUL', 'istanbul' all match."""
    text = text.strip().replace("İ", "i").replace("I", "i").replace("ı", "i").lower()
    return text.translate(_TR_FOLD)


_ACCENTS = str.maketrans({"â": "a", "î": "i", "û": "u"})
_TR_ORDER = "abcçdefgğhıijklmnoöprsştuüvyz"
_TR_RANK = {ch: i for i, ch in enumerate(_TR_ORDER)}


def _sort_key(name: str):
    low = name.replace("İ", "i").replace("I", "ı").lower().translate(_ACCENTS)
    return [_TR_RANK.get(ch, 100 + ord(ch)) for ch in low]


def _in_ring(x: float, y: float, xs, ys) -> bool:
    inside = False
    n = len(xs)
    j = n - 1
    xj = xs[j]
    yj = ys[j]
    for i in range(n):
        xi = xs[i]
        yi = ys[i]
        if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi) + xi:
            inside = not inside
        xj = xi
        yj = yi
    return inside


def _in_polygon(x: float, y: float, poly) -> bool:
    minx, miny, maxx, maxy, (oxs, oys), holes = poly
    if x < minx or x > maxx or y < miny or y > maxy:
        return False
    if not _in_ring(x, y, oxs, oys):
        return False
    for hxs, hys in holes:
        if _in_ring(x, y, hxs, hys):
            return False
    return True


def lookup(lat: float, lon: float) -> Optional[Dict[str, Union[str, int]]]:
    """Return the province and district containing a WGS84 point, or ``None``.

    ``None`` means the point is outside the bundled land boundaries: at sea,
    abroad, or in northern Cyprus (not part of the dataset).

    >>> lookup(41.0086, 28.9802)
    {'il': 'İstanbul', 'plaka': 34, 'iso': 'TR-34', 'ilce': 'Fatih'}

    Raises ``ValueError`` for a latitude outside -90..90, a longitude outside
    -180..180, or a non-finite value.
    """
    lat = float(lat)
    lon = float(lon)
    if not (math.isfinite(lat) and math.isfinite(lon)):
        raise ValueError("lat and lon must be finite numbers")
    if not -90.0 <= lat <= 90.0:
        raise ValueError("lat must be between -90 and 90, got %r" % lat)
    if not -180.0 <= lon <= 180.0:
        raise ValueError("lon must be between -180 and 180, got %r" % lon)

    for minx, miny, maxx, maxy, polys, info in _load()["cells"]:
        if lon < minx or lon > maxx or lat < miny or lat > maxy:
            continue
        for poly in polys:
            if _in_polygon(lon, lat, poly):
                return dict(info)
    return None


def data_info() -> Dict[str, object]:
    """Metadata of the bundled data: Overture release, counts, licence, attribution."""
    return dict(_load()["meta"])


def iller() -> List[Dict[str, Union[str, int]]]:
    """All 81 provinces, ordered by plate code: ``{"il", "plaka", "iso"}``."""
    return [dict(e) for e in _load()["iller"]]


def ilceler(il: Union[str, int]) -> List[str]:
    """District names of a province, in Turkish alphabetical order.

    ``il`` can be the name (``"İstanbul"``, ``"istanbul"``), the plate code
    (``34``, ``"34"``, ``"06"``) or the ISO code (``"TR-34"``).
    Raises ``KeyError`` for an unknown province.
    """
    key = _fold(str(il))
    record = _load()["by_key"].get(key)
    if record is None:
        raise KeyError("unknown il: %r" % (il,))
    return list(record["ilceler"])
