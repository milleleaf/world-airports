"""OurAirports (public domain, updated daily) as GeoParquet and vector tiles. Every row and every field is kept.
  airports.parquet             GeoParquet, one point per airport (latitude_deg, longitude_deg), all columns
  runways.parquet              GeoParquet, all columns + geometry (LineString le -> he, when both ends have coordinates),
                               le_geometry and he_geometry (a point per end that has coordinates)
  navaids.parquet, airport-frequencies.parquet   all columns
  countries.csv, regions.csv   copied as published
  airports.pmtiles             layer `airports`, every airport, all fields; large from z2, medium z5, closed z10, the rest z8
  runways.pmtiles              layer `runways`, the runway lines
index.json counts the rows of each file, and the features at the deepest zoom of each tile set.
Usage: python3 bake.py"""
import datetime, json, os, shutil, subprocess, urllib.request
import duckdb
import sources

BASE = 'https://davidmegginson.github.io/ourairports-data/'
CSVS = ['airports', 'runways', 'navaids', 'airport-frequencies', 'countries', 'regions']
MINZOOM = {'large_airport': 2, 'medium_airport': 5, 'closed': 10}      # every other type (small, heliport, ...): 8
AIRPORTS_MAXZOOM, RUNWAYS_MINZOOM, RUNWAYS_MAXZOOM = 10, 8, 13


def download(name):
    """fetched every run (about 20 MB in all, the source changes daily); the cache copy is replaced only when it changed"""
    p = os.path.join(sources.CACHE, name + '.csv')
    req = urllib.request.Request(BASE + name + '.csv', headers={'User-Agent': 'Milleleaf world-airports (https://github.com/milleleaf/world-airports)'})
    with urllib.request.urlopen(req, timeout=300) as r:
        b = r.read()
    if not os.path.exists(p) or open(p, 'rb').read() != b:
        open(p + '.part', 'wb').write(b); os.replace(p + '.part', p)
    return p


def csv(name):
    # whole-file type sniffing, so a late odd value never fails a cast; only an empty field is null ('NA' is Namibia / North America)
    return f"read_csv('{os.path.join(sources.CACHE, name + '.csv')}', sample_size=-1, nullstr='')"


def tiles(geojsonl, out, layer, minzoom, maxzoom):
    subprocess.run(['tippecanoe', '-o', out, '--force', '-l', layer, f'-Z{minzoom}', f'-z{maxzoom}', '-r1',
                    '--no-feature-limit', '--no-tile-size-limit', '--quiet', geojsonl], check=True)
    # every feature must be in the deepest zoom: count distinct ids there (a point near a tile edge shows in two tiles' buffers)
    ids = set()
    dec = subprocess.run(['tippecanoe-decode', '-z', str(maxzoom), '-Z', str(maxzoom), out], check=True, capture_output=True, text=True)
    for line in dec.stdout.splitlines():
        line = line.strip().rstrip(',')
        if line.startswith('{ "type": "Feature"') or line.startswith('{"type":"Feature"'):
            ids.add(json.loads(line)['properties']['id'])
    return len(ids)


def features(con, sql, out, zoom):
    """rows of sql (with a GeoJSON `geom` column) as GeoJSON lines for tippecanoe; zoom(row) gives a per-feature minzoom or None"""
    cur = con.execute(sql); cols = [d[0] for d in cur.description]; n = 0
    with open(out, 'w') as f:
        while rows := cur.fetchmany(10000):
            for r in rows:
                p = dict(zip(cols, r)); g = json.loads(p.pop('geom'))
                ft = {'type': 'Feature', 'geometry': g, 'properties': {k: v for k, v in p.items() if v is not None}}
                if (z := zoom(p)) is not None: ft['tippecanoe'] = {'minzoom': z}
                f.write(json.dumps(ft) + '\n'); n += 1
    return n


