"""TDD tests for the Safety adapter (FBI CDE summarized crime).
Pure functions only (no network): place-key parse, agency pick, annual rollup, normalize.
Run: python3 scripts/tests/test_safety.py -v"""
import sys
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(SCRIPTS / "adapters"))
import safety

AG = "Aurora Police Department"


def _months(value, year, n=12):
    """{'MM-YYYY': value} for the first n months of a year."""
    return {f"{m:02d}-{year}": value for m in range(1, n + 1)}


def _cde(agency, agency_monthly, us_monthly, state_monthly, *, state="Colorado",
         actual_monthly=None):
    """Minimal CDE summarized-response shape (rates + actuals)."""
    rates = {
        f"{agency} Offenses": agency_monthly,
        f"{agency} Clearances": {},
        f"{state} Offenses": state_monthly,
        f"{state} Clearances": {},
        "United States Offenses": us_monthly,
        "United States Clearances": {},
    }
    actuals = {f"{agency} Offenses": actual_monthly or {}, f"{agency} Clearances": {}}
    return {"offenses": {"rates": rates, "actuals": actuals}}


class CityStateFromPlaceKey(unittest.TestCase):
    def test_city_and_state(self):
        self.assertEqual(
            safety._city_state_from_place_key("city::aurora-co::39.7,-104.8"),
            ("aurora", "CO"))

    def test_multiword_city(self):
        self.assertEqual(
            safety._city_state_from_place_key("city::elk-grove-ca::38.4,-121.4"),
            ("elk grove", "CA"))

    def test_state_is_last_token(self):
        _, st = safety._city_state_from_place_key(
            "neighborhood::mission-viejo-aurora-co::39.6,-104.8")
        self.assertEqual(st, "CO")


class PickAgency(unittest.TestCase):
    AGENCIES = [
        {"ori": "CO0010100", "agency_name": "Aurora Police Department",
         "agency_type_name": "City", "latitude": 39.71, "longitude": -104.81},
        {"ori": "CO0030000", "agency_name": "Arapahoe County Sheriff's Office",
         "agency_type_name": "County", "latitude": 39.65, "longitude": -104.80},
        {"ori": "CO0010200", "agency_name": "Denver Police Department",
         "agency_type_name": "City", "latitude": 39.74, "longitude": -104.99},
    ]

    def test_prefers_city_name_match(self):
        ori, _ = safety._pick_agency(self.AGENCIES, "aurora", 39.73, -104.83)
        self.assertEqual(ori, "CO0010100")

    def test_proximity_fallback_when_no_name_match(self):
        ori, _ = safety._pick_agency(self.AGENCIES, "mission viejo aurora", 39.72, -104.82)
        self.assertEqual(ori, "CO0010100")

    def test_city_pd_beats_closer_noncity_substring_match(self):
        # Reno bug: 'Reno-Sparks Indian Colony PD' (Tribal) name-contains 'reno' and sits
        # CLOSER to the centroid than 'Reno Police Department' (City) — must still pick the
        # City PD, not the tribal agency.
        agencies = [
            {"ori": "NVTRIBE", "agency_name": "Reno-Sparks Indian Colony Police Department",
             "agency_type_name": "Tribal", "latitude": 39.530, "longitude": -119.814},  # closer
            {"ori": "NV0020100", "agency_name": "Reno Police Department",
             "agency_type_name": "City", "latitude": 39.540, "longitude": -119.860},     # farther
        ]
        ori, name = safety._pick_agency(agencies, "reno", 39.5296, -119.8138)
        self.assertEqual(ori, "NV0020100")
        self.assertEqual(name, "Reno Police Department")


