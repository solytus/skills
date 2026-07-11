"""TDD tests for clocks.py — the multi-clock model.

v1 scope: one monotonic odometer base clock + zero-or-more single-segment
derived mileage clocks (derived = base - offset). validate_clocks REJECTS any
config it cannot model (hours clocks, chained/piecewise derived, unknown base,
>1 base) rather than silently miscomputing.

Run: python3 scripts/tests/test_clocks.py -v
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import clocks as ck


TRUCK_CLOCKS = [
    {"name": "chassis", "kind": "odometer", "unit": "mi", "label": "Chassis odometer", "primary": True},
    {"name": "engine", "kind": "derived", "unit": "mi", "base": "chassis", "offset": 210870,
     "label": "Swapped JDM 5VZ-FE engine miles"},
]


class TestLoad(unittest.TestCase):
    def test_load_parses_clocks(self):
        clocks = ck.load_clocks({"clocks": TRUCK_CLOCKS})
        self.assertEqual([c.name for c in clocks], ["chassis", "engine"])
        eng = ck.clocks_by_name(clocks)["engine"]
        self.assertEqual(eng.kind, "derived")
        self.assertEqual(eng.base, "chassis")
        self.assertEqual(eng.offset, 210870)

    def test_missing_clocks_defaults_to_single_chassis_odometer(self):
        # A vehicle with no declared clocks gets one primary chassis odometer.
        clocks = ck.load_clocks({})
        self.assertEqual(len(clocks), 1)
        self.assertEqual(clocks[0].name, "chassis")
        self.assertEqual(clocks[0].kind, "odometer")
        self.assertTrue(clocks[0].primary)


class TestReadingResolution(unittest.TestCase):
    def setUp(self):
        self.by_name = ck.clocks_by_name(ck.load_clocks({"clocks": TRUCK_CLOCKS}))

    def test_base_current_reading_is_the_logged_value(self):
        r = ck.current_reading(self.by_name["chassis"], {"chassis": 260870}, self.by_name)
        self.assertEqual(r, 260870)

    def test_derived_current_reading_is_base_minus_offset(self):
        r = ck.current_reading(self.by_name["engine"], {"chassis": 260870}, self.by_name)
        self.assertEqual(r, 50000)  # 260870 - 210870

    def test_base_reading_unknown_when_absent(self):
        self.assertIsNone(ck.current_reading(self.by_name["chassis"], {}, self.by_name))

    def test_derived_reading_unknown_when_base_absent(self):
        self.assertIsNone(ck.current_reading(self.by_name["engine"], {}, self.by_name))

    def test_record_reading_matches_record_dict(self):
        self.assertEqual(ck.record_reading(self.by_name["engine"], {"chassis": 230870}, self.by_name), 20000)


class TestPreClock(unittest.TestCase):
    def setUp(self):
        self.by_name = ck.clocks_by_name(ck.load_clocks({"clocks": TRUCK_CLOCKS}))

    def test_record_before_offset_is_pre_clock(self):
        # chassis 62015 < offset 210870 -> the record predates the swapped engine
        self.assertTrue(ck.is_pre_clock(self.by_name["engine"], {"chassis": 62015}, self.by_name))

    def test_record_after_offset_is_not_pre_clock(self):
        self.assertFalse(ck.is_pre_clock(self.by_name["engine"], {"chassis": 230870}, self.by_name))

    def test_base_clock_is_never_pre_clock(self):
        self.assertFalse(ck.is_pre_clock(self.by_name["chassis"], {"chassis": 100}, self.by_name))


class TestValidateClocksAccepts(unittest.TestCase):
    def test_accepts_truck_config(self):
        ck.validate_clocks(ck.load_clocks({"clocks": TRUCK_CLOCKS}))  # must not raise

    def test_accepts_single_odometer(self):
        ck.validate_clocks(ck.load_clocks({"clocks": [
            {"name": "chassis", "kind": "odometer", "unit": "mi", "primary": True}]}))


class TestValidateClocksRejects(unittest.TestCase):
    def _v(self, clocks_list):
        ck.validate_clocks(ck.load_clocks({"clocks": clocks_list}))

    def test_rejects_hours_clock_deferred(self):
        with self.assertRaises(ck.ClockConfigError):
            self._v([{"name": "chassis", "kind": "odometer", "unit": "mi", "primary": True},
                     {"name": "tcase", "kind": "hours", "unit": "hr"}])

    def test_rejects_derived_with_unknown_base(self):
        with self.assertRaises(ck.ClockConfigError):
            self._v([{"name": "chassis", "kind": "odometer", "unit": "mi", "primary": True},
                     {"name": "engine", "kind": "derived", "unit": "mi", "base": "ghost", "offset": 1000}])

    def test_rejects_chained_derived_clock(self):
        # derived-on-derived is piecewise/second-swap territory — not supported in v1.
        with self.assertRaises(ck.ClockConfigError):
            self._v([{"name": "chassis", "kind": "odometer", "unit": "mi", "primary": True},
                     {"name": "engine", "kind": "derived", "unit": "mi", "base": "chassis", "offset": 210870},
                     {"name": "engine2", "kind": "derived", "unit": "mi", "base": "engine", "offset": 10}])

    def test_rejects_two_primary_base_clocks(self):
        with self.assertRaises(ck.ClockConfigError):
            self._v([{"name": "chassis", "kind": "odometer", "unit": "mi", "primary": True},
                     {"name": "chassis2", "kind": "odometer", "unit": "mi", "primary": True}])

    def test_rejects_no_base_clock(self):
        with self.assertRaises(ck.ClockConfigError):
            self._v([{"name": "engine", "kind": "derived", "unit": "mi", "base": "chassis", "offset": 1}])

    def test_rejects_unit_mismatch_between_derived_and_base(self):
        with self.assertRaises(ck.ClockConfigError):
            self._v([{"name": "chassis", "kind": "odometer", "unit": "mi", "primary": True},
                     {"name": "engine", "kind": "derived", "unit": "km", "base": "chassis", "offset": 1}])

    def test_rejects_negative_offset(self):
        with self.assertRaises(ck.ClockConfigError):
            self._v([{"name": "chassis", "kind": "odometer", "unit": "mi", "primary": True},
                     {"name": "engine", "kind": "derived", "unit": "mi", "base": "chassis", "offset": -5}])

    def test_rejects_duplicate_clock_name(self):
        with self.assertRaises(ck.ClockConfigError):
            self._v([{"name": "chassis", "kind": "odometer", "unit": "mi", "primary": True},
                     {"name": "chassis", "kind": "derived", "unit": "mi", "base": "chassis", "offset": 1}])

    def test_rejects_unknown_unit(self):
        with self.assertRaises(ck.ClockConfigError):
            self._v([{"name": "chassis", "kind": "odometer", "unit": "furlongs", "primary": True}])


class TestMonotonic(unittest.TestCase):
    def test_backwards_reading_flagged(self):
        # A later odometer reading lower than an earlier one (fat-finger or rollover).
        self.assertTrue(ck.is_backwards(prev=260233, curr=26033))

    def test_forward_reading_ok(self):
        self.assertFalse(ck.is_backwards(prev=260233, curr=260870))

    def test_equal_reading_ok(self):
        self.assertFalse(ck.is_backwards(prev=260233, curr=260233))


if __name__ == "__main__":
    unittest.main()
