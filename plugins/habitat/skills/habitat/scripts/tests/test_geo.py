"""TDD tests for the shared Census FIPS resolver (geo.py). Run: python3 scripts/tests/test_geo.py -v"""
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))
import adapter_base as ab
import geo

# Census geocoder /geographies/coordinates shape (captured live 2026-05-27, Tacoma).
GEOGRAPHIES = {"result": {"geographies": {
    "States": [{"GEOID": "53", "STATE": "53", "BASENAME": "Washington", "NAME": "Washington"}],
    "Counties": [{"GEOID": "53053", "STATE": "53", "COUNTY": "053", "BASENAME": "Pierce",
                  "NAME": "Pierce County"}],
    "Incorporated Places": [{"GEOID": "5370000", "STATE": "53", "PLACE": "70000",
                             "BASENAME": "Tacoma", "NAME": "Tacoma city"}],
    "Census Tracts": [{"GEOID": "53053061601", "STATE": "53", "COUNTY": "053",
                       "TRACT": "061601", "BASENAME": "616.01"}],
}}}


class NormalizeGeographiesTest(unittest.TestCase):
    def test_extracts_all_fips(self):
        f = geo.normalize_geographies(GEOGRAPHIES)
        self.assertEqual(f["state_fips"], "53")
        self.assertEqual(f["county_fips"], "53053")
        self.assertEqual(f["county_name"], "Pierce")
        self.assertEqual(f["place_fips"], "70000")
        self.assertEqual(f["place_name"], "Tacoma city")
        self.assertEqual(f["tract_geoid"], "53053061601")
        self.assertEqual(f["tract"], "061601")

    def test_missing_place_is_none_but_county_resolves(self):
        partial = {"result": {"geographies": {"Counties": [
            {"GEOID": "53053", "STATE": "53", "COUNTY": "053", "BASENAME": "Pierce"}]}}}
        f = geo.normalize_geographies(partial)
        self.assertEqual(f["county_fips"], "53053")
        self.assertIsNone(f["place_fips"])

    def test_empty_is_none(self):
        f = geo.normalize_geographies({})
        self.assertIsNone(f["state_fips"])
        self.assertIsNone(f["county_fips"])


class CachedResolutionTest(unittest.TestCase):
    NOW = datetime(2026, 5, 28, 12, 0, 0)
    LAT, LON = 47.2529, -122.4443

    def _seed(self, d):
        ab.write_cache(d, geo.GEO_SOURCE, ab.coord_cache_key(self.LAT, self.LON),
                       ab.make_record(ab.coord_cache_key(self.LAT, self.LON), geo.GEO_SOURCE,
                                      geo.normalize_geographies(GEOGRAPHIES), "point",
                                      "2026-05-28T00:00:00", "fresh"))

    def test_cached_coordinate_skips_network(self):
        # Cost resolves the point and caches; Dynamism (same coord+data_root) reuses it.
        with tempfile.TemporaryDirectory() as d:
            self._seed(d)
            boom = lambda *a, **k: (_ for _ in ()).throw(AssertionError("network was hit"))
            orig, ab.http_json = ab.http_json, boom
            try:
                f = geo.census_geographies(self.LAT, self.LON, data_root=d, now=self.NOW)
            finally:
                ab.http_json = orig
            self.assertEqual(f["county_fips"], "53053")

    def test_no_data_root_resolves_live_without_caching(self):
        captured = []
        orig, ab.http_json = ab.http_json, lambda url, **k: (captured.append(url) or GEOGRAPHIES)
        try:
            f = geo.census_geographies(self.LAT, self.LON)
        finally:
            ab.http_json = orig
        self.assertEqual(f["county_fips"], "53053")
        self.assertEqual(len(captured), 1)


if __name__ == "__main__":
    unittest.main()
