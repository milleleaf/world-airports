---
pretty_name: World airports (OurAirports)
license: other
license_name: public-domain
license_link: https://ourairports.com/about.html
tags:
  - geospatial
  - airports
  - aviation
---

# World airports

Every airport, heliport, seaplane base and closed airfield in OurAirports, with its runways, navaids and radio frequencies,
rebuilt weekly by [AlreadyOpen/world-airports](https://github.com/milleleaf/world-airports). Every row and every field of
the source is kept.

| File | Holds |
|---|---|
| `airports.parquet` | GeoParquet: one point per airport, all columns |
| `runways.parquet` | GeoParquet: all columns, `geometry` (a line from one end to the other, when both ends have coordinates), `le_geometry` and `he_geometry` (a point per end that has coordinates) |
| `navaids.parquet` | Radio navigation aids, all columns |
| `airport-frequencies.parquet` | Airport radio frequencies, all columns |
| `countries.csv`, `regions.csv` | Copied as published |
| `airports.pmtiles` | Vector tiles, layer `airports`, every airport, all fields. Large airports from zoom 2, medium from zoom 5, closed from zoom 10, all others from zoom 8; every airport is in zoom 10 |
| `runways.pmtiles` | Vector tiles, layer `runways`, zooms 8 to 13, every runway with both ends located |

Two notes on the tiles. Web maps stop at 85.05 degrees latitude, so the South Pole airports and runway sit at that latitude
in the tiles; their true coordinates are in the fields and in the Parquet files. A runway whose two ends are at the same spot
is a point in the tiles, since a line of no length cannot be drawn.

`manifest.json` lists every file's sha256, the counts and the source of the latest bake.

## Sources and terms

Data from [OurAirports (public domain)](https://ourairports.com/about.html): "all in the Public Domain (no permission
required)". Downloaded from [ourairports-data](https://davidmegginson.github.io/ourairports-data/), which is updated daily.
Provided as is, with no warranty, not endorsed by OurAirports. Do not use it for navigation.
