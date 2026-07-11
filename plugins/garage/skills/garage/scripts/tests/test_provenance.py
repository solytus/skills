"""TDD tests for kb_lint.py — the citation gate with provenance teeth.

Beyond Tacoma's format gate (tiers, non-weasel locator sources), Garage adds a
`method` provenance column and the rules the panel required: a web-researched fact
can't claim an FSM citation it never ingested (confabulation guard); a single-fetch
lazy fact is provisional (low confidence); safety facts must pin their config and,
when lazily sourced, corroborate across >=2 sources; torque values must carry a
unit; and a safety-keyword fact can't suppress its own safety flag.

Run: python3 scripts/tests/test_provenance.py -v
"""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import kb_lint

HEADER = ("## Facts\n"
          "| key | value | applies-to | tier | conf | safety | method | source |\n"
          "|--|--|--|--|--|--|--|--|\n")


def _file(rows: list[str], section="## Facts") -> str:
    body = HEADER if section == "## Facts" else ""
    body += "".join("| " + " | ".join(r) + " |\n" for r in rows)
    d = tempfile.mkdtemp()
    p = Path(d) / "topic.md"
    p.write_text(body)
    return str(p)


def lint(rows):
    _, problems = kb_lint.lint_file(_file(rows))
    return problems


class TestPortedChecks(unittest.TestCase):
    def test_clean_official_row(self):
        self.assertEqual(lint([
            ["oil_capacity", "5.2 L", "5VZ-FE 4WD", "official", "high", "no", "fsm-ocr", "1996 FSM EG-176"]]), [])

    def test_wrong_column_count(self):
        self.assertTrue(any("columns" in p for p in lint([["a", "b", "c"]])))

    def test_bad_tier(self):
        self.assertTrue(any("tier" in p for p in lint([
            ["k", "v", "x", "rumor", "high", "no", "fsm-ocr", "FSM"]])))

    def test_weasel_source_for_official(self):
        self.assertTrue(any("weasel" in p.lower() or "source" in p.lower() for p in lint([
            ["k", "v", "x", "official", "high", "no", "fsm-ocr", "standard"]])))

    def test_no_facts_rows(self):
        _, problems = kb_lint.lint_file(_file([]))
        self.assertTrue(any("no Facts" in p for p in problems))


class TestMethodColumn(unittest.TestCase):
    def test_bad_method_flagged(self):
        self.assertTrue(any("method" in p for p in lint([
            ["k", "v", "x", "community", "low", "no", "guessing", "example.com"]])))

    def test_valid_methods_accepted(self):
        for m in ("owner-confirmed", "fsm-ocr", "deep-research-verified", "generic-heuristic"):
            self.assertEqual(lint([["k", "v", "x", "community", "medium", "no", m, "example.com"]]), [],
                             f"method {m} should be valid")


class TestConfabulationGuard(unittest.TestCase):
    def test_official_fsm_cite_requires_ingested_method(self):
        # tier=official + FSM source but method=lazy-single -> you didn't read the FSM.
        self.assertTrue(any("confabulat" in p.lower() or "ingest" in p.lower() for p in lint([
            ["lug_torque", "83 ft-lb", "4WD", "official", "high", "yes", "lazy-single", "1996 FSM SA-37"]])))

    def test_official_fsm_with_fsm_ocr_ok(self):
        self.assertEqual(lint([
            ["lug_torque", "83 ft-lb", "4WD", "official", "high", "yes", "fsm-ocr", "1996 FSM SA-37"]]), [])


class TestLazyProvisional(unittest.TestCase):
    def test_lazy_single_must_be_low_conf(self):
        self.assertTrue(any("provisional" in p.lower() or "conf" in p.lower() for p in lint([
            ["k", "v", "x", "community", "high", "no", "lazy-single", "example.com"]])))

    def test_lazy_single_low_conf_ok(self):
        self.assertEqual(lint([["k", "v", "x", "community", "low", "no", "lazy-single", "example.com"]]), [])


class TestSafetyApplicability(unittest.TestCase):
    def test_safety_row_requires_applies_to(self):
        self.assertTrue(any("applies" in p.lower() for p in lint([
            ["coolant_type", "Toyota SLLC", "", "official", "high", "yes", "fsm-ocr", "FSM"]])))


class TestTorqueUnit(unittest.TestCase):
    def test_torque_value_without_unit_flagged(self):
        self.assertTrue(any("unit" in p.lower() for p in lint([
            ["lug_torque", "83", "4WD", "official", "high", "yes", "fsm-ocr", "1996 FSM SA-37"]])))

    def test_torque_value_with_unit_ok(self):
        self.assertEqual(lint([
            ["lug_torque", "83 ft-lb", "4WD", "official", "high", "yes", "fsm-ocr", "1996 FSM SA-37"]]), [])


class TestSafetyKeywordEnforcement(unittest.TestCase):
    def test_torque_key_cannot_be_safety_no(self):
        self.assertTrue(any("safety" in p.lower() for p in lint([
            ["caliper_torque", "80 ft-lb", "4WD", "official", "high", "no", "fsm-ocr", "FSM"]])))


