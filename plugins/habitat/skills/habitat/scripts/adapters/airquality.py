"""Air-quality adapter — EPA AirNow (current, authoritative) with Open-Meteo Air
Quality (keyless) as the fallback. 24h TTL: current/recent readings, refreshed daily.
Richer historical aggregates (smoke-season day counts) are a documented Phase-2 enrichment."""
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import adapter_base as ab  # noqa: E402

SOURCE = "epa-airnow"
SOURCE_OPENMETEO = "open-meteo-aq"
TTL_DAYS = 1
PAYLOAD_FIELDS = ["current_aqi", "category", "dominant_pollutant",
                  "pm25_aqi", "ozone_aqi", "reporting_area"]

_AIRNOW_URL = ("https://www.airnowapi.org/aq/observation/latLong/current/"
               "?format=application/json&latitude={lat}&longitude={lon}"
               "&distance=50&API_KEY={key}")
_OPENMETEO_AQ_URL = ("https://air-quality-api.open-meteo.com/v1/air-quality"
                     "?latitude={lat}&longitude={lon}&current=us_aqi,pm2_5,ozone")


def _aqi_category(aqi):
    """US EPA AQI band name for a numeric AQI (None -> None)."""
    if not isinstance(aqi, (int, float)):
        return None
    if aqi <= 50:
        return "Good"
    if aqi <= 100:
        return "Moderate"
    if aqi <= 150:
        return "Unhealthy for Sensitive Groups"
    if aqi <= 200:
        return "Unhealthy"
    if aqi <= 300:
        return "Very Unhealthy"
    return "Hazardous"


def _normalize_airnow(obs):
    """AirNow returns one observation per pollutant; overall AQI is the max."""
    obs = obs or []
    by = {(o.get("ParameterName") or "").upper(): o.get("AQI") for o in obs}
    aqis = [o.get("AQI") for o in obs if isinstance(o.get("AQI"), (int, float))]
    current = max(aqis) if aqis else None
    dominant = category = None
    for o in obs:
        if o.get("AQI") == current and current is not None:
            dominant = o.get("ParameterName")
            category = (o.get("Category") or {}).get("Name")
            break
    return {
        "current_aqi": current,
        "category": category,
        "dominant_pollutant": dominant,
        "pm25_aqi": by.get("PM2.5"),
        "ozone_aqi": by.get("O3") or by.get("OZONE"),
        "reporting_area": obs[0].get("ReportingArea") if obs else None,
    }


def _normalize_open_meteo_aq(resp):
    c = (resp or {}).get("current") or {}
    aqi = c.get("us_aqi")
    return {
        "current_aqi": aqi,
        "category": _aqi_category(aqi),
        "dominant_pollutant": None,
        "pm25_aqi": None,
        "ozone_aqi": None,
        "reporting_area": None,
        "pm25_concentration": c.get("pm2_5"),
    }


def _is_us_airnow_coverage(lat, lon):
    """Rough EPA-AirNow (US) coverage test — continental US + Alaska + Hawaii boxes.
    Outside these, AirNow has no data, so Open-Meteo becomes the primary (global, keyless)."""
    boxes = ((24, 50, -125, -66), (51, 72, -170, -129), (18, 23, -161, -154))
    return any(la0 <= lat <= la1 and lo0 <= lon <= lo1 for la0, la1, lo0, lo1 in boxes)


def fetch(place_key, geocode, level, data_root, now=None, force_refresh=False):
    """Within US AirNow coverage: AirNow primary, Open-Meteo AQ fallback. Off-US (international):
    Open-Meteo AQ (keyless, global) is the primary, so it stays fresh and refreshes cleanly."""
    now = now or datetime.now()
    lat, lon = ab.parse_geocode(geocode)
    key = ab.load_secrets().get("EPA_AIRNOW_API_KEY")

    def airnow():
        if not key:
            raise RuntimeError("EPA_AIRNOW_API_KEY missing")
        payload = _normalize_airnow(ab.http_json(_AIRNOW_URL.format(lat=lat, lon=lon, key=key)))
        # AirNow returns an empty list (no usable AQI) for points it doesn't cover — treat as a
        # primary MISS so the fallback runs, never caching an empty record as 'fresh'.
        if payload.get("current_aqi") is None:
            raise RuntimeError("AirNow: no observation for this location (outside US coverage?)")
        return payload

    def open_meteo():
        return _normalize_open_meteo_aq(ab.http_json(_OPENMETEO_AQ_URL.format(lat=lat, lon=lon)))

    if _is_us_airnow_coverage(lat, lon):
        primary, alt, src = airnow, open_meteo, SOURCE
    else:
        primary, alt, src = open_meteo, None, SOURCE_OPENMETEO  # global authority off-US; label honestly

    return ab.fetch_with_cache(data_root, src, place_key, TTL_DAYS, primary,
                               now=now, place_grain=level, force_refresh=force_refresh,
                               alt_fetch=alt)


if __name__ == "__main__":
    ab.adapter_cli(fetch)
