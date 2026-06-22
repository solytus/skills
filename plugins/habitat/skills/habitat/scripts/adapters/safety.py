"""Safety adapter — FBI Crime Data Explorer (CDE), agency/city grain.

Resolves the place to a police agency (ORI) via CDE's by-state agency list, then pulls
summarized violent + property crime for that agency. Normalizes monthly per-100k rates to
annual figures, picks the latest *complete* year, and reports trend + vs-national context.

Auth: DATA_GOV_API_KEY (api.data.gov). FBI NIBRS data lags ~18 months, hence the 180-day
TTL — cache freshness is theatrical at shorter windows. 3-tier fallback: FBI -> stale cache
-> graceful gap (per-city open-data is the documented Phase-2 alternative tier)."""
import os
import sys
from datetime import datetime
from urllib.parse import urlencode

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import adapter_base as ab  # noqa: E402
import geo  # noqa: E402

SOURCE = "fbi-crime"
TTL_DAYS = 180  # FBI data publishes annually and lags ~18 months regardless of fetch recency
PAYLOAD_FIELDS = ["violent_crime_per_100k", "property_crime_per_100k",
                  "recent_trend", "vs_national", "national_per_100k", "state_per_100k",
                  "year", "partial_year", "agency", "ori", "grain"]

_BASE = "https://api.usa.gov/crime/fbi/cde"

# USPS abbreviations CDE's byStateAbbr accepts (50 states + DC). Used to reject a place_key
# whose suffix isn't a real state (e.g. an un-suffixed slug 'city::cottonwood::...') before
# any network call, so it degrades with a clear reason instead of querying a bogus state.
_US_STATES = frozenset(
    "AL AK AZ AR CA CO CT DE FL GA HI ID IL IN IA KS KY LA ME MD MA MI MN MS MO MT NE NV "
    "NH NJ NM NY NC ND OH OK OR PA RI SC SD TN TX UT VT VA WA WV WI WY DC".split())


# --- place -> agency resolution ------------------------------------------------

def _city_state_from_place_key(place_key):
    """'city::aurora-co::39.7,-104.8' -> ('aurora', 'CO'). City hyphens -> spaces."""
    norm = place_key.split("::")[1]
    city, _, st = norm.rpartition("-")
    return city.replace("-", " "), st.upper()


def _flatten_agencies(listing):
    """Flatten CDE's byStateAbbr response ({county_name: [agency_dict, ...]}) to a flat list
    of agency dicts, tolerant of error/unexpected shapes. A bogus state — or a transient FBI
    error on a valid one — returns a bare string or an error object; iterating that blindly
    seeds `agencies` with non-dict elements that crash `_pick_agency` ('str' has no attribute
    'get'), an exception then masked as a generic outage. Keep only well-formed dicts so a
    malformed response degrades cleanly (no agency -> honest 'no agency resolved')."""
    out = []
    if isinstance(listing, dict):
        for county in listing.values():
            if isinstance(county, list):
                out.extend(a for a in county if isinstance(a, dict))
    return out