class TestMultiSourceSafety(unittest.TestCase):
    def test_lazy_safety_needs_two_sources(self):
        # safety + lazy single-source -> not enough corroboration.
        self.assertTrue(any("corroborat" in p.lower() or "source" in p.lower() for p in lint([
            ["ball_joint_torque", "80 ft-lb", "4WD", "community", "low", "yes", "lazy-single",
             "tacomaworld.com/thread/123"]])))

    def test_lazy_safety_two_sources_ok(self):
        self.assertEqual(lint([
            ["ball_joint_torque", "80 ft-lb", "4WD", "community", "low", "yes", "lazy-single",
             "tacomaworld.com/123 ; yotatech.com/456"]]), [])


class TestApplicabilityContradiction(unittest.TestCase):
    def test_contradicts_vehicle_drivetrain(self):
        vehicle = {"drivetrain": "4WD", "transmission": "A340F automatic", "fuel": "gasoline"}
        _, problems = kb_lint.lint_file(_file([
            ["front_diff_cap", "1.1 L", "2WD only", "community", "low", "no", "generic-heuristic", "example.com"]]),
            vehicle=vehicle)
        self.assertTrue(any("contradict" in p.lower() or "2wd" in p.lower() for p in problems))


class TestEngineOutputTorque(unittest.TestCase):
    def test_engine_output_torque_may_be_safety_no(self):
        # Peak crankshaft torque (a power-curve figure @ rpm) is a performance spec, not a
        # fastener torque — it must not be forced to safety=yes.
        self.assertEqual(lint([
            ["torque", "220 lb·ft (298 N·m) @ 3,600 rpm", "5VZ-FE Tacoma", "community", "high", "no",
             "seed-web", "https://en.wikipedia.org/wiki/Toyota_VZ_engine"]]), [])

    def test_fastener_torque_without_rpm_still_gated(self):
        self.assertTrue(any("safety" in p.lower() for p in lint([
            ["caliper_torque", "80 ft-lb", "4WD", "official", "high", "no", "fsm-ocr", "1996 FSM (OCR p1)"]])))


class TestOfficialTierRequiresAuthority(unittest.TestCase):
    def test_official_web_source_flagged(self):
        # a Wikipedia/vendor/forum row cannot be tier=official (the tier-inflation the audit found)
        self.assertTrue(any("official" in p.lower() for p in lint([
            ["displacement", "3.4 L", "5VZ-FE", "official", "high", "no", "seed-web",
             "https://en.wikipedia.org/wiki/Toyota_VZ_engine"]])))

    def test_official_deep_research_ok(self):
        self.assertEqual(lint([
            ["kit", "TKT-025", "5VZ-FE 4WD", "official", "high", "no", "deep-research-verified",
             "https://aisin.com/x ; https://rockauto.net/y"]]), [])

    def test_official_fsm_ocr_ok(self):
        self.assertEqual(lint([
            ["oil_cap", "5.2 L", "5VZ-FE 4WD", "official", "high", "no", "fsm-ocr", "1996 FSM EG-176 (OCR p529)"]]), [])


class TestDistinctSourceCount(unittest.TestCase):
    def test_single_url_is_one_source(self):
        # old bug: one URL counted as 2 (https:// + .com). Now it's one domain.
        self.assertTrue(any("corroborat" in p.lower() or "domain" in p.lower() for p in lint([
            ["lug_torque", "83 ft-lb", "4WD", "community", "low", "yes", "lazy-single", "https://tacomaworld.com/t/1"]])))

    def test_same_domain_twice_is_one_source(self):
        self.assertTrue(any("corroborat" in p.lower() or "domain" in p.lower() for p in lint([
            ["lug_torque", "83 ft-lb", "4WD", "community", "low", "yes", "lazy-single",
             "tacomaworld.com/1 ; tacomaworld.com/2"]])))

    def test_two_distinct_domains_ok(self):
        self.assertEqual(lint([
            ["lug_torque", "83 ft-lb", "4WD", "community", "low", "yes", "lazy-single",
             "https://tacomaworld.com/1 ; https://yotatech.com/2"]]), [])


class TestScheduleSourceGate(unittest.TestCase):
    def _item(self, **kw):
        import schedule as sched
        base = dict(key="oil", label="Oil", service_slug="oil-change", clock="chassis",
                    mileage_interval=5000, time_interval_months=6, safety_critical=False,
                    baseline_tier=None, is_fluid=True, provenance="x", estimate=False,
                    tier="official", source="1996 FSM EG-176", aliases=())
        base.update(kw)
        return sched.ScheduleItem(**base)

    def test_claimed_oem_without_locator_flagged(self):
        problems = kb_lint.lint_schedule([self._item(source="KB severe (short-trip)")])
        self.assertTrue(any("locator" in p for p in problems))

    def test_claimed_oem_with_locator_clean(self):
        self.assertEqual(kb_lint.lint_schedule([self._item(source="1996 FSM EG-176")]), [])

    def test_estimate_item_needs_only_derivation(self):
        self.assertEqual(kb_lint.lint_schedule([
            self._item(estimate=True, tier="inference", source="set-by-us; street est.")]), [])


if __name__ == "__main__":
    unittest.main()
