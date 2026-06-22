"""TDD tests for the air-quality adapter normalizers (AirNow + Open-Meteo AQ fallback).
Run: python3 scripts/tests/test_airquality.py -v"""
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(SCRIPTS / "adapters"))
import airquality

# AirNow current obs shape (captured live 2026-05-27, Tacoma) — two pollutants.
AIRNOW = [
    {"ParameterName": "O3", "AQI": 30, "Category": {"Name": "Good"}, "ReportingArea": "Tacoma-Puyallup"},
    {"ParameterName": "PM2.5", "AQI": 42, "Category": {"Name": "Good"}, "ReportingArea": "Tacoma-Puyallup"},
]
OPENMETEO = {"current": {"us_aqi": 55, "pm2_5": 13.2, "ozone": 48.0}}


class AirNowNormalizeTest(unittest.TestCase):
    def test_overall_aqi_is_max_pollutant(self):
        p = airquality._normalize_airnow(AIRNOW)
        self.assertEqual(p["current_aqi"], 42)
        self.assertEqual(p["dominant_pollutant"], "PM2.5")
        self.assertEqual(p["category"], "Good")
        self.assertEqual(p["pm25_aqi"], 42)
        self.assertEqual(p["ozone_aqi"], 30)
        self.assertEqual(p["reporting_area"], "Tacoma-Puyallup")

    def test_empty_obs_is_none(self):
        p = airquality._normalize_airnow([])
        self.assertIsNone(p["current_aqi"])
        self.assertIsNone(p["reporting_area"])


class AqiCategoryTest(unittest.TestCase):
    def test_bands(self):
        self.assertEqual(airquality._aqi_category(25), "Good")
        self.assertEqual(airquality._aqi_category(75), "Moderate")
        self.assertEqual(airquality._aqi_category(125), "Unhealthy for Sensitive Groups")
        self.assertEqual(airquality._aqi_category(175), "Unhealthy")
        self.assertEqual(airquality._aqi_category(250), "Very Unhealthy")
        self.assertEqual(airquality._aqi_category(350), "Hazardous")
        self.assertIsNone(airquality._aqi_category(None))


class OpenMeteoAqNormalizeTest(unittest.TestCase):
    def test_maps_current_us_aqi(self):
        p = airquality._normalize_open_meteo_aq(OPENMETEO)
        self.assertEqual(p["current_aqi"], 55)
        self.assertEqual(p["category"], "Moderate")
        self.assertEqual(p["pm25_concentration"], 13.2)

    def test_empty_is_none(self):
        self.assertIsNone(airquality._normalize_open_meteo_aq({})["current_aqi"])


class CoverageRoutingTest(unittest.TestCase):
    def test_us_point_in_coverage(self):
        self.assertTrue(airquality._is_us_airnow_coverage(47.25, -122.44))   # Tacoma

    def test_korea_point_out_of_coverage(self):
        self.assertFalse(airquality._is_us_airnow_coverage(37.0, 127.5))     # South Korea


class FetchFallbackTest(unittest.TestCase):
    """AirNow is US-only. Off-US, Open-Meteo (keyless, global) is the PRIMARY so the record is
    fresh and refreshes cleanly; within US coverage, an empty AirNow still falls back to it."""

    NOW = datetime(2026, 5, 28)

    def _stub(self, url, **k):
        return [] if "airnowapi" in url else OPENMETEO  # AirNow empty; Open-Meteo has data

    def test_international_uses_open_meteo_as_primary(self):
        orig = (airquality.ab.load_secrets, airquality.ab.http_json)
        airquality.ab.load_secrets = lambda *a, **k: {"EPA_AIRNOW_API_KEY": "x"}
        airquality.ab.http_json = self._stub
        try:
            with tempfile.TemporaryDirectory() as d:
                rec = airquality.fetch("country::south-korea-kr::37.0000,127.5000",
                                       "37.0000,127.5000", "country", d, now=self.NOW)
            self.assertEqual(rec["payload"]["current_aqi"], 55)   # from Open-Meteo
            self.assertEqual(rec["data_status"], "fresh")         # primary, not a degraded fallback
        finally:
            airquality.ab.load_secrets, airquality.ab.http_json = orig

    def test_us_coverage_gap_falls_back_to_open_meteo(self):
        orig = (airquality.ab.load_secrets, airquality.ab.http_json)
        airquality.ab.load_secrets = lambda *a, **k: {"EPA_AIRNOW_API_KEY": "x"}
        airquality.ab.http_json = self._stub
        try:
            with tempfile.TemporaryDirectory() as d:
                rec = airquality.fetch("city::remote-ak::64.0000,-150.0000",
                                       "64.0000,-150.0000", "city", d, now=self.NOW)
            self.assertEqual(rec["payload"]["current_aqi"], 55)   # Open-Meteo fallback
            self.assertEqual(rec["data_status"], "degraded")      # AirNow (primary) missed
            self.assertIn("AirNow", rec.get("degraded_reason", ""))
        finally:
            airquality.ab.load_secrets, airquality.ab.http_json = orig


if __name__ == "__main__":
    unittest.main()
