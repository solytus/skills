"""Economic-dynamism adapter — BLS LAUS (county unemployment + employment level).
Unemployment rate + 1y/5y employment growth at county grain. Business-formation rate,
wages-by-sector, and dominant-industries are deferred to Phase 2 (Census BDS county API
returned 404 at every grain/vintage tried 2026-05-27; QCEW industry breakdown not yet wired)."""
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import adapter_base as ab  # noqa: E402
import geo  # noqa: E402

SOURCE = "bls-laus"
TTL_DAYS = 30
PAYLOAD_FIELDS = ["unemployment_rate", "employment_growth_1y", "employment_growth_5y",
                  "wages_by_sector", "business_formation_rate", "dominant_industries"]

_BLS_URL = "https://api.bls.gov/publicAPI/v2/timeseries/data/"


def _series_value(data, idx=0):
    if not data or len(data) <= idx:
        return None
    try:
        return float(data[idx]["value"])
    except (TypeError, ValueError, KeyError):
        return None


def _growth(data, months):
    cur, past = _series_value(data, 0), _series_value(data, months)
    if cur is None or not past:
        return None
    return round((cur - past) / past * 100, 1)


def _normalize(unemp_data, emp_data):
    return {
        "unemployment_rate": _series_value(unemp_data, 0),
        "employment_growth_1y": _growth(emp_data, 12),
        "employment_growth_5y": _growth(emp_data, 60),
        "wages_by_sector": None,          # Phase-2: QCEW industry wages
        "business_formation_rate": None,  # Phase-2: BDS county API path unresolved
        "dominant_industries": None,      # Phase-2: QCEW industry shares
    }


def fetch(place_key, geocode, level, data_root, now=None, force_refresh=False):
    """BLS LAUS for the resolved county. Key (BLS_API_KEY) lifts 25->500 queries/day."""
    now = now or datetime.now()
    lat, lon = ab.parse_geocode(geocode)
    key = ab.load_secrets().get("BLS_API_KEY")

    def primary():
        fips = geo.census_geographies(lat, lon, data_root=data_root, now=now,
                                      force_refresh=force_refresh).get("county_fips")
        if not fips or len(fips) != 5:
            raise RuntimeError("county FIPS unresolved")
        st, co = fips[:2], fips[2:]
        unemp_id, emp_id = f"LAUCN{st}{co}0000000003", f"LAUCN{st}{co}0000000005"
        body = {"seriesid": [unemp_id, emp_id],
                "startyear": str(now.year - 6), "endyear": str(now.year)}
        if key:
            body["registrationkey"] = key
        resp = ab.http_json(_BLS_URL, data=body, timeout=30)
        if resp.get("status") != "REQUEST_SUCCEEDED":
            raise RuntimeError(f"BLS status {resp.get('status')}")
        by = {s["seriesID"]: s.get("data", []) for s in resp.get("Results", {}).get("series", [])}
        payload = _normalize(by.get(unemp_id, []), by.get(emp_id, []))
        payload["grain"] = "county"
        payload["county_fips"] = fips
        return payload

    return ab.fetch_with_cache(data_root, SOURCE, place_key, TTL_DAYS, primary,
                               now=now, place_grain=level, force_refresh=force_refresh,
                               grain_key="grain")


if __name__ == "__main__":
    ab.adapter_cli(fetch)
