"""Lookup tests against well known landmarks.

Every point is a landmark or town centre whose district is common knowledge
(coordinates from Wikipedia and OpenStreetMap). Points were also checked
against the full-resolution Overture polygons, so a failure here means the
simplified bundle drifted, not that the reference was wrong. No network.
"""

import pytest

from turkiye_il_ilce import lookup

# name, lat, lon, il, plaka, ilce
KNOWN_POINTS = [
    # Marmara
    ("Kadikoy, Haydarpasa station", 40.9966, 29.0189, "İstanbul", 34, "Kadıköy"),
    ("Kadikoy, Bull statue", 40.9903, 29.0291, "İstanbul", 34, "Kadıköy"),
    ("Fatih, Hagia Sophia", 41.0086, 28.9802, "İstanbul", 34, "Fatih"),
    ("Beyoglu, Galata Tower", 41.0256, 28.9744, "İstanbul", 34, "Beyoğlu"),
    ("Besiktas, Dolmabahce Palace", 41.0392, 29.0005, "İstanbul", 34, "Beşiktaş"),
    ("Uskudar, Mihrimah Sultan Mosque", 41.0230, 29.0152, "İstanbul", 34, "Üsküdar"),
    ("Sariyer, Rumeli Fortress", 41.0848, 29.0568, "İstanbul", 34, "Sarıyer"),
    ("Adalar, Buyukada", 40.8738, 29.1290, "İstanbul", 34, "Adalar"),
    ("Bursa, Grand Mosque", 40.1841, 29.0628, "Bursa", 16, "Osmangazi"),
    ("Izmit centre", 40.7650, 29.9400, "Kocaeli", 41, "İzmit"),
    ("Gebze centre", 40.8028, 29.4307, "Kocaeli", 41, "Gebze"),
    ("Adapazari centre", 40.7800, 30.4000, "Sakarya", 54, "Adapazarı"),
    ("Corlu centre", 41.1590, 27.8000, "Tekirdağ", 59, "Çorlu"),
    ("Edirne, Selimiye Mosque", 41.6779, 26.5593, "Edirne", 22, "Edirne Merkez"),
    ("Canakkale, clock tower", 40.1500, 26.4070, "Çanakkale", 17, "Çanakkale Merkez"),
    ("Gokceada town", 40.1990, 25.8740, "Çanakkale", 17, "Gökçeada"),
    ("Bozcaada town", 39.8355, 26.0720, "Çanakkale", 17, "Bozcaada"),
    # Aegean
    ("Konak, Izmir clock tower", 38.4189, 27.1287, "İzmir", 35, "Konak"),
    ("Selcuk, Ephesus", 37.9392, 27.3418, "İzmir", 35, "Selçuk"),
    ("Kusadasi centre", 37.8579, 27.2610, "Aydın", 9, "Kuşadası"),
    ("Pamukkale travertines", 37.9204, 29.1210, "Denizli", 20, "Pamukkale"),
    ("Bodrum town", 37.0344, 27.4305, "Muğla", 48, "Bodrum"),
    ("Marmaris centre", 36.8550, 28.2740, "Muğla", 48, "Marmaris"),
    ("Fethiye centre", 36.6220, 29.1160, "Muğla", 48, "Fethiye"),
    ("Datca centre", 36.7390, 27.6860, "Muğla", 48, "Datça"),
    ("Mugla city", 37.2153, 28.3636, "Muğla", 48, "Menteşe"),
    ("Odunpazari, Eskisehir", 39.7650, 30.5200, "Eskişehir", 26, "Odunpazarı"),
    # Mediterranean
    ("Antalya, Kaleici", 36.8847, 30.7061, "Antalya", 7, "Muratpaşa"),
    ("Alanya centre", 36.5438, 31.9998, "Antalya", 7, "Alanya"),
    ("Tarsus, Cleopatra Gate", 36.9190, 34.8920, "Mersin", 33, "Tarsus"),
    ("Antakya, Habib-i Neccar Mosque", 36.2020, 36.1600, "Hatay", 31, "Antakya"),
    ("Iskenderun centre", 36.5870, 36.1700, "Hatay", 31, "İskenderun"),
    # Central Anatolia
    ("Cankaya, Anitkabir", 39.9256, 32.8369, "Ankara", 6, "Çankaya"),
    ("Cankaya, Kizilay", 39.9208, 32.8541, "Ankara", 6, "Çankaya"),
    ("Urgup centre", 38.6310, 34.9130, "Nevşehir", 50, "Ürgüp"),
    ("Goreme", 38.6431, 34.8287, "Nevşehir", 50, "Nevşehir Merkez"),
    ("Safranbolu old town", 41.2500, 32.6900, "Karabük", 78, "Safranbolu"),
    ("Bolu centre", 40.7350, 31.6060, "Bolu", 14, "Bolu Merkez"),
    # Black Sea
    ("Trabzon, Ortahisar square", 41.0027, 39.7168, "Trabzon", 61, "Ortahisar"),
    ("Macka, Sumela Monastery", 40.6906, 39.6586, "Trabzon", 61, "Maçka"),
    ("Rize centre", 41.0201, 40.5234, "Rize", 53, "Rize Merkez"),
    ("Samsun, Republic Square", 41.2867, 36.3300, "Samsun", 55, "İlkadım"),
    ("Sinop centre", 42.0270, 35.1510, "Sinop", 57, "Sinop Merkez"),
    ("Amasra centre", 41.7500, 32.3860, "Bartın", 74, "Amasra"),
    # East and Southeast
    ("Van, Ipekyolu centre", 38.4946, 43.3832, "Van", 65, "İpekyolu"),
    ("Van Fortress", 38.5036, 43.3400, "Van", 65, "İpekyolu"),
    ("Erzurum, Double Minaret Madrasa", 39.9056, 41.2745, "Erzurum", 25, "Yakutiye"),
    ("Kars, castle", 40.6076, 43.0975, "Kars", 36, "Kars Merkez"),
    ("Dogubayazit, Ishak Pasha Palace", 39.5183, 44.1342, "Ağrı", 4, "Doğubayazıt"),
    ("Kahta, Mount Nemrut", 37.9808, 38.7406, "Adıyaman", 2, "Kâhta"),
    ("Diyarbakir, Great Mosque", 37.9114, 40.2368, "Diyarbakır", 21, "Sur"),
    ("Mardin, Artuklu", 37.3130, 40.7350, "Mardin", 47, "Artuklu"),
    ("Birecik centre", 37.0240, 37.9760, "Şanlıurfa", 63, "Birecik"),
    ("Harran", 36.8650, 39.0270, "Şanlıurfa", 63, "Harran"),
    ("Yuksekova centre", 37.5740, 44.2850, "Hakkâri", 30, "Yüksekova"),
]