class PickAgencySparseCityState(unittest.TestCase):
    """Hawaii: the whole state has exactly ONE City-type agency (Honolulu PD) and three
    County-type police departments (Maui / Kauai / Hawaii). A 'nearest City-type' fallback
    tier collapses every coordinate in the state onto Honolulu PD — even a Big Island point
    ~150 mi away on another island — because Honolulu is the only City-type agency. The
    correct jurisdiction for a neighbor island is its County police department. (Live shapes
    from CDE byStateAbbr/HI.)"""

    HI = [
        {"ori": "HI0020000", "agency_name": "Honolulu Police Department",
         "agency_type_name": "City", "latitude": 21.304317, "longitude": -157.85077},
        {"ori": "HI0050000", "agency_name": "Maui Police Department",
         "agency_type_name": "County", "latitude": 20.887321, "longitude": -156.48763},
        {"ori": "HI0040000", "agency_name": "Kauai Police Department",
         "agency_type_name": "County", "latitude": 22.012038, "longitude": -159.705965},
        {"ori": "HI0010000", "agency_name": "Hawaii Police Department",
         "agency_type_name": "County", "latitude": 19.716698, "longitude": -155.08688},
        # a special-jurisdiction agency with no coords must never win
        {"ori": "HI0010200", "agency_name": "Department of Law Enforcement: Hawaii Island",
         "agency_type_name": "Other State Agency", "latitude": None, "longitude": None},
    ]

    def test_big_island_resolves_to_hawaii_county_pd(self):
        # Kailua-Kona, Big Island — must NOT be Honolulu PD (different island, ~150 mi away).
        ori, name = safety._pick_agency(self.HI, "kailua", 19.6455, -155.9977)
        self.assertEqual(ori, "HI0010000")
        self.assertEqual(name, "Hawaii Police Department")

    def test_maui_resolves_to_maui_county_pd(self):
        ori, _ = safety._pick_agency(self.HI, "kahului", 20.8684, -156.4656)
        self.assertEqual(ori, "HI0050000")

    def test_kauai_resolves_to_kauai_county_pd(self):
        ori, _ = safety._pick_agency(self.HI, "lihue", 21.9725, -159.3558)
        self.assertEqual(ori, "HI0040000")

    def test_oahu_still_resolves_to_honolulu_pd(self):
        # Regression guard: the lone City agency is still correct for its own island.
        ori, _ = safety._pick_agency(self.HI, "urban honolulu", 21.3243, -157.8476)
        self.assertEqual(ori, "HI0020000")


class PickAgencySubstringAndNeighborhood(unittest.TestCase):
    """Two resolution traps, with live CDE coords:
    (A) 'South Tucson PD' (a 1-sq-mi enclave) name-contains 'tucson' AND sits closer to the
        Tucson centroid than 'Tucson PD' — a bare substring match + nearest tie-break lets the
        enclave (extreme per-capita crime) hijack the pick. A prefix match must win.
    (B) at neighborhood grain the place_key city-token carries the neighborhood prefix
        ('north thornton', 'west elk grove'), so a whole-string name match never fires and
        resolution falls to the nearest agency by HQ — an adjacent city's PD (Northglenn) or a
        co-located county sheriff. Stripping leading words must recover the parent city."""

    TUCSON = [
        {"ori": "AZTPD", "agency_name": "Tucson Police Department",
         "agency_type_name": "City", "latitude": 32.21807, "longitude": -110.9706},
        {"ori": "AZSTPD", "agency_name": "South Tucson Police Department",
         "agency_type_name": "City", "latitude": 32.2026, "longitude": -110.96844},  # closer
    ]

    def test_tucson_not_south_tucson(self):
        ori, name = safety._pick_agency(self.TUCSON, "tucson", 32.1530, -110.8707)
        self.assertEqual(ori, "AZTPD")
        self.assertEqual(name, "Tucson Police Department")

    THORNTON = [
        {"ori": "COTPD", "agency_name": "Thornton Police Department",
         "agency_type_name": "City", "latitude": 39.868996, "longitude": -104.984215},
        {"ori": "CONGPD", "agency_name": "Northglenn Police Department",
         "agency_type_name": "City", "latitude": 39.9079, "longitude": -104.98737},  # closer
    ]

    def test_neighborhood_prefix_strips_to_parent_city(self):
        ori, _ = safety._pick_agency(self.THORNTON, "north thornton", 39.9450, -104.9550)
        self.assertEqual(ori, "COTPD")

    ELK_GROVE = [
        {"ori": "CAEGPD", "agency_name": "Elk Grove Police Department",
         "agency_type_name": "City", "latitude": 38.450011, "longitude": -121.340441},
        {"ori": "CASACSO", "agency_name": "Sacramento County Sheriff's Office",
         "agency_type_name": "County", "latitude": 38.450011, "longitude": -121.340441},  # co-located
    ]

    def test_multiword_city_neighborhood_prefix(self):
        # 'west elk grove' must recover the City PD, not the co-located County Sheriff.
        ori, _ = safety._pick_agency(self.ELK_GROVE, "west elk grove", 38.4250, -121.4250)
        self.assertEqual(ori, "CAEGPD")

    def test_end_to_end_neighborhood_place_key(self):
        agencies = [
            {"ori": "COAUR", "agency_name": "Aurora Police Department",
             "agency_type_name": "City", "latitude": 39.71, "longitude": -104.81},
            {"ori": "COARAP", "agency_name": "Arapahoe County Sheriff's Office",
             "agency_type_name": "County", "latitude": 39.65, "longitude": -104.80},  # closer
        ]
        city, st = safety._city_state_from_place_key(
            "neighborhood::mission-viejo-aurora-co::39.6550,-104.7850")
        self.assertEqual(st, "CO")
        ori, _ = safety._pick_agency(agencies, city, 39.6550, -104.7850)
        self.assertEqual(ori, "COAUR")


