"""TDD tests for bundle_datasets staleness checking (pure; no network).
Run: python3 scripts/tests/test_bundle_datasets.py -v"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import bundle_datasets as bd

SOURCES = """# Habitat bundled datasets
- dataset: country_centroids.csv | source: mledoze/countries | license: ODbL-1.0 | url: x | vintage: 2025
- dataset: passport_index.csv | source: ilyankou | license: MPL-2.0 | url: y | vintage: 2025
- dataset: gpi.csv | source: IEP Global Peace Index | license: non-commercial | url: z | vintage: 2020
"""


class ParseSources(unittest.TestCase):
    def test_parses_dataset_and_vintage(self):
        rows = bd.parse_sources(SOURCES)
        self.assertEqual(len(rows), 3)
        self.assertEqual(rows[0]["dataset"], "country_centroids.csv")
        self.assertEqual(rows[0]["vintage"], 2025)
        self.assertEqual(rows[2]["license"], "non-commercial")

    def test_ignores_comment_and_blank_lines(self):
        rows = bd.parse_sources("# header\n\n" + SOURCES)
        self.assertEqual(len(rows), 3)


class CheckStale(unittest.TestCase):
    def test_flags_only_old_datasets(self):
        stale = bd.check_stale(bd.parse_sources(SOURCES), now_year=2026, max_age_years=3)
        self.assertEqual([s["dataset"] for s in stale], ["gpi.csv"])  # 2020 is >3yr old

    def test_nothing_stale_when_all_recent(self):
        stale = bd.check_stale(bd.parse_sources(SOURCES), now_year=2026, max_age_years=10)
        self.assertEqual(stale, [])


class JoinPopulation(unittest.TestCase):
    def test_attaches_population_by_geoid(self):
        rows = [{"geoid": "1000001", "name": "Summit city"},
                {"geoid": "9999999", "name": "Nowhere city"}]
        out = bd._join_population(rows, {"1000001": 200000})
        self.assertEqual(out[0]["population"], 200000)
        self.assertIsNone(out[1]["population"])  # unknown GEOID -> None, not dropped

    def test_geoid_is_state_plus_place(self):
        # ACS rows come back as [pop, state, place]; GEOID is their concatenation.
        self.assertEqual(bd._acs_geoid(["228518", "06", "00562"]), "0600562")


class AcsUrl(unittest.TestCase):
    def test_appends_key_when_present(self):
        # The ACS place:* query shape REQUIRES a Census API key (returns a "Missing Key"
        # HTML page otherwise) — the key must be appended to the URL.
        url = bd._acs_url("06", "ABC123")
        self.assertIn("state:06", url)
        self.assertTrue(url.endswith("&key=ABC123"))

    def test_no_key_suffix_when_absent(self):
        self.assertNotIn("key=", bd._acs_url("06", None))


if __name__ == "__main__":
    unittest.main()
