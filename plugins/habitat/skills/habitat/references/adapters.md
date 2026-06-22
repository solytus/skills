# Adapters, lookups & fallbacks (Phase 1b)

Three handling modes per dimension: **cached adapter** / **utility lookup** /
**reason-with-search** (`reason-with-search.md`). This file catalogs the deterministic
two. Implemented for real in Phase 3; stubs return placeholder records until then.

## Cached adapters (6)

Pattern: `fetch from primary → normalize → cache locally with TTL → return record with
freshness metadata`. Envelope: `{place_key, source, fetched_at, place_grain, data_status,
payload:{...}}`, `data_status ∈ fresh | stale | degraded | unavailable`. A fallback record
also carries an optional `degraded_reason` (the failure cause) — additive, degrades gracefully
on old records.

| # | Adapter | Primary source (V1 as-built) | TTL | Returns (sub-fields) | Fallback chain |
|---|---|---|---|---|---|
| 1 | Climate | Open-Meteo archive (keyless) † | 90 d | temp ranges, precip, sunlight *(humidity/season → Phase-2 / Claude narrative)* | primary → stale cache → (NOAA NCEI normals = Phase-2) |
| 2 | Cost | Census ACS (`CENSUS_API_KEY`) | 30 d | median household income, median residential rent, housing cost burden, demographics (pop, median age, **Asian-alone count + %** via B02001_005E — backs the "Asian population ≥ X%" must_have deterministically), education attainment | primary → stale cache → gap |
| 3 | Safety | FBI CDE (`DATA_GOV_API_KEY`), agency/city grain | 180 d* | violent + property crime per 100k, raw counts, YoY trend, vs-national + vs-state ratios | primary → stale cache → gap (city open-data = Phase-2 alt) |
| 4 | Air quality | EPA AirNow (`EPA_AIRNOW_API_KEY`) | 24 h | current AQI, category, dominant pollutant, PM2.5/ozone | primary → stale cache → **Open-Meteo AQ (keyless)** |
| 5 | Social signals | Reddit + Google News RSS | Reddit 7 d / News 3 d | recent threads + tone, local headlines + summary | primary → stale cache → reason-with-WebFetch |
| 6 | Economic dynamism | BLS LAUS (county, `BLS_API_KEY`) | 30 d | unemployment, employment growth 1y/5y *(wages/business-formation/industries → Phase-2)* | primary → stale cache → gap |

\* Safety's 180-day TTL acknowledges FBI data publishes annually and lags ~18 months
regardless of fetch recency. The social adapter exposes one interface but fans out to
Reddit + Google News RSS internally (separate caches/TTLs).

**† Phase-3 as-built notes (2026-05-27).** Climate V1 uses **Open-Meteo** (keyless; one call
yields temp/precip/sunshine aggregates over 3 yrs); NOAA NCEI official 1991-2020 normals +
nearest-station resolution are a Phase-2 enrichment (the validated `NOAA_CDO_TOKEN` is ready).
Air quality's tier-3 fallback is Open-Meteo AQ (PurpleAir dropped — paid). Dynamism is BLS-LAUS
only for V1 (Census BDS county API 404s; QCEW wages/industries deferred). **Safety went live
2026-05-28** (FBI CDE recovered): it resolves the place to a police agency (ORI) via CDE's
by-state agency list — name-match on the city, else nearest City-type agency by haversine — then
pulls summarized violent + property crime, sums monthly per-100k rates to annual, and reports the
latest *complete* (12 reported months) year + YoY trend + vs-national/vs-state ratios. Null
(unreported/future) months are skipped, so a partial current year never understates the headline.
Per-city open-data remains the documented Phase-2 alternative tier. Cost/Dynamism resolve FIPS via
shared `geo.py` (Census geocoder), cached per-coordinate under `census-geo` so the two share one
call; Internet/Hazard likewise share one FCC per-coordinate lookup (`fcc-area`); Safety derives
city+state from the `place_key`; Air/Climate/Walkability are lat/lon-direct. A cold eval resolves
each coordinate **once** (not four times), and the long-TTL coordinate caches keep the dependents
alive through a transient geocoder/FCC outage.

**Social fallback — reason-with-WebFetch source hints (keyless, no key; verified 2026-05-27).**
When Reddit is unavailable (or pending API access), the social adapter's reason-with-WebFetch
fallback draws resident signal from: **AreaVibes** (`areavibes.com/<city-state>/` — livability
grades + resident reviews, city/neighborhood), **city-data.com** (`/city/<City-State>.html` +
`/forum/<state>/` — long-form resident voice), **Numbeo** (`numbeo.com/quality-of-life|crime/in/<City>`
— resident-perception indices; cache quarterly), and **Patch.com** (`patch.com/<state>/<city>` —
hyperlocal news supplementing Google News RSS; coverage gaps for smaller cities). All keyless,
WebFetch-able, light per-eval touch; cache results per session. **Municipal 311 open data**
(objective lived-friction signal) is a Phase-2 candidate — needs a per-city portal registry.

