"""TDD tests for the FEMA hazard lookup (NRI county scores + NFHL flood zone).
Run: python3 scripts/tests/test_hazard.py -v"""
import sys
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))
import lookups

# Captured live 2026-05-27.
NFHL_X = {"features": [{"attributes": {"FLD_ZONE": "X",
          "ZONE_SUBTY": "AREA OF MINIMAL FLOOD HAZARD", "SFHA_TF": "F"}}]}
NFHL_SFHA = {"features": [{"attributes": {"FLD_ZONE": "AE", "ZONE_SUBTY": "", "SFHA_TF": "T"}}]}
NRI = {"features": [{"attributes": {"COUNTY": "Pierce", "STATEABBRV": "WA",
       "RISK_SCORE": 98.53689567, "RISK_RATNG": "Relatively High",
       "WFIR_RISKS": 76.78117, "WFIR_RISKR": "Relatively Low",
       "EAL_SCORE": 99.133663, "SOVI_SCORE": 14.37659, "RESL_SCORE": 60.082697}}]}
EMPTY = {"features": []}


class FloodNormalizeTest(unittest.TestCase):
    def test_zone_x_not_in_sfha(self):
        p = lookups._normalize_flood(NFHL_X)
        self.assertEqual(p["flood_zone"], "X")
        self.assertEqual(p["flood_zone_subtype"], "AREA OF MINIMAL FLOOD HAZARD")
        self.assertFalse(p["in_special_flood_hazard_area"])

    def test_zone_ae_in_sfha(self):
        self.assertTrue(lookups._normalize_flood(NFHL_SFHA)["in_special_flood_hazard_area"])

    def test_empty_is_none(self):
        p = lookups._normalize_flood(EMPTY)
        self.assertIsNone(p["flood_zone"])
        self.assertIsNone(p["in_special_flood_hazard_area"])


class NriNormalizeTest(unittest.TestCase):
    def test_maps_and_rounds_scores(self):
        p = lookups._normalize_nri(NRI)
        self.assertEqual(p["county"], "Pierce")
        self.assertEqual(p["state"], "WA")
        self.assertEqual(p["risk_score"], 98.5)
        self.assertEqual(p["risk_rating"], "Relatively High")
        self.assertEqual(p["wildfire_risk_score"], 76.8)
        self.assertEqual(p["wildfire_risk_rating"], "Relatively Low")
        self.assertEqual(p["expected_annual_loss_score"], 99.1)
        self.assertEqual(p["social_vulnerability_score"], 14.4)
        self.assertEqual(p["community_resilience_score"], 60.1)

    def test_empty_is_none(self):
        p = lookups._normalize_nri(EMPTY)
        self.assertIsNone(p["risk_score"])
        self.assertIsNone(p["county"])


if __name__ == "__main__":
    unittest.main()
