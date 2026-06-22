"""TDD tests for the climate adapter aggregation (Open-Meteo daily archive -> seasonal
summary). Run: python3 scripts/tests/test_climate.py -v"""
import sys
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(SCRIPTS / "adapters"))
import climate

# Two years, one summer + one winter day each (°F, inches, seconds of sunshine).
DAILY = {
    "time": ["2023-07-15", "2023-12-15", "2024-07-15", "2024-12-15"],
    "temperature_2m_max": [80, 45, 82, 47],
    "temperature_2m_min": [55, 35, 57, 37],
    "precipitation_sum": [0.0, 0.4, 0.0, 0.6],
    "sunshine_duration": [36000, 18000, 36000, 18000],
}


class NormalizeTest(unittest.TestCase):
    def test_temp_ranges(self):
        t = climate._normalize(DAILY)["temp_ranges"]
        self.assertEqual(t["annual_high_avg_f"], 63.5)   # mean(80,45,82,47)
        self.assertEqual(t["annual_low_avg_f"], 46.0)    # mean(55,35,57,37)
        self.assertEqual(t["summer_high_avg_f"], 81.0)   # mean(80,82)
        self.assertEqual(t["winter_low_avg_f"], 36.0)    # mean(35,37)

    def test_precipitation_per_year(self):
        p = climate._normalize(DAILY)["precipitation"]
        self.assertEqual(p["annual_total_in"], 0.5)      # 1.0 in over 2 yrs
        self.assertEqual(p["wet_days_per_year"], 1)      # 2 wet days over 2 yrs

    def test_sunshine_per_year(self):
        s = climate._normalize(DAILY)["sunlight_hours"]
        self.assertEqual(s["annual_sunshine_hours"], 15)  # 108000s = 30h over 2 yrs

    def test_deferred_and_narrative_fields(self):
        p = climate._normalize(DAILY)
        self.assertIsNone(p["humidity_profile"])   # Phase-2
        self.assertIsNone(p["season_character"])    # Claude composes

    def test_empty_is_none(self):
        t = climate._normalize({})["temp_ranges"]
        self.assertIsNone(t["annual_high_avg_f"])


if __name__ == "__main__":
    unittest.main()
