"""TDD tests for the airport lookup (haversine + nearest-airport selection over the
bundled OurAirports CSV). Run: python3 scripts/tests/test_airport.py -v"""
import sys
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))
import geo
import lookups

AIRPORTS = [
    {"iata": "TIW", "name": "Tacoma Narrows", "type": "medium_airport", "lat": 47.268, "lon": -122.578},
    {"iata": "SEA", "name": "Seattle-Tacoma Intl", "type": "large_airport", "lat": 47.449, "lon": -122.309},
    {"iata": "PDX", "name": "Portland Intl", "type": "large_airport", "lat": 45.589, "lon": -122.597},
]


class HaversineTest(unittest.TestCase):
    def test_zero_distance(self):
        self.assertEqual(geo.haversine_mi(47.0, -122.0, 47.0, -122.0), 0.0)

    def test_one_degree_latitude_is_about_69_miles(self):
        self.assertAlmostEqual(geo.haversine_mi(47.0, -122.0, 48.0, -122.0), 69.0, delta=0.6)


class NearestAirportTest(unittest.TestCase):
    TACOMA = (47.2529, -122.4443)

    def test_nearest_commercial_is_closest_any_type(self):
        ap, _ = lookups._nearest_airport(AIRPORTS, *self.TACOMA)
        self.assertEqual(ap["iata"], "TIW")  # medium, but closest

    def test_nearest_hub_filters_to_large(self):
        ap, _ = lookups._nearest_airport(AIRPORTS, *self.TACOMA, types=("large_airport",))
        self.assertEqual(ap["iata"], "SEA")

    def test_empty_list_returns_none(self):
        ap, dist = lookups._nearest_airport([], *self.TACOMA)
        self.assertIsNone(ap)
        self.assertIsNone(dist)


if __name__ == "__main__":
    unittest.main()
