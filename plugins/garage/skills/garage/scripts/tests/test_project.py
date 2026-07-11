"""TDD tests for project.py — the vehicle-scoped projection core.

Carries forward Tacoma's event-sourced reduce (corrections/supersedes,
build-sheet, verified-spec) and adds: a vehicle_id line, multi-clock `readings:`
replacing the fixed chassis_miles/engine_miles fields, and read-side clock
validation.

Run: python3 scripts/tests/test_project.py -v
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import project
import clocks as ck

TRUCK_CLOCKS = [
    {"name": "chassis", "kind": "odometer", "unit": "mi", "primary": True},
    {"name": "engine", "kind": "derived", "unit": "mi", "base": "chassis", "offset": 210870},
]
BY_NAME = ck.clocks_by_name(ck.load_clocks({"clocks": TRUCK_CLOCKS}))


class TestParseReadings(unittest.TestCase):
    def test_single_pair(self):
        self.assertEqual(project.parse_readings("chassis=260233"), {"chassis": 260233})

    def test_multiple_pairs(self):
        self.assertEqual(project.parse_readings("chassis=260233, engine=20000"),
                         {"chassis": 260233, "engine": 20000})

    def test_strips_commas_in_numbers(self):
        self.assertEqual(project.parse_readings("chassis=260,233"), {"chassis": 260233})

    def test_empty_or_none(self):
        self.assertEqual(project.parse_readings(""), {})
        self.assertEqual(project.parse_readings(None), {})

    def test_ignores_non_numeric(self):
        self.assertEqual(project.parse_readings("chassis=abc, engine=20000"), {"engine": 20000})


class TestParseEvent(unittest.TestCase):
    EVENT = (
        "seq: 8\n"
        "vehicle_id: 1995-toyota-tacoma\n"
        "type: maintenance\n"
        "date: 2026-05-03\n"
        "readings: chassis=260233\n"
        "service: oil-change\n"
        "parts: Toyota 90915-YZZD1\n"
        "summary: Oil + filter\n"
    )

    def test_extracts_vehicle_id(self):
        self.assertEqual(project.parse_event(self.EVENT)["vehicle_id"], "1995-toyota-tacoma")

    def test_extracts_readings_dict(self):
        self.assertEqual(project.parse_event(self.EVENT)["readings"], {"chassis": 260233})

    def test_seq_is_int(self):
        self.assertEqual(project.parse_event(self.EVENT)["seq"], 8)


class TestReduce(unittest.TestCase):
    def _ev(self, **kw):
        return kw

    def test_service_history_record_carries_readings(self):
        events = [self._ev(seq=1, vehicle_id="t", type="maintenance", date="2026-05-03",
                           readings={"chassis": 260233}, service="oil-change", summary="oil")]
        proj = project.reduce_events(events)
        rec = proj["service_history"][0]
        self.assertEqual(rec["readings"], {"chassis": 260233})
        self.assertEqual(rec["service"], "oil-change")

    def test_correction_voids_prior_seq(self):
        events = [
            self._ev(seq=1, type="maintenance", date="2026-01-01", readings={"chassis": 100},
                     service="oil-change", summary="wrong"),
            self._ev(seq=2, type="correction", supersedes=1),
            self._ev(seq=3, type="maintenance", date="2026-01-02", readings={"chassis": 101},
                     service="oil-change", summary="right"),
        ]
        proj = project.reduce_events(events)
        summaries = [r["summary"] for r in proj["service_history"]]
        self.assertEqual(summaries, ["right"])

    def test_build_sheet_lists_and_vehicle_summary(self):
        events = [
            self._ev(seq=1, type="build-sheet", field="vehicle", value="1995 Tacoma 4x4"),
            self._ev(seq=2, type="build-sheet", field="mods", value="+JBA UCAs"),
        ]
        proj = project.reduce_events(events)
        self.assertEqual(proj["vehicle"]["summary"], "1995 Tacoma 4x4")
        self.assertIn("JBA UCAs", proj["mods"])

    def test_verified_spec_latest_wins(self):
        events = [
            self._ev(seq=1, type="verified-spec", key="lug_torque", value="76 ft-lb"),
            self._ev(seq=2, type="verified-spec", key="lug_torque", value="83 ft-lb"),
        ]
        proj = project.reduce_events(events)
        self.assertEqual(proj["verified_specs"]["lug_torque"]["value"], "83 ft-lb")

    def test_max_seq(self):
        events = [self._ev(seq=5, type="build-sheet", field="mods", value="+x")]
        self.assertEqual(project.reduce_events(events)["max_seq"], 5)


class TestValidateEvents(unittest.TestCase):
    def test_duplicate_seq_flagged(self):
        events = [{"seq": 1, "type": "maintenance"}, {"seq": 1, "type": "maintenance"}]
        self.assertTrue(any("Duplicate" in p for p in project.validate_events(events)))

    def test_vehicle_id_mismatch_flagged(self):
        events = [{"seq": 1, "type": "maintenance", "vehicle_id": "civic"}]
        problems = project.validate_events(events, expected_vehicle_id="tacoma")
        self.assertTrue(any("vehicle_id" in p for p in problems))

    def test_vehicle_id_match_clean(self):
        events = [{"seq": 1, "type": "maintenance", "vehicle_id": "tacoma",
                   "readings": {"chassis": 100}, "service": "oil", "date": "2026-01-01"}]
        self.assertEqual(project.validate_events(events, expected_vehicle_id="tacoma", by_name=BY_NAME), [])

    def test_reading_for_derived_clock_rejected(self):
        # engine is derived — it must never be logged directly.
        events = [{"seq": 1, "type": "maintenance", "readings": {"engine": 20000}}]
        problems = project.validate_events(events, by_name=BY_NAME)
        self.assertTrue(any("engine" in p for p in problems))

    def test_reading_for_undeclared_clock_rejected(self):
        events = [{"seq": 1, "type": "maintenance", "readings": {"ghost": 5}}]
        problems = project.validate_events(events, by_name=BY_NAME)
        self.assertTrue(any("ghost" in p for p in problems))


class TestMonotonic(unittest.TestCase):
    def test_backwards_base_reading_warned(self):
        events = [
            {"seq": 1, "type": "maintenance", "date": "2026-01-01", "readings": {"chassis": 260000}},
            {"seq": 2, "type": "maintenance", "date": "2026-02-01", "readings": {"chassis": 26000}},
        ]
        warnings = project.check_monotonic(events, "chassis")
        self.assertTrue(warnings)

    def test_forward_readings_clean(self):
        events = [
            {"seq": 1, "type": "maintenance", "date": "2026-01-01", "readings": {"chassis": 260000}},
            {"seq": 2, "type": "maintenance", "date": "2026-02-01", "readings": {"chassis": 260870}},
        ]
        self.assertEqual(project.check_monotonic(events, "chassis"), [])


class TestNextSeq(unittest.TestCase):
    def test_next_seq(self):
        self.assertEqual(project.next_seq([{"seq": 3}, {"seq": 7}]), 8)

    def test_next_seq_empty(self):
        self.assertEqual(project.next_seq([]), 1)


if __name__ == "__main__":
    unittest.main()
