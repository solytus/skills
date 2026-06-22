"""Cost adapter — Census ACS 5-year. Resolves the place coordinate to a Census geography
(place for city grain, tract for neighborhood, county fallback) via geo.py, then queries
ACS for income / rent / cost-burden / demographics / education. Key: CENSUS_API_KEY."""
import os
import sys
from datetime import datetime
from urllib.parse import quote

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import adapter_base as ab  # noqa: E402
import geo  # noqa: E402

SOURCE = "census-acs"
TTL_DAYS = 30
PAYLOAD_FIELDS = ["median_household_income", "median_residential_rent",
                  "housing_cost_burden", "demographics", "education_attainment"]

_ACS_YEAR = "2023"
_ACS_VARS = ["B19013_001E", "B25064_001E", "B25070_001E", "B25070_010E",
             "B01003_001E", "B01002_001E", "B15003_001E", "B15003_022E",
             "B15003_023E", "B15003_024E", "B15003_025E", "B02001_005E"]
# Census "jam" sentinels for unavailable estimates.
_JAM = {"-666666666", "-999999999", "-888888888", "-555555555", "-333333333", "-222222222"}


def _num(v):
    if v is None or v == "" or v in _JAM:
        return None
    try:
        f = float(v)
        return int(f) if f.is_integer() else f
    except (TypeError, ValueError):
        return None


def _pct(numer, denom):
    if not denom or numer is None:
        return None
    return round(numer / denom * 100, 1)


def _normalize(rows):
    if not rows or len(rows) < 2:
        return {f: None for f in PAYLOAD_FIELDS}
    d = dict(zip(rows[0], rows[1]))
    rent_denom = _num(d.get("B25070_001E"))
    rent_50plus = _num(d.get("B25070_010E"))
    edu_denom = _num(d.get("B15003_001E"))
    bach_vals = [_num(d.get(v)) for v in ("B15003_022E", "B15003_023E", "B15003_024E", "B15003_025E")]
    bach_plus = sum(x for x in bach_vals if x is not None) if any(v is not None for v in bach_vals) else None
    population = _num(d.get("B01003_001E"))
    asian_alone = _num(d.get("B02001_005E"))  # B02001_005E = Asian alone; backs the must_have
    return {
        "median_household_income": _num(d.get("B19013_001E")),
        "median_residential_rent": _num(d.get("B25064_001E")),
        "housing_cost_burden": {"renters_50pct_plus_share": _pct(rent_50plus, rent_denom)},
        "demographics": {"population": population,
                         "median_age": _num(d.get("B01002_001E")),
                         "asian_alone_count": asian_alone,
                         "asian_alone_pct": _pct(asian_alone, population)},
        "education_attainment": {"bachelors_or_higher_pct": _pct(bach_plus, edu_denom)},
    }


def _acs_scope(level, f):
    """Choose the ACS geography for the requested grain -> (for_clause, in_clause, grain)."""
    state, county, place, tract = (f.get("state_fips"), f.get("county_fips"),
                                   f.get("place_fips"), f.get("tract"))
    county3 = county[2:] if county and len(county) == 5 else None
    if level in ("neighborhood", "property") and tract and county3 and state:
        return f"tract:{tract}", f"state:{state} county:{county3}", "tract"
    if place and state:
        return f"place:{place}", f"state:{state}", "place"
    if county3 and state:
        return f"county:{county3}", f"state:{state}", "county"
    if state:
        return f"state:{state}", "", "state"
    return None, None, None


def fetch(place_key, geocode, level, data_root, now=None, force_refresh=False):
    """Census ACS for the resolved geography. No key -> primary raises -> graceful gap."""
    now = now or datetime.now()
    lat, lon = ab.parse_geocode(geocode)
    key = ab.load_secrets().get("CENSUS_API_KEY")

    def primary():
        if not key:
            raise RuntimeError("CENSUS_API_KEY missing")
        fips = geo.census_geographies(lat, lon, data_root=data_root, now=now,
                                      force_refresh=force_refresh)
        for_clause, in_clause, grain = _acs_scope(level, fips)
        if not for_clause:
            raise RuntimeError("could not resolve ACS geography")
        url = (f"https://api.census.gov/data/{_ACS_YEAR}/acs/acs5"
               f"?get=NAME,{','.join(_ACS_VARS)}&for={quote(for_clause, safe=':')}")
        if in_clause:
            url += f"&in={quote(in_clause, safe=':')}"
        url += f"&key={key}"
        payload = _normalize(ab.http_json(url))
        payload["geography_level"] = grain
        return payload

    return ab.fetch_with_cache(data_root, SOURCE, place_key, TTL_DAYS, primary,
                               now=now, place_grain=level, force_refresh=force_refresh,
                               grain_key="geography_level")


if __name__ == "__main__":
    ab.adapter_cli(fetch)
