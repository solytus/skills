"""TDD tests for placekey. Run: python3 scripts/tests/test_placekey.py -v"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import placekey as pk


class TestNormalizeName(unittest.TestCase):
    def test_city_with_state(self):
        self.assertEqual(pk.normalize_name("Tacoma, WA"), "tacoma-wa")

    def test_neighborhood(self):
        self.assertEqual(pk.normalize_name("Capitol Hill, Seattle"), "capitol-hill-seattle")

    def test_punctuation_and_numbers(self):
        self.assertEqual(pk.normalize_name("123 Main St., Tacoma WA"), "123-main-st-tacoma-wa")

    def test_collapses_and_strips(self):
        self.assertEqual(pk.normalize_name("  St.  Louis  "), "st-louis")


class TestTruncGeocode(unittest.TestCase):
    def test_truncates_to_4_decimals(self):
        self.assertEqual(pk.trunc_geocode("47.25291,-122.44432"), "47.2529,-122.4443")

    def test_pads_to_4_decimals(self):
        self.assertEqual(pk.trunc_geocode("47.25,-122.44"), "47.2500,-122.4400")


class TestBuildPlaceKey(unittest.TestCase):
    def test_composes_key(self):
        self.assertEqual(
            pk.build_place_key("city", "tacoma-wa", "47.2529,-122.4443"),
            "city::tacoma-wa::47.2529,-122.4443",
        )

    def test_normalizes_name_and_truncates_geocode(self):
        self.assertEqual(
            pk.build_place_key("city", "Tacoma, WA", "47.25291,-122.44432"),
            "city::tacoma-wa::47.2529,-122.4443",
        )

    def test_country_key_carries_iso_suffix(self):
        # International extension: the ISO-3166 alpha-2 code rides as a name suffix,
        # the country analog of the state suffix, with a representative centroid geocode.
        self.assertEqual(
            pk.build_place_key("country", "Portugal, PT", "39.5,-8.0"),
            "country::portugal-pt::39.5000,-8.0000",
        )

    def test_international_city_key_carries_iso_suffix(self):
        self.assertEqual(
            pk.build_place_key("city", "Lisbon, PT", "38.7223,-9.1393"),
            "city::lisbon-pt::38.7223,-9.1393",
        )


if __name__ == "__main__":
    unittest.main()