## Utility lookups (5)

Small deterministic functions, no LLM. Same record envelope so the footer is uniform.
#4 walkability and #5 hazard were promoted from reason-with-search (Phase-3a token-collapse
wins — keyless, structured, neighborhood/county grain) and cache via `fetch_with_cache`.

| # | Lookup | Source (V1 as-built) | Behavior |
|---|---|---|---|
| 1 | Family distance | Census Geocoder + bundled Gazetteer centroids + `config.family_locations` | distance + drive/flight estimate to each family location |
| 2 | Internet quality | FCC `geo.fcc.gov` (keyless) | block/county/state FIPS; provider availability + speeds → reason-with-search (BDC API token-gated) |
| 3 | Airport access | bundled OurAirports CSV + haversine (no runtime API) | nearest commercial airport + nearest large hub, ground-time estimates |
| 4 | Walkability | EPA National Walkability Index ArcGIS (keyless) | block-group NatWalkInd 1–20 + category |
| 5 | Hazard | FEMA NRI county FeatureServer + NFHL flood point (keyless) | composite + per-hazard risk scores, flood zone / SFHA flag |

## TTL bands

Fast (1–7 d): air quality, social news. · Moderate (14–30 d): cost, dynamism, social
Reddit. · Slow (60–90 d): climate. · Lag-acknowledged (180 d): safety.

## Freshness & fallback policy

- Every response carries `source` + `fetched_at` + `place_grain` + `data_status`.
- **Stale-on-failure:** if a fresh fetch fails/rate-limits, use the cached value with a
  marker reflecting its *actual* freshness — a failed **forced** refresh over still-in-TTL
  data stays `fresh` (not falsely `stale`); only genuinely TTL-expired cache reads `stale`.
  Honest > blocking. Never fabricate.
- **Failure breadcrumb:** any fallback record carries `degraded_reason` (the cause), so a
  degradation is debuggable rather than silent. `HABITAT_DEBUG=1` re-raises unexpected fetch
  errors instead of degrading — surfaces a code bug in development that would otherwise look
  like a source outage.
- **User refresh:** the evaluate workflow accepts a natural-language refresh modifier
  ("with fresh data", "force refresh") that bypasses TTLs for that place.
- **Fallback order per adapter:** primary → stale cache (marker) → alternative source /
  graceful gap.

## Place-grain matrix (degraded-mode summary)

The geo-resolving adapters (**cost / dynamism / safety**) stamp the grain *actually
achieved* (`tract` / `place` / `county` / `agency`), so a coarser fallback shows up as
`place_grain` ≠ the requested level rather than over-claiming. Lat/lon-direct sources stamp
the requested level; their native grain (walkability = block-group, hazard = county) sits in
the payload. The narrative surfaces fallback honestly.

- **City / county:** native for nearly all adapters and lookups.
- **State / country:** Census/BLS native; climate & air quality coarsen or go N/A;
  most reason-with-search dimensions return meta-summaries.
- **Neighborhood:** Cost/Safety/Dynamism fall back to city `[city-level fallback]`;
  climate/air usually city/county is fine; walkability/healthcare/education/nature are
  most informative here.
- **Property:** structured adapters fall back to neighborhood `[neighborhood-level
  fallback]`; family distance + internet are property-grain; walkability becomes
  property-radius native.

## International (country grain) — source/mode map

US adapters do NOT transfer (FIPS/Census/FBI/BLS/FCC/FEMA are US-only); **safety returns
`unavailable` at `country` level by design**, air quality uses the keyless Open-Meteo path.
Country grain is served by a separate backbone (see `evaluate-country.md`):

| Dimension | Source | Mode |
|---|---|---|
| Climate / Air | Open-Meteo / Open-Meteo-AQ (reused adapters) | live, `country-centroid` (coarse) |
| Economy, labor, cost-coarse, governance (WGI), internet, health | World Bank (`worldbank.py`, no auth, ISO3, per-indicator, empty→degrade) | live cached 90 d |
| Safety | Global Peace Index (`gpi`) | bundled annual *(awaiting data drop → degrade/reason)* |
| Belonging / diaspora | UN Migrant Stock origin×dest (`diaspora`) | bundled annual *(awaiting data drop → reason)* |
| Short-stay TRAVEL access | Passport Index (`passport`) | bundled — **firewalled from fit/verdict** |
| Cost in home currency | Frankfurter (`fx`) | live cached |
| Residence/visa, relocation friction, nature, city belonging | reason-with-search | ≤3 passes / ≤6 fetches |

Identity/centroid/currency/tz come from `country_lookups.resolve_country` over
`country_centroids.csv`. Bundled vintages/licenses + `--check-stale` live in
`datasets/SOURCES.md`.
