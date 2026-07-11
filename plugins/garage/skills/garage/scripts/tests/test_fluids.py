"""TDD tests for fluids.py — block dangerous cross-standard fluid substitutions.

The wrong fluid is one of the most expensive AI errors possible (Toyota WS vs
Dexron, a CVT vs a regular ATF, GL-4 vs GL-5 attacking yellow-metal synchros,
DOT 5 silicone vs glycol brake fluid). The skill must hard-block suggesting one
where the other is specified.

Run: python3 scripts/tests/test_fluids.py -v
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import fluids


class TestSubstitutionBlocked(unittest.TestCase):
    def test_ws_vs_dexron_blocked(self):
        blocked, reason = fluids.substitution_blocked("Toyota WS", "Dexron VI")
        self.assertTrue(blocked)
        self.assertTrue(reason)

    def test_gl4_vs_gl5_blocked(self):
        self.assertTrue(fluids.substitution_blocked("75W-90 GL-4", "75W-90 GL-5")[0])

    def test_dot5_vs_dot4_blocked(self):
        self.assertTrue(fluids.substitution_blocked("DOT 5", "DOT 4")[0])

    def test_cvt_vs_atf_blocked(self):
        self.assertTrue(fluids.substitution_blocked("HCF-2 CVT fluid", "Dexron VI")[0])

    def test_coolant_oat_vs_iat_blocked(self):
        self.assertTrue(fluids.substitution_blocked("Toyota SLLC (OAT)", "green IAT")[0])


class TestSubstitutionAllowed(unittest.TestCase):
    def test_dot3_vs_dot4_allowed(self):
        # Both glycol, intermixable (DOT4 has a higher boiling point but is compatible).
        self.assertFalse(fluids.substitution_blocked("DOT 3", "DOT 4")[0])

    def test_same_standard_allowed(self):
        self.assertFalse(fluids.substitution_blocked("Toyota WS", "Toyota WS ATF")[0])

    def test_unrelated_categories_not_blocked(self):
        self.assertFalse(fluids.substitution_blocked("5W-30 engine oil", "Toyota SLLC coolant")[0])


if __name__ == "__main__":
    unittest.main()
