"""TDD tests for render_footer. Run: python3 scripts/tests/test_render_footer.py -v"""
import sys
import unittest
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import render_footer as rf

NOW = datetime(2026, 5, 26, 12, 0, 0)


def rec(label, source, days=0, hours=0, status="fresh", note=None):
    r = {
        "label": label,
        "source": source,
        "fetched_at": (NOW - timedelta(days=days, hours=hours)).isoformat(),
        "data_status": status,
    }
    if note:
        r["note"] = note
    return r


class TestRelativeTime(unittest.TestCase):
    def test_days(self):
        self.assertEqual(rf.relative_time((NOW - timedelta(days=12)).isoformat(), NOW), "12 d ago")

    def test_hours(self):
        self.assertEqual(rf.relative_time((NOW - timedelta(hours=6)).isoformat(), NOW), "6 h ago")

    def test_under_an_hour(self):
        self.assertEqual(rf.relative_time((NOW - timedelta(minutes=30)).isoformat(), NOW), "just now")


class TestRender(unittest.TestCase):
    def test_starts_with_sources_header(self):
        out = rf.render([rec("Climate", "NOAA CDO", days=1)], [], [], NOW)
        self.assertTrue(out.startswith("Sources:"))

    def test_fresh_cached_line_has_no_marker(self):
        out = rf.render([rec("Climate", "NOAA CDO", days=12)], [], [], NOW)
        self.assertIn("- Climate: NOAA CDO • fetched 12 d ago", out)
        self.assertNotIn("[", out)

    def test_stale_cached_line_has_default_marker(self):
        out = rf.render([rec("Safety", "FBI Crime Data", days=65, status="stale")], [], [], NOW)
        self.assertIn(
            "- Safety: FBI Crime Data • fetched 65 d ago [stale: TTL expired, fresh fetch failed]",
            out,
        )

    def test_note_overrides_default_marker(self):
        out = rf.render(
            [rec("Safety", "FBI Crime Data", days=65, status="stale",
                 note="stale FBI: data inherently lags ~18 months")],
            [], [], NOW,
        )
        self.assertIn("[stale FBI: data inherently lags ~18 months]", out)
        self.assertNotIn("TTL expired", out)

    def test_reasoned_and_lookup_summary_lines(self):
        out = rf.render([], ["Walkability", "Healthcare"], ["Family distance", "Airport"], NOW)
        self.assertIn("- Walkability, Healthcare: reasoned via WebFetch (real-time)", out)
        self.assertIn("- Family distance, Airport: utility lookups (real-time)", out)

    def test_empty_sections_are_omitted(self):
        out = rf.render([rec("Climate", "NOAA CDO", days=1)], [], [], NOW)
        self.assertNotIn("reasoned via WebFetch", out)
        self.assertNotIn("utility lookups", out)


if __name__ == "__main__":
    unittest.main()
