"""TDD tests for country_lookups (international extension).
Pure/deterministic functions over fixture CSVs + canned JSON (no network).
Run: python3 scripts/tests/test_country_lookups.py -v"""
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))
import country_lookups as cl

CENTROIDS = """iso2,iso3,name,capital,lat,lon,tz,region,subregion
PT,PRT,Portugal,Lisbon,39.5,-8.0,Europe/Lisbon,Europe,Southern Europe
JP,JPN,Japan,Tokyo,36.2,138.25,Asia/Tokyo,Asia,Eastern Asia
US,USA,United States,Washington,39.8283,-98.5795,America/New_York,Americas,Northern America
"""


def _centroids_file(d):
    p = Path(d) / "country_centroids.csv"
    p.write_text(CENTROIDS)
    return str(p)


class ResolveCountry(unittest.TestCase):
    def test_resolves_by_iso2(self):
        with tempfile.TemporaryDirectory() as d:
            r = cl.resolve_country("PT", path=_centroids_file(d))
            self.assertEqual(r["iso2"], "PT")
            self.assertEqual(r["iso3"], "PRT")
            self.assertEqual(r["name"], "Portugal")
            self.assertEqual(r["normalized_name"], "portugal-pt")
            self.assertEqual(r["geocode"], "39.5000,-8.0000")
            self.assertEqual(r["tz"], "Europe/Lisbon")

    def test_resolves_by_iso3(self):
        with tempfile.TemporaryDirectory() as d:
            r = cl.resolve_country("PRT", path=_centroids_file(d))
            self.assertEqual(r["iso2"], "PT")

    def test_resolves_by_name_case_insensitive(self):
        with tempfile.TemporaryDirectory() as d:
            r = cl.resolve_country("portugal", path=_centroids_file(d))
            self.assertEqual(r["iso3"], "PRT")

    def test_unknown_returns_empty(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(cl.resolve_country("Atlantis", path=_centroids_file(d)), {})

    def test_negative_longitude_truncates(self):
        with tempfile.TemporaryDirectory() as d:
            r = cl.resolve_country("JP", path=_centroids_file(d))
            self.assertEqual(r["geocode"], "36.2000,138.2500")


GPI = """iso3,iso2,country,score,rank,year
PRT,PT,Portugal,1.301,7,2024
JPN,JP,Japan,1.336,9,2024
"""

DIASPORA = """dest_iso2,origin_iso2,origin_name,migrants,year
PT,KR,"Korea, Rep.",2500,2024
PT,CN,China,15000,2024
PT,JP,Japan,800,2024
PT,BR,Brazil,400000,2024
"""

PASSPORT = """passport_iso2,dest_iso2,requirement
US,PT,90
KR,PT,90
US,JP,90
US,CN,visa required
KR,CN,visa free
"""

KEY = "country::portugal-pt::39.5000,-8.0000"


def _file(d, name, text):
    p = Path(d) / name
    p.write_text(text)
    return str(p)


class Gpi(unittest.TestCase):
    def test_returns_score_and_rank(self):
        with tempfile.TemporaryDirectory() as d:
            rec = cl.gpi(KEY, "PT", path=_file(d, "gpi.csv", GPI), now=datetime(2026, 5, 28))
            self.assertEqual(rec["data_status"], "fresh")
            self.assertEqual(rec["place_grain"], "country")
            self.assertEqual(rec["payload"]["score"], 1.301)
            self.assertEqual(rec["payload"]["rank"], 7)
            self.assertEqual(rec["payload"]["year"], 2024)

    def test_unknown_country_unavailable(self):
        with tempfile.TemporaryDirectory() as d:
            rec = cl.gpi(KEY, "ZZ", path=_file(d, "gpi.csv", GPI), now=datetime(2026, 5, 28))
            self.assertEqual(rec["data_status"], "unavailable")


class Diaspora(unittest.TestCase):
    def test_sums_belonging_origin_set(self):
        with tempfile.TemporaryDirectory() as d:
            rec = cl.diaspora(KEY, "PT", ["KR", "CN", "JP"],
                              path=_file(d, "diaspora.csv", DIASPORA), now=datetime(2026, 5, 28))
            self.assertEqual(rec["payload"]["total_from_origins"], 18300)
            self.assertEqual(rec["payload"]["by_origin"]["CN"], 15000)
            self.assertEqual(rec["payload"]["top_origin"], "CN")  # largest of the requested set
            self.assertEqual(rec["payload"]["year"], 2024)
            self.assertEqual(rec["data_status"], "fresh")

    def test_ignores_origins_outside_the_set(self):
        with tempfile.TemporaryDirectory() as d:
            rec = cl.diaspora(KEY, "PT", ["KR"],
                              path=_file(d, "diaspora.csv", DIASPORA), now=datetime(2026, 5, 28))
            self.assertEqual(rec["payload"]["total_from_origins"], 2500)  # not Brazil's 400000

    def test_no_matches_unavailable(self):
        with tempfile.TemporaryDirectory() as d:
            rec = cl.diaspora(KEY, "PT", ["ZZ"],
                              path=_file(d, "diaspora.csv", DIASPORA), now=datetime(2026, 5, 28))
            self.assertEqual(rec["data_status"], "unavailable")


class Passport(unittest.TestCase):
    def test_personalized_best_status(self):
        with tempfile.TemporaryDirectory() as d:
            rec = cl.passport(KEY, ["US"], "PT",
                              path=_file(d, "p.csv", PASSPORT), now=datetime(2026, 5, 28))
            self.assertEqual(rec["payload"]["best_status"], "90")
            self.assertTrue(rec["payload"]["short_stay_only"])  # tourist access, NOT residence
            self.assertFalse(rec["payload"]["generic"])

    def test_multi_citizenship_picks_least_restrictive(self):
        with tempfile.TemporaryDirectory() as d:
            rec = cl.passport(KEY, ["US", "KR"], "CN",
                              path=_file(d, "p.csv", PASSPORT), now=datetime(2026, 5, 28))
            # US->CN visa required, KR->CN visa free -> best is visa free
            self.assertEqual(rec["payload"]["best_status"], "visa free")

    def test_generic_mode_reports_accessibility_proxy(self):
        with tempfile.TemporaryDirectory() as d:
            rec = cl.passport(KEY, [], "PT",
                              path=_file(d, "p.csv", PASSPORT), now=datetime(2026, 5, 28))
            self.assertTrue(rec["payload"]["generic"])
            self.assertIsNone(rec["payload"]["best_status"])
            # both passports in data reach PT visa-free -> proxy 2/2
            self.assertEqual(rec["payload"]["visa_free_count"], 2)
            self.assertEqual(rec["payload"]["passports_in_data"], 2)


class Fx(unittest.TestCase):
    def test_returns_rate(self):
        orig = cl.ab.http_json
        cl.ab.http_json = lambda *a, **k: {"amount": 1.0, "base": "USD",
                                           "date": "2026-05-28", "rates": {"EUR": 0.92}}
        try:
            rec = cl.fx(KEY, "USD", "EUR", now=datetime(2026, 5, 28))
            self.assertEqual(rec["payload"]["rate"], 0.92)
            self.assertEqual(rec["payload"]["base"], "USD")
            self.assertEqual(rec["payload"]["dest"], "EUR")
            self.assertEqual(rec["data_status"], "fresh")
        finally:
            cl.ab.http_json = orig

    def test_same_currency_is_identity(self):
        rec = cl.fx(KEY, "USD", "USD", now=datetime(2026, 5, 28))
        self.assertEqual(rec["payload"]["rate"], 1.0)


if __name__ == "__main__":
    unittest.main()
