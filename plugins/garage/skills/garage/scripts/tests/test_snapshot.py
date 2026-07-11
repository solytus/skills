"""TDD tests for snapshot.py — render a vehicle's projection to current-state text.

The service-history / last-done / verified-specs formatting is held identical to
the single-vehicle original so the migration reproduces the existing projection.

Run: python3 scripts/tests/test_snapshot.py -v
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import snapshot
import clocks as ck

CLOCKS = ck.load_clocks({"clocks": [
    {"name": "chassis", "kind": "odometer", "unit": "mi", "primary": True}]})

PROJ = {
    "vehicle": {"summary": "1995 Toyota Tacoma 4x4"},
    "mods": ["JBA UCAs"], "known_issues": ["weeping rear main"], "backlog": [],
    "service_history": [
        {"seq": 8, "service": "oil-change", "date": "2026-05-03",
         "readings": {"chassis": 260233}, "parts": "90915-YZZD1", "fluids": "Mobil 1",
         "cost": None, "summary": "Oil + filter"},
        {"seq": 9, "service": "inspection", "date": "2026-05-10",
         "readings": {}, "parts": None, "fluids": None, "cost": None, "summary": "looked ok"},
    ],
    "last_done": {"oil-change": {"seq": 8, "service": "oil-change", "date": "2026-05-03",
                                 "readings": {"chassis": 260233}, "summary": "Oil + filter"}},
    "verified_specs": {"lug_torque": {"value": "83 ft-lb", "applies_to": "4WD",
                                      "source_doc": "FSM p.SA-1", "seq": 5, "confirmed": True}},
    "max_seq": 9,
}


class TestRender(unittest.TestCase):
    def setUp(self):
        self.out = snapshot.render_full(PROJ, vehicle={"display": "1995 Toyota Tacoma"}, clocks=CLOCKS)

    def test_header_has_max_seq(self):
        self.assertIn("(seq 9)", self.out.splitlines()[0])

    def test_service_history_formats_base_miles(self):
        self.assertIn("260,233 mi", self.out)

    def test_record_without_reading_shows_dash(self):
        self.assertIn("— mi", self.out)

    def test_mods_and_known_issues_render(self):
        self.assertIn("JBA UCAs", self.out)
        self.assertIn("weeping rear main", self.out)

    def test_verified_spec_renders_with_source(self):
        self.assertIn("lug_torque: 83 ft-lb", self.out)
        self.assertIn("FSM p.SA-1", self.out)

    def test_ends_with_max_seq_marker(self):
        self.assertTrue(self.out.rstrip().endswith("max_seq: 9"))


if __name__ == "__main__":
    unittest.main()
