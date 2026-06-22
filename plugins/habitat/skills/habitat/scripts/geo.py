"""Shared geographic resolution: lat/lon -> Census FIPS (state / county / incorporated
place / tract) via the keyless Census Geocoder. Used by the Cost, Dynamism, and Safety
adapters. Stdlib only."""
import math
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import adapter_base as ab  # noqa: E402

GEO_SOURCE = "census-geo"
GEO_TTL_DAYS = 3650  # a coordinate's FIPS is stable for years; cache aggressively


def haversine_mi(lat1, lon1, lat2, lon2):
    """Great-circle distance in statute miles between two lat/lon points."""
    radius = 3958.7613
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi, dlmb = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return round(2 * radius * math.asin(math.sqrt(a)), 1)


_GEOCODER_URL = (
    "https://geocoding.geo.census.gov/geocoder/geographies/coordinates"
    "?x={lon}&y={lat}&benchmark=Public_AR_Current&vintage=Current_Current&format=json"
)


def _first(layer):
    return layer[0] if layer else {}


def normalize_geographies(resp):
    """Census geocoder /geographies response -> flat FIPS dict (missing layers -> None)."""
    g = ((resp or {}).get("result") or {}).get("geographies") or {}
    state = _first(g.get("States"))
    county = _first(g.get("Counties"))
    place = _first(g.get("Incorporated Places"))
    tract = _first(g.get("Census Tracts"))
    return {
        "state_fips": state.get("GEOID") or county.get("STATE") or place.get("STATE"),
        "county_fips": county.get("GEOID"),
        "county_name": county.get("BASENAME"),
        "place_fips": place.get("PLACE"),
        "place_name": place.get("NAME"),
        "tract_geoid": tract.get("GEOID"),
        "tract": tract.get("TRACT"),
    }


def census_geographies(lat, lon, data_root=None, now=None, force_refresh=False):
    """Resolve a coordinate to Census FIPS via the keyless geocoder.

    When `data_root` is given, the resolution is cached (long TTL) under a shared
    coordinate key, so Cost and Dynamism reuse one geocoder call per point instead of
    each making its own — and a cached result keeps them alive through a geocoder outage.
    """
    def primary():
        return normalize_geographies(ab.http_json(_GEOCODER_URL.format(lat=lat, lon=lon), timeout=30))
    if not data_root:
        return primary()
    rec = ab.fetch_with_cache(data_root, GEO_SOURCE, ab.coord_cache_key(lat, lon),
                              GEO_TTL_DAYS, primary, now=now or datetime.now(),
                              place_grain="point", force_refresh=force_refresh)
    return rec["payload"] or normalize_geographies(None)


if __name__ == "__main__":
    import argparse
    import json
    ap = argparse.ArgumentParser(description="Resolve lat,lon -> Census FIPS.")
    ap.add_argument("--geocode", required=True, help="'lat,lon'")
    a = ap.parse_args()
    lat, lon = ab.parse_geocode(a.geocode)
    print(json.dumps(census_geographies(lat, lon), indent=2, sort_keys=True))
