"""Utility lookups. family_distance / internet_quality / airport_access / walkability /
hazard. Each returns the same record envelope as the cached adapters so the Sources footer
treats every source uniformly. Values come in as explicit args (Claude reads config.yaml
and passes them); these scripts never parse YAML.
"""
import csv
import os
from datetime import datetime
from urllib.parse import quote

import adapter_base as ab
import geo
import placekey as pk

_DATASETS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "datasets")


FAMILY_SOURCE = "census-geocoder"
_CENTROIDS_PATH = os.path.join(_DATASETS, "us_place_centroids.csv")
_GEOCODER_ONELINE = ("https://geocoding.geo.census.gov/geocoder/locations/onelineaddress"
                     "?address={addr}&benchmark=Public_AR_Current&format=json")
_PLACE_SUFFIXES = (" city", " town", " CDP", " village", " borough", " municipality")


def _strip_place_suffix(n):
    for suf in _PLACE_SUFFIXES:
        if n.endswith(suf):
            return n[:-len(suf)]
    return n


def _parse_location(loc):
    """'Seattle, WA' -> ('Seattle', 'WA'); 'Seattle' -> ('Seattle', None).
    Street addresses keep the full prefix as name (gazetteer won't match -> geocoder)."""
    parts = [p.strip() for p in loc.split(",")]
    if len(parts) >= 2 and len(parts[-1]) == 2 and parts[-1].isalpha():
        name = parts[0] if len(parts) == 2 else ", ".join(parts[:-1])
        return name, parts[-1].upper()
    return loc.strip(), None


def _place_centroid(name, state, places):
    target = name.strip().lower()
    for r in places:
        if r.get("usps") == state and _strip_place_suffix(r.get("name", "")).lower() == target:
            try:
                return float(r["lat"]), float(r["lon"])
            except (TypeError, ValueError):
                return None
    return None


def _place_row(name, state, places):
    """Matched centroid row for a 'name'/'state' (place-suffix-insensitive), else None."""
    target = name.strip().lower()
    for r in places:
        if r.get("usps") == state and _strip_place_suffix(r.get("name", "")).lower() == target:
            return r
    return None


def resolve_place_centroid(location, path=None):
    """'Aurora, CO' -> {name, state, normalized_name, geocode} from the bundled Census
    place centroids, or {} when the location has no state or no exact match.

    Gives city-grain places a deterministic identity: the same city always resolves to one
    normalized_name + centroid geocode, so its place_key and cache are shared across evals
    instead of forking when a slightly different coordinate is supplied.
    """
    name, state = _parse_location(location)
    if not state:
        return {}
    try:
        row = _place_row(name, state, _load_centroids(path))
    except OSError:
        return {}
    if not row:
        return {}
    try:
        lat, lon = float(row["lat"]), float(row["lon"])
    except (TypeError, ValueError, KeyError):
        return {}
    official = _strip_place_suffix(row.get("name", "")).strip()
    return {"name": official, "state": state,
            "normalized_name": pk.normalize_name(f"{official}, {state}"),
            "geocode": pk.trunc_geocode(f"{lat},{lon}")}


def _to_int(v):
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return None


def _nearby_places(places, lat, lon, radius_mi, min_pop=None, max_pop=None,
                   exclude_within_mi=0.0, limit=None):
    """Bundled-gazetteer places within radius_mi of (lat,lon), nearest-first.

    Population filters apply only when a place's population is KNOWN — a place with unknown
    (null/blank) population is never dropped for missing data (it's surfaced, flagged by a
    null `population`). `exclude_within_mi` drops the anchor's own immediate area.
    """
    out = []
    for r in places:
        try:
            plat, plon = float(r["lat"]), float(r["lon"])
        except (TypeError, ValueError, KeyError):
            continue
        d = geo.haversine_mi(lat, lon, plat, plon)
        if d > radius_mi or d < exclude_within_mi:
            continue
        pop = _to_int(r.get("population"))
        if pop is not None:
            if (min_pop is not None and pop < min_pop) or (max_pop is not None and pop > max_pop):
                continue
        official = _strip_place_suffix(r.get("name", "")).strip()
        state = r.get("usps")
        out.append({
            "name": official,
            "state": state,
            "normalized_name": pk.normalize_name(f"{official}, {state}" if state else official),
            "geocode": pk.trunc_geocode(f"{plat},{plon}"),
            "population": pop,
            "distance_mi": d,
        })
    out.sort(key=lambda x: x["distance_mi"])
    return out[:limit] if limit is not None else out