def _pick_agency(agencies, city, lat, lon):
    """Choose the best ORI, in priority order: a City-type agency whose name matches the
    city (prefix match preferred) → nearest general-jurisdiction (City *or* County) agency →
    any agency whose name matches the city → nearest of any type. Ties broken by haversine
    distance. Three traps this guards against:

    1. **Wrong type.** Checking City-type-AND-named before anything else stops a same-named
       non-city agency from hijacking the pick — e.g. for 'reno' the Tribal 'Reno-Sparks
       Indian Colony PD' must not outrank the City 'Reno Police Department'.
    2. **Substring hijack.** A bare `city in name` match treats 'South Tucson Police
       Department' as a hit for 'tucson'; that 1-sq-mi enclave (extreme per-capita crime)
       then wins on proximity. `_match_quality` ranks a *prefix* match ('Tucson PD') above a
       later-word-boundary match ('South Tucson PD'), so the real city wins.
    3. **Neighborhood prefix.** A neighborhood place_key yields a city token carrying the
       neighborhood prefix ('north thornton', 'west elk grove') that matches no agency, so
       resolution would fall to the nearest agency by HQ — an adjacent city's PD (Northglenn)
       or a co-located county sheriff. Trying progressively shorter trailing token-runs
       recovers the parent city ('thornton', 'elk grove').

    The proximity fallback considers City *and* County agencies together so distance decides
    between them — a City-only tier collapses every coordinate in a sparse-City-agency state
    onto the lone City agency (Hawaii: one City PD statewide + three County PDs, so a Big
    Island point would resolve to Honolulu PD ~150 mi away instead of the nearer Hawaii
    County PD)."""
    def dist(a):
        try:
            return geo.haversine_mi(lat, lon, float(a["latitude"]), float(a["longitude"]))
        except (TypeError, ValueError, KeyError):
            return float("inf")

    def is_city(a):
        return a.get("agency_type_name") == "City"

    def is_local(a):  # general-jurisdiction police: municipal or county
        return a.get("agency_type_name") in ("City", "County")

    def match_quality(a, cand):
        # 2 = agency name starts with the candidate ('Tucson Police Department' for 'tucson');
        # 1 = candidate appears at a later word boundary ('South Tucson Police Department');
        # 0 = no match. Prefix beats substring so a smaller same-named city can't hijack it.
        name = a.get("agency_name", "").lower()
        if cand and name.startswith(cand):
            return 2
        if cand and (" " + cand) in name:
            return 1
        return 0

    # Candidate jurisdiction names, most specific first: progressively drop leading words so
    # a neighborhood slug ('mission viejo aurora') falls back to its parent city ('aurora').
    words = city.split()
    candidates = [" ".join(words[i:]) for i in range(len(words))]

    def best_named(pool, cand):  # highest match quality, then nearest
        return min(pool, key=lambda a: (-match_quality(a, cand), dist(a)))

    # 1) A City-type agency whose name PREFIX matches the most specific candidate that hits.
    #    Prefix-only (quality 2), not a mere word-boundary match: a consolidated city-county
    #    like 'carson city' has no City-type agency, so its candidates degrade to the generic
    #    trailing word 'city', which word-boundary-matches an unrelated 'Boulder City PD'
    #    ~350 mi away. Requiring a prefix match drops that hijack; the place then resolves via
    #    the proximity tier below (its own nearby County Sheriff). All are equal-quality
    #    prefixes here, so nearest wins.
    for cand in candidates:
        pool = [a for a in agencies if is_city(a) and match_quality(a, cand) == 2]
        if pool:
            best = min(pool, key=dist)
            return best.get("ori"), best.get("agency_name")
    # 2) Nearest general-jurisdiction (City or County) agency.
    local = [a for a in agencies if is_local(a)]
    if local:
        best = min(local, key=dist)
        return best.get("ori"), best.get("agency_name")
    # 3) Any named agency (any type), most specific candidate first; then nearest of any type.
    for cand in candidates:
        pool = [a for a in agencies if match_quality(a, cand)]
        if pool:
            best = best_named(pool, cand)
            return best.get("ori"), best.get("agency_name")
    if agencies:
        best = min(agencies, key=dist)
        return best.get("ori"), best.get("agency_name")
    return None, None


# --- normalization -------------------------------------------------------------

def _sum_year(series, year):
    """Sum reported months only — the CDE returns null for unreported/future months."""
    return sum(v for m, v in (series or {}).items()
               if m.endswith("-" + year) and v is not None)


def _count_months(series, year):
    """Count reported (non-null) months — so a year is 'complete' only at 12 real months."""
    return sum(1 for m, v in (series or {}).items()
               if m.endswith("-" + year) and v is not None)


def _annual(offense_json, agency_name):
    """Roll monthly per-100k rates up to annual totals per year for the agency, the
    state, and the US, plus the agency's raw incident count and month coverage."""
    rates = offense_json.get("offenses", {}).get("rates", {})
    actuals = offense_json.get("offenses", {}).get("actuals", {})
    ag_key = f"{agency_name} Offenses"
    us_key = "United States Offenses"
    state_key = next((k for k in rates
                      if k.endswith(" Offenses") and k not in (ag_key, us_key)), None)
    years = sorted({m.split("-")[1] for m in rates.get(ag_key, {})}, key=int)
    out = {}
    for y in years:
        out[int(y)] = {
            "agency": round(_sum_year(rates.get(ag_key), y)),
            "us": round(_sum_year(rates.get(us_key), y)),
            "state": round(_sum_year(rates.get(state_key), y)) if state_key else None,
            "count": int(round(_sum_year(actuals.get(ag_key), y))),
            "months": _count_months(rates.get(ag_key), y),
        }
    return out


def _pick_year(annual):
    """(year, partial?) — latest year with 12 months, else latest present (partial)."""
    if not annual:
        return None, True
    complete = [y for y, d in annual.items() if d["months"] == 12]
    if complete:
        return max(complete), False
    return max(annual), True


def _ratio(num, den):
    return round(num / den, 2) if den else None


