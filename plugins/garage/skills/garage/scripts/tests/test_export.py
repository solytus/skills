"""TDD tests for export.py — render a report/checklist/guide to Markdown.

VIN/plate are redacted by default (safe to hand a shop or post to a forum), with an
opt-in to include. A header disclaimer rides every export. Synthetic identifiers are
built at runtime so no real PII sits in committed source.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import export

FAKE_VIN = "ZZ" + "9" * 15
FAKE_PLATE = "TEST123"
VEHICLE = {"display": "1995 Toyota Tacoma", "vin": FAKE_VIN, "plate": FAKE_PLATE}


class TestRender(unittest.TestCase):
    def test_redacts_identity_by_default(self):
        out = export.render_markdown(f"Torque: 83 ft-lb. VIN {FAKE_VIN} plate {FAKE_PLATE}",
                                     VEHICLE, kind="checklist", title="Job Sheet")
        self.assertNotIn(FAKE_VIN, out)
        self.assertNotIn(FAKE_PLATE, out)

    def test_include_identity_keeps_vin(self):
        out = export.render_markdown(f"VIN {FAKE_VIN}", VEHICLE, kind="records",
                                     title="Sale Records", redact=False)
        self.assertIn(FAKE_VIN, out)

    def test_has_disclaimer_header(self):
        out = export.render_markdown("body", VEHICLE, kind="checklist", title="X")
        self.assertIn("not professional advice", out.lower())

    def test_title_in_output(self):
        out = export.render_markdown("body", VEHICLE, kind="checklist", title="Pre-Trip")
        self.assertIn("Pre-Trip", out)


if __name__ == "__main__":
    unittest.main()