def nearby_places(geocode, radius_mi, min_pop=None, max_pop=None,
                  exclude_within_mi=0.0, limit=None, path=None):
    """Overlooked Census-Gazetteer places around an anchor coordinate — the gem-hunt engine.
    Pure bundled-data, no network. Returns a list (not the source-record envelope)."""
    lat, lon = ab.parse_geocode(geocode)
    try:
        places = _load_centroids(path)
    except OSError:
        return []
    return _nearby_places(places, lat, lon, radius_mi, min_pop, max_pop,
                          exclude_within_mi, limit)


def _distance_entry(loc, plat, plon, coord):
    if not coord:
        return {"location": loc, "distance_mi": None, "est_drive_hr": None, "est_flight_hr": None}
    d = geo.haversine_mi(plat, plon, coord[0], coord[1])
    return {"location": loc, "distance_mi": d,
            "est_drive_hr": round(d / 55, 1),
            "est_flight_hr": round(d / 500 + 1.5, 1) if d > 300 else None}


def _load_centroids(path=None):
    with open(path or _CENTROIDS_PATH, newline="") as f:
        return list(csv.DictReader(f))


def _resolve_location(loc, places):
    """City/state -> bundled centroid; else street address -> Census Geocoder."""
    name, state = _parse_location(loc)
    if state:
        c = _place_centroid(name, state, places)
        if c:
            return c
    try:
        r = ab.http_json(_GEOCODER_ONELINE.format(addr=quote(loc)), timeout=30)
        matches = r.get("result", {}).get("addressMatches") or []
        if matches:
            co = matches[0]["coordinates"]
            return float(co["y"]), float(co["x"])
    except Exception:  # noqa: BLE001
        pass
    return None


def family_distance(place_key, geocode, level, family_locations, now=None):
    """Distance + drive/flight estimate from the place to each configured family location."""
    now = now or datetime.now()
    plat, plon = ab.parse_geocode(geocode)
    family_locations = family_locations or []
    places = _load_centroids() if any("," in loc for loc in family_locations) else []
    entries = [_distance_entry(loc, plat, plon, _resolve_location(loc, places))
               for loc in family_locations]
    return ab.make_record(place_key, FAMILY_SOURCE, {"distances": entries}, level,
                          now.isoformat(), "fresh" if entries else "unavailable")


def internet_quality(place_key, geocode, level, data_root=None, now=None, force_refresh=False):
    """Keyless FCC block/county/state FIPS for the coordinate — cached by coordinate and
    shared with the hazard lookup when data_root is given (one FCC call per point).
    Provider availability and max advertised speeds are token-gated (BDC API) -> filled
    via reason-with-search."""
    now = now or datetime.now()
    lat, lon = ab.parse_geocode(geocode)
    try:
        resp = _fcc_area_resp(lat, lon, data_root=data_root, now=now, force_refresh=force_refresh)
    except Exception:
        resp = None
    payload = _normalize_fcc_area(resp)
    status = "fresh" if payload.get("county_fips") else "unavailable"
    return ab.make_record(place_key, "fcc-broadband", payload, level, now.isoformat(), status)


AIRPORT_SOURCE = "ourairports"
_AIRPORTS_PATH = os.path.join(_DATASETS, "us_airports.csv")


