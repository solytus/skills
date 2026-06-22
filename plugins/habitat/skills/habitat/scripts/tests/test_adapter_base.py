"""TDD tests for adapter_base. Run: python3 scripts/tests/test_adapter_base.py -v"""
import os
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import adapter_base as ab


class TestPlaceKeyFilename(unittest.TestCase):
    def test_sanitizes_colons_and_commas(self):
        self.assertEqual(
            ab.place_key_to_filename("city::tacoma-wa::47.25,-122.44"),
            "city__tacoma-wa__47.25_-122.44.json",
        )


class TestMakeRecord(unittest.TestCase):
    def test_builds_envelope_with_all_fields(self):
        rec = ab.make_record(
            "city::x::1,2", "noaa", {"k": 1}, "city", "2026-05-26T14:32:00", "fresh"
        )
        self.assertEqual(rec["place_key"], "city::x::1,2")
        self.assertEqual(rec["source"], "noaa")
        self.assertEqual(rec["payload"], {"k": 1})
        self.assertEqual(rec["place_grain"], "city")
        self.assertEqual(rec["fetched_at"], "2026-05-26T14:32:00")
        self.assertEqual(rec["data_status"], "fresh")


class TestFreshness(unittest.TestCase):
    def test_within_ttl_is_fresh(self):
        now = datetime(2026, 5, 26)
        fetched = datetime(2026, 5, 16).isoformat()  # 10 days ago
        self.assertEqual(ab.freshness(fetched, 30, now), "fresh")

    def test_beyond_ttl_is_stale(self):
        now = datetime(2026, 5, 26)
        fetched = datetime(2026, 4, 1).isoformat()  # 55 days ago
        self.assertEqual(ab.freshness(fetched, 30, now), "stale")

    def test_exactly_at_ttl_boundary_is_fresh(self):
        now = datetime(2026, 5, 26)
        fetched = datetime(2026, 4, 26).isoformat()  # exactly 30 days
        self.assertEqual(ab.freshness(fetched, 30, now), "fresh")


