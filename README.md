# turkiye-il-ilce

Find the Turkish province (il) and district (ilce) of any coordinate, offline, in pure Python. Ships current boundary data as GeoJSON too.

```python
>>> from turkiye_il_ilce import lookup
>>> lookup(40.99, 29.03)
{'il': 'İstanbul', 'plaka': 34, 'iso': 'TR-34', 'ilce': 'Kadıköy'}
```

*Türkçe açıklama için aşağıya bakın: [Türkçe](#türkçe).*

## Why this exists

- **Most Turkish boundary GeoJSON repositories are old.** The ones that come up first date from 2021-22 and many stop at province level. This one is built from a November 2026 release and rebuilds with one command when the data changes.
- **Offline reverse geocoders do not know district borders.** Libraries built on GeoNames return the nearest populated place, which is often the wrong district and says nothing about whether the point is inside Turkiye at all.
- **Calling a geocoding API per row does not scale.** Tagging a customer list, a delivery log or a million business records by province and district should not need a network call, a key or a quota.

This package gives you real polygons (Overture Maps release 2026-11-18.0, 81 provinces, 973 districts), a lookup that needs no dependencies, and the same data as plain GeoJSON for any other language.

## Install

The package is not on PyPI yet. Install from GitHub (Python 3.9+, no dependencies):

```bash
pip install git+https://github.com/Pinlyx/turkiye-il-ilce
```

## Quick start

```python
from turkiye_il_ilce import lookup, iller, ilceler

lookup(39.9256, 32.8369)   # Anitkabir
# {'il': 'Ankara', 'plaka': 6, 'iso': 'TR-06', 'ilce': 'Çankaya'}

lookup(40.70, 28.00)       # Marmara Sea
# None

len(iller())               # 81
ilceler("izmir")[:4]       # ['Aliağa', 'Balçova', 'Bayındır', 'Bayraklı']
ilceler(34)[:3]            # ['Adalar', 'Arnavutköy', 'Ataşehir']
```

Command line:

```console
$ il-ilce 40.99 29.03
İstanbul / Kadıköy (34, TR-34)
$ il-ilce 40.99 29.03 --json
{"il": "İstanbul", "plaka": 34, "iso": "TR-34", "ilce": "Kadıköy"}
$ il-ilce 40.70 28.00     # open sea: prints "not found" to stderr, exit code 1
```

Latitude comes first, longitude second (WGS84, decimal degrees).

## API

| Call | Returns |
| --- | --- |
| `lookup(lat, lon)` | `{"il", "plaka", "iso", "ilce"}`, or `None` when the point is not on Turkish land (sea, abroad, northern Cyprus). Raises `ValueError` for a latitude outside -90..90, a longitude outside -180..180 or a non-finite value. |
| `iller()` | The 81 provinces ordered by plate code, as `{"il", "plaka", "iso"}`. |
| `ilceler(il)` | District names of one province in Turkish alphabetical order. `il` may be the name in any case or without diacritics (`"İstanbul"`, `"istanbul"`, `"ISTANBUL"`), the plate code (`34`, `"34"`, `"06"`) or the ISO code (`"TR-34"`). Raises `KeyError` for an unknown province. |
| `data_info()` | Metadata of the bundled data: Overture release, counts, simplification tolerance, licence. |
| `data_path(name)` | `pathlib.Path` of a bundled data file, if you want to read the GeoJSON yourself. |

`plaka` is the plate code as an integer (1 to 81). It is identical to the number in the ISO 3166-2:TR code (`TR-34`).

Names follow the Overture / OpenStreetMap spelling: `Elâzığ`, `Hakkâri` and `Kâhta` carry the circumflex, and the central district of a province is written `<Province> Merkez` (`Edirne Merkez`, `Çanakkale Merkez`).

## Use the data from any language

The `data/` folder is plain GeoJSON in WGS84 (`[longitude, latitude]`), so Node, Go, QGIS, PostGIS, DuckDB and everything else can use it without Python.

| File | Content | Size |
| --- | --- | --- |
| `data/ilceler.geojson` | 973 district polygons. Properties: `il`, `plaka`, `iso`, `ilce` | 5.6 MB |
| `data/iller.geojson` | 81 province polygons. Properties: `il`, `plaka`, `iso`, `ilce_sayisi` | 2.2 MB |
| `data/il-ilce.json` | Per province: plate code, ISO code, name and the list of district names, plus build metadata | 23 KB |

Provinces are the union of their simplified districts, so the two layers share every edge and never disagree.

DuckDB:

```sql
INSTALL spatial; LOAD spatial;
SELECT il, ilce FROM ST_Read('data/ilceler.geojson') WHERE ST_Contains(geom, ST_Point(29.03, 40.99));
```

Node with Turf (`npm i @turf/boolean-point-in-polygon @turf/helpers`):

```js
import { readFileSync } from "node:fs";
import booleanPointInPolygon from "@turf/boolean-point-in-polygon";
import { point } from "@turf/helpers";

const districts = JSON.parse(readFileSync("data/ilceler.geojson", "utf8"));
const hit = districts.features.find((f) => booleanPointInPolygon(point([29.03, 40.99]), f));
console.log(hit?.properties); // { il: 'İstanbul', plaka: 34, iso: 'TR-34', ilce: 'Kadıköy' }
```

## How it works, and its limits

**How.** Each district is a polygon. `lookup` rejects polygons by bounding box first, then runs a ray-casting point-in-polygon test on the few that remain. Data is read from the bundled file on the first call and kept in memory.

**Speed.** On a Windows PC with Python 3.10, 20,000 random points in the Turkish bounding box: mean 0.15 ms, median 0.11 ms, 99th percentile 0.8 ms per lookup. The first call also loads the data and takes about 0.4 s. The target was under 5 ms.

**Accuracy.** Boundaries are simplified (topology-preserving coverage simplification, tolerance 0.0008 degrees, about 90 m) and coordinates are rounded to 4 decimals (about 11 m) to keep the data near 8 MB. Measured against the full-resolution Overture polygons on 20,000 random points in the Turkish bounding box (14,257 of them on land): 14,254 got the identical province and district (99.98%), 3 landed in a neighbouring district of the same province, none changed province, and land versus sea agreed every time. Points within roughly 100 m of a district border or the coastline can land on the wrong side. This is a data product for tagging and filtering, not a cadastral tool.

**Limits, honestly:**

- The boundaries are **not official**. They come from OpenStreetMap through Overture Maps, not from the General Directorate of Mapping or TUIK. Recent administrative changes appear only after OpenStreetMap contributors map them.
- Provinces and districts only. No neighbourhoods (mahalle) and no villages.
- Land only, clipped to the OpenStreetMap coastline. A point on a pier, in a harbour or on a ship returns `None` or the nearest district depending on where the simplified coast falls. Territorial waters are not included.
- Northern Cyprus is not part of the dataset, so it returns `None`.
- 973 districts, not 974. Overture has 974 land rows with `subtype = county`; one of them, the islet "Kara Ada" in Muğla, is a boundary that lies completely inside Bodrum and is not a district. `scripts/build_data.py` drops any county that is more than 90% covered by another county. The province level has 81 land rows, but 109 rows overall because every coastal province also carries a `class = 'maritime'` polygon; those are filtered out.
- Source licences were checked on the `sources` field of every row used: all geometry is OpenStreetMap (ODbL-1.0). Esri Community Maps (CC-BY-4.0) appears only on translated names, which this package does not use.

## Rebuild the data

`scripts/build_data.py` reads the Overture `divisions` theme from the public S3 bucket with DuckDB and writes `data/`. It needs `duckdb` at build time only.

```bash
python -m pip install duckdb
python scripts/build_data.py                   # newest Overture release
python scripts/build_data.py --release 2026-11-18.0 --tolerance 0.0008
python -m pytest
```

It prints the release it used, the row counts, the licences found and the final sizes. Current data: Overture release 2026-11-18.0, 81 provinces, 973 districts, 7.8 MB in total.

## Contributing

Issues and pull requests are welcome, especially wrong-district reports with a coordinate. See [CONTRIBUTING.md](CONTRIBUTING.md). Run the tests with `python -m pip install -e ".[test]" && python -m pytest`.

## License

| What | License |
| --- | --- |
| Code (`src/`, `scripts/`, `tests/`) | MIT, see [LICENSE](LICENSE) |
| Data (`data/*`, and the copies inside the package) | ODbL 1.0, see [LICENSE-DATA](LICENSE-DATA) |

Required attribution for the data: **(c) OpenStreetMap contributors, Overture Maps Foundation.** If you publish a database built from these files, the ODbL share-alike terms apply to that database.

Built and maintained by [Pinlyx](https://pinlyx.com/?utm_source=github&utm_medium=readme&utm_campaign=turkiye-il-ilce), an omnichannel inbox and AI agent, where this data is used to filter 1.79M Turkish businesses by province and district.

---

# Türkçe

Herhangi bir koordinatın Türkiye'de hangi il ve ilçeye düştüğünü internetsiz, saf Python ile bulan kütüphane. Güncel il ve ilçe sınırlarını GeoJSON olarak da içerir.

```python
>>> from turkiye_il_ilce import lookup
>>> lookup(40.99, 29.03)
{'il': 'İstanbul', 'plaka': 34, 'iso': 'TR-34', 'ilce': 'Kadıköy'}
```

## Neden var?

- **Türkiye sınırlarını veren GeoJSON depolarının çoğu eski.** Arama sonuçlarında ilk çıkanlar 2021-22 tarihli ve birçoğu yalnızca il düzeyinde. Bu paket Kasım 2026 sürümünden üretildi ve veri değiştiğinde tek komutla yeniden üretilir.
- **İnternetsiz ters geokodlayıcılar ilçe sınırına bakmaz.** GeoNames tabanlı kütüphaneler "en yakın yerleşim yerini" döndürür; bu çoğu zaman yanlış ilçedir ve noktanın Türkiye içinde olup olmadığını da söylemez.
- **Her satır için geokodlama API'si çağırmak ölçeklenmez.** Bir müşteri listesini, bir teslimat kaydını ya da bir milyon işletmeyi il ve ilçeye göre etiketlemek için ağ çağrısı, anahtar ya da kota gerekmemeli.

Bu paket gerçek poligonlar (Overture Maps 2026-11-18.0 sürümü, 81 il, 973 ilçe), bağımlılığı olmayan bir sorgu fonksiyonu ve aynı veriyi başka dillerde kullanmanız için düz GeoJSON verir.

## Kurulum

Paket henüz PyPI'de değil. GitHub'dan kurun (Python 3.9+, bağımlılık yok):

```bash
pip install git+https://github.com/Pinlyx/turkiye-il-ilce
```

## Hızlı başlangıç

```python
from turkiye_il_ilce import lookup, iller, ilceler

lookup(39.9256, 32.8369)   # Anıtkabir
# {'il': 'Ankara', 'plaka': 6, 'iso': 'TR-06', 'ilce': 'Çankaya'}

lookup(40.70, 28.00)       # Marmara Denizi
# None

len(iller())               # 81
ilceler("izmir")[:4]       # ['Aliağa', 'Balçova', 'Bayındır', 'Bayraklı']
ilceler(34)[:3]            # ['Adalar', 'Arnavutköy', 'Ataşehir']
```

Komut satırı:

```console
$ il-ilce 40.99 29.03
İstanbul / Kadıköy (34, TR-34)
$ il-ilce 40.99 29.03 --json
{"il": "İstanbul", "plaka": 34, "iso": "TR-34", "ilce": "Kadıköy"}
$ il-ilce 40.70 28.00     # açık deniz: stderr'e "not found" yazar, çıkış kodu 1
```

Önce enlem, sonra boylam yazılır (WGS84, ondalık derece).

## API

| Çağrı | Döndürdüğü |
| --- | --- |
| `lookup(lat, lon)` | `{"il", "plaka", "iso", "ilce"}`; nokta Türkiye karasında değilse (deniz, yurt dışı, Kuzey Kıbrıs) `None`. Enlem -90..90, boylam -180..180 dışındaysa ya da sayı sonlu değilse `ValueError` verir. |
| `iller()` | 81 ili plaka sırasıyla, `{"il", "plaka", "iso"}` olarak verir. |
| `ilceler(il)` | Bir ilin ilçe adlarını Türkçe alfabe sırasıyla verir. `il` büyük/küçük harfe ve aksanlara bakmaksızın ad (`"İstanbul"`, `"istanbul"`, `"ISTANBUL"`), plaka kodu (`34`, `"34"`, `"06"`) ya da ISO kodu (`"TR-34"`) olabilir. Bilinmeyen ilde `KeyError` verir. |
| `data_info()` | Pakete gömülü verinin üst bilgisi: Overture sürümü, sayılar, sadeleştirme toleransı, lisans. |
| `data_path(ad)` | Gömülü bir veri dosyasının `pathlib.Path` yolu; GeoJSON'u kendiniz okumak isterseniz. |

`plaka` tam sayı plaka kodudur (1 ile 81) ve ISO 3166-2:TR kodundaki sayıyla (`TR-34`) aynıdır.

Adlar Overture / OpenStreetMap yazımını izler: `Elâzığ`, `Hakkâri`, `Kâhta` düzeltme işaretiyle yazılır; ilin merkez ilçesi `<İl> Merkez` biçimindedir (`Edirne Merkez`, `Çanakkale Merkez`).

## Veriyi başka dillerden kullanma

`data/` klasörü WGS84 düz GeoJSON'dur (`[boylam, enlem]`); Node, Go, QGIS, PostGIS, DuckDB ve diğer her şey Python olmadan kullanabilir.

| Dosya | İçerik | Boyut |
| --- | --- | --- |
| `data/ilceler.geojson` | 973 ilçe poligonu. Özellikler: `il`, `plaka`, `iso`, `ilce` | 5,6 MB |
| `data/iller.geojson` | 81 il poligonu. Özellikler: `il`, `plaka`, `iso`, `ilce_sayisi` | 2,2 MB |
| `data/il-ilce.json` | Her il için plaka kodu, ISO kodu, ad ve ilçe adları listesi; ayrıca üretim üst bilgisi | 23 KB |

İller, sadeleştirilmiş ilçelerin birleşimidir; iki katman her kenarı paylaşır ve birbiriyle çelişmez.

DuckDB:

```sql
INSTALL spatial; LOAD spatial;
SELECT il, ilce FROM ST_Read('data/ilceler.geojson') WHERE ST_Contains(geom, ST_Point(29.03, 40.99));
```

Node ve Turf (`npm i @turf/boolean-point-in-polygon @turf/helpers`):

```js
import { readFileSync } from "node:fs";
import booleanPointInPolygon from "@turf/boolean-point-in-polygon";
import { point } from "@turf/helpers";

const ilceler = JSON.parse(readFileSync("data/ilceler.geojson", "utf8"));
const bulunan = ilceler.features.find((f) => booleanPointInPolygon(point([29.03, 40.99]), f));
console.log(bulunan?.properties); // { il: 'İstanbul', plaka: 34, iso: 'TR-34', ilce: 'Kadıköy' }
```

## Nasıl çalışır, sınırları nelerdir?

**Nasıl.** Her ilçe bir poligondur. `lookup` önce sınır kutusuyla (bbox) poligonları eler, kalan birkaç poligonda ışın atma yöntemiyle nokta-poligon testi yapar. Veri ilk çağrıda pakete gömülü dosyadan okunur ve bellekte tutulur.

**Hız.** Windows PC, Python 3.10, Türkiye sınır kutusunda 20.000 rastgele nokta: sorgu başına ortalama 0,15 ms, medyan 0,11 ms, 99. yüzdelik 0,8 ms. İlk çağrı veriyi de yüklediği için yaklaşık 0,4 sn sürer. Hedef 5 ms altıydı.

**Doğruluk.** Veriyi yaklaşık 8 MB'ta tutmak için sınırlar sadeleştirildi (topoloji koruyan kapsama sadeleştirmesi, tolerans 0,0008 derece, yaklaşık 90 m) ve koordinatlar 4 ondalığa yuvarlandı (yaklaşık 11 m). Tam çözünürlüklü Overture poligonlarına karşı, Türkiye sınır kutusunda 20.000 rastgele nokta ile ölçüldü (14.257'si karada): 14.254'ü birebir aynı il ve ilçeyi verdi (%99,98), 3'ü aynı ilin komşu ilçesine düştü, hiçbiri il değiştirmedi ve kara/deniz ayrımı her seferinde aynı çıktı. Bir ilçe sınırına ya da kıyıya yaklaşık 100 m'den yakın noktalar yanlış tarafa düşebilir. Bu bir etiketleme ve filtreleme verisidir, kadastro aracı değildir.

**Sınırlar, dürüstçe:**

- Sınırlar **resmi değildir.** OpenStreetMap'ten Overture Maps üzerinden gelir; Harita Genel Müdürlüğü ya da TÜİK kaynaklı değildir. Yeni idari değişiklikler, OpenStreetMap katkıcıları haritalayınca veriye yansır.
- Yalnızca il ve ilçe. Mahalle ve köy yok.
- Yalnızca kara; OpenStreetMap kıyı çizgisine göre kesilmiştir. İskele, liman ya da gemideki bir nokta, sadeleştirilmiş kıyının nereden geçtiğine göre `None` ya da en yakın ilçeyi döndürür. Karasuları dahil değildir.
- Kuzey Kıbrıs veri kümesinde yoktur, `None` döner.
- 974 değil 973 ilçe. Overture'da `subtype = county` olan 974 kara satırı var; bunlardan biri, Muğla'daki "Kara Ada" adacığı, tamamen Bodrum'un içinde kalan ve ilçe olmayan bir sınırdır. `scripts/build_data.py`, başka bir ilçe tarafından %90'dan fazla kaplanan her ilçeyi eler. İl düzeyinde 81 kara satırı var ama toplam 109 satır gelir, çünkü her kıyı ilinin bir de `class = 'maritime'` poligonu vardır; bunlar süzülür.
- Lisanslar, kullanılan her satırın `sources` alanında kontrol edildi: tüm geometri OpenStreetMap kaynaklıdır (ODbL-1.0). Esri Community Maps (CC-BY-4.0) yalnızca çevrilmiş adlarda görünür; bu paket onları kullanmaz.

## Veriyi yeniden üretme

`scripts/build_data.py`, Overture `divisions` temasını herkese açık S3 kovasından DuckDB ile okur ve `data/` klasörünü yazar. `duckdb` yalnızca üretim sırasında gerekir.

```bash
python -m pip install duckdb
python scripts/build_data.py                   # en yeni Overture sürümü
python scripts/build_data.py --release 2026-11-18.0 --tolerance 0.0008
python -m pytest
```

Kullandığı sürümü, satır sayılarını, bulunan lisansları ve son boyutları yazdırır. Güncel veri: Overture 2026-11-18.0 sürümü, 81 il, 973 ilçe, toplam 7,8 MB.

## Katkı

Sorunlar ve çekme istekleri (pull request) memnuniyetle karşılanır; özellikle koordinatıyla birlikte yanlış ilçe bildirimleri. Bkz. [CONTRIBUTING.md](CONTRIBUTING.md). Testleri `python -m pip install -e ".[test]" && python -m pytest` ile çalıştırın.

## Lisans

| Ne | Lisans |
| --- | --- |
| Kod (`src/`, `scripts/`, `tests/`) | MIT, bkz. [LICENSE](LICENSE) |
| Veri (`data/*` ve paketin içindeki kopyaları) | ODbL 1.0, bkz. [LICENSE-DATA](LICENSE-DATA) |

Veri için zorunlu atıf: **(c) OpenStreetMap contributors, Overture Maps Foundation.** Bu dosyalardan türettiğiniz bir veritabanını yayımlarsanız, o veritabanına ODbL'nin aynı lisansla paylaşma koşulları uygulanır.

[Pinlyx](https://pinlyx.com/?utm_source=github&utm_medium=readme&utm_campaign=turkiye-il-ilce) tarafından geliştirilir ve bakımı yapılır (çok kanallı gelen kutusu ve yapay zeka ajanı); bu veri orada 1,79 milyon Türk işletmesini il ve ilçeye göre filtrelemek için kullanılıyor.