def _load_airports(path=None):
    out = []
    with open(path or _AIRPORTS_PATH, newline="") as f:
        for r in csv.DictReader(f):
            try:
                r["lat"], r["lon"] = float(r["lat"]), float(r["lon"])
            except (TypeError, ValueError, KeyError):
                continue
            out.append(r)
    return out


def _nearest_airport(airports, lat, lon, types=None):
    best, best_d = None, None
    for a in airports:
        if types and a.get("type") not in types:
            continue
        d = geo.haversine_mi(lat, lon, a["lat"], a["lon"])
        if best_d is None or d < best_d:
            best, best_d = a, d
    return (best, best_d) if best else (None, None)


def _airport_fmt(ap, dist):
    if not ap:
        return None
    return {"iata": ap.get("iata") or None, "name": ap.get("name"),
            "distance_mi": dist, "est_drive_min": round(dist / 45 * 60) if dist else 0}


def airport_access(place_key, geocode, level, now=None):
    """Nearest commercial airport + nearest large hub from the bundled OurAirports CSV."""
    now = now or datetime.now()
    lat, lon = ab.parse_geocode(geocode)
    try:
        airports = _load_airports()
    except OSError:
        airports = []
    comm, dc = _nearest_airport(airports, lat, lon)
    hub, dh = _nearest_airport(airports, lat, lon, types=("large_airport",))
    payload = {"nearest_commercial": _airport_fmt(comm, dc),
               "nearest_intl_hub": _airport_fmt(hub, dh)}
    return ab.make_record(place_key, AIRPORT_SOURCE, payload, level, now.isoformat(),
                          "fresh" if comm else "unavailable")


# --- Walkability — EPA National Walkability Index (keyless, block-group grain) ---
WALKABILITY_SOURCE = "epa-nwi"
WALKABILITY_TTL = 365  # SLD v3 updates ~decadally; long cache
_NWI_URL = (
    "https://geodata.epa.gov/arcgis/rest/services/OA/WalkabilityIndex/MapServer/0/query"
    "?geometry={lon},{lat}&geometryType=esriGeometryPoint&inSR=4326"
    "&spatialRel=esriSpatialRelIntersects&outFields=NatWalkInd,GEOID10"
    "&returnGeometry=false&f=json"
)


def _walk_category(idx):
    """EPA NWI band for a 1-20 index (breakpoints 5.75 / 10.5 / 15.25)."""
    if idx is None:
        return None
    if idx <= 5.75:
        return "least walkable"
    if idx <= 10.5:
        return "below average"
    if idx <= 15.25:
        return "above average"
    return "most walkable"


def _normalize_nwi(resp):
    a = ab.arcgis_first_attrs(resp)
    idx = a.get("NatWalkInd")
    return {"nat_walk_index": idx, "category": _walk_category(idx),
            "block_group_geoid": a.get("GEOID10")}


def walkability(place_key, geocode, level, data_root=None, now=None, force_refresh=False):
    """EPA National Walkability Index at the place coordinate (block-group grain).
    Keyless. Cacheable with a long TTL when `data_root` is given."""
    now = now or datetime.now()
    lat, lon = ab.parse_geocode(geocode)
    url = _NWI_URL.format(lat=lat, lon=lon)

    def primary():
        return _normalize_nwi(ab.http_json(url, timeout=30))

    if data_root:
        return ab.fetch_with_cache(data_root, WALKABILITY_SOURCE, place_key,
                                   WALKABILITY_TTL, primary, now=now,
                                   place_grain=level, force_refresh=force_refresh)
    try:
        payload, status = primary(), "fresh"
    except Exception:
        payload, status = _normalize_nwi(None), "unavailable"
    return ab.make_record(place_key, WALKABILITY_SOURCE, payload, level, now.isoformat(), status)