class TestCacheIO(unittest.TestCase):
    def _rec(self):
        return ab.make_record(
            "city::x::1,2", "noaa", {"k": 1}, "city", "2026-05-26T00:00:00", "fresh"
        )

    def test_write_then_read_roundtrip(self):
        with tempfile.TemporaryDirectory() as d:
            rec = self._rec()
            ab.write_cache(d, "noaa", "city::x::1,2", rec)
            self.assertEqual(ab.read_cache(d, "noaa", "city::x::1,2"), rec)

    def test_read_missing_returns_none(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertIsNone(ab.read_cache(d, "noaa", "city::nope::0,0"))

    def test_write_is_atomic_no_temp_files_left(self):
        with tempfile.TemporaryDirectory() as d:
            ab.write_cache(d, "noaa", "city::x::1,2", self._rec())
            files = os.listdir(os.path.join(d, "cache", "noaa"))
            self.assertEqual(files, ["city__x__1_2.json"])
            self.assertFalse(any(f.endswith(".tmp") for f in files))


def _boom():
    raise AssertionError("fetch should not have been called")


def _fail():
    raise RuntimeError("source down")


class TestFetchWithCache(unittest.TestCase):
    NOW = datetime(2026, 5, 26)
    KEY = "city::x::1,2"

    def _seed(self, d, payload, days_ago):
        from datetime import timedelta
        fetched = (self.NOW - timedelta(days=days_ago)).isoformat()
        ab.write_cache(d, "noaa", self.KEY,
                       ab.make_record(self.KEY, "noaa", payload, "city", fetched, "fresh"))

    def test_fresh_cache_hit_skips_primary(self):
        with tempfile.TemporaryDirectory() as d:
            self._seed(d, {"v": 1}, days_ago=5)  # within ttl 30
            rec = ab.fetch_with_cache(d, "noaa", self.KEY, 30, _boom, now=self.NOW)
            self.assertEqual(rec["data_status"], "fresh")
            self.assertEqual(rec["payload"], {"v": 1})

    def test_force_refresh_calls_primary_and_updates_cache(self):
        with tempfile.TemporaryDirectory() as d:
            self._seed(d, {"v": "old"}, days_ago=1)  # fresh, but bypassed
            rec = ab.fetch_with_cache(d, "noaa", self.KEY, 30, lambda: {"v": "new"},
                                      now=self.NOW, force_refresh=True)
            self.assertEqual(rec["data_status"], "fresh")
            self.assertEqual(rec["payload"], {"v": "new"})
            self.assertEqual(ab.read_cache(d, "noaa", self.KEY)["payload"], {"v": "new"})

    def test_primary_success_with_no_cache_caches_result(self):
        with tempfile.TemporaryDirectory() as d:
            rec = ab.fetch_with_cache(d, "noaa", self.KEY, 30, lambda: {"v": 2}, now=self.NOW)
            self.assertEqual(rec["data_status"], "fresh")
            self.assertEqual(rec["payload"], {"v": 2})
            self.assertEqual(ab.read_cache(d, "noaa", self.KEY)["payload"], {"v": 2})

    def test_primary_failure_falls_back_to_stale_cache(self):
        with tempfile.TemporaryDirectory() as d:
            self._seed(d, {"v": "cached"}, days_ago=200)  # stale for ttl 30
            rec = ab.fetch_with_cache(d, "noaa", self.KEY, 30, _fail, now=self.NOW)
            self.assertEqual(rec["data_status"], "stale")
            self.assertEqual(rec["payload"], {"v": "cached"})

    def test_primary_failure_no_cache_uses_alt_as_degraded(self):
        with tempfile.TemporaryDirectory() as d:
            rec = ab.fetch_with_cache(d, "noaa", self.KEY, 30, _fail, now=self.NOW,
                                      alt_fetch=lambda: {"v": "alt"})
            self.assertEqual(rec["data_status"], "degraded")
            self.assertEqual(rec["payload"], {"v": "alt"})
            self.assertEqual(ab.read_cache(d, "noaa", self.KEY)["payload"], {"v": "alt"})

    def test_primary_failure_no_cache_no_alt_is_unavailable(self):
        with tempfile.TemporaryDirectory() as d:
            rec = ab.fetch_with_cache(d, "noaa", self.KEY, 30, _fail, now=self.NOW)
            self.assertEqual(rec["data_status"], "unavailable")
            self.assertEqual(rec["payload"], {})

    def test_forced_refresh_failure_keeps_in_ttl_cache_fresh(self):
        # A forced refresh whose fetch fails must NOT relabel still-in-TTL data as stale.
        with tempfile.TemporaryDirectory() as d:
            self._seed(d, {"v": "cached"}, days_ago=1)  # within ttl 30 -> genuinely fresh
            rec = ab.fetch_with_cache(d, "noaa", self.KEY, 30, _fail,
                                      now=self.NOW, force_refresh=True)
            self.assertEqual(rec["data_status"], "fresh")
            self.assertEqual(rec["payload"], {"v": "cached"})
            self.assertIn("source down", rec.get("degraded_reason", ""))

    def test_stale_fallback_records_reason(self):
        with tempfile.TemporaryDirectory() as d:
            self._seed(d, {"v": "cached"}, days_ago=200)  # genuinely beyond ttl 30
            rec = ab.fetch_with_cache(d, "noaa", self.KEY, 30, _fail, now=self.NOW)
            self.assertEqual(rec["data_status"], "stale")
            self.assertIn("source down", rec.get("degraded_reason", ""))

    def test_unavailable_records_reason(self):
        with tempfile.TemporaryDirectory() as d:
            rec = ab.fetch_with_cache(d, "noaa", self.KEY, 30, _fail, now=self.NOW)
            self.assertIn("source down", rec.get("degraded_reason", ""))

    def test_degraded_alt_records_primary_reason(self):
        with tempfile.TemporaryDirectory() as d:
            rec = ab.fetch_with_cache(d, "noaa", self.KEY, 30, _fail, now=self.NOW,
                                      alt_fetch=lambda: {"v": "alt"})
            self.assertEqual(rec["data_status"], "degraded")
            self.assertIn("source down", rec.get("degraded_reason", ""))

    def test_success_paths_carry_no_reason(self):
        # Fresh-cache hit and primary success stay clean (no spurious breadcrumb).
        with tempfile.TemporaryDirectory() as d:
            self._seed(d, {"v": 1}, days_ago=5)
            self.assertNotIn("degraded_reason",
                             ab.fetch_with_cache(d, "noaa", self.KEY, 30, _boom, now=self.NOW))
        with tempfile.TemporaryDirectory() as d:
            self.assertNotIn("degraded_reason",
                             ab.fetch_with_cache(d, "noaa", self.KEY, 30, lambda: {"v": 2}, now=self.NOW))


class TestGrainKey(unittest.TestCase):
    NOW = datetime(2026, 5, 26)

    def test_grain_key_stamps_achieved_grain_not_requested(self):
        # A neighborhood request whose data resolves only to county must say so.
        with tempfile.TemporaryDirectory() as d:
            rec = ab.fetch_with_cache(d, "src", "neighborhood::x::1,1", 30,
                                      lambda: {"v": 1, "geography_level": "county"},
                                      now=self.NOW, place_grain="neighborhood",
                                      grain_key="geography_level")
            self.assertEqual(rec["place_grain"], "county")

    def test_without_grain_key_uses_requested_grain(self):
        with tempfile.TemporaryDirectory() as d:
            rec = ab.fetch_with_cache(d, "src", "city::x::1,1", 30, lambda: {"v": 1},
                                      now=self.NOW, place_grain="city")
            self.assertEqual(rec["place_grain"], "city")

    def test_missing_grain_value_falls_back_to_requested(self):
        with tempfile.TemporaryDirectory() as d:
            rec = ab.fetch_with_cache(d, "src", "city::x::1,1", 30, lambda: {"v": 1},
                                      now=self.NOW, place_grain="city", grain_key="geography_level")
            self.assertEqual(rec["place_grain"], "city")

    def test_achieved_grain_persists_through_stale_fallback(self):
        # Grain written at fetch time survives a later stale fallback (proves it's cached).
        with tempfile.TemporaryDirectory() as d:
            ab.fetch_with_cache(d, "src", "neighborhood::x::1,1", 30,
                                lambda: {"v": 1, "geography_level": "tract"},
                                now=self.NOW, place_grain="neighborhood", grain_key="geography_level")
            later = self.NOW.replace(year=2027)  # beyond ttl 30
            rec = ab.fetch_with_cache(d, "src", "neighborhood::x::1,1", 30, _fail,
                                      now=later, place_grain="neighborhood", grain_key="geography_level")
            self.assertEqual(rec["data_status"], "stale")
            self.assertEqual(rec["place_grain"], "tract")


class TestCoordCacheKey(unittest.TestCase):
    def test_four_decimal_coordinate_key(self):
        self.assertEqual(ab.coord_cache_key(47.25291, -122.44432), "coord::47.2529,-122.4443")

    def test_same_coordinate_same_key_for_sharing(self):
        # Cost and Dynamism resolve the same point -> identical key -> one shared cache entry.
        self.assertEqual(ab.coord_cache_key(39.7294, -104.8319),
                         ab.coord_cache_key(39.7294, -104.8319))


class TestDebugReraise(unittest.TestCase):
    NOW = datetime(2026, 5, 26)

    def test_habitat_debug_reraises_instead_of_silently_degrading(self):
        with tempfile.TemporaryDirectory() as d:
            os.environ["HABITAT_DEBUG"] = "1"
            try:
                with self.assertRaises(RuntimeError):
                    ab.fetch_with_cache(d, "noaa", "city::x::1,2", 30, _fail, now=self.NOW)
            finally:
                del os.environ["HABITAT_DEBUG"]


if __name__ == "__main__":
    unittest.main()
