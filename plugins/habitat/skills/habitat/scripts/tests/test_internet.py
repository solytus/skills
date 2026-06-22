"""TDD tests for the internet lookup (keyless FCC block/county FIPS; provider/speed
deferred to reason-with-search per the Phase-3a triage). Run: python3 scripts/tests/test_internet.py -v"""
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))
import adapter_base as ab
import lookups

# geo.fcc.gov/api/census/area shape (captured live 2026-05-27, Tacoma).
FCC = {"results": [{"block_fips": "530530616011010", "county_fips": "53053",
       "county_name": "Pierce County", "state_fips": "53", "state_code": "WA",
       "state_name": "Washington"}]}
EMPTY = {"results": []}


class FccAreaNormalizeTest(unittest.TestCase):
    def test_maps_fips_fields(self):
        p = lookups._normalize_fcc_area(FCC)
        self.assertEqual(p["block_fips"], "530530616011010")
        self.assertEqual(p["county_fips"], "53053")
        self.assertEqual(p["county_name"], "Pierce County")
        self.assertEqual(p["state_code"], "WA")
        # providers/speeds are not available keyless -> deferred to reason-with-search
        self.assertIsNone(p["providers"])
        self.assertIsNone(p["max_speeds"])

    def test_empty_is_none(self):
        p = lookups._normalize_fcc_area(EMPTY)
        self.assertIsNone(p["block_fips"])
        self.assertIsNone(p["county_fips"])


class FccSharedCacheTest(unittest.TestCase):
    NOW = datetime(2026, 5, 28, 12, 0, 0)

    def test_repeat_resolution_served_from_shared_cache(self):
        # internet_quality and hazard both resolve the SAME point via FCC; the second
        # resolution must come from the shared fcc-area cache, not a fresh network call.
        with tempfile.TemporaryDirectory() as d:
            captured = []
            orig, ab.http_json = ab.http_json, lambda url, **k: (captured.append(url) or FCC)
            try:
                r1 = lookups.internet_quality("city::tacoma-wa::g", "47.2529,-122.4443", "city",
                                              data_root=d, now=self.NOW)
                r2 = lookups.internet_quality("city::tacoma-wa::g", "47.2529,-122.4443", "city",
                                              data_root=d, now=self.NOW)
            finally:
                ab.http_json = orig
            self.assertEqual(r1["payload"]["county_fips"], "53053")
            self.assertEqual(r2["payload"]["county_fips"], "53053")
            self.assertEqual(len(captured), 1)  # one FCC call, reused


if __name__ == "__main__":
    unittest.main()
