"""Targeted edge-case matrix — the panel's named risks + corruption handling.

Odometer rollover, dual independent derived clocks, a km vehicle, the pre-clock
boundary, correction chains, migration idempotency, and build_vehicle refusing
corrupt stores. Complements the random fuzz with the specific nasty cases.

Run: python3 scripts/tests/test_edge_cases.py -v
"""
import json
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import build_state
import clocks as ck
import due
import migrate_tacoma as mig
import project
import schedule as sched


def _item(clock, mi=8000, mo=6, **kw):
    base = dict(key="oil", label="Oil", service_slug="oil", clock=clock, mileage_interval=mi,
                time_interval_months=mo, safety_critical=False, baseline_tier=None, is_fluid=True,
                provenance="p", estimate=True, tier="inference", source="x")
    base.update(kw)
    return sched.ScheduleItem(**base)


class TestOdometerRollover(unittest.TestCase):
    def test_six_digit_rollover_flagged(self):
        events = [{"type": "maintenance", "seq": 1, "date": "2024-01-01", "readings": {"chassis": 999500}},
                  {"type": "maintenance", "seq": 2, "date": "2024-06-01", "readings": {"chassis": 500}}]
        self.assertTrue(project.check_monotonic(events, "chassis"))

    def test_cluster_swap_backwards_flagged(self):
        self.assertTrue(ck.is_backwards(260000, 12000))


class TestDualDerivedClocks(unittest.TestCase):
    def setUp(self):
        self.clocks = ck.load_clocks({"clocks": [
            {"name": "chassis", "kind": "odometer", "unit": "mi", "primary": True},
            {"name": "engine", "kind": "derived", "unit": "mi", "base": "chassis", "offset": 200000},
            {"name": "trans", "kind": "derived", "unit": "mi", "base": "chassis", "offset": 250000}]})
        self.by = ck.clocks_by_name(self.clocks)

    def test_two_derived_clocks_validate(self):
        ck.validate_clocks(self.clocks)  # engine + trans is a legit config

    def test_independent_readings(self):
        r = {"chassis": 260000}
        self.assertEqual(ck.current_reading(self.by["engine"], r, self.by), 60000)
        self.assertEqual(ck.current_reading(self.by["trans"], r, self.by), 10000)

    def test_pre_clock_is_per_clock(self):
        rec = {"chassis": 240000}  # post-engine (40k) but pre-trans
        self.assertFalse(ck.is_pre_clock(self.by["engine"], rec, self.by))
        self.assertTrue(ck.is_pre_clock(self.by["trans"], rec, self.by))


class TestKmVehicle(unittest.TestCase):
    def test_km_config_validates_and_computes(self):
        clocks = ck.load_clocks({"clocks": [{"name": "chassis", "kind": "odometer", "unit": "km", "primary": True}]})
        ck.validate_clocks(clocks)
        by = ck.clocks_by_name(clocks)
        last = {"oil": {"readings": {"chassis": 100000}, "date": "2026-05-01", "seq": 1}}
        r = due.compute_due_item(_item("chassis"), last, {"chassis": 105000}, by, date(2026, 6, 16))
        self.assertEqual(r.miles_remaining, 8000 - (105000 - 100000))  # unit-agnostic delta


class TestPreClockBoundary(unittest.TestCase):
    def setUp(self):
        self.by = ck.clocks_by_name(ck.load_clocks({"clocks": [
            {"name": "chassis", "kind": "odometer", "unit": "mi", "primary": True},
            {"name": "engine", "kind": "derived", "unit": "mi", "base": "chassis", "offset": 210870}]}))

    def test_record_exactly_at_offset_valid(self):
        self.assertFalse(ck.is_pre_clock(self.by["engine"], {"chassis": 210870}, self.by))
        self.assertEqual(ck.record_reading(self.by["engine"], {"chassis": 210870}, self.by), 0)

    def test_record_one_below_offset_is_pre_clock(self):
        self.assertTrue(ck.is_pre_clock(self.by["engine"], {"chassis": 210869}, self.by))


class TestCorrectionChains(unittest.TestCase):
    def test_correction_of_correction(self):
        events = [
            {"seq": 1, "type": "maintenance", "service": "oil", "date": "2026-01-01", "readings": {"chassis": 100}, "summary": "a"},
            {"seq": 2, "type": "correction", "supersedes": 1},
            {"seq": 3, "type": "correction", "supersedes": 2}]
        proj = project.reduce_events(events)
        self.assertEqual([r["summary"] for r in proj["service_history"]], [])  # seq1 stays voided

    def test_relog_after_void(self):
        events = [
            {"seq": 1, "type": "maintenance", "service": "oil", "date": "2026-01-01", "readings": {"chassis": 100}, "summary": "wrong"},
            {"seq": 2, "type": "correction", "supersedes": 1},
            {"seq": 3, "type": "maintenance", "service": "oil", "date": "2026-01-02", "readings": {"chassis": 101}, "summary": "right"}]
        proj = project.reduce_events(events)
        self.assertEqual([r["summary"] for r in proj["service_history"]], ["right"])


