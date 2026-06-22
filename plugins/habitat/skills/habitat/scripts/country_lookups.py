"""Country-grain lookups for the international extension.

Deterministic reads over bundled country datasets (and one keyless FX API), each
returning the same record envelope as the US lookups so the Sources footer treats every
source uniformly. Values come in as explicit args (Claude reads config.yaml / profile.md
and passes them); these scripts never parse YAML/markdown.

Datasets are built by bundle_datasets.py into ../datasets/. Country identity is anchored
on country_centroids.csv (the country analog of us_place_centroids.csv).
"""
import csv
import os
from datetime import datetime

import adapter_base as ab
import placekey as pk

_DATASETS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "datasets")
_CENTROIDS_PATH = os.path.join(_DATASETS, "country_centroids.csv")
_GPI_PATH = os.path.join(_DATASETS, "gpi.csv")
_DIASPORA_PATH = os.path.join(_DATASETS, "diaspora.csv")
_PASSPORT_PATH = os.path.join(_DATASETS, "passport_index.csv")

GPI_SOURCE = "global-peace-index"
DIASPORA_SOURCE = "un-migrant-stock"
PASSPORT_SOURCE = "passport-index"
FX_SOURCE = "frankfurter-fx"
_FX_BASE = "https://api.frankfurter.app/latest"


def _num(s):
    try:
        return float(s)
    except (TypeError, ValueError):
        return None


def _int(s):
    s = (s or "").strip()
    return int(s) if s.lstrip("-").isdigit() else None


def _load_csv(path):
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


# --- country identity ----------------------------------------------------------

def resolve_country(name_or_iso, path=None):
    """'Portugal' / 'PT' / 'PRT' -> {iso2, iso3, name, normalized_name, geocode, tz}.

    The country analog of lookups.resolve_place_centroid: gives a country a deterministic
    identity (one normalized_name + representative-centroid geocode) so its place_key and
    cache are stable across evals. Returns {} when no match or the file is missing.
    """
    q = (name_or_iso or "").strip()
    if not q:
        return {}
    try:
        rows = _load_csv(path or _CENTROIDS_PATH)
    except OSError:
        return {}
    qu, ql = q.upper(), q.lower()
    row = next((r for r in rows if r.get("iso2", "").upper() == qu), None) \
        or next((r for r in rows if r.get("iso3", "").upper() == qu), None) \
        or next((r for r in rows if r.get("name", "").lower() == ql), None)
    if not row:
        return {}
    try:
        geocode = pk.trunc_geocode(f"{float(row['lat'])},{float(row['lon'])}")
    except (TypeError, ValueError, KeyError):
        return {}
    iso2 = row.get("iso2", "").upper()
    name = row.get("name", "")
    return {
        "iso2": iso2,
        "iso3": row.get("iso3", "").upper(),
        "name": name,
        "normalized_name": pk.normalize_name(f"{name}, {iso2}"),
        "geocode": geocode,
        "tz": row.get("tz", ""),
        "currency": row.get("currency", ""),
    }


# --- safety: Global Peace Index (country grain, bundled annual) -----------------

def gpi(place_key, iso2, path=None, now=None):
    """Global Peace Index score (lower = more peaceful) + rank, from the bundled annual CSV."""
    now = now or datetime.now()
    try:
        rows = _load_csv(path or _GPI_PATH)
    except OSError:
        rows = []
    row = next((r for r in rows if r.get("iso2", "").upper() == iso2.upper()), None)
    if not row:
        return ab.make_record(place_key, GPI_SOURCE, {}, "country", now.isoformat(), "unavailable")
    payload = {"score": _num(row.get("score")), "rank": _int(row.get("rank")),
               "year": _int(row.get("year"))}
    return ab.make_record(place_key, GPI_SOURCE, payload, "country", now.isoformat(), "fresh")


# --- belonging: diaspora / migrant stock (origin x destination, bundled) -------

def diaspora(place_key, dest_iso2, origin_iso_list, path=None, now=None):
    """Foreign-born stock in `dest` from the profile's belonging-origin set (UN Migrant Stock).

    Gives the softened international 'Asian/Korean community' preference a real country-grain
    number instead of pure reasoning: sums migrants from the requested origin countries.
    """
    now = now or datetime.now()
    try:
        rows = _load_csv(path or _DIASPORA_PATH)
    except OSError:
        rows = []
    dest = dest_iso2.upper()
    wanted = {o.upper() for o in (origin_iso_list or [])}
    by_origin, year = {}, None
    for r in rows:
        if r.get("dest_iso2", "").upper() != dest:
            continue
        oi = r.get("origin_iso2", "").upper()
        if oi not in wanted:
            continue
        m = _num(r.get("migrants"))
        if m is None:
            continue
        by_origin[oi] = int(m)
        year = year or _int(r.get("year"))
    if not by_origin:
        return ab.make_record(place_key, DIASPORA_SOURCE, {}, "country", now.isoformat(),
                              "unavailable")
    payload = {"total_from_origins": sum(by_origin.values()), "by_origin": by_origin,
               "top_origin": max(by_origin, key=by_origin.get), "year": year}
    return ab.make_record(place_key, DIASPORA_SOURCE, payload, "country", now.isoformat(), "fresh")


