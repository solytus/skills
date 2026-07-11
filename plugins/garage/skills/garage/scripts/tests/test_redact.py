"""TDD tests for redact.py — the PII guard, reused at the export boundary (the only
place data leaves the home-private data root).

Synthetic identifiers are built at runtime so no real VIN/plate (and no 17-char
VIN-shaped literal) sits in committed source.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import redact

FAKE_VIN = "ZZ" + "9" * 15   # 17-char VIN-shaped token, assembled so no literal VIN is in source
FAKE_PLATE = "TEST123"


class TestAssertNoPii(unittest.TestCase):
    def test_vin_shape_detected(self):
        with self.assertRaises(redact.PiiLeakError):
            redact.assert_no_pii(f"VIN is {FAKE_VIN} here", forbidden=())

    def test_forbidden_plate_detected(self):
        with self.assertRaises(redact.PiiLeakError):
            redact.assert_no_pii(f"plate {FAKE_PLATE}", forbidden=(FAKE_PLATE,))

    def test_clean_text_ok(self):
        redact.assert_no_pii("oil change at 260,233 mi", forbidden=(FAKE_PLATE,))


class TestScrub(unittest.TestCase):
    def test_scrub_replaces_vin_and_forbidden(self):
        out = redact.scrub(f"VIN {FAKE_VIN} plate {FAKE_PLATE}", forbidden=(FAKE_PLATE,))
        self.assertNotIn(FAKE_VIN, out)
        self.assertNotIn(FAKE_PLATE, out)
        redact.assert_no_pii(out, forbidden=(FAKE_PLATE,))  # scrubbed text passes the guard


if __name__ == "__main__":
    unittest.main()
