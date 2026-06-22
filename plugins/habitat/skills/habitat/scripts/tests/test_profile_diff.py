"""TDD tests for profile_diff (quantify profile change between versions, for F1/F3).
Run: python3 scripts/tests/test_profile_diff.py -v"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import profile_diff as pd


def pref(name, weight="medium", must_have=False, must_not=False):
    return {"name": name, "weight": weight, "must_have": must_have, "must_not": must_not}


class DiffPreferencesTest(unittest.TestCase):
    def test_identical_profiles_have_zero_delta(self):
        prefs = [pref("dry climate", "high"), pref("low cost", "high")]
        d = pd.diff_preferences(prefs, [dict(p) for p in prefs])
        self.assertEqual(d["delta_pct"], 0.0)
        self.assertEqual((d["added"], d["removed"], d["changed"]), ([], [], []))

    def test_added_and_removed_detected(self):
        d = pd.diff_preferences([pref("a"), pref("b")], [pref("a"), pref("c")])
        self.assertEqual(d["added"], ["c"])
        self.assertEqual(d["removed"], ["b"])
        self.assertEqual(d["delta_pct"], 66.7)  # 2 changes / union of 3

    def test_weight_change_is_a_change(self):
        d = pd.diff_preferences([pref("climate", "medium")], [pref("climate", "high")])
        self.assertEqual(len(d["changed"]), 1)
        self.assertEqual(d["changed"][0]["fields"]["weight"], ["medium", "high"])
        self.assertEqual(d["delta_pct"], 100.0)  # 1 change / union of 1

    def test_must_not_toggle_is_a_change(self):
        d = pd.diff_preferences([pref("HOA")], [pref("HOA", must_not=True)])
        self.assertEqual(d["changed"][0]["fields"]["must_not"], [False, True])

    def test_name_match_ignores_case_and_surrounding_space(self):
        d = pd.diff_preferences([pref("Dry Climate ", "high")], [pref("dry climate", "high")])
        self.assertEqual(d["delta_pct"], 0.0)
        self.assertEqual(d["changed"], [])

    def test_counts_reported(self):
        d = pd.diff_preferences([pref("a"), pref("b")], [pref("a", "high"), pref("c")])
        self.assertEqual((d["before_count"], d["after_count"]), (2, 2))
        self.assertEqual((d["added_n"], d["removed_n"], d["changed_n"]), (1, 1, 1))


if __name__ == "__main__":
    unittest.main()
