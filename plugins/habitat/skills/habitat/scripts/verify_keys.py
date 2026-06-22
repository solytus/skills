"""Habitat key verifier — probe one tiny endpoint per key in secrets.env and report
OK / FAIL / SKIP. Run: python3 scripts/verify_keys.py
Exit code is non-zero if any configured key FAILs (missing keys are SKIP, not failures)."""
import base64
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import adapter_base as ab  # noqa: E402

OK, FAIL, SKIP = "OK  ", "FAIL", "SKIP"


def _err(e):
    return str(e).splitlines()[0][:90]


def check_census(k):
    if not k:
        return SKIP, "not set"
    try:
        r = ab.http_json("https://api.census.gov/data/2023/acs/acs5?get=NAME,B19013_001E"
                         f"&for=place:70000&in=state:53&key={k}")
        return OK, f"Tacoma median HH income ${r[1][1]}"
    except Exception as e:  # noqa: BLE001
        return FAIL, _err(e)


def check_bls(k):
    if not k:
        return SKIP, "not set"
    try:
        r = ab.http_json("https://api.bls.gov/publicAPI/v2/timeseries/data/",
                         data={"seriesid": ["LNS14000000"], "startyear": "2024",
                               "endyear": "2024", "registrationkey": k})
        st = r.get("status")
        return (OK, st) if st == "REQUEST_SUCCEEDED" else (FAIL, st)
    except Exception as e:  # noqa: BLE001
        return FAIL, _err(e)


def check_airnow(k):
    if not k:
        return SKIP, "not set"
    try:
        r = ab.http_json("https://www.airnowapi.org/aq/observation/zipCode/current/"
                         f"?format=application/json&zipCode=98402&distance=50&API_KEY={k}")
        return OK, f"{len(r)} current observation(s)"
    except Exception as e:  # noqa: BLE001
        return FAIL, _err(e)


def check_datagov(k):
    if not k:
        return SKIP, "not set"
    try:
        # FEC is a fast, light endpoint behind the SAME api.data.gov key as the FBI CDE.
        r = ab.http_json(f"https://api.open.fec.gov/v1/candidates/?per_page=1&api_key={k}")
        return OK, f"api.data.gov key valid (FEC: {r['pagination']['count']} candidates)"
    except Exception as e:  # noqa: BLE001
        return FAIL, _err(e)


def check_noaa(k):
    if not k:
        return SKIP, "not set"
    try:
        r = ab.http_json("https://www.ncdc.noaa.gov/cdo-web/api/v2/datasets?limit=1",
                         headers={"token": k})
        return (OK, "CDO token accepted") if r.get("results") else (FAIL, "no results")
    except Exception as e:  # noqa: BLE001
        return FAIL, _err(e)


def check_reddit(cid, csec):
    if not cid or not csec:
        return SKIP, "not set (request pending)"
    try:
        auth = base64.b64encode(f"{cid}:{csec}".encode()).decode()
        r = ab.http_json("https://www.reddit.com/api/v1/access_token",
                         headers={"Authorization": f"Basic {auth}",
                                  "Content-Type": "application/x-www-form-urlencoded"},
                         data=b"grant_type=client_credentials")
        return (OK, "OAuth token issued") if r.get("access_token") else (FAIL, "no access_token")
    except Exception as e:  # noqa: BLE001
        return FAIL, _err(e)


def main():
    s = ab.load_secrets()
    rows = [
        ("DATA_GOV_API_KEY", check_datagov(s.get("DATA_GOV_API_KEY"))),
        ("BLS_API_KEY", check_bls(s.get("BLS_API_KEY"))),
        ("EPA_AIRNOW_API_KEY", check_airnow(s.get("EPA_AIRNOW_API_KEY"))),
        ("CENSUS_API_KEY", check_census(s.get("CENSUS_API_KEY"))),
        ("NOAA_CDO_TOKEN", check_noaa(s.get("NOAA_CDO_TOKEN"))),
        ("REDDIT_CLIENT_ID/SECRET", check_reddit(s.get("REDDIT_CLIENT_ID"),
                                                 s.get("REDDIT_CLIENT_SECRET"))),
    ]
    failed = 0
    for name, (status, detail) in rows:
        if status == FAIL:
            failed += 1
        print(f"  [{status}] {name:<24} {detail}")
    print(f"\n{sum(1 for _, (st, _) in rows if st == OK)} OK, "
          f"{failed} FAIL, {sum(1 for _, (st, _) in rows if st == SKIP)} SKIP")
    raise SystemExit(1 if failed else 0)


if __name__ == "__main__":
    main()
