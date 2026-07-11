"""TDD tests for safety.py — the proportionate 4-tier safety model.

Keeps the common case clean for a competent DIYer; gates the few things that kill.
Tier 0 informational (no warning) -> Tier 1 verify-before-acting (footer on numbers)
-> Tier 2 procedure caution (lead with the hazard) -> Tier 3 professional/hard-gate
-> hard refuse (defeating a safety system). Plus: a safety item on an estimated or
unknown interval never reads a bare 'OK', and a belt on a (possibly) interference
engine warns hard, fail-closed.

Run: python3 scripts/tests/test_safety.py -v
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import safety


class TestTierClassification(unittest.TestCase):
    def test_info_default(self):
        self.assertEqual(safety.classify_intent("what oil does it take"), safety.TIER_INFO)

    def test_torque_is_verify(self):
        self.assertEqual(safety.classify_intent("what's the lug nut torque"), safety.TIER_VERIFY)

    def test_brake_bleed_is_procedure(self):
        self.assertEqual(safety.classify_intent("how do I bleed the brakes"), safety.TIER_PROCEDURE)

    def test_jacking_is_procedure(self):
        self.assertEqual(safety.classify_intent("how do I jack up the truck safely"), safety.TIER_PROCEDURE)

    def test_airbag_removal_is_professional(self):
        self.assertEqual(safety.classify_intent("how do I remove the airbag to reach the clockspring"),
                         safety.TIER_PRO)

    def test_hv_on_ev_is_professional(self):
        self.assertEqual(safety.classify_intent("how do I service the high voltage battery", fuel="electric"),
                         safety.TIER_PRO)

    def test_defeat_safety_system_refused(self):
        self.assertEqual(safety.classify_intent("how do I disable the ABS"), safety.REFUSE)
        self.assertEqual(safety.classify_intent("airbag delete resistor trick"), safety.REFUSE)


class TestFooter(unittest.TestCase):
    def test_info_has_no_footer(self):
        self.assertEqual(safety.footer_for(safety.TIER_INFO), "")

    def test_verify_footer_mentions_manual(self):
        self.assertIn("manual", safety.footer_for(safety.TIER_VERIFY).lower())

    def test_procedure_footer_mentions_hazard(self):
        self.assertTrue(safety.footer_for(safety.TIER_PROCEDURE))

    def test_pro_footer_says_professional(self):
        self.assertIn("profession", safety.footer_for(safety.TIER_PRO).lower())


class TestDueDisplay(unittest.TestCase):
    class _Row:
        def __init__(self, status, safety_critical, estimate):
            self.status = status
            self.safety_critical = safety_critical
            self.estimate = estimate

    def test_safety_estimate_ok_gets_caveat_not_bare_ok(self):
        tag, caveat = safety.due_display(self._Row("OK", True, True))
        self.assertTrue(caveat)  # never a bare OK
        self.assertIn("estimat", caveat.lower())

    def test_nonsafety_ok_is_clean(self):
        tag, caveat = safety.due_display(self._Row("OK", False, True))
        self.assertEqual(caveat, "")

    def test_safety_cited_ok_is_clean(self):
        tag, caveat = safety.due_display(self._Row("OK", True, False))
        self.assertEqual(caveat, "")


class TestInterference(unittest.TestCase):
    def test_unknown_interference_warns_fail_closed(self):
        self.assertTrue(safety.interference_warning({"interference": None}))

    def test_missing_interference_warns(self):
        self.assertTrue(safety.interference_warning({}))

    def test_true_interference_warns(self):
        self.assertIn("destroy", safety.interference_warning({"interference": True}).lower())

    def test_noninterference_does_not_warn(self):
        self.assertEqual(safety.interference_warning({"interference": False}), "")


class TestRedTeamFixes(unittest.TestCase):
    def test_resistor_spoof_airbag_refused(self):
        self.assertEqual(safety.classify_intent("put resistors on the airbag connector to clear the light"),
                         safety.REFUSE)
        self.assertEqual(safety.classify_intent("resistor to clear the airbag light"), safety.REFUSE)

    def test_steering_under_load_gated(self):
        for q in ("replace the tie rod ends", "swap the ball joint", "change a control arm",
                  "replace the front wheel bearing"):
            self.assertEqual(safety.classify_intent(q), safety.TIER_PROCEDURE, q)

    def test_brake_hydraulic_gated(self):
        self.assertEqual(safety.classify_intent("rebuild the brake caliper"), safety.TIER_PROCEDURE)
        self.assertEqual(safety.classify_intent("bleed my abs at the module"), safety.TIER_PRO)

    def test_nm_no_longer_overwarns(self):
        # 'nm' must not substring-match ordinary words -> Tier 0, not a torque footer
        self.assertEqual(safety.classify_intent("how does wheel alignment work"), safety.TIER_INFO)
        self.assertEqual(safety.classify_intent("what is the environment like"), safety.TIER_INFO)
        # but a real 'Nm' torque still classifies
        self.assertEqual(safety.classify_intent("is it 35 Nm?"), safety.TIER_VERIFY)

    def test_hv_normalization_and_no_overwarn(self):
        self.assertEqual(safety.classify_intent("open the traction battery", fuel="phev"), safety.TIER_PRO)
        self.assertEqual(safety.classify_intent("service the HV battery", fuel="bev"), safety.TIER_PRO)
        # a hybrid's ordinary 12V battery question must NOT hard-gate
        self.assertEqual(safety.classify_intent("how do I jump the 12v battery", fuel="hybrid"),
                         safety.TIER_INFO)

    def test_brake_fluid_spec_is_verify(self):
        self.assertEqual(safety.classify_intent("what brake fluid dot spec does it use"), safety.TIER_VERIFY)


if __name__ == "__main__":
    unittest.main()