def _trend(annual, year):
    """YoY % change from the prior complete year to `year` (None if unavailable)."""
    if year is None or year not in annual or annual[year]["months"] != 12:
        return None, None
    prev = year - 1
    if prev not in annual or annual[prev]["months"] != 12 or not annual[prev]["agency"]:
        return None, prev
    pct = round((annual[year]["agency"] - annual[prev]["agency"])
                / annual[prev]["agency"] * 100, 1)
    return pct, prev


def _normalize(violent_json, property_json, agency_name):
    v = _annual(violent_json, agency_name)
    p = _annual(property_json, agency_name)
    vy, v_partial = _pick_year(v)
    py, p_partial = _pick_year(p)
    v_pct, v_from = _trend(v, vy)
    p_pct, _ = _trend(p, py)
    vd = v.get(vy, {})
    pd = p.get(py, {})
    return {
        "violent_crime_per_100k": vd.get("agency"),
        "property_crime_per_100k": pd.get("agency"),
        "violent_count": vd.get("count"),
        "property_count": pd.get("count"),
        "recent_trend": {"violent_pct": v_pct, "property_pct": p_pct,
                         "from_year": v_from, "to_year": vy},
        "vs_national": {"violent": _ratio(vd.get("agency"), vd.get("us")),
                        "property": _ratio(pd.get("agency"), pd.get("us"))},
        "national_per_100k": {"violent": vd.get("us"), "property": pd.get("us")},
        "state_per_100k": {"violent": vd.get("state"), "property": pd.get("state")},
        "year": vy,
        "partial_year": bool(v_partial or p_partial),
        "agency": agency_name,
        "grain": "agency",
    }


# --- fetch ---------------------------------------------------------------------

def _summarized(ori, offense, key, frm, to):
    q = urlencode({"from": frm, "to": to, "type": "counts", "api_key": key})
    return ab.http_json(f"{_BASE}/summarized/agency/{ori}/{offense}?{q}", timeout=30)


def fetch(place_key, geocode, level, data_root, now=None, force_refresh=False):
    """FBI CDE for the resolved agency. Requires DATA_GOV_API_KEY (degrades if absent)."""
    now = now or datetime.now()
    # FBI CDE is US-only. Guard before any network call so an international/country
    # place_key degrades honestly instead of parsing its ISO suffix ('pt') as a US
    # state and querying CDE for a bogus state. Crime abroad comes from Global Peace
    # Index (country grain) via the country workflow, not this adapter.
    if level == "country":
        rec = ab.make_record(place_key, SOURCE, {}, level, now.isoformat(), "unavailable")
        rec["degraded_reason"] = ("FBI CDE is US-only; no country-grain crime "
                                  "(use Global Peace Index)")
        return rec
    lat, lon = ab.parse_geocode(geocode)
    city, state_abbr = _city_state_from_place_key(place_key)
    # Reject a place_key with no valid US-state suffix BEFORE any network call, so an
    # un-suffixed/malformed key degrades with a clear reason instead of querying a bogus
    # state ('COTTONWOOD') and masking the resulting crash as a generic outage.
    if state_abbr not in _US_STATES:
        rec = ab.make_record(place_key, SOURCE, {}, level, now.isoformat(), "unavailable")
        rec["degraded_reason"] = (
            f"malformed place_key: '{state_abbr}' is not a US state abbreviation "
            "(expected a '<city>-<st>' suffix)")
        return rec
    key = ab.load_secrets().get("DATA_GOV_API_KEY")

    def primary():
        if not key:
            raise RuntimeError("DATA_GOV_API_KEY not set")
        listing = ab.http_json(
            f"{_BASE}/agency/byStateAbbr/{state_abbr}?{urlencode({'api_key': key})}",
            timeout=30)
        agencies = _flatten_agencies(listing)
        ori, agency_name = _pick_agency(agencies, city, lat, lon)
        if not ori:
            raise RuntimeError(f"no agency resolved for {city}, {state_abbr}")
        frm, to = f"01-{now.year - 4}", f"12-{now.year}"
        violent = _summarized(ori, "violent-crime", key, frm, to)
        prop = _summarized(ori, "property-crime", key, frm, to)
        payload = _normalize(violent, prop, agency_name)
        payload["ori"] = ori
        if payload.get("violent_crime_per_100k") is None \
                and payload.get("property_crime_per_100k") is None:
            raise RuntimeError(f"no crime data for ORI {ori}")
        return payload

    return ab.fetch_with_cache(data_root, SOURCE, place_key, TTL_DAYS, primary,
                               now=now, place_grain=level, force_refresh=force_refresh,
                               grain_key="grain")


if __name__ == "__main__":
    ab.adapter_cli(fetch)
