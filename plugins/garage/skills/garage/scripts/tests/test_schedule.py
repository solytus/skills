"""TDD tests for schedule.py — per-vehicle schedule as cited data.

The hard-coded single-vehicle SCHEDULE becomes a loader/validator over a
schedule.json. validate_schedule enforces clock-reference integrity, the
estimate<->inference biconditional, and the structural rules carried forward
from the original. (The locator-bearing-source gate for claimed-OEM items is
layered on in Phase 2 via kb_lint.)

Run: python3 scripts/tests/test_schedule.py -v
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import schedule as sched
import clocks as ck

CLOCKS = ck.load_clocks({"clocks": [
    {"name": "chassis", "kind": "odometer", "unit": "mi", "primary": True},
    {"name": "engine", "kind": "derived", "unit": "mi", "base": "chassis", "offset": 210870},
]})


def _item(**kw):
    base = dict(key="oil", label="Engine oil", service_slug="oil-change", clock="chassis",
                mileage_interval=5000, time_interval_months=6, safety_critical=False,
                baseline_tier=None, is_fluid=True, provenance="KB", estimate=False,
                tier="official", source="1996 FSM EG-176", aliases=())
    base.update(kw)
    return sched.ScheduleItem(**base)


class TestLoad(unittest.TestCase):
    def test_load_from_dict(self):
        data = {"schema_version": 1, "vehicle_id": "t", "items": [
            {"key": "oil", "label": "Engine oil", "service_slug": "oil-change", "clock": "chassis",
             "mileage_interval": 5000, "time_interval_months": 6, "safety_critical": False,
             "baseline_tier": None, "is_fluid": True, "provenance": "KB", "estimate": False,
             "tier": "official", "source": "1996 FSM EG-176"}]}
        items = sched.load_schedule(data)
        self.assertEqual(items[0].key, "oil")
        self.assertEqual(items[0].clock, "chassis")
        self.assertEqual(items[0].aliases, ())  # defaults when omitted

    def test_load_parses_aliases(self):
        data = {"schema_version": 1, "vehicle_id": "t", "items": [
            {"key": "tc", "label": "Tires", "service_slug": "tire-condition", "clock": "chassis",
             "mileage_interval": None, "time_interval_months": 72, "safety_critical": True,
             "baseline_tier": "inspect", "is_fluid": False, "provenance": "x", "estimate": True,
             "tier": "inference", "source": "set-by-us", "aliases": ["tires"]}]}
        self.assertEqual(sched.load_schedule(data)[0].aliases, ("tires",))


class TestValidateAccepts(unittest.TestCase):
    def test_accepts_good_items(self):
        sched.validate_schedule([_item(), _item(key="belt", service_slug="timing-belt",
            clock="engine", safety_critical=True, baseline_tier="safety", is_fluid=False,
            estimate=True, tier="inference", source="set-by-us")], CLOCKS)


class TestValidateRejects(unittest.TestCase):
    def _v(self, items):
        sched.validate_schedule(items, CLOCKS)

    def test_rejects_duplicate_key(self):
        with self.assertRaises(ValueError):
            self._v([_item(), _item(service_slug="other")])

    def test_rejects_duplicate_slug(self):
        with self.assertRaises(ValueError):
            self._v([_item(), _item(key="oil2")])

    def test_rejects_unknown_clock(self):
        with self.assertRaises(ValueError):
            self._v([_item(clock="ghost")])

    def test_rejects_no_interval(self):
        with self.assertRaises(ValueError):
            self._v([_item(mileage_interval=None, time_interval_months=None)])

    def test_rejects_fluid_without_time_interval(self):
        with self.assertRaises(ValueError):
            self._v([_item(is_fluid=True, time_interval_months=None)])

    def test_rejects_bad_baseline_tier(self):
        with self.assertRaises(ValueError):
            self._v([_item(baseline_tier="bogus")])

    def test_rejects_bad_tier(self):
        with self.assertRaises(ValueError):
            self._v([_item(tier="rumor")])

    def test_rejects_estimate_true_with_noninference_tier(self):
        with self.assertRaises(ValueError):
            self._v([_item(estimate=True, tier="official")])

    def test_rejects_estimate_false_with_inference_tier(self):
        with self.assertRaises(ValueError):
            self._v([_item(estimate=False, tier="inference")])


if __name__ == "__main__":
    unittest.main()
