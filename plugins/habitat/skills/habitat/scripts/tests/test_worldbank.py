"""TDD tests for the World Bank adapter (country-grain workhorse).
_normalize is pure (canned WB JSON rows); fetch tested with stubbed network + resolver.
Run: python3 scripts/tests/test_worldbank.py -v"""
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(SCRIPTS / "adapters"))
import worldbank as wb

FMAP = {"NY.GDP.PCAP.PP.CD": "gdp_per_capita_ppp", "SL.UEM.TOTL.ZS": "unemployment_pct"}


def row(code, year, value):
    return {"indicator": {"id": code, "value": ""}, "countryiso3code": "PRT",
            "date": str(year), "value": value}


class Normalize(unittest.TestCase):
    def test_picks_latest_non_null_per_indicator(self):
        rows = [
            row("NY.GDP.PCAP.PP.CD", 2021, None),
            row("NY.GDP.PCAP.PP.CD", 2022, 35000.0),
            row("NY.GDP.PCAP.PP.CD", 2023, None),     # latest reported year is null -> skip it
            row("SL.UEM.TOTL.ZS", 2023, 6.5),
        ]
        p = wb._normalize(rows, FMAP)
        self.assertEqual(p["gdp_per_capita_ppp"], 35000.0)
        self.assertEqual(p["years"]["gdp_per_capita_ppp"], 2022)
        self.assertEqual(p["unemployment_pct"], 6.5)
        self.assertEqual(p["years"]["unemployment_pct"], 2023)

    def test_oldest_year_summarizes_freshness(self):
        rows = [row("NY.GDP.PCAP.PP.CD", 2022, 35000.0), row("SL.UEM.TOTL.ZS", 2019, 7.0)]
        self.assertEqual(wb._normalize(rows, FMAP)["oldest_year"], 2019)

    def test_string_value_is_coerced(self):
        rows = [row("NY.GDP.PCAP.PP.CD", 2022, "35000.5")]
        self.assertEqual(wb._normalize(rows, FMAP)["gdp_per_capita_ppp"], 35000.5)

    def test_missing_indicator_is_none_but_does_not_raise(self):
        rows = [row("NY.GDP.PCAP.PP.CD", 2022, 35000.0)]   # unemployment absent
        p = wb._normalize(rows, FMAP)
        self.assertIsNone(p["unemployment_pct"])
        self.assertNotIn("unemployment_pct", p["years"])

    def test_empty_rows_raises(self):
        with self.assertRaises(ValueError):
            wb._normalize([], FMAP)

    def test_all_null_raises(self):
        # An empty/all-null WB response must RAISE so fetch_with_cache degrades to
        # cache/gap rather than caching an empty record as 'fresh' (fabrication-by-omission).
        rows = [row("NY.GDP.PCAP.PP.CD", 2022, None), row("SL.UEM.TOTL.ZS", 2023, None)]
        with self.assertRaises(ValueError):
            wb._normalize(rows, FMAP)


class Fetch(unittest.TestCase):
    NOW = datetime(2026, 5, 28)

    def _patch(self, http_return):
        orig = (wb.cl.resolve_country, wb.ab.http_json)
        wb.cl.resolve_country = lambda *a, **k: {"iso3": "PRT", "iso2": "PT"}
        wb.ab.http_json = http_return
        return orig

    def _restore(self, orig):
        wb.cl.resolve_country, wb.ab.http_json = orig

    def test_success_stamps_country_grain(self):
        data = [{"page": 1}, [row("NY.GDP.PCAP.PP.CD", 2022, 35000.0)]]
        orig = self._patch(lambda *a, **k: data)
        try:
            with tempfile.TemporaryDirectory() as d:
                rec = wb.fetch("country::portugal-pt::39.5000,-8.0000", "39.5000,-8.0000",
                               "country", d, now=self.NOW)
            self.assertEqual(rec["data_status"], "fresh")
            self.assertEqual(rec["place_grain"], "country")
            self.assertEqual(rec["payload"]["gdp_per_capita_ppp"], 35000.0)
        finally:
            self._restore(orig)

    def test_empty_response_degrades_not_fresh(self):
        orig = self._patch(lambda *a, **k: [{"message": [{"value": "no data"}]}])  # no [1]
        try:
            with tempfile.TemporaryDirectory() as d:
                rec = wb.fetch("country::portugal-pt::39.5000,-8.0000", "39.5000,-8.0000",
                               "country", d, now=self.NOW)
            self.assertEqual(rec["data_status"], "unavailable")
            self.assertEqual(rec["payload"], {})  # empty, not a fabricated fresh record
        finally:
            self._restore(orig)


if __name__ == "__main__":
    unittest.main()