class TestMigrationIdempotent(unittest.TestCase):
    def test_migrate_twice_identical(self):
        src = Path(tempfile.mkdtemp())
        (src / "events").mkdir()
        (src / "events" / "00001-2026-01-01-maintenance-oil").write_text(
            "seq: 1\ntype: maintenance\ndate: 2026-01-01\nchassis_miles: 100\nservice: oil\nhash: abc\n")
        sch = Path(tempfile.mkdtemp()) / "schedule.py"
        sch.write_text("SWAP_CHASSIS_ODO=1\nSCHEDULE=[]\n")
        d1 = Path(tempfile.mkdtemp()) / "v"
        d2 = Path(tempfile.mkdtemp()) / "v"
        mig.migrate(src, sch, d1, force=True)
        mig.migrate(src, sch, d2, force=True)
        for rel in ["events/00001-2026-01-01-maintenance-oil", "vehicle.json", "schedule.json"]:
            self.assertEqual((d1 / rel).read_text(), (d2 / rel).read_text(), f"{rel} not idempotent")


class TestBeltWarningRobustness(unittest.TestCase):
    """The interference belt warning must survive (a) no logged odometer and (b) a belt
    item keyed without the literal 'belt'."""
    def _veh(self, interference, belt_key, belt_slug, reading):
        d = Path(tempfile.mkdtemp()) / "veh"
        (d / "events").mkdir(parents=True)
        (d / "vehicle.json").write_text(json.dumps({
            "schema_version": 1, "vehicle_id": "t", "slug": "t", "display": "T",
            "interference": interference,
            "clocks": [{"name": "chassis", "kind": "odometer", "unit": "mi", "primary": True}]}))
        (d / "schedule.json").write_text(json.dumps({"schema_version": 1, "vehicle_id": "t", "items": [
            {"key": belt_key, "label": "Belt", "service_slug": belt_slug, "clock": "chassis",
             "mileage_interval": 90000, "time_interval_months": 84, "safety_critical": True,
             "baseline_tier": "safety", "is_fluid": False, "provenance": "g", "estimate": True,
             "tier": "inference", "source": "h"}]}))
        if reading:
            (d / "events" / "00001-2026-01-01-maintenance-oil").write_text(
                "seq: 1\nvehicle_id: t\ntype: maintenance\ndate: 2026-01-01\nreadings: chassis=50000\nservice: oil\n")
        return d

    def test_belt_warning_shows_with_no_odometer(self):  # Gap 1
        d = self._veh(interference=None, belt_key="timing_belt", belt_slug="timing-belt", reading=False)
        body = build_state.build_vehicle(d, as_of=date(2026, 7, 1), write=False)["body"]
        self.assertIn("== WHAT'S DUE ==", body)  # due section not dropped when readings empty
        self.assertIn("DESTROY", body)           # interference=None → fail-closed belt warning fires

    def test_belt_warning_keyed_on_service_slug(self):  # Gap 2
        d = self._veh(interference=True, belt_key="tb_100k", belt_slug="timing-belt", reading=True)
        body = build_state.build_vehicle(d, as_of=date(2026, 7, 1), write=False)["body"]
        self.assertIn("DESTROY", body)  # keyed on service_slug, so a non-'belt' key still warns


class TestBuildVehicleCorruption(unittest.TestCase):
    def _vehicle(self, events):
        d = Path(tempfile.mkdtemp()) / "veh"
        (d / "events").mkdir(parents=True)
        (d / "vehicle.json").write_text(json.dumps({
            "schema_version": 1, "vehicle_id": "t", "slug": "t", "display": "T",
            "clocks": [{"name": "chassis", "kind": "odometer", "unit": "mi", "primary": True}]}))
        for fname, body in events:
            (d / "events" / fname).write_text(body)
        return d

    def test_duplicate_seq_raises(self):
        d = self._vehicle([
            ("00001-2026-01-01-maintenance-a", "seq: 1\nvehicle_id: t\ntype: maintenance\ndate: 2026-01-01\nservice: oil\n"),
            ("00001-2026-01-02-maintenance-b", "seq: 1\nvehicle_id: t\ntype: maintenance\ndate: 2026-01-02\nservice: oil\n")])
        with self.assertRaises(ValueError):
            build_state.build_vehicle(d, as_of=date(2026, 6, 16), write=False)

    def test_dangling_correction_raises(self):
        d = self._vehicle([("00001-2026-01-01-correction-x", "seq: 1\nvehicle_id: t\ntype: correction\nsupersedes: 99\n")])
        with self.assertRaises(ValueError):
            build_state.build_vehicle(d, as_of=date(2026, 6, 16), write=False)

    def test_misfiled_vehicle_id_raises(self):
        d = self._vehicle([("00001-2026-01-01-maintenance-a",
                            "seq: 1\nvehicle_id: OTHER\ntype: maintenance\ndate: 2026-01-01\nservice: oil\nreadings: chassis=100\n")])
        with self.assertRaises(ValueError):
            build_state.build_vehicle(d, as_of=date(2026, 6, 16), write=False)

    def test_reading_for_derived_clock_raises(self):
        # a derived clock must never be logged directly
        d = self._vehicle([("00001-2026-01-01-maintenance-a",
                            "seq: 1\nvehicle_id: t\ntype: maintenance\ndate: 2026-01-01\nservice: oil\nreadings: chassis=100\n")])
        # add a derived clock + a bad event that logs it
        vj = json.loads((d / "vehicle.json").read_text())
        vj["clocks"].append({"name": "engine", "kind": "derived", "unit": "mi", "base": "chassis", "offset": 50})
        (d / "vehicle.json").write_text(json.dumps(vj))
        (d / "events" / "00002-2026-02-01-maintenance-b").write_text(
            "seq: 2\nvehicle_id: t\ntype: maintenance\ndate: 2026-02-01\nservice: plugs\nreadings: engine=20\n")
        with self.assertRaises(ValueError):
            build_state.build_vehicle(d, as_of=date(2026, 6, 16), write=False)


if __name__ == "__main__":
    unittest.main()