# --- immigration: passport / short-stay TRAVEL access (bundled) ----------------
# IMPORTANT: this measures tourist/short-stay travel access only — NOT the right to work
# or reside. The country workflow firewalls it out of the fit number and the residence
# verdict; it is reported as a labeled travel signal.

_VISA_RANKS = (
    (("visa free", "visa-free", "home", "-1"), 0),
    (("visa on arrival", "voa"), 1),
    (("e-visa", "evisa", "eta", "e-visa / eta"), 2),
    (("visa required",), 3),
)


def _visa_rank(req):
    """Lower = less restrictive. A bare number is visa-free days (rank 0); unknown = 3."""
    r = (req or "").strip().lower()
    if r.replace(".", "", 1).isdigit():
        return 0
    for keys, rank in _VISA_RANKS:
        if r in keys:
            return rank
    return 3


def passport(place_key, citizenships, dest_iso2, path=None, now=None):
    """Short-stay (TOURIST) travel access to `dest`. Personalized when citizenships given,
    else a generic accessibility proxy. Never a right-to-reside signal."""
    now = now or datetime.now()
    try:
        rows = _load_csv(path or _PASSPORT_PATH)
    except OSError:
        rows = []
    dest = dest_iso2.upper()
    dest_rows = [r for r in rows if r.get("dest_iso2", "").upper() == dest]
    if not dest_rows:
        return ab.make_record(place_key, PASSPORT_SOURCE, {}, "country", now.isoformat(),
                              "unavailable")
    cits = [c.upper() for c in (citizenships or [])]
    if not cits:
        vf = sum(1 for r in dest_rows if _visa_rank(r.get("requirement")) == 0)
        payload = {"generic": True, "best_status": None, "short_stay_only": True,
                   "visa_free_count": vf, "passports_in_data": len(dest_rows)}
        return ab.make_record(place_key, PASSPORT_SOURCE, payload, "country", now.isoformat(),
                              "fresh")
    by_passport = {c: next((r.get("requirement") for r in dest_rows
                            if r.get("passport_iso2", "").upper() == c), None) for c in cits}
    found = [v for v in by_passport.values() if v is not None]
    status = "fresh" if found else "unavailable"
    best = min(found, key=_visa_rank) if found else None
    payload = {"generic": False, "best_status": best, "by_passport": by_passport,
               "short_stay_only": True}
    return ab.make_record(place_key, PASSPORT_SOURCE, payload, "country", now.isoformat(), status)


# --- cost in home currency: FX (Frankfurter, keyless ECB rates) ----------------

def fx(place_key, base, dest, now=None):
    """Spot rate base->dest from Frankfurter (free, no key), so cost reads in home currency."""
    now = now or datetime.now()
    base, dest = base.upper(), dest.upper()
    if base == dest:
        payload = {"base": base, "dest": dest, "rate": 1.0, "date": now.date().isoformat()}
        return ab.make_record(place_key, FX_SOURCE, payload, "country", now.isoformat(), "fresh")
    try:
        resp = ab.http_json(f"{_FX_BASE}?from={base}&to={dest}", timeout=20)
        rate = (resp.get("rates") or {}).get(dest)
        if rate is None:
            raise ValueError(f"no {dest} rate")
        payload = {"base": base, "dest": dest, "rate": rate, "date": resp.get("date")}
        return ab.make_record(place_key, FX_SOURCE, payload, "country", now.isoformat(), "fresh")
    except Exception as e:  # noqa: BLE001
        rec = ab.make_record(place_key, FX_SOURCE, {}, "country", now.isoformat(), "unavailable")
        rec["degraded_reason"] = ab._exc_reason(e)
        return rec


def _main(argv=None):
    import argparse
    import json
    ap = argparse.ArgumentParser(description="Habitat country-grain lookups.")
    ap.add_argument("which", choices=["resolve_country", "gpi", "diaspora", "passport", "fx"])
    ap.add_argument("--place-key")
    ap.add_argument("--country", help="country name or ISO code (resolve_country)")
    ap.add_argument("--iso2", help="destination ISO alpha-2")
    ap.add_argument("--origin", action="append", default=[], help="origin ISO-2 (repeatable)")
    ap.add_argument("--citizenship", action="append", default=[], help="passport ISO-2 (repeatable)")
    ap.add_argument("--base", help="home/earning currency (fx)")
    ap.add_argument("--dest-ccy", help="destination currency (fx)")
    a = ap.parse_args(argv)
    if a.which == "resolve_country":
        print(json.dumps(resolve_country(a.country), indent=2))
        return
    pkey = a.place_key or "country::unknown::0,0"
    if a.which == "gpi":
        out = gpi(pkey, a.iso2)
    elif a.which == "diaspora":
        out = diaspora(pkey, a.iso2, a.origin)
    elif a.which == "passport":
        out = passport(pkey, a.citizenship, a.iso2)
    elif a.which == "fx":
        out = fx(pkey, a.base, a.dest_ccy)
    print(json.dumps(out, indent=2, sort_keys=True))


if __name__ == "__main__":
    _main()
