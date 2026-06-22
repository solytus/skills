"""TDD tests for the EPA National Walkability Index lookup + shared ArcGIS/geocode
helpers. Run: python3 scripts/tests/test_walkability.py -v"""
import sys
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))
import adapter_base as ab
import lookups

# Captured live 2026-05-27 (Capitol Hill, Seattle).
NWI_RESPONSE = {"features": [{"attributes": {"NatWalkInd": 17.5, "GEOID10": "530330075001"}}]}
EMPTY_ARCGIS = {"features": []}


class ParseGeocodeTest(unittest.TestCase):
    def test_parses_lat_lon(self):
        self.assertEqual(ab.parse_geocode("47.2529,-122.4443"), (47.2529, -122.4443))

    def test_tolerates_spaces(self):
        self.assertEqual(ab.parse_geocode(" 47.25 , -122.44 "), (47.25, -122.44))


class ArcgisFirstAttrsTest(unittest.TestCase):
    def test_returns_first_feature_attributes(self):
        self.assertEqual(ab.arcgis_first_attrs(NWI_RESPONSE),
                         {"NatWalkInd": 17.5, "GEOID10": "530330075001"})

    def test_empty_features_returns_empty_dict(self):
        self.assertEqual(ab.arcgis_first_attrs(EMPTY_ARCGIS), {})

    def test_none_returns_empty_dict(self):
        self.assertEqual(ab.arcgis_first_attrs(None), {})


class WalkabilityNormalizeTest(unittest.TestCase):
    def test_maps_index_and_geoid(self):
        p = lookups._normalize_nwi(NWI_RESPONSE)
        self.assertEqual(p["nat_walk_index"], 17.5)
        self.assertEqual(p["block_group_geoid"], "530330075001")
        self.assertEqual(p["category"], "most walkable")

    def test_category_boundaries(self):
        self.assertEqual(lookups._walk_category(3.0), "least walkable")
        self.assertEqual(lookups._walk_category(5.75), "least walkable")
        self.assertEqual(lookups._walk_category(10.5), "below average")
        self.assertEqual(lookups._walk_category(15.25), "above average")
        self.assertEqual(lookups._walk_category(17.5), "most walkable")

    def test_missing_index_is_none(self):
        p = lookups._normalize_nwi(EMPTY_ARCGIS)
        self.assertIsNone(p["nat_walk_index"])
        self.assertIsNone(p["category"])


if __name__ == "__main__":
    unittest.main()