class PickAgencyConsolidatedCityCounty(unittest.TestCase):
    """Carson City is a consolidated city-county: its law enforcement is a COUNTY-type
    Sheriff ('Carson City County Sheriff's Office'), with NO City-type 'Carson City' agency.
    The progressive trailing-token candidates for 'carson city' end in the degenerate single
    word 'city', which word-boundary-matches an unrelated City PD in another town ('Boulder
    City Police Department', ~350 mi away). That far enclave must NOT hijack the pick — a
    consolidated city-county resolves to its own nearby Sheriff via the proximity tier.
    (Live shapes from CDE byStateAbbr/NV.)"""

    NV = [
        {"ori": "NVCCSO", "agency_name": "Carson City County Sheriff's Office",
         "agency_type_name": "County", "latitude": 39.1638, "longitude": -119.7674},   # ~1 mi
        {"ori": "NV0020400", "agency_name": "Boulder City Police Department",
         "agency_type_name": "City", "latitude": 35.9786, "longitude": -114.8344},      # ~350 mi
        {"ori": "NVRENO", "agency_name": "Reno Police Department",
         "agency_type_name": "City", "latitude": 39.5296, "longitude": -119.8138},
    ]

    def test_carson_city_resolves_to_its_own_sheriff_not_boulder_city(self):
        ori, name = safety._pick_agency(self.NV, "carson city", 39.1530, -119.7473)
        self.assertEqual(ori, "NVCCSO")
        self.assertEqual(name, "Carson City County Sheriff's Office")

    def test_real_city_pd_still_wins_when_present(self):
        # If a City-type 'Carson City PD' existed, the prefix match must still win over the
        # county sheriff — the fix must not over-correct away from genuine municipal matches.
        agencies = self.NV + [
            {"ori": "NVCCPD", "agency_name": "Carson City Police Department",
             "agency_type_name": "City", "latitude": 39.16, "longitude": -119.75}]
        ori, _ = safety._pick_agency(agencies, "carson city", 39.1530, -119.7473)
        self.assertEqual(ori, "NVCCPD")


class Annual(unittest.TestCase):
    def test_annual_rate_is_sum_of_months(self):
        j = _cde(AG, _months(80.0, "2023"), _months(30.0, "2023"), _months(40.0, "2023"),
                 actual_monthly=_months(317, "2023"))
        a = safety._annual(j, AG)
        self.assertEqual(a[2023]["agency"], 960)
        self.assertEqual(a[2023]["us"], 360)
        self.assertEqual(a[2023]["state"], 480)
        self.assertEqual(a[2023]["months"], 12)
        self.assertEqual(a[2023]["count"], 3804)

    def test_null_months_are_ignored(self):
        # Live CDE returns null for unreported months; sum the reported ones only.
        monthly = _months(80.0, "2023")   # 12 @ 80 = 960
        monthly["12-2023"] = None         # one unreported -> 11 @ 80 = 880, months=11
        j = _cde(AG, monthly, _months(30.0, "2023"), _months(40.0, "2023"))
        a = safety._annual(j, AG)
        self.assertEqual(a[2023]["agency"], 880)
        self.assertEqual(a[2023]["months"], 11)


