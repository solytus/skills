"""World Bank Open Data adapter — the country-grain workhorse.

One cached fetch covers economy & labor health, a coarse cost-of-living signal,
governance (WGI), internet, and headline health indicators. No auth. The World Bank
API keys on ISO-3 country codes (api.worldbank.org/v2/country/PRT/...), so the iso2
suffix carried in the place_key is resolved to iso3 via country_lookups before the call.

WDI indicators live in source 2, WGI (governance, 0-100 scores) in source 3. Indicators are
fetched ONE PER CALL: the World Bank multi-indicator (`A;B;C`) endpoint fails the entire
request if any single code lacks data for the country (verified against the live API), so a
per-indicator fetch degrades a missing indicator to one null field instead of poisoning the
whole record. Each call is tiny (mrv=20) and the result is cached 90 days. The normalizer
picks the latest non-null year per indicator and RAISES on an empty/all-null response, so a
no-data reply degrades to cache/gap via the standard 3-tier ladder rather than caching an
empty record as 'fresh' (never fabricate by omission).
"""
import os
import sys
import urllib.error
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import adapter_base as ab  # noqa: E402
import country_lookups as cl  # noqa: E402

SOURCE = "worldbank"
TTL_DAYS = 90
_BASE = "https://api.worldbank.org/v2"

# WDI (source=2): economy, labor, cost-coarse signal, internet, health.
WDI_INDICATORS = {
    "NY.GDP.PCAP.PP.CD": "gdp_per_capita_ppp",
    "SL.UEM.TOTL.ZS": "unemployment_pct",
    "FP.CPI.TOTL.ZG": "inflation_pct",
    "IT.NET.BBND.P2": "fixed_broadband_per_100",
    "SP.DYN.LE00.IN": "life_expectancy",
    "SH.XPD.CHEX.PC.CD": "health_expenditure_per_capita_usd",
}
# WGI (source=3): governance, 0-100 percentile scores (higher = better).
WGI_INDICATORS = {
    "GOV_WGI_GE.SC": "governance_effectiveness",
    "GOV_WGI_RL.SC": "rule_of_law",
    "GOV_WGI_PV.SC": "political_stability",
    "GOV_WGI_CC.SC": "control_of_corruption",
    "GOV_WGI_VA.SC": "voice_accountability",
}
FIELD_MAP = {**WDI_INDICATORS, **WGI_INDICATORS}


def _normalize(rows, field_map):
    """Latest non-null value per indicator -> {field: value, years: {field: yr}, oldest_year}.

    Raises ValueError when there are no rows or every value is null, so the caller degrades
    honestly instead of stamping an empty payload as fresh.
    """
    if not rows:
        raise ValueError("no World Bank data")
    by_code = {}
    for r in rows:
        code = (r.get("indicator") or {}).get("id")
        val = r.get("value")
        if code is None or val is None:
            continue
        try:
            year = int(r.get("date"))
            val = float(val)
        except (TypeError, ValueError):
            continue
        prev = by_code.get(code)
        if prev is None or year > prev[0]:
            by_code[code] = (year, val)
    if not by_code:
        raise ValueError("World Bank data all null")
    payload, years = {}, {}
    for code, field in field_map.items():
        if code in by_code:
            years[field], payload[field] = by_code[code]
        else:
            payload[field] = None
    payload["years"] = years
    payload["oldest_year"] = min(years.values()) if years else None
    return payload


def _iso2_from_place_key(place_key):
    """'country::portugal-pt::39.5,-8.0' -> 'PT' (last hyphen segment of the name)."""
    return place_key.split("::")[1].rsplit("-", 1)[-1].upper()


def _fetch_indicator(iso3, code, source=None):
    """Rows for one indicator (latest 20 years), or [] when the API returns no data array.

    Network / bad-JSON errors are swallowed by the caller so one unavailable indicator
    never poisons the others; a real code bug (other exception types) still propagates.
    """
    src = f"&source={source}" if source else ""
    url = f"{_BASE}/country/{iso3}/indicator/{code}?format=json&per_page=100&mrv=20{src}"
    resp = ab.http_json(url, timeout=30)
    return resp[1] if isinstance(resp, list) and len(resp) > 1 and isinstance(resp[1], list) else []


def fetch(place_key, geocode, level, data_root, now=None, force_refresh=False):
    """World Bank indicators for the country. 90-day TTL; 3-tier fallback to cache/gap."""
    now = now or datetime.now()
    iso2 = _iso2_from_place_key(place_key)

    def primary():
        iso3 = cl.resolve_country(iso2).get("iso3")
        if not iso3:
            raise RuntimeError(f"no ISO-3 for {iso2} (country_centroids dataset missing?)")
        rows = []
        for code, source in [(c, None) for c in WDI_INDICATORS] \
                + [(c, 3) for c in WGI_INDICATORS]:
            try:
                rows.extend(_fetch_indicator(iso3, code, source))
            except (urllib.error.URLError, ValueError):  # network / bad JSON only
                continue
        return _normalize(rows, FIELD_MAP)

    return ab.fetch_with_cache(data_root, SOURCE, place_key, TTL_DAYS, primary,
                               now=now, place_grain=level, force_refresh=force_refresh)


if __name__ == "__main__":
    ab.adapter_cli(fetch)
