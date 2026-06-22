"""TDD tests for the Dynamism adapter normalizer (BLS LAUS county series).
Run: python3 scripts/tests/test_dynamism.py -v"""
import sys
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(SCRIPTS / "adapters"))
import dynamism

# BLS series data is most-recent-first; index 0 = latest, 12 = 1y ago, 60 = 5y ago.
UNEMP = [{"year": "2024", "periodName": "December", "value": "4.1"}, {"value": "4.2"}]


def emp_data():
    d = [{"value": "0"} for _ in range(72)]
    d[0] = {"value": "471362"}
    d[12] = {"value": "460000"}
    d[60] = {"value": "440000"}
    return d


class NormalizeTest(unittest.TestCase):
    def test_unemployment_rate_is_latest(self):
        self.assertEqual(dynamism._normalize(UNEMP, emp_data())["unemployment_rate"], 4.1)

    def test_employment_growth(self):
        p = dynamism._normalize(UNEMP, emp_data())
        self.assertEqual(p["employment_growth_1y"], 2.5)   # (471362-460000)/460000
        self.assertEqual(p["employment_growth_5y"], 7.1)   # (471362-440000)/440000

    def test_short_series_growth_is_none(self):
        p = dynamism._normalize(UNEMP, [{"value": "100"}, {"value": "99"}])
        self.assertIsNone(p["employment_growth_1y"])
        self.assertIsNone(p["employment_growth_5y"])

    def test_deferred_fields_are_none(self):
        p = dynamism._normalize(UNEMP, emp_data())
        self.assertIsNone(p["business_formation_rate"])
        self.assertIsNone(p["wages_by_sector"])
        self.assertIsNone(p["dominant_industries"])

    def test_empty_is_none(self):
        p = dynamism._normalize([], [])
        self.assertIsNone(p["unemployment_rate"])


if __name__ == "__main__":
    unittest.main()
