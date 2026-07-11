"""TDD tests for Phase-4 schedule helpers: config predicates + severe/normal defaulting."""
import sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import schedule as sched

def _item(**kw):
    base = dict(key="x", label="X", service_slug="x", clock="chassis", mileage_interval=10000,
                time_interval_months=12, safety_critical=False, baseline_tier=None, is_fluid=False,
                provenance="p", estimate=True, tier="inference", source="set-by-us")
    base.update(kw); return sched.ScheduleItem(**base)

class TestConfigPredicate(unittest.TestCase):
    def test_excluded_when_predicate_unmet(self):
        item = _item(include_if=(("drivetrain", ("4WD", "AWD")),))
        self.assertFalse(sched.applies_to_vehicle(item, {"drivetrain": "2WD"}))
    def test_included_when_predicate_met(self):
        item = _item(include_if=(("drivetrain", ("4WD", "AWD")),))
        self.assertTrue(sched.applies_to_vehicle(item, {"drivetrain": "4WD"}))
    def test_no_predicate_always_applies(self):
        self.assertTrue(sched.applies_to_vehicle(_item(), {"drivetrain": "2WD"}))

class TestSevereDefault(unittest.TestCase):
    def test_unknown_usage_picks_severe(self):
        item = _item(mileage_interval=10000, severe_mileage_interval=5000)
        self.assertEqual(sched.effective_intervals(item, None)[0], 5000)
    def test_normal_usage_picks_normal(self):
        item = _item(mileage_interval=10000, severe_mileage_interval=5000)
        self.assertEqual(sched.effective_intervals(item, "normal")[0], 10000)
    def test_no_severe_set_uses_normal(self):
        self.assertEqual(sched.effective_intervals(_item(mileage_interval=10000), None)[0], 10000)

if __name__ == "__main__":
    unittest.main()
