"""TDD tests for migrate_tacoma.py + the Phase-1 migration acceptance gate.

Unit tests (transform_event, translate_schedule) run anywhere. The full-store
acceptance test reproduces the deterministic sections of the real 201-event
projection and confirms the timing belt reads the engine clock; it skips when the
standalone Tacoma project isn't present (e.g. CI / a fresh checkout).

Run: python3 scripts/tests/test_migrate.py -v
"""
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import migrate_tacoma as mig
import build_state
import project
import schedule as sched
import clocks as ck
import due

# Local standalone Tacoma project (acceptance test skips when absent, e.g. in CI).
TACOMA = Path.home() / "Documents" / "Projects" / "Tacoma"
TACOMA_STATE = TACOMA / "state"
TACOMA_SCHED = TACOMA / "skill" / "tacoma" / "scripts" / "schedule.py"
ORACLE = TACOMA_STATE / "current-state.full.md"

COMPARED_SECTIONS = ["MODS", "KNOWN ISSUES", "BACKLOG", "SERVICE HISTORY", "LAST DONE",
                     "VERIFIED SPECS (owner-confirmed from documents)"]


def split_sections(text: str) -> dict[str, str]:
    """Split current-state text into {section_title: body} on '== TITLE ==' lines."""
    out: dict[str, str] = {}
    title = None
    buf: list[str] = []
    for line in text.splitlines():
        if line.startswith("== ") and line.endswith(" =="):
            if title is not None:
                out[title] = "\n".join(buf).strip("\n")
            title = line[3:-3]
            buf = []
        elif line.startswith("max_seq:"):
            if title is not None:
                out[title] = "\n".join(buf).strip("\n")
            title = None
            buf = []
        elif title is not None:
            buf.append(line)
    if title is not None:
        out[title] = "\n".join(buf).strip("\n")
    return out


class TestTransformEvent(unittest.TestCase):
    def test_chassis_miles_becomes_reading_and_vehicle_id_added(self):
        src = "seq: 8\ntype: maintenance\ndate: 2026-05-03\nchassis_miles: 260233\nservice: oil-change\nhash: abc123\n"
        out = mig.transform_event(src, "1995-toyota-tacoma")
        self.assertIn("vehicle_id: 1995-toyota-tacoma", out)
        self.assertIn("readings: chassis=260233", out)
        self.assertNotIn("chassis_miles:", out)
        self.assertNotIn("hash:", out)

    def test_roundtrips_through_parse(self):
        src = "seq: 8\ntype: maintenance\ndate: 2026-05-03\nchassis_miles: 260,233\nservice: oil-change\nhash: abc\n"
        ev = project.parse_event(mig.transform_event(src, "t"))
        self.assertEqual(ev["readings"], {"chassis": 260233})
        self.assertEqual(ev["vehicle_id"], "t")

    def test_notes_block_preserved(self):
        src = "seq: 1\ntype: maintenance\nservice: x\nnotes:\n  line one\n  line two\n"
        out = mig.transform_event(src, "t")
        self.assertIn("line one", out)
        self.assertIn("line two", out)

    def test_event_without_reading_has_no_readings_line(self):
        src = "seq: 2\ntype: build-sheet\nfield: mods\nvalue: +winch\nhash: z\n"
        out = mig.transform_event(src, "t")
        self.assertNotIn("readings:", out)
        self.assertIn("vehicle_id: t", out)


class TestTranslateSchedule(unittest.TestCase):
    """Translate a synthetic Tacoma-shaped schedule.py — no real store needed."""
    FAKE = (
        "from dataclasses import dataclass\n"
        "SWAP_CHASSIS_ODO = 210870\n"
        "@dataclass(frozen=True)\n"
        "class ScheduleItem:\n"
        "    key: str; label: str; service_slug: str; clock_basis: str\n"
        "    mileage_interval: object; time_interval_months: object\n"
        "    safety_critical: bool; baseline_tier: object; is_fluid: bool\n"
        "    provenance: str; estimate: bool; aliases: tuple = ()\n"
        "SCHEDULE = [\n"
        "    ScheduleItem('oil','Oil','oil-change','chassis',5000,6,False,None,True,'KB',False),\n"
        "    ScheduleItem('belt','Belt','timing-belt','engine',60000,72,True,'safety',False,'set-by-us',True),\n"
        "]\n"
    )

    def setUp(self):
        d = tempfile.mkdtemp()
        self.path = Path(d) / "schedule.py"
        self.path.write_text(self.FAKE)

    def test_clock_basis_becomes_clock_and_tier_set(self):
        data = mig.translate_schedule(self.path, "t")
        clocks = ck.load_clocks({"clocks": [
            {"name": "chassis", "kind": "odometer", "unit": "mi", "primary": True},
            {"name": "engine", "kind": "derived", "unit": "mi", "base": "chassis", "offset": 210870}]})
        items = sched.load_schedule(data)
        sched.validate_schedule(items, clocks)  # the translated schedule must be valid
        by_key = {i.key: i for i in items}
        self.assertEqual(by_key["belt"].clock, "engine")
        self.assertEqual(by_key["belt"].tier, "inference")   # estimate -> inference
        self.assertEqual(by_key["oil"].tier, "community")    # cited -> community


