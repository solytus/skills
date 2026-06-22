"""TDD tests for log_query. Run: python3 scripts/tests/test_log_query.py -v"""
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import log_query as lq

PLACE = """---
schema_version: 1
place_key: "{level}::{name}::47.0000,-122.0000"
level: {level}
normalized_name: {name}
status: {status}
verdict: {verdict}
fit: {fit}
last_touched: {touched}
parent_chain: ["state::washington::47.7511,-120.7401"]
verdict_history:
  - {{date: {touched}, verdict: {verdict}, eval: "x", note: ""}}
owner: me
---

# {name}
body text
"""


def write_place(root, level, name, status, verdict, fit, touched):
    d = Path(root) / "places" / level
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{name}.md").write_text(PLACE.format(
        level=level, name=name, status=status, verdict=verdict, fit=fit, touched=touched))


def seed(d):
    write_place(d, "city", "tacoma-wa", "Researched", "Shortlist", 72, "2026-05-20")
    write_place(d, "city", "boise-id", "Considered", "Curious", 75, "2026-01-01")
    write_place(d, "neighborhood", "capitol-hill-seattle", "Visited", "Shortlist", 60, "2026-05-25")


INTL_PLACE = """---
schema_version: 1
place_key: "country::{name}::39.5000,-8.0000"
level: country
normalized_name: {name}
country_code: {cc}
grain_class: international
status: {status}
verdict: {verdict}
fit: {fit}
last_touched: 2026-05-28
owner: me
---

# {name}
body text
"""


def write_country(root, name, cc, status, verdict, fit):
    d = Path(root) / "places" / "country"
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{name}.md").write_text(INTL_PLACE.format(
        name=name, cc=cc, status=status, verdict=verdict, fit=fit))


class TestReadFrontmatter(unittest.TestCase):
    def test_extracts_scalars_strips_quotes_ints_fit_ignores_nested(self):
        with tempfile.TemporaryDirectory() as d:
            write_place(d, "city", "tacoma-wa", "Researched", "Shortlist", 72, "2026-05-01")
            fm = lq.read_place_frontmatter(Path(d) / "places" / "city" / "tacoma-wa.md")
            self.assertEqual(fm["place_key"], "city::tacoma-wa::47.0000,-122.0000")
            self.assertEqual(fm["level"], "city")
            self.assertEqual(fm["status"], "Researched")
            self.assertEqual(fm["verdict"], "Shortlist")
            self.assertEqual(fm["fit"], 72)
            self.assertEqual(fm["last_touched"], "2026-05-01")
            self.assertNotIn("verdict_history", fm)
            self.assertNotIn("parent_chain", fm)
            self.assertNotIn("owner", fm)


class TestQuery(unittest.TestCase):
    def test_no_filters_returns_all(self):
        with tempfile.TemporaryDirectory() as d:
            seed(d)
            self.assertEqual(len(lq.query_places(d)), 3)

    def test_filter_by_verdict(self):
        with tempfile.TemporaryDirectory() as d:
            seed(d)
            res = lq.query_places(d, verdict="Shortlist")
            self.assertEqual({r["normalized_name"] for r in res}, {"tacoma-wa", "capitol-hill-seattle"})

    def test_filter_by_fit_range(self):
        with tempfile.TemporaryDirectory() as d:
            seed(d)
            res = lq.query_places(d, fit_min=70)
            self.assertEqual({r["normalized_name"] for r in res}, {"tacoma-wa", "boise-id"})

    def test_filter_by_level(self):
        with tempfile.TemporaryDirectory() as d:
            seed(d)
            res = lq.query_places(d, level="neighborhood")
            self.assertEqual([r["normalized_name"] for r in res], ["capitol-hill-seattle"])

    def test_filter_stale(self):
        with tempfile.TemporaryDirectory() as d:
            seed(d)
            res = lq.query_places(d, stale_days=90, now=datetime(2026, 5, 26))
            self.assertEqual([r["normalized_name"] for r in res], ["boise-id"])

    def test_combined_filters_are_anded(self):
        with tempfile.TemporaryDirectory() as d:
            seed(d)
            res = lq.query_places(d, verdict="Shortlist", fit_min=70)
            self.assertEqual([r["normalized_name"] for r in res], ["tacoma-wa"])