# --- Hazard — FEMA National Risk Index (county) + NFHL flood zone (point). Keyless. ---
HAZARD_SOURCE = "fema-nri-nfhl"
HAZARD_TTL = 180
_FCC_AREA_URL = "https://geo.fcc.gov/api/census/area?lat={lat}&lon={lon}&format=json"
_NRI_URL = (
    "https://services.arcgis.com/XG15cJAlne2vxtgt/arcgis/rest/services/"
    "National_Risk_Index_Counties/FeatureServer/0/query?where=STCOFIPS%3D%27{fips}%27"
    "&outFields=COUNTY,STATEABBRV,RISK_SCORE,RISK_RATNG,WFIR_RISKS,WFIR_RISKR,"
    "EAL_SCORE,SOVI_SCORE,RESL_SCORE&returnGeometry=false&f=json"
)
_NFHL_URL = (
    "https://hazards.fema.gov/arcgis/rest/services/public/NFHL/MapServer/28/query"
    "?geometry={lon},{lat}&geometryType=esriGeometryPoint&inSR=4326"
    "&spatialRel=esriSpatialRelIntersects&outFields=FLD_ZONE,ZONE_SUBTY,SFHA_TF"
    "&returnGeometry=false&f=json"
)


def _round1(x):
    return round(x, 1) if isinstance(x, (int, float)) else None


def _normalize_nri(resp):
    a = ab.arcgis_first_attrs(resp)
    return {
        "county": a.get("COUNTY"),
        "state": a.get("STATEABBRV"),
        "risk_score": _round1(a.get("RISK_SCORE")),
        "risk_rating": a.get("RISK_RATNG"),
        "wildfire_risk_score": _round1(a.get("WFIR_RISKS")),
        "wildfire_risk_rating": a.get("WFIR_RISKR"),
        "expected_annual_loss_score": _round1(a.get("EAL_SCORE")),
        "social_vulnerability_score": _round1(a.get("SOVI_SCORE")),
        "community_resilience_score": _round1(a.get("RESL_SCORE")),
    }


def _normalize_flood(resp):
    a = ab.arcgis_first_attrs(resp)
    tf = a.get("SFHA_TF")
    return {
        "flood_zone": a.get("FLD_ZONE"),
        "flood_zone_subtype": a.get("ZONE_SUBTY"),
        "in_special_flood_hazard_area": (tf == "T") if tf else None,
    }


def _fcc_area(lat, lon):
    """Keyless FCC census-area lookup (block/county/state FIPS) for a coordinate."""
    return ab.http_json(_FCC_AREA_URL.format(lat=lat, lon=lon), timeout=30)


FCC_AREA_SOURCE = "fcc-area"
FCC_AREA_TTL = 3650  # a coordinate's FIPS is stable for years; cache aggressively


def _fcc_area_resp(lat, lon, data_root=None, now=None, force_refresh=False):
    """Raw FCC census-area response, cached by coordinate when data_root is given so the
    internet and hazard lookups reuse one FCC call per point (and survive an FCC outage).
    Without data_root it resolves live and may raise — the caller handles failure."""
    if not data_root:
        return _fcc_area(lat, lon)
    rec = ab.fetch_with_cache(data_root, FCC_AREA_SOURCE, ab.coord_cache_key(lat, lon),
                              FCC_AREA_TTL, lambda: _fcc_area(lat, lon),
                              now=now or datetime.now(), place_grain="point",
                              force_refresh=force_refresh)
    return rec["payload"] or None


def _normalize_fcc_area(resp):
    results = (resp or {}).get("results") or []
    r = results[0] if results else {}
    return {
        "block_fips": r.get("block_fips"),
        "county_fips": r.get("county_fips"),
        "county_name": r.get("county_name"),
        "state_code": r.get("state_code"),
        "providers": None,   # BDC availability API is token-gated -> reason-with-search
        "max_speeds": None,
    }


def _fcc_county_fips(lat, lon, data_root=None, now=None, force_refresh=False):
    return _normalize_fcc_area(
        _fcc_area_resp(lat, lon, data_root=data_root, now=now, force_refresh=force_refresh)
    ).get("county_fips")


