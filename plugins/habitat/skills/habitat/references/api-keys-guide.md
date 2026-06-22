# API keys guide

Habitat uses **free-tier** keys only. Every one is optional — an unset key makes its adapter
degrade gracefully (`unavailable`, never fabricated), so you can start with none and add as you
go. Put values in `~/.solytus/habitat/secrets.env` (copied from `secrets.env.example`; lives outside
the skill so updates never touch it; gitignored, never committed).

> Registration URLs change; if one 404s, search the provider's developer/API page. All of these
> were free tiers at last check — confirm current terms when you sign up.

| Key | Powers | Register | Auth |
|---|---|---|---|
| `CENSUS_API_KEY` | Cost (Census ACS) + Dynamism (BDS) | api.census.gov/data/key_signup.html | `&key=` query param |
| `DATA_GOV_API_KEY` | Safety (FBI CDE); shared by FEC/NPS | api.data.gov/signup/ | `?api_key=` or `X-Api-Key` header |
| `NOAA_CDO_TOKEN` | Climate (NOAA NCEI) | ncdc.noaa.gov/cdo-web/token | `token:` header |
| `EPA_AIRNOW_API_KEY` | Air quality (EPA AirNow) | docs.airnowapi.org/account/request/ | `&API_KEY=` query param |
| `BLS_API_KEY` | Lifts BLS LAUS/QCEW 25→500 queries/day | data.bls.gov/registrationEngine/ | `registrationkey` in JSON POST body |
| `REDDIT_CLIENT_ID` + `REDDIT_CLIENT_SECRET` | Reddit half of Social signals | reddit.com/prefs/apps → create a "script" app | OAuth client-credentials; descriptive User-Agent required |

## Suggested fill order

1. **`CENSUS_API_KEY`** — highest leverage; powers cost + dynamism, mandatory for those queries.
2. **`DATA_GOV_API_KEY`** — instant signup; unlocks crime/safety.
3. The rest as you want richer signals. Climate and air quality have keyless fallbacks
   (Open-Meteo), so they work — if coarser — without their keys.

After filling in, verify:

```bash
set -a && . ./secrets.env && set +a
python3 scripts/verify_keys.py     # OK / FAIL / SKIP per key
```
