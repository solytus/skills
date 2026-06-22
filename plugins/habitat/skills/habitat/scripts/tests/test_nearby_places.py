"""TDD tests for nearby_places (haversine + radius/population filtering over the bundled
gazetteer). Pure; no network. Run: python3 scripts/tests/test_nearby_places.py -v"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import lookups

# Synthetic anchor + places (no real geography). Distances from ANCHOR (approx mi):
# Nearborough ~14, Midvale ~39, Westport ~43, Hamlet ~39, Newtown ~39, Farburg ~297.
ANCHOR = (40.0000, -100.0000)
PLACES = [
    {"usps": "ST", "name": "Nearborough city", "lat": "40.2030", "lon": "-100.0000", "population": "230504"},
    {"usps": "ST", "name": "Midvale city", "lat": "40.5650", "lon": "-100.0000", "population": "27131"},
    {"usps": "ST", "name": "Westport city", "lat": "40.6230", "lon": "-100.0000", "population": "126090"},
    {"usps": "ST", "name": "Hamlet CDP", "lat": "39.4350", "lon": "-100.0000", "population": "800"},
    {"usps": "ST", "name": "Newtown CDP", "lat": "40.0000", "lon": "-100.7370", "population": ""},
    {"usps": "ST", "name": "Farburg city", "lat": "44.3000", "lon": "-100.0000", "population": "50000"},
]


def _names(rows):
    return [r["name"] for r in rows]


class NearbyPlaces(unittest.TestCase):
    def test_radius_filters_and_sorts_nearest_first(self):
        rows = lookups._nearby_places(PLACES, *ANCHOR, radius_mi=60)
        self.assertEqual(rows[0]["name"], "Nearborough")      # nearest, suffix stripped
        self.assertNotIn("Farburg", _names(rows))             # ~297 mi -> excluded
        self.assertEqual(rows, sorted(rows, key=lambda r: r["distance_mi"]))

    def test_population_band_filters_known_pops_keeps_unknown(self):
        rows = lookups._nearby_places(PLACES, *ANCHOR, radius_mi=60, min_pop=10000, max_pop=150000)
        names = _names(rows)
        self.assertIn("Midvale", names)        # 27k -> in band
        self.assertIn("Westport", names)       # 126k -> in band
        self.assertNotIn("Nearborough", names) # 230k -> over max
        self.assertNotIn("Hamlet", names)      # 800 -> under min
        self.assertIn("Newtown", names)        # null pop -> never dropped for missing data

    def test_exclude_within_drops_the_anchor_neighborhood(self):
        rows = lookups._nearby_places(PLACES, *ANCHOR, radius_mi=60, exclude_within_mi=20)
        self.assertNotIn("Nearborough", _names(rows))   # ~14 mi -> excluded
        self.assertIn("Midvale", _names(rows))          # ~39 mi -> kept

    def test_limit_caps_results(self):
        rows = lookups._nearby_places(PLACES, *ANCHOR, radius_mi=60, limit=1)
        self.assertEqual(_names(rows), ["Nearborough"])

    def test_no_match_returns_empty(self):
        self.assertEqual(lookups._nearby_places(PLACES, *ANCHOR, radius_mi=2), [])

    def test_rows_carry_normalized_name_and_geocode(self):
        rows = lookups._nearby_places(PLACES, *ANCHOR, radius_mi=60, limit=1)
        self.assertEqual(rows[0]["normalized_name"], "nearborough-st")
        self.assertEqual(rows[0]["state"], "ST")
        self.assertEqual(rows[0]["geocode"], "40.2030,-100.0000")


if __name__ == "__main__":
    unittest.main()