class TestInternationalScalars(unittest.TestCase):
    """The international extension adds optional country_code + grain_class scalars,
    used to filter the log and keep grains apart in the ranking check."""

    def test_reads_country_code_and_grain_class(self):
        with tempfile.TemporaryDirectory() as d:
            write_country(d, "portugal-pt", "PT", "Researched", "Promising", 71)
            fm = lq.read_place_frontmatter(Path(d) / "places" / "country" / "portugal-pt.md")
            self.assertEqual(fm["country_code"], "PT")
            self.assertEqual(fm["grain_class"], "international")

    def test_filter_by_country(self):
        with tempfile.TemporaryDirectory() as d:
            seed(d)
            write_country(d, "portugal-pt", "PT", "Researched", "Promising", 71)
            write_country(d, "japan-jp", "JP", "Considered", "Marginal", 55)
            res = lq.query_places(d, country="PT")
            self.assertEqual([r["normalized_name"] for r in res], ["portugal-pt"])

    def test_filter_by_grain_class_international(self):
        with tempfile.TemporaryDirectory() as d:
            seed(d)
            write_country(d, "portugal-pt", "PT", "Researched", "Promising", 71)
            res = lq.query_places(d, grain_class="international")
            self.assertEqual([r["normalized_name"] for r in res], ["portugal-pt"])

    def test_grain_class_domestic_matches_fieldless_places(self):
        # Regression safety: the 19 existing US places carry no grain_class field and
        # MUST be treated as domestic, so a --grain-class domestic filter includes them.
        with tempfile.TemporaryDirectory() as d:
            seed(d)  # three fieldless (domestic) places
            write_country(d, "portugal-pt", "PT", "Researched", "Promising", 71)
            res = lq.query_places(d, grain_class="domestic")
            self.assertEqual(
                {r["normalized_name"] for r in res},
                {"tacoma-wa", "boise-id", "capitol-hill-seattle"},
            )


class TestExistingPlacesRegressionGuard(unittest.TestCase):
    """Schema-migration safety: every real logged place must still parse with the new
    SCALAR_KEYS, and all of them (being fieldless) read as domestic."""

    def _data_root(self):
        import os
        root = os.environ.get("HABITAT_DATA_ROOT")
        if not root:
            self.skipTest("set HABITAT_DATA_ROOT to validate a real data store")
        return Path(root)

    def test_all_logged_places_parse_and_partition_cleanly(self):
        root = self._data_root()
        if not (root / "places").exists():
            self.skipTest("real data store not present")
        files = list(root.glob("places/**/*.md"))
        self.assertGreater(len(files), 0, "expected logged places")
        for p in files:
            fm = lq.read_place_frontmatter(p)
            self.assertIn("place_key", fm, f"{p} failed to parse place_key")
        total = lq.query_places(str(root))
        intl = lq.query_places(str(root), grain_class="international")
        domestic = lq.query_places(str(root), grain_class="domestic")
        # clean partition: every place is exactly one of domestic / international (fieldless => domestic)
        self.assertEqual(len(domestic) + len(intl), len(total))
        # international places are well-formed (non-US country_code); domestic places never carry one
        for p in intl:
            self.assertIn("country_code", p, f"{p['normalized_name']} international but no country_code")
            self.assertNotEqual(p["country_code"], "US")
        for p in domestic:
            self.assertNotEqual(p.get("grain_class"), "international")
            self.assertIn(p.get("country_code", "US"), (None, "US"))


class TestFindPlace(unittest.TestCase):
    """Dedupe support: the evaluate workflow reuses an existing place rather than
    forking a new file when a place is re-evaluated."""

    def test_finds_existing_by_level_and_name(self):
        with tempfile.TemporaryDirectory() as d:
            seed(d)
            res = lq.find_place(d, "city", "tacoma-wa")
            self.assertEqual(len(res), 1)
            self.assertTrue(res[0]["path"].endswith("tacoma-wa.md"))

    def test_no_match_is_empty(self):
        with tempfile.TemporaryDirectory() as d:
            seed(d)
            self.assertEqual(lq.find_place(d, "city", "denver-co"), [])

    def test_scoped_to_level(self):
        with tempfile.TemporaryDirectory() as d:
            seed(d)
            self.assertEqual(lq.find_place(d, "city", "capitol-hill-seattle"), [])


if __name__ == "__main__":
    unittest.main()
