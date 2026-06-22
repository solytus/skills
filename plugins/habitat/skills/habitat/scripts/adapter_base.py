"""Habitat cached-adapter base.

Atomic local cache, TTL freshness, and 3-tier fallback orchestration shared by every
cached adapter. Python stdlib only. Times are naive local datetimes / ISO strings (V1).
"""
from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

DATA_STATUS = ("fresh", "stale", "degraded", "unavailable")


def _resolve_secrets_path(home=None):
    """Resolve where to read secrets.env when no explicit path is given.

    Order (Tier-2 first so keys survive plugin updates):
      1. $HABITAT_SECRETS                       — explicit power-user override
      2. ~/.solytus/habitat/secrets.env         — Tier-2 instance location (default),
         alongside config.yaml and OUTSIDE the skill, so a marketplace reinstall or
         `git pull` never touches your keys
      3. <skill>/secrets.env                     — beside-skill fallback for repo-local dev
    `home` is injectable for testing; defaults to the real home directory.
    """
    env = os.environ.get("HABITAT_SECRETS")
    if env:
        return env
    base = Path(home) if home is not None else Path.home()
    tier2 = base / ".solytus" / "habitat" / "secrets.env"
    if tier2.exists():
        return str(tier2)
    return str(Path(__file__).resolve().parent.parent / "secrets.env")


def load_secrets(path=None, *, home=None):
    """Parse KEY=VALUE lines from secrets.env into a dict (stdlib only).

    Comment lines (starting with #) and blanks are ignored; values split on the
    first '='; surrounding matching quotes are stripped. A missing file returns
    {} so a missing key degrades gracefully rather than crashing. Resolution order
    when no explicit `path`: $HABITAT_SECRETS > ~/.solytus/habitat/secrets.env
    (Tier-2) > the secrets.env beside the skill (see `_resolve_secrets_path`).
    Inline comments on a value line are NOT supported (keep comments on their
    own line) so an API key is never silently truncated.
    """
    if path is None:
        path = _resolve_secrets_path(home=home)
    p = Path(path)
    if not p.exists():
        return {}
    out = {}
    for line in p.read_text().splitlines():
        s = line.strip()
        if not s or s.startswith("#") or "=" not in s:
            continue
        key, _, val = s.partition("=")
        key, val = key.strip(), val.strip()
        if len(val) >= 2 and val[0] == val[-1] and val[0] in ("'", '"'):
            val = val[1:-1]
        if key:
            out[key] = val
    return out


DEFAULT_UA = "habitat/0.1 (personal place-evaluation tool)"


def http_fetch(url, *, headers=None, data=None, timeout=30):
    """GET (or POST when `data` is given) and return the response body as text.

    `data`: dict → JSON-encoded POST body (Content-Type set); bytes → raw body.
    Raises urllib.error.HTTPError on non-2xx and URLError on network failure, so a
    failing source surfaces through the adapter fallback ladder rather than hanging.
    """
    import urllib.request
    hdrs = {"User-Agent": DEFAULT_UA}
    if headers:
        hdrs.update(headers)
    body = None
    if data is not None:
        if isinstance(data, (bytes, bytearray)):
            body = bytes(data)
        else:
            body = json.dumps(data).encode("utf-8")
            hdrs.setdefault("Content-Type", "application/json")
    req = urllib.request.Request(url, data=body, headers=hdrs)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", "replace")


def http_json(url, **kw):
    """http_fetch + json.loads (convenience for JSON APIs)."""
    return json.loads(http_fetch(url, **kw))


def parse_geocode(geocode):
    """'lat,lon' string -> (lat, lon) floats. Tolerates surrounding spaces."""
    lat, lon = geocode.split(",")
    return float(lat.strip()), float(lon.strip())


def arcgis_first_attrs(resp):
    """First feature's `attributes` dict from an ArcGIS REST query response, or {}."""
    feats = (resp or {}).get("features") or []
    return feats[0].get("attributes", {}) if feats else {}


def make_record(place_key, source, payload, place_grain, fetched_at, data_status="fresh"):
    """Build the normalized record envelope every adapter/lookup returns."""
    return {
        "place_key": place_key,
        "source": source,
        "fetched_at": fetched_at,  # ISO 8601 string
        "place_grain": place_grain,
        "data_status": data_status,
        "payload": payload,
    }


def place_key_to_filename(place_key):
    """Sanitize a place_key into a cache filename: '::' -> '__', ',' -> '_'."""
    return place_key.replace("::", "__").replace(",", "_") + ".json"


def coord_cache_key(lat, lon):
    """Coordinate-keyed cache id (4-decimal) for point-resolution caches shared across
    adapters: census-geo (Cost + Dynamism) and fcc-area (Internet + Hazard) both resolve
    the same lat/lon, so a shared key means one fetch per point instead of one per caller.
    """
    return f"coord::{lat:.4f},{lon:.4f}"


def cache_path(data_root, source, place_key):
    return Path(data_root) / "cache" / source / place_key_to_filename(place_key)