class Normalize(unittest.TestCase):
    def _two_year(self):
        v = _cde(AG,
                 {**_months(100.0, "2022"), **_months(80.0, "2023")},   # 1200 -> 960
                 {**_months(30.0, "2022"), **_months(30.0, "2023")},    # US 360
                 {**_months(41.0, "2022"), **_months(41.0, "2023")})    # CO 492
        p = _cde(AG,
                 {**_months(360.0, "2022"), **_months(318.5, "2023")},  # 4320 -> 3822
                 {**_months(162.0, "2022"), **_months(162.0, "2023")},  # US 1944
                 {**_months(248.0, "2022"), **_months(248.0, "2023")})  # CO 2976
        return v, p

    def test_headline_latest_complete_year(self):
        out = safety._normalize(*self._two_year(), AG)
        self.assertEqual(out["year"], 2023)
        self.assertEqual(out["violent_crime_per_100k"], 960)
        self.assertEqual(out["property_crime_per_100k"], 3822)
        self.assertFalse(out["partial_year"])

    def test_trend_pct(self):
        out = safety._normalize(*self._two_year(), AG)
        self.assertEqual(out["recent_trend"]["violent_pct"], -20.0)
        self.assertEqual(out["recent_trend"]["property_pct"], -11.5)
        self.assertEqual(out["recent_trend"]["from_year"], 2022)
        self.assertEqual(out["recent_trend"]["to_year"], 2023)

    def test_vs_national_ratio(self):
        out = safety._normalize(*self._two_year(), AG)
        self.assertEqual(out["vs_national"]["violent"], 2.67)   # 960/360
        self.assertEqual(out["vs_national"]["property"], 1.97)  # 3822/1944

    def test_national_and_state_context(self):
        out = safety._normalize(*self._two_year(), AG)
        self.assertEqual(out["national_per_100k"]["violent"], 360)
        self.assertEqual(out["state_per_100k"]["violent"], 492)

    def test_ignores_partial_later_year(self):
        v, p = self._two_year()
        v["offenses"]["rates"][f"{AG} Offenses"].update(_months(70.0, "2024", n=6))
        p["offenses"]["rates"][f"{AG} Offenses"].update(_months(300.0, "2024", n=6))
        out = safety._normalize(v, p, AG)
        self.assertEqual(out["year"], 2023)
        self.assertFalse(out["partial_year"])

    def test_future_all_null_year_ignored(self):
        v, p = self._two_year()
        nulls = {f"{m:02d}-2026": None for m in range(1, 13)}
        v["offenses"]["rates"][f"{AG} Offenses"].update(nulls)
        p["offenses"]["rates"][f"{AG} Offenses"].update(dict(nulls))
        out = safety._normalize(v, p, AG)
        self.assertEqual(out["year"], 2023)
        self.assertFalse(out["partial_year"])

    def test_missing_prior_year_trend_none(self):
        v = _cde(AG, _months(80.0, "2023"), _months(30.0, "2023"), _months(40.0, "2023"))
        p = _cde(AG, _months(318.5, "2023"), _months(162.0, "2023"), _months(248.0, "2023"))
        out = safety._normalize(v, p, AG)
        self.assertIsNone(out["recent_trend"]["violent_pct"])
        self.assertIsNone(out["recent_trend"]["property_pct"])


class CountryGuard(unittest.TestCase):
    """FBI CDE is US-only. A country/international place_key must degrade honestly to
    `unavailable` rather than fail dirty — the place_key suffix 'pt' would otherwise be
    parsed as a US state and CDE queried for a bogus state 'PT'."""

    def test_country_level_never_calls_cde_and_is_unavailable(self):
        import tempfile
        from datetime import datetime
        orig = (safety.ab.load_secrets, safety.ab.http_json)
        safety.ab.load_secrets = lambda *a, **k: {"DATA_GOV_API_KEY": "x"}

        def _boom(*a, **k):
            raise AssertionError("CDE must not be called for a country place_key")

        safety.ab.http_json = _boom
        try:
            with tempfile.TemporaryDirectory() as d:
                rec = safety.fetch("country::portugal-pt::39.5000,-8.0000",
                                   "39.5000,-8.0000", "country", d,
                                   now=datetime(2026, 5, 28))
            self.assertEqual(rec["data_status"], "unavailable")
            self.assertIn("US-only", rec.get("degraded_reason", ""))
        finally:
            safety.ab.load_secrets, safety.ab.http_json = orig


