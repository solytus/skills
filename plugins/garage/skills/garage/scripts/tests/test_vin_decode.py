"""TDD tests for vin_decode.py — parse NHTSA vPIC output. The fetch is I/O; the
parser is pure. Decoded engine/trim is a starting point, not the truth (a JDM swap
won't show), so it carries a 'confirmed: false' marker for the onboarding gate."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import vin_decode

SAMPLE = {"Results": [{
    "Make": "TOYOTA", "Model": "Tacoma", "ModelYear": "1995", "Trim": "",
    "EngineModel": "5VZ-FE", "DisplacementL": "3.4", "BodyClass": "Pickup",
    "DriveType": "4WD/4-Wheel Drive", "FuelTypePrimary": "Gasoline"}]}


class TestParse(unittest.TestCase):
    def test_extracts_fields(self):
        d = vin_decode.parse_decode(SAMPLE)
        self.assertEqual(d["make"], "TOYOTA")
        self.assertEqual(d["year"], "1995")
        self.assertEqual(d["displacement_l"], "3.4")
        self.assertEqual(d["fuel"], "Gasoline")
        self.assertFalse(d["confirmed"])  # decode is unconfirmed until the owner verifies

    def test_blank_fields_dropped_to_empty(self):
        self.assertEqual(vin_decode.parse_decode(SAMPLE)["trim"], "")

    def test_malformed_returns_empty_dict(self):
        self.assertEqual(vin_decode.parse_decode({}), {})
        self.assertEqual(vin_decode.parse_decode(None), {})


if __name__ == "__main__":
    unittest.main()
