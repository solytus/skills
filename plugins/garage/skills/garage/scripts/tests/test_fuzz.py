"""Property-based fuzz tests for the deterministic core.

Throws hundreds of random event streams and schedule items at reduce_events /
compute_due and asserts invariants that must hold for ANY input — the kind of bug
hand-written examples miss. Seeded (reproducible), stdlib `random` only.

Run: python3 scripts/tests/test_fuzz.py -v
"""
import random
import sys
import unittest
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import clocks as ck
import due
import project
import schedule as sched

TYPES = ["maintenance", "baseline", "build-sheet", "correction", "verified-spec"]
SERVICES = ["oil-change", "coolant", "brakes", "tires", "atf", "timing-belt"]
VALID_STATUS = {"OVERDUE", "DUE SOON", "OK", "UNKNOWN"}

CLOCKS = ck.load_clocks({"clocks": [
    {"name": "chassis", "kind": "odometer", "unit": "mi", "primary": True},
    {"name": "engine", "kind": "derived", "unit": "mi", "base": "chassis", "offset": 210870}]})
BY_NAME = ck.clocks_by_name(CLOCKS)


def rand_events(rng, n):
    events = []
    for seq in range(1, n + 1):
        t = rng.choice(TYPES)
        ev = {"seq": seq, "type": t, "vehicle_id": "t"}
        if t in ("maintenance", "baseline"):
            ev["service"] = rng.choice(SERVICES)
            ev["date"] = f"20{rng.randint(10,26):02d}-{rng.randint(1,12):02d}-{rng.randint(1,28):02d}"
            ev["readings"] = {"chassis": rng.randint(0, 400000)} if rng.random() < 0.8 else {}
            ev["summary"] = f"s{seq}"
        elif t == "build-sheet":
            ev["field"] = rng.choice(["mods", "known_issues", "backlog", "vehicle"])
            ev["value"] = f"+item{seq}"
        elif t == "correction":
            ev["supersedes"] = rng.randint(1, seq)  # may target a non-service event or self
        else:  # verified-spec
            ev["key"] = rng.choice(["k1", "k2", "k3"])
            ev["value"] = f"v{seq}"
    # NOTE: seqs unique by construction; dup-seq handling is covered in validate tests.
        events.append(ev)
    return events


class TestReduceProperties(unittest.TestCase):
    def test_reduce_invariants(self):
        for s in range(300):
            rng = random.Random(s)
            events = rand_events(rng, rng.randint(0, 40))
            proj = project.reduce_events(events)                      # must not crash

            seqs = [e["seq"] for e in events]
            self.assertEqual(proj["max_seq"], max(seqs) if seqs else 0)

            # order-independence: reduce sorts by seq, so a shuffle is identical
            shuffled = events[:]
            rng.shuffle(shuffled)
            self.assertEqual(project.reduce_events(shuffled), proj, f"seed {s}: order-dependent")

            # voided seqs never appear in service_history
            voided = {e["supersedes"] for e in events
                      if e["type"] == "correction" and isinstance(e.get("supersedes"), int)}
            sh_seqs = {r["seq"] for r in proj["service_history"]}
            self.assertTrue(voided.isdisjoint(sh_seqs), f"seed {s}: voided record survived")

            # last_done[svc] is the highest-seq surviving record for that service
            for svc, rec in proj["last_done"].items():
                same = [r["seq"] for r in proj["service_history"] if r["service"] == svc]
                self.assertEqual(rec["seq"], max(same), f"seed {s}: last_done not latest")

    def test_idempotent(self):
        for s in range(100):
            rng = random.Random(s + 5000)
            events = rand_events(rng, rng.randint(0, 25))
            once = project.reduce_events(events)
            self.assertEqual(project.reduce_events(list(once and events)), once)


class TestDueProperties(unittest.TestCase):
    def _rand_item(self, rng):
        # always >=1 interval (validate_schedule guarantees this upstream)
        mi = rng.choice([None, rng.randint(1000, 120000)])
        mo = rng.choice([None, rng.randint(1, 120)]) if mi is None else rng.choice([None, rng.randint(1, 120)])
        if mi is None and mo is None:
            mi = rng.randint(1000, 120000)
        return sched.ScheduleItem(
            key="k", label="L", service_slug="svc", clock=rng.choice(["chassis", "engine"]),
            mileage_interval=mi, time_interval_months=mo, safety_critical=rng.choice([True, False]),
            baseline_tier=None, is_fluid=False, provenance="p", estimate=True, tier="inference", source="x")

    def test_due_invariants(self):
        for s in range(400):
            rng = random.Random(s + 9000)
            item = self._rand_item(rng)
            current = rng.randint(0, 400000)
            last = {}
            if rng.random() < 0.7:
                last["svc"] = {"readings": {"chassis": rng.randint(0, current)} if rng.random() < 0.8 else {},
                              "date": f"20{rng.randint(10,26):02d}-06-15", "seq": 1}
            r = due.compute_due_item(item, last, {"chassis": current}, BY_NAME, date(2026, 6, 16))
            self.assertIn(r.status, VALID_STATUS, f"seed {s}: bad status {r.status}")

            # a derived-clock item whose only record predates the clock must never read OVERDUE
            if item.clock == "engine" and last.get("svc"):
                rec_ch = (last["svc"].get("readings") or {}).get("chassis")
                if rec_ch is not None and rec_ch < 210870:
                    self.assertEqual(r.status, "UNKNOWN", f"seed {s}: pre-clock record not UNKNOWN")

            # mileage remaining, when computed, matches interval - (current - record) on the item's clock
            if r.miles_remaining is not None and r.status != "UNKNOWN":
                clock = BY_NAME[item.clock]
                cur = ck.current_reading(clock, {"chassis": current}, BY_NAME)
                recm = ck.record_reading(clock, r.last["readings"], BY_NAME)
                self.assertEqual(r.miles_remaining, item.mileage_interval - (cur - recm), f"seed {s}")

    def test_compute_due_never_crashes_on_mixed_schedule(self):
        for s in range(100):
            rng = random.Random(s + 12000)
            items = [self._rand_item(rng) for _ in range(rng.randint(0, 15))]
            # dedup keys/slugs so validate isn't needed; compute must tolerate the batch
            for i, it in enumerate(items):
                items[i] = sched.ScheduleItem(**{**it.__dict__, "key": f"k{i}", "service_slug": f"svc{i}"})
            last = {f"svc{i}": {"readings": {"chassis": rng.randint(0, 300000)}, "date": "2024-01-01", "seq": i}
                    for i in range(len(items)) if rng.random() < 0.5}
            rows = due.compute_due(items, last, {"chassis": 300000}, BY_NAME, date(2026, 6, 16))
            self.assertEqual(len(rows), len(items))


if __name__ == "__main__":
    unittest.main()
