# Adapters, lookups & fallbacks

Three handling modes per dimension: **cached adapter**, **utility lookup**, or
**reason-with-search** (`reason-with-search.md`). This file catalogs the deterministic two.

## Cached adapters (6)

Pattern: `fetch from primary → normalize → cache locally with TTL → return record with
freshness metadata`. Envelope: `{place_key, source, fetched_at, place_grain, data_status,
payload:{...}}`, `data_status ∈ fresh | stale | degraded | unavailable`. A fallback record
may also carry `degraded_reason` (the failure cause) — additive, absent on older records.

| # | Adapter | Primary source | TTL | Returns | Fallback chain |
|---|---|---|---|---|---|
| 1 | Climate | Open-Meteo archive (keyless) | 90 d | temp ranges, precip, sunlight *(humidity/season → Claude narrative)* | primary → stale cache → gap |
| 2 | Cost | Census ACS (`CENSUS_API_KEY`) | 30 d | median household income, median residential rent, housing cost burden, demographics (pop, median age, **Asian-alone count + %** via B02001_005E, backing an "Asian population ≥ X%" must_have deterministically), education attainment | primary → stale cache → gap |
| 3 | Safety | FBI CDE (`DATA_GOV_API_KEY`), agency/city grain | 180 d* | violent + property crime per 100k, raw counts, YoY trend, vs-national + vs-state ratios | primary → stale cache → gap |
| 4 | Air quality | EPA AirNow (`EPA_AIRNOW_API_KEY`) | 24 h | current AQI, category, dominant pollutant, PM2.5/ozone | primary → stale cache → **Open-Meteo AQ (keyless)** |
| 5 | Social signals | Reddit + Google News RSS | Reddit 7 d / News 3 d | recent threads + tone, local headlines + summary | primary → stale cache → reason-with-WebFetch (below) |
| 6 | Economic dynamism | BLS LAUS (county, `BLS_API_KEY`) | 30 d | unemployment, employment growth 1y/5y | primary → stale cache → gap |

\* Safety's 180-day TTL reflects that FBI data publishes annually and lags ~18 months
regardless of fetch recency. The adapter resolves the place to a police agency (ORI) by
name-match, else the nearest City-type agency — so `place_grain` may read `agency` rather than
`place`. The social adapter exposes one interface but fans out to Reddit + Google News RSS
internally (separate caches/TTLs).

**Social reason-with-WebFetch fallback (keyless).** When Reddit is unavailable, Claude draws
resident signal from: **AreaVibes** (`areavibes.com/<city-state>/` — livability grades +
reviews), **city-data.com** (`/city/<City-State>.html`, `/forum/<state>/` — long-form resident
voice), **Numbeo** (`numbeo.com/quality-of-life|crime/in/<City>` — perception indices; cache
quarterly), and **Patch.com** (`patch.com/<state>/<city>` — hyperlocal news; sparse for small
cities). All keyless and WebFetch-able; cache results per session.

## Utility lookups (5)

Small deterministic functions, no LLM, same record envelope so the footer stays uniform.
Walkability and hazard cache via `fetch_with_cache`.

| # | Lookup | Source | Behavior |
|---|---|---|---|
| 1 | Family distance | Census Geocoder + bundled Gazetteer centroids + `config.family_locations` | distance + drive/flight estimate to each family location |
| 2 | Internet quality | FCC `geo.fcc.gov` (keyless) | block/county/state FIPS; provider availability + speeds → reason-with-search (BDC API token-gated) |
| 3 | Airport access | bundled OurAirports CSV + haversine | nearest commercial airport + nearest large hub, ground-time estimates |
| 4 | Walkability | EPA National Walkability Index ArcGIS (keyless) | block-group NatWalkInd 1–20 + category |
| 5 | Hazard | FEMA NRI county FeatureServer + NFHL flood point (keyless) | composite + per-hazard risk scores, flood zone / SFHA flag |

## TTL bands

Fast (1–7 d): air quality, social news. · Moderate (14–30 d): cost, dynamism, social
Reddit. · Slow (60–90 d): climate. · Lag-acknowledged (180 d): safety.

## Freshness & fallback policy

- Every response carries `source`, `fetched_at`, `place_grain`, `data_status`.
- **Stale-on-failure:** if a fresh fetch fails or rate-limits, use the cached value with a
  marker reflecting its *actual* freshness — a failed **forced** refresh over still-in-TTL data
  stays `fresh`, not falsely `stale`; only genuinely TTL-expired cache reads `stale`. Honest
  over blocking; never fabricate.
- **Failure breadcrumb:** any fallback record carries `degraded_reason`, so a degradation is
  debuggable rather than silent. `HABITAT_DEBUG=1` re-raises unexpected fetch errors instead of
  degrading — surfacing a code bug that would otherwise look like a source outage.
- **User refresh:** the evaluate workflow accepts a natural-language refresh modifier ("with
  fresh data", "force refresh") that bypasses TTLs for that place.
- **Fallback order:** primary → stale cache (marked) → alternative source / graceful gap.

## Place-grain matrix (degraded-mode summary)

The geo-resolving adapters (**cost / dynamism / safety**) stamp the grain *actually achieved*
(`tract` / `place` / `county` / `agency`), so a coarser fallback shows as `place_grain` ≠ the
requested level rather than over-claiming. Lat/lon-direct sources stamp the requested level;
their native grain (walkability = block-group, hazard = county) sits in the payload. The
narrative surfaces any fallback honestly.

- **City / county:** native for nearly all adapters and lookups.
- **State / country:** Census/BLS native; climate & air quality coarsen or go N/A; most
  reason-with-search dimensions return meta-summaries.
- **Neighborhood:** cost/safety/dynamism fall back to city `[city-level fallback]`; climate/air
  are usually fine at city/county; walkability/healthcare/education/nature are most informative
  here.
- **Property:** structured adapters fall back to neighborhood `[neighborhood-level fallback]`;
  family distance + internet are property-grain; walkability becomes property-radius native.

## International (country grain) — source/mode map

US adapters do NOT transfer (FIPS/Census/FBI/BLS/FCC/FEMA are US-only); **safety returns
`unavailable` at country grain by design**, and air quality uses the keyless Open-Meteo path.
Country grain is served by a separate backbone (see `evaluate-country.md`):

| Dimension | Source | Mode |
|---|---|---|
| Climate / Air | Open-Meteo / Open-Meteo-AQ (reused adapters) | live, `country-centroid` (coarse) |
| Economy, labor, cost-coarse, governance (WGI), internet, health | World Bank (`worldbank.py`, no auth, ISO3, per-indicator, empty→degrade) | live, cached 90 d |
| Safety | Global Peace Index (`gpi`) | bundled annual *(awaiting data drop → degrade/reason)* |
| Belonging / diaspora | UN Migrant Stock origin×dest (`diaspora`) | bundled annual *(awaiting data drop → reason)* |
| Short-stay TRAVEL access | Passport Index (`passport`) | bundled — **firewalled from fit/verdict** |
| Cost in home currency | Frankfurter (`fx`) | live, cached |
| Residence/visa, relocation friction, nature, city belonging | reason-with-search | ≤3 passes / ≤6 fetches |

Identity/centroid/currency/tz come from `country_lookups.resolve_country` over
`country_centroids.csv`. Bundled vintages/licenses + `--check-stale` live in `datasets/SOURCES.md`.