class TestKnowledgeCopy(unittest.TestCase):
    """The hand-curated KB must port; the legacy conventions doc must not (garage's
    references/kb-conventions.md supersedes it). Uses a synthetic knowledge dir."""
    def setUp(self):
        self.kdir = Path(tempfile.mkdtemp()) / "knowledge"
        self.kdir.mkdir()
        (self.kdir / "torque-specs.md").write_text("## Facts\n| key | value |\n")
        (self.kdir / "INDEX.md").write_text("# index\n")
        (self.kdir / "identity.md").write_text("VIN narrative card\n")
        (self.kdir / "_CONVENTIONS.md").write_text("legacy 7-col contract\n")
        self.sched = Path(tempfile.mkdtemp()) / "schedule.py"
        self.sched.write_text("SWAP_CHASSIS_ODO=1\nSCHEDULE=[]\n")
        self.state = Path(tempfile.mkdtemp()) / "state"
        (self.state / "events").mkdir(parents=True)

    def test_topic_files_copied_conventions_skipped(self):
        dest = Path(tempfile.mkdtemp()) / "veh"
        mig.migrate(self.state, self.sched, dest, tacoma_knowledge_dir=self.kdir, force=True)
        self.assertTrue((dest / "knowledge" / "torque-specs.md").is_file())
        self.assertTrue((dest / "knowledge" / "INDEX.md").is_file())
        self.assertFalse((dest / "knowledge" / "_CONVENTIONS.md").exists())  # superseded
        self.assertTrue((dest / "identity.md").is_file())  # human card lifted to the vehicle root


@unittest.skipUnless(ORACLE.exists(), "standalone Tacoma store not present")
class TestMigrationAcceptance(unittest.TestCase):
    def setUp(self):
        self.dest = Path(tempfile.mkdtemp()) / "1995-toyota-tacoma"
        self.count = mig.migrate(TACOMA_STATE, TACOMA_SCHED, self.dest,
                                 vin="TESTVIN0000000001", plate="TEST123", force=True)

    def test_all_events_ported(self):
        self.assertEqual(self.count, 201)

    def test_deterministic_sections_match_oracle(self):
        result = build_state.build_vehicle(self.dest, as_of=date(2026, 6, 16), write=False)
        new = split_sections(result["body"])
        oracle = split_sections(ORACLE.read_text())
        for section in COMPARED_SECTIONS:
            self.assertEqual(new.get(section), oracle.get(section),
                             f"section {section!r} diverged from the oracle")

    def test_max_seq_is_201(self):
        result = build_state.build_vehicle(self.dest, as_of=date(2026, 6, 16), write=False)
        self.assertIn("max_seq: 201", result["body"])

    def test_timing_belt_reads_engine_clock_not_false_overdue(self):
        import json
        vj = json.loads((self.dest / "vehicle.json").read_text())
        clocks = ck.load_clocks(vj)
        by_name = ck.clocks_by_name(clocks)
        events = build_state.load_events(self.dest / "events")
        proj = project.reduce_events(events)
        items = sched.load_schedule(self.dest / "schedule.json")
        readings, _ = build_state.current_clock_readings(proj, "chassis")
        rows = {r.key: r for r in due.compute_due(items, proj["last_done"], readings, by_name, date(2026, 6, 16))}
        self.assertEqual(rows["timing_belt"].status, "UNKNOWN")  # never a false OVERDUE off chassis odo


if __name__ == "__main__":
    unittest.main()
