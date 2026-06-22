"""Climate adapter — Open-Meteo historical archive (keyless): temperature ranges,
precipitation, and sunshine summarized over the last 3 complete years. NOAA NCEI official
1991-2020 normals are a Phase-2 enrichment (nearest-station resolution + the validated
NOAA_CDO_TOKEN); Open-Meteo gives the full aggregate signal in one keyless call for V1."""
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import adapter_base as ab  # noqa: E402

SOURCE = "open-meteo"
TTL_DAYS = 90
PAYLOAD_FIELDS = ["temp_ranges", "precipitation", "sunlight_hours",
                  "humidity_profile", "season_character"]

_ARCHIVE_URL = (
    "https://archive-api.open-meteo.com/v1/archive?latitude={lat}&longitude={lon}"
    "&start_date={start}&end_date={end}"
    "&daily=temperature_2m_max,temperature_2m_min,precipitation_sum,sunshine_duration"
    "&temperature_unit=fahrenheit&precipitation_unit=inch&timezone=auto"
)
_SUMMER, _WINTER = {6, 7, 8}, {12, 1, 2}


def _avg(xs):
    xs = [x for x in xs if x is not None]
    return round(sum(xs) / len(xs), 1) if xs else None


def _normalize(daily):
    time = daily.get("time") or []
    tmax = daily.get("temperature_2m_max") or []
    tmin = daily.get("temperature_2m_min") or []
    prcp = daily.get("precipitation_sum") or []
    sun = daily.get("sunshine_duration") or []
    months = [int(t[5:7]) for t in time if len(t) >= 7]
    years = len(set(t[:4] for t in time)) or 1

    def season(arr, season_months):
        vals = [arr[i] for i in range(min(len(arr), len(months)))
                if months[i] in season_months and arr[i] is not None]
        return _avg(vals)

    return {
        "temp_ranges": {
            "annual_high_avg_f": _avg(tmax),
            "annual_low_avg_f": _avg(tmin),
            "summer_high_avg_f": season(tmax, _SUMMER),
            "winter_low_avg_f": season(tmin, _WINTER),
        },
        "precipitation": {
            "annual_total_in": round(sum(p for p in prcp if p is not None) / years, 1) if prcp else None,
            "wet_days_per_year": round(sum(1 for p in prcp if p and p >= 0.01) / years) if prcp else None,
        },
        "sunlight_hours": {
            "annual_sunshine_hours": round(sum(s for s in sun if s) / 3600 / years) if sun else None,
        },
        "humidity_profile": None,   # Phase-2: hourly RH aggregation
        "season_character": None,   # Claude composes from the numbers
    }


def fetch(place_key, geocode, level, data_root, now=None, force_refresh=False):
    """Open-Meteo archive over the last 3 complete years -> seasonal climate summary."""
    now = now or datetime.now()
    lat, lon = ab.parse_geocode(geocode)
    start, end = f"{now.year - 3}-01-01", f"{now.year - 1}-12-31"

    def primary():
        url = _ARCHIVE_URL.format(lat=lat, lon=lon, start=start, end=end)
        return _normalize(ab.http_json(url, timeout=45).get("daily") or {})

    return ab.fetch_with_cache(data_root, SOURCE, place_key, TTL_DAYS, primary,
                               now=now, place_grain=level, force_refresh=force_refresh)


if __name__ == "__main__":
    ab.adapter_cli(fetch)
