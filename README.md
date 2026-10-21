# world-airports

Every airport, runway, navaid and airport frequency in [OurAirports (public domain)](https://ourairports.com/about.html), as
GeoParquet and vector tiles, published weekly to Hugging Face
([dataset](https://huggingface.co/datasets/milleleaf/world-airports), [bucket](https://huggingface.co/buckets/milleleaf/world-airports)
read by browsers) and mirrored to [Kaggle](https://www.kaggle.com/datasets/helenkwok/world-airports). Built from
[pipeline-template](https://github.com/milleleaf/pipeline-template). Every row and every field is kept; the files are
listed in `hf/README.md`.

    python3 bake.py          # data/out/: Parquet, CSV, PMTiles + index.json (needs tippecanoe)
    python3 publish.py       # gate, then Hugging Face (HF_TOKEN)
    python3 check.py         # data-free checks (CI)

The bake stops if a tile set's deepest zoom holds fewer features than there are rows: `airports.pmtiles` must hold every
airport at zoom 10, `runways.pmtiles` every located runway at zoom 13.

Code: Apache-2.0. Data: public domain (OurAirports), see `sources.json`.