def test_at_least_thirty_known_points():
    assert len(KNOWN_POINTS) >= 30


@pytest.mark.parametrize("name,lat,lon,il,plaka,ilce", KNOWN_POINTS, ids=[p[0] for p in KNOWN_POINTS])
def test_known_point(name, lat, lon, il, plaka, ilce):
    assert lookup(lat, lon) == {
        "il": il,
        "plaka": plaka,
        "iso": "TR-%02d" % plaka,
        "ilce": ilce,
    }


def test_spec_example_kadikoy():
    assert lookup(40.99, 29.03)["ilce"] == "Kadıköy"


@pytest.mark.parametrize(
    "name,lat,lon",
    [
        ("Marmara Sea, open water", 40.70, 28.00),
        ("Black Sea, open water", 42.50, 35.00),
        ("Mediterranean, open water", 35.50, 33.00),
        ("Aegean Sea, open water", 38.50, 25.20),
        ("Athens", 37.9838, 23.7275),
        ("Tbilisi", 41.7151, 44.8271),
        ("Baku", 40.4093, 49.8671),
        ("Sofia", 42.6977, 23.3219),
        ("Nicosia (northern Cyprus is not in the dataset)", 35.1856, 33.3823),
        ("Null Island", 0.0, 0.0),
        ("Mid Atlantic", 30.0, -40.0),
        ("Southern hemisphere", -33.8688, 151.2093),
    ],
)
def test_outside_returns_none(name, lat, lon):
    assert lookup(lat, lon) is None


@pytest.mark.parametrize("lat,lon", [(91, 10), (-91, 10), (10, 181), (10, -181), (float("nan"), 30), (30, float("inf"))])
def test_invalid_coordinates_raise(lat, lon):
    with pytest.raises(ValueError):
        lookup(lat, lon)


def test_result_is_a_copy():
    first = lookup(40.99, 29.03)
    first["ilce"] = "changed"
    assert lookup(40.99, 29.03)["ilce"] == "Kadıköy"


def test_swapped_arguments_do_not_match():
    # (lon, lat) order by mistake lands far outside Turkiye
    assert lookup(29.03, 40.99) is None


def test_strings_are_coerced():
    assert lookup("40.99", "29.03")["ilce"] == "Kadıköy"


def test_lookup_speed():
    import time

    lookup(40.99, 29.03)  # warm: loads the data once
    points = [(p[1], p[2]) for p in KNOWN_POINTS]
    start = time.perf_counter()
    rounds = 5
    for _ in range(rounds):
        for lat, lon in points:
            lookup(lat, lon)
    per_call_ms = (time.perf_counter() - start) * 1000 / (rounds * len(points))
    # README quotes the measured figure (target < 5 ms); the bound here is loose
    # so a slow CI runner does not fail the build.
    assert per_call_ms < 25, per_call_ms
