"""TDD tests for the Cost adapter (Census ACS normalize + geography scope).
Run: python3 scripts/tests/test_cost.py -v"""
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(SCRIPTS / "adapters"))
import cost

HEADER = ["NAME", "B19013_001E", "B25064_001E", "B25070_001E", "B25070_010E",
          "B01003_001E", "B01002_001E", "B15003_001E", "B15003_022E", "B15003_023E",
          "B15003_024E", "B15003_025E", "B02001_005E", "state", "place"]


def rows(vals):
    return [HEADER, vals]


class NormalizeTest(unittest.TestCase):
    def test_maps_core_fields(self):
        p = cost._normalize(rows(["Tacoma city, Washington", "83857", "1456", "30000", "6000",
                                  "219346", "36.5", "145000", "30000", "12000", "3000", "2000",
                                  "50000", "53", "70000"]))
        self.assertEqual(p["median_household_income"], 83857)
        self.assertEqual(p["median_residential_rent"], 1456)
        self.assertEqual(p["demographics"]["population"], 219346)
        self.assertEqual(p["demographics"]["median_age"], 36.5)
        self.assertEqual(p["housing_cost_burden"]["renters_50pct_plus_share"], 20.0)
        self.assertEqual(p["education_attainment"]["bachelors_or_higher_pct"], 32.4)

    def test_asian_share_is_computed(self):
        # Backs the "Asian population >= 3%" must_have deterministically.
        p = cost._normalize(rows(["Elk Grove city, California", "122229", "2180", "40000", "9840",
                                  "177221", "39", "120000", "30000", "12000", "3000", "2000",
                                  "55470", "06", "22020"]))
        self.assertEqual(p["demographics"]["asian_alone_count"], 55470)
        self.assertEqual(p["demographics"]["asian_alone_pct"], 31.3)

    def test_census_jam_values_become_none(self):
        p = cost._normalize(rows(["X", "-666666666", "1456", "30000", "6000", "219346", "36.5",
                                  "145000", "30000", "12000", "3000", "2000", "50000", "53", "70000"]))
        self.assertIsNone(p["median_household_income"])

    def test_zero_denominator_is_safe(self):
        p = cost._normalize(rows(["X", "83857", "1456", "0", "0", "219346", "36.5",
                                  "0", "0", "0", "0", "0", "0", "53", "70000"]))
        self.assertIsNone(p["housing_cost_burden"]["renters_50pct_plus_share"])
        self.assertIsNone(p["education_attainment"]["bachelors_or_higher_pct"])
        self.assertEqual(p["demographics"]["asian_alone_pct"], 0.0)

    def test_missing_population_makes_asian_pct_none(self):
        p = cost._normalize(rows(["X", "83857", "1456", "30000", "6000", "-666666666", "36.5",
                                  "145000", "30000", "12000", "3000", "2000", "50000", "53", "70000"]))
        self.assertEqual(p["demographics"]["asian_alone_count"], 50000)
        self.assertIsNone(p["demographics"]["asian_alone_pct"])

    def test_empty_rows_all_none(self):
        p = cost._normalize([])
        self.assertIsNone(p["median_household_income"])


class AcsScopeTest(unittest.TestCase):
    F = {"state_fips": "53", "county_fips": "53053", "place_fips": "70000", "tract": "061601"}

    def test_city_uses_place(self):
        self.assertEqual(cost._acs_scope("city", self.F), ("place:70000", "state:53", "place"))

    def test_neighborhood_uses_tract(self):
        self.assertEqual(cost._acs_scope("neighborhood", self.F),
                         ("tract:061601", "state:53 county:053", "tract"))

    def test_falls_back_to_county_when_no_place(self):
        f = {"state_fips": "53", "county_fips": "53053", "place_fips": None, "tract": None}
        self.assertEqual(cost._acs_scope("city", f), ("county:053", "state:53", "county"))


class FetchGrainTest(unittest.TestCase):
    """The envelope's place_grain must reflect the geography actually achieved, so a
    coarser fallback is honest rather than over-claimed (network stubbed)."""

    NOW = datetime(2026, 5, 26)
    F_FULL = {"state_fips": "53", "county_fips": "53053", "place_fips": "70000", "tract": "061601"}
    F_NO_TRACT = {"state_fips": "53", "county_fips": "53053", "place_fips": "70000", "tract": None}

    def _run(self, fips, level):
        orig = (cost.ab.load_secrets, cost.geo.census_geographies, cost.ab.http_json)
        cost.ab.load_secrets = lambda *a, **k: {"CENSUS_API_KEY": "x"}
        cost.geo.census_geographies = lambda *a, **k: fips
        cost.ab.http_json = lambda *a, **k: [["NAME"], ["x"]]
        try:
            with tempfile.TemporaryDirectory() as d:
                return cost.fetch(f"{level}::x::47.25,-122.44", "47.25,-122.44", level, d, now=self.NOW)
        finally:
            cost.ab.load_secrets, cost.geo.census_geographies, cost.ab.http_json = orig

    def test_neighborhood_resolving_to_tract_is_stamped_tract(self):
        self.assertEqual(self._run(self.F_FULL, "neighborhood")["place_grain"], "tract")

    def test_neighborhood_without_tract_stamps_the_coarser_grain_reached(self):
        rec = self._run(self.F_NO_TRACT, "neighborhood")
        self.assertEqual(rec["place_grain"], "place")          # fell back from tract
        self.assertNotEqual(rec["place_grain"], "neighborhood")  # never over-claims the request


if __name__ == "__main__":
    unittest.main()
