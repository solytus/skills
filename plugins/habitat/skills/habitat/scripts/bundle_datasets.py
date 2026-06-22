"""Build-time: download + filter the static datasets the deterministic lookups use, into
the skill's datasets/ directory. Re-run to refresh (airports ~quarterly, gazetteer ~yearly).
  US (domestic):
  - us_airports.csv         OurAirports, US scheduled-service large/medium airports
  - us_place_centroids.csv  Census Gazetteer places: USPS state, name, centroid lat/lon
  International (country grain):
  - country_centroids.csv   mledoze/countries: iso2/iso3, name, capital, centroid, tz~, currency
  - passport_index.csv      ilyankou: short-stay TRAVEL access by passport x destination
  - gpi.csv                 Global Peace Index (safety) — verified periodic drop (see SOURCES.md)
  - diaspora.csv            UN Migrant Stock origin x destination (belonging) — verified drop
Usage: python3 scripts/bundle_datasets.py [airports|gazetteer|country_centroids|passport|all]
       python3 scripts/bundle_datasets.py --check-stale [--max-age-years N]"""
import csv
import io
import json
import os
import re
import sys
import urllib.request
import zipfile
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(os.path.dirname(HERE), "datasets")

AIRPORTS_URL = "https://davidmegginson.github.io/ourairports-data/airports.csv"
GAZ_URL = ("https://www2.census.gov/geo/docs/maps-data/data/gazetteer/"
           "2024_Gazetteer/2024_Gaz_place_national.zip")
COUNTRIES_URL = "https://raw.githubusercontent.com/mledoze/countries/master/countries.json"
PASSPORT_URL = ("https://raw.githubusercontent.com/ilyankou/passport-index-dataset/"
                "master/passport-index-tidy-iso2.csv")
ACS_POP_URL = ("https://api.census.gov/data/2023/acs/acs5"
               "?get=B01003_001E&for=place:*&in=state:{ss}")
# 50 states + DC FIPS (skips unused 03/07/14/43/52)
STATE_FIPS = ["01", "02", "04", "05", "06", "08", "09", "10", "11", "12", "13", "15", "16",
              "17", "18", "19", "20", "21", "22", "23", "24", "25", "26", "27", "28", "29",
              "30", "31", "32", "33", "34", "35", "36", "37", "38", "39", "40", "41", "42",
              "44", "45", "46", "47", "48", "49", "50", "51", "53", "54", "55", "56"]
SOURCES_PATH = os.path.join(OUT, "SOURCES.md")


def _download(url, timeout=180):
    req = urllib.request.Request(url, headers={"User-Agent": "habitat/0.1 (place tool)"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def _acs_geoid(row):
    """ACS place row [pop, state, place] -> 7-digit place GEOID (state+place)."""
    return f"{row[1]}{row[2]}"


def _acs_url(ss, key=None):
    """ACS5 B01003 query URL for one state; appends the API key when provided. The place:*
    query shape REQUIRES a Census API key (it returns a 'Missing Key' HTML page otherwise)."""
    url = ACS_POP_URL.format(ss=ss)
    return f"{url}&key={key}" if key else url


def fetch_place_population():
    """{7-digit place GEOID -> population} from ACS5 B01003, one call per state.
    Requires CENSUS_API_KEY (read from secrets.env); without it every call returns a
    'Missing Key' page and the result is empty (build_gazetteer warns loudly in that case)."""
    import adapter_base as ab  # local import: keeps module load free of the secrets/network dep
    key = ab.load_secrets().get("CENSUS_API_KEY")
    pop = {}
    for ss in STATE_FIPS:
        try:
            data = json.loads(_download(_acs_url(ss, key)).decode("utf-8", "replace"))
        except Exception:  # noqa: BLE001 — a flaky state shouldn't abort the bundle
            continue
        for row in data[1:]:  # data[0] is the ACS header row; skip it
            try:
                pop[_acs_geoid(row)] = int(row[0])
            except (TypeError, ValueError, IndexError):
                continue
    return pop


def _join_population(rows, pop_by_geoid):
    """Add a 'population' field to each gazetteer row by GEOID (None when unknown)."""
    for r in rows:
        r["population"] = pop_by_geoid.get(r.get("geoid"))
    return rows


def build_airports():
    reader = csv.DictReader(io.StringIO(_download(AIRPORTS_URL).decode("utf-8", "replace")))
    rows = [{"ident": r["ident"], "iata": r.get("iata_code", ""), "name": r["name"],
             "type": r["type"], "lat": r["latitude_deg"], "lon": r["longitude_deg"],
             "municipality": r.get("municipality", ""), "region": r.get("iso_region", "")}
            for r in reader
            if r.get("iso_country") == "US" and r.get("scheduled_service") == "yes"
            and r.get("type") in ("large_airport", "medium_airport")]
    path = os.path.join(OUT, "us_airports.csv")
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["ident", "iata", "name", "type", "lat", "lon",
                                          "municipality", "region"])
        w.writeheader()
        w.writerows(rows)
    return len(rows), path


def build_gazetteer():
    zf = zipfile.ZipFile(io.BytesIO(_download(GAZ_URL)))
    txt = next(n for n in zf.namelist() if n.lower().endswith(".txt"))
    reader = csv.DictReader(io.StringIO(zf.read(txt).decode("latin-1")), delimiter="\t")
    rows = []
    for r in reader:
        rr = {(k or "").strip(): (v or "").strip() for k, v in r.items()}
        rows.append({"usps": rr.get("USPS"), "geoid": rr.get("GEOID"),
                     "name": rr.get("NAME"),
                     "lat": rr.get("INTPTLAT"), "lon": rr.get("INTPTLONG")})
    pop_by_geoid = fetch_place_population()
    if not pop_by_geoid:
        print("WARNING: place population empty (CENSUS_API_KEY missing/invalid?); "
              "population column will be blank", file=sys.stderr)
    _join_population(rows, pop_by_geoid)
    path = os.path.join(OUT, "us_place_centroids.csv")
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["usps", "geoid", "name", "lat", "lon", "population"])
        w.writeheader()
        w.writerows(rows)
    return len(rows), path