def hazard(place_key, geocode, level, data_root=None, now=None, force_refresh=False):
    """FEMA composite hazard: NRI risk scores (county grain) + NFHL flood zone (point). Keyless."""
    now = now or datetime.now()
    lat, lon = ab.parse_geocode(geocode)

    def primary():
        fips = _fcc_county_fips(lat, lon, data_root=data_root, now=now, force_refresh=force_refresh)
        nri = _normalize_nri(ab.http_json(_NRI_URL.format(fips=fips))) if fips else _normalize_nri(None)
        flood = _normalize_flood(ab.http_json(_NFHL_URL.format(lat=lat, lon=lon)))
        return {"national_risk_index": nri, "flood": flood, "county_fips": fips}

    if data_root:
        return ab.fetch_with_cache(data_root, HAZARD_SOURCE, place_key, HAZARD_TTL,
                                   primary, now=now, place_grain=level, force_refresh=force_refresh)
    try:
        payload, status = primary(), "fresh"
    except Exception:
        payload, status = {"national_risk_index": _normalize_nri(None),
                           "flood": _normalize_flood(None), "county_fips": None}, "unavailable"
    return ab.make_record(place_key, HAZARD_SOURCE, payload, level, now.isoformat(), status)


def _main(argv=None):
    import argparse
    import json

    ap = argparse.ArgumentParser(description="Habitat utility lookups.")
    ap.add_argument("which", choices=["family_distance", "internet_quality", "airport_access",
                                      "walkability", "hazard", "place_centroid", "nearby_places"])
    ap.add_argument("--place-key")
    ap.add_argument("--geocode")
    ap.add_argument("--level")
    ap.add_argument("--data-root", help="cache root (enables caching for supported lookups)")
    ap.add_argument("--family", action="append", default=[], help="family location (repeatable)")
    ap.add_argument("--location", help="'City, ST' (place_centroid only)")
    ap.add_argument("--force-refresh", action="store_true",
                    help="bypass the coordinate cache (internet / walkability / hazard)")
    ap.add_argument("--radius", type=float, help="nearby_places: search radius (miles)")
    ap.add_argument("--min-pop", type=int, help="nearby_places: minimum population filter")
    ap.add_argument("--max-pop", type=int, help="nearby_places: maximum population filter")
    ap.add_argument("--exclude-within", type=float, default=0.0,
                    help="nearby_places: drop places nearer than N miles (skip the anchor)")
    ap.add_argument("--limit", type=int, help="nearby_places: cap number of results")
    a = ap.parse_args(argv)
    if a.which == "place_centroid":
        if not a.location:
            ap.error("place_centroid requires --location 'City, ST'")
        print(json.dumps(resolve_place_centroid(a.location), indent=2, sort_keys=True))
        return
    if a.which == "nearby_places":
        if not (a.geocode and a.radius is not None):
            ap.error("nearby_places requires --geocode and --radius")
        print(json.dumps(nearby_places(a.geocode, a.radius, a.min_pop, a.max_pop,
                                        a.exclude_within, a.limit), indent=2, sort_keys=True))
        return
    if not (a.place_key and a.geocode and a.level):
        ap.error("--place-key, --geocode and --level are required")
    if a.which == "family_distance":
        rec = family_distance(a.place_key, a.geocode, a.level, a.family)
    elif a.which == "internet_quality":
        rec = internet_quality(a.place_key, a.geocode, a.level, a.data_root,
                               force_refresh=a.force_refresh)
    elif a.which == "walkability":
        rec = walkability(a.place_key, a.geocode, a.level, a.data_root, force_refresh=a.force_refresh)
    elif a.which == "hazard":
        rec = hazard(a.place_key, a.geocode, a.level, a.data_root, force_refresh=a.force_refresh)
    else:
        rec = airport_access(a.place_key, a.geocode, a.level)
    print(json.dumps(rec, indent=2, sort_keys=True))


if __name__ == "__main__":
    _main()
