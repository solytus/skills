"""TDD tests for the family-distance lookup (location parse, gazetteer centroid match,
distance/estimate math). Run: python3 scripts/tests/test_family.py -v"""
import os
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))
import lookups

CENTROID_CSV = ("usps,name,lat,lon\n"
                "CO,Aurora city,39.709537,-104.720509\n"
                "WA,Tacoma city,47.2521,-122.4416\n")

PLACES = [
    {"usps": "WA", "name": "Seattle city", "lat": "47.6205", "lon": "-122.3509"},
    {"usps": "WA", "name": "Tacoma city", "lat": "47.2522", "lon": "-122.4598"},
    {"usps": "OR", "name": "Portland city", "lat": "45.5370", "lon": "-122.6500"},
]


class ParseLocationTest(unittest.TestCase):
    def test_city_state(self):
        self.assertEqual(lookups._parse_location("Seattle, WA"), ("Seattle", "WA"))

    def test_no_state(self):
        self.assertEqual(lookups._parse_location("Seattle"), ("Seattle", None))


class PlaceCentroidTest(unittest.TestCase):
    def test_matches_stripping_city_suffix(self):
        self.assertEqual(lookups._place_centroid("Seattle", "WA", PLACES), (47.6205, -122.3509))

    def test_state_scoped(self):
        self.assertEqual(lookups._place_centroid("Portland", "OR", PLACES), (45.5370, -122.6500))

    def test_no_match_returns_none(self):
        self.assertIsNone(lookups._place_centroid("Nowhere", "WA", PLACES))


class DistanceEntryTest(unittest.TestCase):
    TACOMA = (47.2529, -122.4443)

    def test_nearby_has_drive_no_flight(self):
        e = lookups._distance_entry("Seattle, WA", *self.TACOMA, (47.6205, -122.3509))
        self.assertAlmostEqual(e["distance_mi"], 25.5, delta=4)
        self.assertIsNotNone(e["est_drive_hr"])
        self.assertIsNone(e["est_flight_hr"])   # < 300 mi -> drive only

    def test_far_has_flight(self):
        e = lookups._distance_entry("New York, NY", *self.TACOMA, (40.71, -74.0))
        self.assertGreater(e["distance_mi"], 2000)
        self.assertIsNotNone(e["est_flight_hr"])

    def test_unresolved_is_none(self):
        e = lookups._distance_entry("Mystery", *self.TACOMA, None)
        self.assertIsNone(e["distance_mi"])
        self.assertIsNone(e["est_drive_hr"])


class ResolvePlaceCentroidTest(unittest.TestCase):
    """Canonical city identity: 'Aurora, CO' -> stable slug + centroid geocode, so the
    same city always resolves to one place_key (no coordinate-fork) and shares its cache."""

    def _csv(self):
        f = tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False, newline="")
        f.write(CENTROID_CSV)
        f.close()
        return f.name

    def test_returns_canonical_slug_and_truncated_geocode(self):
        path = self._csv()
        try:
            r = lookups.resolve_place_centroid("Aurora, CO", path=path)
        finally:
            os.unlink(path)
        self.assertEqual(r["name"], "Aurora")
        self.assertEqual(r["state"], "CO")
        self.assertEqual(r["normalized_name"], "aurora-co")
        self.assertEqual(r["geocode"], "39.7095,-104.7205")  # truncated to 4 decimals

    def test_no_state_returns_empty(self):
        self.assertEqual(lookups.resolve_place_centroid("Aurora"), {})

    def test_unmatched_returns_empty(self):
        path = self._csv()
        try:
            self.assertEqual(lookups.resolve_place_centroid("Nowhere, ZZ", path=path), {})
        finally:
            os.unlink(path)


if __name__ == "__main__":
    unittest.main()
