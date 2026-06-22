# Habitat bundled datasets — sources, licenses, vintages

`bundle_datasets.py --check-stale` parses the machine-readable lines below (it reads
`dataset:` and `vintage:`). Keep the `- dataset: … | … | vintage: YYYY` format intact.
Bump `vintage` whenever a dataset is re-fetched. License column governs redistribution.

## US (domestic) — pre-existing

- dataset: us_airports.csv | source: OurAirports | license: public-domain | url: https://davidmegginson.github.io/ourairports-data/airports.csv | vintage: 2024
- dataset: us_place_centroids.csv | source: US Census Gazetteer | license: public-domain | url: https://www2.census.gov/geo/docs/maps-data/data/gazetteer/2024_Gazetteer/ | vintage: 2024
- dataset: us_place_centroids.csv:population | source: Census ACS5 B01003 | license: public-domain | url: https://api.census.gov/data/2023/acs/acs5 | vintage: 2023

## International (country grain) — auto-built (network)

- dataset: country_centroids.csv | source: mledoze/countries | license: ODbL-1.0 | url: https://github.com/mledoze/countries | vintage: 2025
- dataset: passport_index.csv | source: ilyankou/passport-index-dataset | license: MPL-2.0 | url: https://github.com/ilyankou/passport-index-dataset | vintage: 2025

Build: `python3 scripts/bundle_datasets.py country_centroids` / `… passport`.
Notes:
- `country_centroids.csv` `tz` is a **coarse centroid-derived UTC offset** (mledoze master
  carries no timezone field) — fine for a "hours ahead/behind" remote-work signal, off by up
  to ~1h for countries that don't follow solar time; the eval labels it approximate.
- `passport_index.csv` is **short-stay TRAVEL access only** (visa-free days / on-arrival /
  e-visa / required) — NOT the right to work or reside. The country workflow firewalls it out
  of the fit number and the residence verdict.

## International — VERIFIED PERIODIC DROP REQUIRED (no clean stdlib-fetchable source)

These have no stable free CSV endpoint (GPI lives in IEP report Excel; UN Migrant Stock is a
large multi-sheet .xlsx). Until a verified drop lands at the path below, the country workflow
sources these dimensions via reason-with-search and the lookups degrade to `unavailable`.

- dataset: gpi.csv | source: IEP Global Peace Index | license: non-commercial (personal use; do not redistribute) | url: https://www.visionofhumanity.org/maps/ | vintage: 2024
- dataset: diaspora.csv | source: UN DESA International Migrant Stock 2024 (origin × destination) | license: UN terms (free use w/ attribution) | url: https://www.un.org/development/desa/pd/content/international-migrant-stock | vintage: 2024

Expected schemas (so the lookups read them when dropped):
- `gpi.csv`: `iso3,iso2,country,score,rank,year` (score lower = more peaceful)
- `diaspora.csv`: `dest_iso2,origin_iso2,origin_name,migrants,year` (foreign-born from origin in dest)
