"""Sanity checks on the bundled data files and the listing API."""

import json

import pytest

from turkiye_il_ilce import data_info, data_path, ilceler, iller

TR_BBOX = (25.5, 35.7, 45.0, 42.3)


@pytest.fixture(scope="module")
def meta():
    with open(data_path("il-ilce.json"), encoding="utf-8") as fh:
        return json.load(fh)


@pytest.fixture(scope="module")
def ilce_fc():
    with open(data_path("ilceler.geojson"), encoding="utf-8") as fh:
        return json.load(fh)


@pytest.fixture(scope="module")
def il_fc():
    with open(data_path("iller.geojson"), encoding="utf-8") as fh:
        return json.load(fh)


def test_81_provinces_with_plate_codes():
    rows = iller()
    assert len(rows) == 81
    assert [r["plaka"] for r in rows] == list(range(1, 82))
    assert all(r["iso"] == "TR-%02d" % r["plaka"] for r in rows)


@pytest.mark.parametrize(
    "plaka,name",
    [
        (1, "Adana"),
        (6, "Ankara"),
        (7, "Antalya"),
        (16, "Bursa"),
        (34, "İstanbul"),
        (35, "İzmir"),
        (48, "Muğla"),
        (61, "Trabzon"),
        (65, "Van"),
        (81, "Düzce"),
    ],
)
def test_plate_code_names(plaka, name):
    row = [r for r in iller() if r["plaka"] == plaka][0]
    assert row["il"] == name


def test_973_districts(meta, ilce_fc):
    total = sum(len(i["ilceler"]) for i in meta["iller"])
    assert total == 973
    assert len(ilce_fc["features"]) == 973
    assert meta["meta"]["ilce_sayisi"] == 973
    assert data_info()["il_sayisi"] == 81


@pytest.mark.parametrize(
    "il,count",
    [("İstanbul", 39), ("Ankara", 25), ("İzmir", 30), ("Konya", 31), ("Muğla", 13), ("Bayburt", 3), ("Kilis", 4)],
)
def test_district_counts(il, count):
    assert len(ilceler(il)) == count


def test_nested_islet_is_not_a_district():
    assert "Kara Ada" not in ilceler("Muğla")
    assert "Bodrum" in ilceler("Muğla")


def test_ilceler_accepts_many_spellings():
    expected = ilceler("İstanbul")
    for key in ("istanbul", "ISTANBUL", "Istanbul", 34, "34", "TR-34", " tr-34 "):
        assert ilceler(key) == expected
    assert ilceler(6) == ilceler("Ankara") == ilceler("06")
    assert ilceler("Hakkari") == ilceler("hakkâri") == ilceler(30)
    assert ilceler("Elazig") == ilceler("Elâzığ")


def test_ilceler_unknown():
    with pytest.raises(KeyError):
        ilceler("Atlantis")


def test_turkish_characters_survive():
    names = ilceler("İstanbul")
    for n in ("Kadıköy", "Şişli", "Üsküdar", "Çatalca", "Beyoğlu", "Kâğıthane"):
        assert n in names


def test_alphabetical_order_is_turkish():
    names = ilceler("İstanbul")
    pos = names.index
    assert names[0] == "Adalar"
    assert names[-1] == "Zeytinburnu"
    # c < ç, s < ş < t, u < ü < v: the Turkish alphabet, not code point order
    assert pos("Büyükçekmece") < pos("Çatalca") < pos("Çekmeköy") < pos("Esenler")
    assert pos("Sultangazi") < pos("Şile") < pos("Şişli") < pos("Tuzla") < pos("Ümraniye") < pos("Üsküdar") < pos("Zeytinburnu")


def _rings(geom):
    polys = [geom["coordinates"]] if geom["type"] == "Polygon" else geom["coordinates"]
    for poly in polys:
        for ring in poly:
            yield ring


def test_geojson_shape(ilce_fc, il_fc):
    for fc, n in ((ilce_fc, 973), (il_fc, 81)):
        assert fc["type"] == "FeatureCollection"
        assert len(fc["features"]) == n
        for feat in fc["features"]:
            assert feat["geometry"]["type"] in ("Polygon", "MultiPolygon")
            for ring in _rings(feat["geometry"]):
                assert len(ring) >= 4 and ring[0] == ring[-1]
                for x, y in ring:
                    assert TR_BBOX[0] <= x <= TR_BBOX[2] and TR_BBOX[1] <= y <= TR_BBOX[3]


def test_province_layer_matches_listing(il_fc, meta):
    by_plaka = {f["properties"]["plaka"]: f["properties"] for f in il_fc["features"]}
    for il in meta["iller"]:
        props = by_plaka[il["plaka"]]
        assert props["il"] == il["ad"] and props["iso"] == il["iso"]
        assert props["ilce_sayisi"] == len(il["ilceler"])


def test_metadata(meta):
    m = meta["meta"]
    assert m["license"] == "ODbL-1.0"
    assert "OpenStreetMap" in m["attribution"]
    assert m["overture_release"]
