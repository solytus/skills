"""TDD tests for recalls.py — NHTSA recall lookup (the #1 missing owner-safety feature).

The fetch is network I/O; the parser is pure and is what we test. A silent or
empty network result must never read as 'no open recalls' — that's a safety claim
the tool can't make offline.

Run: python3 scripts/tests/test_recalls.py -v
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import recalls

SAMPLE = {
    "Count": 1,
    "results": [
        {"NHTSACampaignNumber": "95V123000", "Component": "AIR BAGS",
         "Summary": "The inflator may rupture.", "Consequence": "Metal fragments may injure occupants.",
         "Remedy": "Dealers will replace the inflator free of charge."},
    ],
}


class TestParse(unittest.TestCase):
    def test_extracts_campaign_and_component(self):
        out = recalls.parse_recalls(SAMPLE)
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["campaign"], "95V123000")
        self.assertEqual(out[0]["component"], "AIR BAGS")
        self.assertIn("rupture", out[0]["summary"])

    def test_empty_results(self):
        self.assertEqual(recalls.parse_recalls({"Count": 0, "results": []}), [])

    def test_malformed_input_returns_empty(self):
        self.assertEqual(recalls.parse_recalls({}), [])
        self.assertEqual(recalls.parse_recalls(None), [])


if __name__ == "__main__":
    unittest.main()
