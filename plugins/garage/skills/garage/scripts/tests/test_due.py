"""TDD tests for due.py — deterministic 'what's due', generalized to named clocks.

The headline correctness case: a service item on a DERIVED clock (a swapped
engine) reads against that clock, never the chassis odometer — and a record made
before the clock existed (pre-swap) must not satisfy it. Verified here for the
truck's engine clock and for a second, independent rebuilt-component clock.

Run: python3 scripts/tests/test_due.py -v
"""
import sys
import unittest
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import due
import schedule as sched
import clocks as ck

CLOCKS = ck.load_clocks({"clocks": [
    {"name": "chassis", "kind": "odometer", "unit": "mi", "primary": True},
    {"name": "engine", "kind": "derived", "unit": "mi", "base": "chassis", "offset": 210870},
]})
BY_NAME = ck.clocks_by_name(CLOCKS)
NOW = date(2026, 6, 16)
READINGS = {"chassis": 260870}


def _item(**kw):
    base = dict(key="oil", label="Engine oil", service_slug="oil-change", clock="chassis",
                mileage_interval=5000, time_interval_months=6, safety_critical=False,
                baseline_tier=None, is_fluid=True, provenance="KB", estimate=False,
                tier="official", source="FSM", aliases=())
    base.update(kw)
    return sched.ScheduleItem(**base)


class TestHelpers(unittest.TestCase):
    def test_months_between(self):
        self.assertEqual(round(due._months_between("2026-01-01", date(2026, 7, 1)), 1), 5.9)

    def test_classify_mileage(self):
        self.assertEqual(due._classify_mileage(1000, 5000), "OK")
        self.assertEqual(due._classify_mileage(500, 5000), "DUE SOON")
        self.assertEqual(due._classify_mileage(-1, 5000), "OVERDUE")

    def test_classify_time(self):
        self.assertEqual(due._classify_time(3.0), "OK")
        self.assertEqual(due._classify_time(2.0), "DUE SOON")
        self.assertEqual(due._classify_time(-0.1), "OVERDUE")


class TestChassisItems(unittest.TestCase):
    def test_chassis_item_ok(self):
        last = {"oil-change": {"readings": {"chassis": 260233}, "date": "2026-05-03"}}
        r = due.compute_due_item(_item(), last, READINGS, BY_NAME, NOW)
        self.assertEqual(r.status, "OK")
        self.assertEqual(r.miles_remaining, 5000 - (260870 - 260233))

    def test_time_governed_overdue(self):
        item = _item(key="brake_fluid", service_slug="brake-fluid", mileage_interval=None,
                     time_interval_months=24, safety_critical=True, baseline_tier="safety")
        last = {"brake-fluid": {"readings": {"chassis": 200000}, "date": "2022-06-16"}}
        r = due.compute_due_item(item, last, READINGS, BY_NAME, NOW)
        self.assertEqual(r.status, "OVERDUE")
        self.assertEqual(r.governing, "time")

    def test_unknown_when_no_record(self):
        item = _item(key="coolant", service_slug="coolant", safety_critical=True, baseline_tier="fluid")
        r = due.compute_due_item(item, {}, READINGS, BY_NAME, NOW)
        self.assertEqual(r.status, "UNKNOWN")
        self.assertIn("baseline", r.note.lower())

    def test_time_only_computes_without_odometer(self):
        item = _item(key="brake_fluid", service_slug="brake-fluid", mileage_interval=None,
                     time_interval_months=24, safety_critical=True, baseline_tier="safety")
        last = {"brake-fluid": {"readings": {}, "date": "2024-06-16"}}
        r = due.compute_due_item(item, last, READINGS, BY_NAME, NOW)
        self.assertNotEqual(r.status, "UNKNOWN")
        self.assertEqual(r.governing, "time")