class FlattenAgencies(unittest.TestCase):
    """byStateAbbr normally returns {county: [agency_dict, ...]}. A malformed/error response
    (bogus state, or a transient FBI error on a valid state) must yield NO agencies — never
    non-dict elements that crash _pick_agency with an AttributeError later masked as a
    generic outage (the bug behind the 2026-06 gem-hunt all-unavailable run)."""

    A = {"ori": "X", "agency_name": "Aurora Police Department",
         "agency_type_name": "City", "latitude": 39.7, "longitude": -104.8}

    def test_normal_shape(self):
        listing = {"Arapahoe County": [self.A], "Denver County": [dict(self.A, ori="Y")]}
        out = safety._flatten_agencies(listing)
        self.assertEqual(len(out), 2)
        self.assertTrue(all(isinstance(a, dict) for a in out))

    def test_error_dict_shape_yields_empty(self):
        # FBI returns an error object for a bogus state; old inline code iterated the string.
        self.assertEqual(
            safety._flatten_agencies({"error": "Invalid state abbreviation"}), [])

    def test_non_dict_listing_yields_empty(self):
        self.assertEqual(safety._flatten_agencies("Not Found"), [])
        self.assertEqual(safety._flatten_agencies(None), [])

    def test_mixed_county_values_keep_only_dicts(self):
        listing = {"Bad": "oops", "Good": [self.A, "junk", 5]}
        self.assertEqual(safety._flatten_agencies(listing), [self.A])

    def test_pick_agency_survives_flattened_error(self):
        # End-to-end: a flattened error response -> no agency, no AttributeError crash.
        self.assertEqual(
            safety._pick_agency(safety._flatten_agencies({"error": "x"}),
                                "aurora", 39.7, -104.8),
            (None, None))


class MalformedStateGuard(unittest.TestCase):
    """A domestic place_key whose suffix isn't a US state (e.g. an un-suffixed slug
    'city::cottonwood::...') must degrade with a clear reason and NEVER hit the network —
    instead of querying a bogus state ('COTTONWOOD') and masking the resulting crash."""

    def _fetch_blocking_network(self, place_key, geocode):
        import tempfile
        from datetime import datetime
        orig = (safety.ab.load_secrets, safety.ab.http_json)
        safety.ab.load_secrets = lambda *a, **k: {"DATA_GOV_API_KEY": "x"}

        def _boom(*a, **k):
            raise AssertionError("network must not be called for a malformed place_key")

        safety.ab.http_json = _boom
        try:
            with tempfile.TemporaryDirectory() as d:
                return safety.fetch(place_key, geocode, "city", d,
                                    now=datetime(2026, 6, 3))
        finally:
            safety.ab.load_secrets, safety.ab.http_json = orig

    def test_no_state_suffix_degrades_with_clear_reason(self):
        rec = self._fetch_blocking_network(
            "city::cottonwood::34.7508,-111.9840", "34.7508,-111.9840")
        self.assertEqual(rec["data_status"], "unavailable")
        self.assertIn("US state", rec.get("degraded_reason", ""))

    def test_partial_suffix_degrades(self):
        rec = self._fetch_blocking_network(
            "city::chino-valley::34.7398,-112.4060", "34.7398,-112.4060")
        self.assertEqual(rec["data_status"], "unavailable")
        self.assertIn("US state", rec.get("degraded_reason", ""))

    def test_valid_state_passes_guard_and_reaches_network(self):
        # The guard must NOT block well-formed keys: http_json IS invoked for a valid state.
        import tempfile
        from datetime import datetime
        called = {"n": 0}
        orig = (safety.ab.load_secrets, safety.ab.http_json)
        safety.ab.load_secrets = lambda *a, **k: {"DATA_GOV_API_KEY": "x"}

        def _count(*a, **k):
            called["n"] += 1
            return {}  # empty listing -> clean degrade, but network WAS reached

        safety.ab.http_json = _count
        try:
            with tempfile.TemporaryDirectory() as d:
                safety.fetch("city::cottonwood-az::34.7508,-111.9840",
                             "34.7508,-111.9840", "city", d, now=datetime(2026, 6, 3))
        finally:
            safety.ab.load_secrets, safety.ab.http_json = orig
        self.assertGreaterEqual(called["n"], 1)


if __name__ == "__main__":
    unittest.main()