def main():
    os.makedirs(sources.CACHE, exist_ok=True); os.makedirs(sources.OUT, exist_ok=True)
    for c in CSVS: download(c)
    o = lambda f: os.path.join(sources.OUT, f)
    for c in ['countries', 'regions']: shutil.copyfile(os.path.join(sources.CACHE, c + '.csv'), o(c + '.csv'))
    con = duckdb.connect(); con.execute('INSTALL spatial; LOAD spatial')
    con.execute(f"CREATE TABLE airports AS SELECT *, ST_Point(longitude_deg, latitude_deg) AS geometry FROM {csv('airports')}")
    con.execute(f"""CREATE TABLE runways AS SELECT *,
        CASE WHEN le_longitude_deg IS NOT NULL AND le_latitude_deg IS NOT NULL AND he_longitude_deg IS NOT NULL AND he_latitude_deg IS NOT NULL
             THEN ST_MakeLine(ST_Point(le_longitude_deg, le_latitude_deg), ST_Point(he_longitude_deg, he_latitude_deg)) END AS geometry,
        CASE WHEN le_longitude_deg IS NOT NULL AND le_latitude_deg IS NOT NULL THEN ST_Point(le_longitude_deg, le_latitude_deg) END AS le_geometry,
        CASE WHEN he_longitude_deg IS NOT NULL AND he_latitude_deg IS NOT NULL THEN ST_Point(he_longitude_deg, he_latitude_deg) END AS he_geometry
        FROM {csv('runways')}""")
    for t in ['airports', 'runways']:
        con.execute(f"COPY {t} TO '{o(t + '.parquet')}' (FORMAT parquet, COMPRESSION zstd)")
    for c in ['navaids', 'airport-frequencies']:
        con.execute(f"COPY (SELECT * FROM {csv(c)}) TO '{o(c + '.parquet')}' (FORMAT parquet, COMPRESSION zstd)")
    counts = {c.replace('-', '_'): con.execute(f'SELECT count(*) FROM {csv(c)}').fetchone()[0] for c in CSVS}

    tmp = os.path.join(sources.DATA, 'tmp'); os.makedirs(tmp, exist_ok=True)
    # Web Mercator stops at 85.0511 degrees: the South Pole airports (NZSP at -90) go in at that latitude, keeping their true
    # latitude_deg and longitude_deg as fields, so no airport is left out of the tiles
    n = features(con, 'SELECT * EXCLUDE (geometry), ST_AsGeoJSON(ST_Point(longitude_deg, greatest(least(latitude_deg, 85.0511), -85.0511))) AS geom '
                      'FROM airports WHERE geometry IS NOT NULL',
                 os.path.join(tmp, 'airports.geojsonl'), lambda p: MINZOOM.get(p['type'], 8))
    assert n == counts['airports'], f'{counts["airports"] - n} airports have no coordinates'
    counts['airports_tiles_deepest_zoom'] = tiles(os.path.join(tmp, 'airports.geojsonl'), o('airports.pmtiles'), 'airports', 2, AIRPORTS_MAXZOOM)
    # tippecanoe drops a zero-length line (both ends at the same spot, 19 rows in 2026-10): those go in as that point instead;
    # and the South Pole runway goes in at 85.0511 degrees, as the airports do
    clamp = lambda g: f'ST_Point(ST_X({g}), greatest(least(ST_Y({g}), 85.0511), -85.0511))'
    counts['runway_lines'] = features(con, f'''SELECT * EXCLUDE (geometry, le_geometry, he_geometry),
        ST_AsGeoJSON(CASE WHEN ST_Equals(le_geometry, he_geometry) THEN {clamp('le_geometry')}
                          ELSE ST_MakeLine({clamp('le_geometry')}, {clamp('he_geometry')}) END) AS geom
        FROM runways WHERE geometry IS NOT NULL''',
                                      os.path.join(tmp, 'runways.geojsonl'), lambda p: None)
    counts['runways_tiles_deepest_zoom'] = tiles(os.path.join(tmp, 'runways.geojsonl'), o('runways.pmtiles'), 'runways', RUNWAYS_MINZOOM, RUNWAYS_MAXZOOM)
    shutil.rmtree(tmp)
    for k, v in [('airports', counts['airports']), ('runways', counts['runway_lines'])]:
        assert counts[k + '_tiles_deepest_zoom'] == v, f'{k}.pmtiles: {counts[k + "_tiles_deepest_zoom"]} features at the deepest zoom, {v} rows'
    idx = {'built': datetime.datetime.now().isoformat(timespec='seconds'), 'counts': counts}
    json.dump(idx, open(o('index.json'), 'w'), indent=1)
    print(json.dumps(idx))


if __name__ == '__main__':
    main()