def freshness(fetched_at, ttl_days, now):
    """'fresh' while now - fetched_at <= ttl_days (inclusive boundary), else 'stale'."""
    fetched = datetime.fromisoformat(fetched_at)
    return "fresh" if now - fetched <= timedelta(days=ttl_days) else "stale"


def read_cache(data_root, source, place_key):
    """Return the cached record dict, or None if absent."""
    p = cache_path(data_root, source, place_key)
    if not p.exists():
        return None
    return json.loads(p.read_text())


def write_cache(data_root, source, place_key, record):
    """Atomically write a record: temp file in the same dir, then os.replace."""
    p = cache_path(data_root, source, place_key)
    p.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(p.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(record, f, indent=2, sort_keys=True)
        os.replace(tmp, p)
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)


def _exc_reason(e):
    """Compact, bounded failure cause for the degraded_reason breadcrumb."""
    return f"{type(e).__name__}: {e}"[:200]


def _achieved_grain(payload, grain_key, default):
    """The grain a fetch actually achieved, read from payload[grain_key] when present
    (e.g. a neighborhood request that only resolved to county). Falls back to the
    requested grain when the adapter doesn't report one or the payload is empty."""
    if grain_key and isinstance(payload, dict) and payload.get(grain_key):
        return payload[grain_key]
    return default


def fetch_with_cache(data_root, source, place_key, ttl_days, primary_fetch, *, now,
                     place_grain="city", force_refresh=False, alt_fetch=None, grain_key=None):
    """3-tier fallback: fresh cache -> primary -> cache -> alt source -> gap.

    primary_fetch / alt_fetch are zero-arg callables returning a payload dict (or
    raising on failure). `now` is a naive datetime. Returns a record envelope with
    data_status set to fresh | stale | degraded | unavailable.

    When a fetch fails and the result is served from a fallback tier, the record carries
    `degraded_reason` (the failure cause) so a degradation is debuggable, never silent.
    The cache-fallback tier labels data by its ACTUAL freshness — a forced refresh that
    fails over still-in-TTL data leaves it `fresh`, not falsely `stale`. Setting the
    HABITAT_DEBUG env var re-raises unexpected fetch exceptions instead of degrading, so
    a code bug surfaces in development rather than masquerading as a source outage.

    `grain_key`: when set, the record's `place_grain` is read from `payload[grain_key]` (the
    grain actually achieved) instead of the requested `place_grain`, so a coarser fallback
    (e.g. county data for a neighborhood request) is stamped honestly, not over-claimed.
    """
    cached = read_cache(data_root, source, place_key)

    # Tier 0: a fresh cache hit short-circuits everything (unless forced).
    if cached is not None and not force_refresh:
        if freshness(cached["fetched_at"], ttl_days, now) == "fresh":
            return {**cached, "data_status": "fresh"}

    # Tier 1: the primary source.
    try:
        payload = primary_fetch()
        grain = _achieved_grain(payload, grain_key, place_grain)
        rec = make_record(place_key, source, payload, grain, now.isoformat(), "fresh")
        write_cache(data_root, source, place_key, rec)
        return rec
    except Exception as e:
        if os.environ.get("HABITAT_DEBUG"):
            raise
        reason = _exc_reason(e)

    # Tier 2: cache fallback — labeled by ACTUAL freshness (fresh if still in TTL).
    if cached is not None:
        return {**cached,
                "data_status": freshness(cached["fetched_at"], ttl_days, now),
                "degraded_reason": f"refresh failed: {reason}"}

    # Tier 3: an alternative source, marked degraded.
    if alt_fetch is not None:
        try:
            payload = alt_fetch()
            grain = _achieved_grain(payload, grain_key, place_grain)
            rec = make_record(place_key, source, payload, grain, now.isoformat(), "degraded")
            rec["degraded_reason"] = f"primary failed: {reason}"
            write_cache(data_root, source, place_key, rec)
            return rec
        except Exception as e:
            if os.environ.get("HABITAT_DEBUG"):
                raise
            reason = f"{reason}; alt failed: {_exc_reason(e)}"

    # Tier 4: graceful gap.
    rec = make_record(place_key, source, {}, place_grain, now.isoformat(), "unavailable")
    rec["degraded_reason"] = reason
    return rec


def adapter_cli(fetch_fn, argv=None):
    """Thin CLI shared by cached adapters: parse standard args, print the JSON record."""
    import argparse
    import json as _json
    import sys

    ap = argparse.ArgumentParser()
    ap.add_argument("--data-root", required=True)
    ap.add_argument("--place-key", required=True)
    ap.add_argument("--geocode", required=True)
    ap.add_argument("--level", required=True)
    ap.add_argument("--force-refresh", action="store_true")
    a = ap.parse_args(argv)
    try:
        rec = fetch_fn(a.place_key, a.geocode, a.level, a.data_root, force_refresh=a.force_refresh)
    except Exception as e:  # noqa: BLE001
        print(f"adapter error: {e}", file=sys.stderr)
        raise SystemExit(1)
    print(_json.dumps(rec, indent=2, sort_keys=True))