def _utc_offset_from_lon(lon):
    """Approximate UTC offset from centroid longitude (15deg/hr). Coarse — labeled approx;
    ignores political tz boundaries/DST, fine for a 'hours ahead/behind' remote-work signal."""
    try:
        off = int(round(float(lon) / 15.0))
    except (TypeError, ValueError):
        return ""
    return f"UTC{off:+03d}"


def build_country_centroids():
    """mledoze/countries -> country_centroids.csv (the country analog of the US gazetteer).

    Centroid = capital coordinate if available, else the country centroid (latlng). tz is a
    coarse centroid-derived UTC offset (mledoze master carries no tz field). currency is the
    first listed currency (feeds the FX lookup's destination currency)."""
    data = json.loads(_download(COUNTRIES_URL).decode("utf-8", "replace"))
    rows = []
    for c in data:
        latlng = c.get("capitalInfo", {}).get("latlng") or c.get("latlng") or []
        if len(latlng) != 2:
            continue
        lat, lon = latlng
        cap = c.get("capital") or []
        rows.append({
            "iso2": c.get("cca2", ""), "iso3": c.get("cca3", ""),
            "name": (c.get("name", {}) or {}).get("common", ""),
            "capital": cap[0] if cap else "",
            "lat": lat, "lon": lon, "tz": _utc_offset_from_lon(lon),
            "currency": next(iter((c.get("currencies") or {}).keys()), ""),
            "region": c.get("region", ""), "subregion": c.get("subregion", ""),
        })
    rows.sort(key=lambda r: r["iso2"])
    path = os.path.join(OUT, "country_centroids.csv")
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["iso2", "iso3", "name", "capital", "lat", "lon",
                                          "tz", "currency", "region", "subregion"])
        w.writeheader()
        w.writerows(r for r in rows if r["iso2"])
    return sum(1 for r in rows if r["iso2"]), path


def build_passport_index():
    """ilyankou tidy ISO-2 -> passport_index.csv. SHORT-STAY TRAVEL access only (not residence).
    Drops self-rows ('-1') and 'no admission' is kept (it ranks as restrictive)."""
    reader = csv.reader(io.StringIO(_download(PASSPORT_URL).decode("utf-8", "replace")))
    next(reader, None)  # header: Passport,Destination,Requirement
    rows = [{"passport_iso2": p, "dest_iso2": d, "requirement": req}
            for p, d, req in reader if p and d and req and req != "-1"]
    path = os.path.join(OUT, "passport_index.csv")
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["passport_iso2", "dest_iso2", "requirement"])
        w.writeheader()
        w.writerows(rows)
    return len(rows), path


# --- staleness checking (SOURCES.md is the vintage of record) -------------------

_SRC_LINE = re.compile(r"^-\s*dataset:")


def parse_sources(text):
    """Parse SOURCES.md '- dataset: X | source: Y | license: Z | url: U | vintage: YYYY' lines."""
    out = []
    for line in text.splitlines():
        if not _SRC_LINE.match(line.strip()):
            continue
        fields = {}
        for part in line.lstrip("- ").split("|"):
            k, _, v = part.partition(":")
            fields[k.strip()] = v.strip()
        if "vintage" in fields:
            try:
                fields["vintage"] = int(fields["vintage"])
            except ValueError:
                continue
        out.append(fields)
    return out


def check_stale(sources, now_year=None, max_age_years=3):
    """Datasets whose vintage is more than max_age_years behind now_year."""
    now_year = now_year or datetime.now().year
    return [s for s in sources
            if isinstance(s.get("vintage"), int) and now_year - s["vintage"] > max_age_years]


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    args = sys.argv[1:]
    if "--check-stale" in args:
        max_age = 3
        if "--max-age-years" in args:
            max_age = int(args[args.index("--max-age-years") + 1])
        if not os.path.exists(SOURCES_PATH):
            print(f"no SOURCES.md at {SOURCES_PATH}")
            sys.exit(0)
        srcs = parse_sources(open(SOURCES_PATH).read())
        stale = check_stale(srcs, max_age_years=max_age)
        for s in srcs:
            mark = "STALE" if s in stale else "ok"
            print(f"  [{mark}] {s.get('dataset'):24} vintage {s.get('vintage')} ({s.get('license')})")
        print(f"{len(stale)} stale (> {max_age}y old)" if stale else "all datasets within age budget")
        sys.exit(0)
    which = args[0] if args else "all"
    if which in ("all", "airports"):
        print("airports: %d rows -> %s" % build_airports())
    if which in ("all", "gazetteer"):
        print("gazetteer: %d rows -> %s" % build_gazetteer())
    if which in ("all", "country_centroids"):
        print("country_centroids: %d rows -> %s" % build_country_centroids())
    if which in ("all", "passport"):
        print("passport_index: %d rows -> %s" % build_passport_index())