class TestDerivedClock(unittest.TestCase):
    def _belt(self):
        return _item(key="timing_belt", label="Timing belt", service_slug="timing-belt",
                     clock="engine", mileage_interval=60000, time_interval_months=72,
                     safety_critical=True, baseline_tier="safety", is_fluid=False,
                     estimate=True, tier="inference", source="set-by-us")

    def test_excludes_pre_clock_baseline(self):
        # The only record is pre-swap (chassis 62015 < offset 210870): NOT a false OVERDUE.
        last = {"timing-belt": {"readings": {"chassis": 62015}, "date": "2003-01-10"}}
        r = due.compute_due_item(self._belt(), last, READINGS, BY_NAME, NOW)
        self.assertEqual(r.status, "UNKNOWN")
        self.assertIn("engine", r.note.lower())
        self.assertIn("est", r.note.lower())

    def test_uses_post_clock_baseline_on_engine_clock(self):
        # Belt done post-swap at chassis 230870 (= engine 20k); 60k interval -> 30k left.
        last = {"timing-belt": {"readings": {"chassis": 230870}, "date": "2025-01-01"}}
        r = due.compute_due_item(self._belt(), last, READINGS, BY_NAME, NOW)
        # delta = current_engine(50000) - record_engine(20000) = 30000; remaining = 30000
        self.assertEqual(r.miles_remaining, 30000)
        self.assertIn(r.status, ("OK", "DUE SOON"))

    def test_derived_clock_offset_cancels_to_chassis_delta(self):
        # Sanity: the engine-clock remaining equals the same math on chassis miles.
        last = {"timing-belt": {"readings": {"chassis": 220870}, "date": "2025-01-01"}}
        r = due.compute_due_item(self._belt(), last, READINGS, BY_NAME, NOW)
        self.assertEqual(r.miles_remaining, 60000 - (260870 - 220870))


class TestSecondDerivedClock(unittest.TestCase):
    """A rebuilt transmission is a second, independent derived clock."""
    def setUp(self):
        self.clocks = ck.load_clocks({"clocks": [
            {"name": "chassis", "kind": "odometer", "unit": "mi", "primary": True},
            {"name": "trans", "kind": "derived", "unit": "mi", "base": "chassis", "offset": 250000},
        ]})
        self.by_name = ck.clocks_by_name(self.clocks)

    def test_rebuilt_clock_excludes_pre_rebuild_record(self):
        item = _item(key="atf", service_slug="atf", clock="trans", mileage_interval=30000,
                     time_interval_months=36, is_fluid=True, baseline_tier="fluid")
        # ATF logged at chassis 200000, before the rebuild at 250000 -> must not count.
        last = {"atf": {"readings": {"chassis": 200000}, "date": "2020-01-01"}}
        r = due.compute_due_item(item, last, {"chassis": 260000}, self.by_name, NOW)
        self.assertEqual(r.status, "UNKNOWN")


class TestAliases(unittest.TestCase):
    def test_alias_satisfies_item(self):
        item = _item(key="tire_condition", service_slug="tire-condition", mileage_interval=None,
                     time_interval_months=72, safety_critical=True, baseline_tier="inspect",
                     is_fluid=False, estimate=True, tier="inference", source="set-by-us",
                     aliases=("tires",))
        last = {"tires": {"readings": {"chassis": 257905}, "date": "2025-11-29", "seq": 66}}
        r = due.compute_due_item(item, last, READINGS, BY_NAME, NOW)
        self.assertNotEqual(r.status, "UNKNOWN")
        self.assertEqual(r.last["date"], "2025-11-29")


class TestComputeDue(unittest.TestCase):
    def test_sorted_and_carries_estimate(self):
        items = [_item(), _item(key="belt", service_slug="timing-belt", clock="engine",
                                estimate=True, tier="inference", is_fluid=False,
                                time_interval_months=72, safety_critical=True)]
        last = {"oil-change": {"readings": {"chassis": 260233}, "date": "2026-05-03"}}
        rows = due.compute_due(items, last, READINGS, BY_NAME, NOW)
        self.assertEqual(len(rows), 2)
        belt = next(r for r in rows if r.key == "belt")
        self.assertTrue(belt.estimate)


if __name__ == "__main__":
    unittest.main()
