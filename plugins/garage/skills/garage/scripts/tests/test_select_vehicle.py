"""TDD tests for select_vehicle.py — infer which vehicle a command means.

Infer from context (slug, nickname, make/model token, the only vehicle, the most
recently touched); prompt to pick only when genuinely ambiguous.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import select_vehicle as sv

VEHICLES = [
    {"slug": "1995-toyota-tacoma", "display": "1995 Toyota Tacoma", "nicknames": ["tacoma", "the truck"], "last_touched": "2026-06-16"},
    {"slug": "2015-honda-civic", "display": "2015 Honda Civic", "nicknames": ["civic"], "last_touched": "2026-05-01"},
]


class TestResolve(unittest.TestCase):
    def test_exact_slug(self):
        self.assertEqual(sv.resolve_vehicle("2015-honda-civic", VEHICLES)["slug"], "2015-honda-civic")

    def test_nickname(self):
        self.assertEqual(sv.resolve_vehicle("the truck", VEHICLES)["slug"], "1995-toyota-tacoma")

    def test_make_model_token(self):
        self.assertEqual(sv.resolve_vehicle("log oil on the civic", VEHICLES)["slug"], "2015-honda-civic")

    def test_single_vehicle_defaults(self):
        self.assertEqual(sv.resolve_vehicle("log an oil change", VEHICLES[:1])["slug"], "1995-toyota-tacoma")

    def test_ambiguous_returns_marker(self):
        self.assertEqual(sv.resolve_vehicle("log an oil change", VEHICLES), "AMBIGUOUS")

    def test_no_vehicles_returns_none(self):
        self.assertIsNone(sv.resolve_vehicle("anything", []))


if __name__ == "__main__":
    unittest.main()
