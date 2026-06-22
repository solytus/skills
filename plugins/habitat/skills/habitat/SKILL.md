---
name: habitat
description: >-
  Personal utility for finding and tracking places to live that fit an evolving
  preference profile. Use to run a preference interview, evaluate a specific place,
  surface places matching the profile, or review the place log. Usually invoked by
  name ("Habitat, ...").
---

# Habitat

A personal forever-tool for finding places to live that fit an evolving preference
model, with free-tier, API-backed context from country down to property — US at
city/neighborhood/property grain, plus **international country-grain triage**.
All state is local and human-readable.

**Status:** Production-tested. Store, schemas, router, cache layer, the workflows, and the
deterministic helpers are real; **all 6 US cached adapters + 5 utility lookups make live
free-tier API calls**, plus the **international country-grain backbone** (World Bank adapter +
country lookups + bundled country/passport datasets). **241 tests.** A few sub-fields are honest
gaps (humidity, business-formation, provider broadband speeds) — marked, never fabricated. The
**Reddit** half of Social activates automatically when `REDDIT_*` creds are in `secrets.env`;
Google News RSS works without keys. Free-tier API keys live in *your* `secrets.env` (never
committed); the skill degrades gracefully for any key you don't set.

## Config & data root

Skill code (this directory — **Tier-1**, shipped) is deliberately separate from your
**instance config** (**Tier-2**) and your **data** (**Tier-3**). Nothing personal lives in the
skill.

**On every run, resolve the data root** (see `scripts/config.py`), in order:

1. `HABITAT_DATA_ROOT` environment variable, else
2. `data_root:` in `~/.solytus/habitat/config.yaml`, else
3. the default `~/.solytus/habitat/data`.

Run `python3 scripts/config.py` once at the start of a session — it prints the resolved
`data_root`, `tenant_id`, and config `version` as JSON — then pass that `data_root` to every
script as `--data-root <path>`. (Two distinct configs: the small **system** config above, read by
`config.py`; and the rich **preference** config `profile/config.yaml` *inside* the data root,
which Claude reads — never a script.)

**First run / no config yet:** follow `references/setup.md` — copy `config.example.yaml` to
`~/.solytus/habitat/config.yaml`, set the data root, scaffold the data tree from
`examples/data-root/`, then copy `secrets.env.example` to `~/.solytus/habitat/secrets.env` and register the free-tier
keys (`references/api-keys-guide.md`). Keys are optional-tiered; the skill never fabricates.

## Model selection

- **Sonnet** — default for evaluate / surface / log / routine interviews.
- **Opus** — initial deep-dive interviews and explicit design-tradeoff work.

A skill runs on the session's model and cannot pin its own. **Recommend** the model
and let the user set it; never silently escalate. If routine evaluations need
guaranteed-cheap runs, dispatch them to a Sonnet subagent and keep the interactive
session for interviews.

## Router

Habitat is usually invoked by name. Decide the workflow from what the user says,
then load **only** that reference plus `references/schemas.md`.

| The user is... | Trigger examples | Load |
|---|---|---|
| refining preferences | "I keep thinking about smaller towns", "revisit walkability", "let's do an interview" | `references/interview.md` |
| asking about one place | "evaluate Tacoma", an address, a Zillow/Realtor URL (+ optional "with fresh data" / "force refresh") | `references/evaluate.md` |
| asking about a **country / living abroad** | "evaluate Portugal", "could we live in Japan", "where abroad fits us" | `references/evaluate-country.md` |
| asking for a shortlist | "top places for my profile", "surface places in the West", "surface countries for us" | `references/surface.md` |
| hunting for overlooked spots | "what are we missing", "any hidden gems", "look harder / smaller towns near X", "did we discount anything", "blind spots" | `references/gem-hunt.md` |
| reviewing the log | "show my log", "what's stale", "what did I shortlist" | `references/log.md` |
| hitting a gap / improving the skill | "this got X wrong", "propose a fix upstream", "Habitat should…" | `references/propose-improvement.md` |

If ambiguous, ask which the user wants. Always honor the never-fabricate and honest-grain
rules (`references/reason-with-search.md`).

**Surface vs. gem-hunt:** match on intent — `surface` generates a fresh shortlist from the
profile; `gem-hunt` finds what the standard search *overlooked* (satellites / small towns / twins
of near-misses / "near a known good thing"), triggered by "missing / overlooked / dig deeper /
smaller towns near X" with or without the word "gems."

**International is country-grain triage (V1), deepen opportunistically.** A country eval
screens "worth a city deep-dive?" — it is not a residence decision. City-grain abroad,
personalized visa scoring, and the GPI/diaspora data drops are V2.

## References

- `schemas.md` — data store schemas (profile / place / evaluation / interview), `place_key`, migration policy. **Load with every workflow.**
- `interview.md` · `evaluate.md` · `surface.md` · `log.md` — the core workflows.
- `evaluate-country.md` — country-grain triage workflow (international): preference-portability gate, residence-pathway-gated screen verdict, structured backbone + capped reasoned passes.
- `adapters.md` — the 6 cached adapters + 5 utility lookups (walkability + hazard promoted in Phase 3a) + fallback chains + TTLs + Phase-3 as-built notes.
- `scoring.md` — the fixed headline-fit anchor rubric + ranking check.
- `footer.md` — the compact Sources-footer render spec.
- `reason-with-search.md` — the reason-with-search scaffold, never-fabricate rule, token discipline, source hints.
- `setup.md` — first-run setup (instance config + data-root scaffold + key registration).
- `api-keys-guide.md` — how to register each free-tier API key.
- `propose-improvement.md` — *(opt-in)* turn a gap you hit into a structured upstream contribution (a diff to the generic logic + the failing case). See also the repo `CONTRIBUTING.md`.

## Scripts

Deterministic data work (no LLM, no token cost). Python stdlib only; each takes
`--data-root` and emits JSON to stdout, exiting non-zero with a reason on stderr on
hard failure.

**Division of labor:** scripts read/write only the **JSON cache** and take **explicit
CLI args**. Claude reads/writes the human-facing markdown + YAML data files (profile,
places, evaluations, interviews, `config.yaml`) and passes any needed values to scripts
as args. One bounded exception: `log_query.py` reads a fixed set of place-frontmatter
**scalars** (status / verdict / fit / last_touched / level) for the log index — a
constrained reader, not a general YAML parser. Otherwise scripts never parse YAML/markdown.

- `scripts/adapter_base.py` — atomic cache R/W, TTL freshness, 3-tier fallback, record envelope, shared adapter CLI. **Real (tested).**
- `scripts/placekey.py` — `normalize_name` + `build_place_key` (4-decimal geocode). **Real (tested).**
- `scripts/render_footer.py` — Sources-footer composer. **Real (tested).**
- `scripts/log_query.py` — fixed-scalar frontmatter reader + log filters (status / verdict / fit / last_touched / level / stale) + `--find` (dedupe by level+name). **Real (tested).**
- `scripts/profile_diff.py` — quantifies profile change between two versions (added/removed/changed preferences + `delta_pct`) so F1/F3 falsification is measurable. Takes the two `preferences` lists as JSON args (Claude reads the YAML; the script never parses YAML). **Real (tested).**
- `scripts/adapters/*.py` — the 6 US cached adapters, all **Real (live API)**. climate=Open-Meteo · cost=Census ACS · safety=FBI CDE (US-only; returns `unavailable` at `country` grain) · airquality=AirNow+Open-Meteo (Open-Meteo path when `grain_class=international`) · dynamism=BLS LAUS · social=Google News RSS (+Reddit when keyed). Plus `scripts/adapters/worldbank.py` — **country-grain workhorse** (World Bank, no auth): economy/labor/cost-coarse/governance(WGI)/internet/health, ISO3, per-indicator fetch, empty→degrade. **Real (live, tested).**
- `scripts/lookups.py` — US family-distance / internet / airport / walkability / hazard + `place_centroid` + **`nearby_places`** (gem-finder engine: overlooked places within a radius of an anchor, from the bundled gazetteer + ACS `population` column; pure bundled-data, no network). **Real** (keyless APIs + bundled CSVs).
- `scripts/country_lookups.py` — country-grain lookups: `resolve_country` (identity/centroid/currency/tz), `gpi` (safety), `diaspora` (belonging, origin×dest), `passport` (short-stay TRAVEL access only — firewalled from fit), `fx` (Frankfurter home-currency). **Real (tested);** `gpi`/`diaspora` await verified data drops (see `datasets/SOURCES.md`) and degrade to `unavailable`.
- `scripts/geo.py` — Census FIPS resolver (lat/lon → state/county/place/tract) + haversine. Shared by cost/dynamism/safety + the distance lookups. **Real (tested).**
- `scripts/verify_keys.py` — live per-key probe (OK / FAIL / SKIP). `scripts/bundle_datasets.py` — refresh `datasets/` static CSVs: US (OurAirports + Census Gazetteer) and international (`country_centroids.csv` from mledoze/countries, `passport_index.csv` from ilyankou); `--check-stale` reports each dataset's vintage/license from `datasets/SOURCES.md`.
- `scripts/config.py` — resolve the instance config: data root + `tenant_id` + schema `version` (env → `~/.solytus/habitat/config.yaml` → default). **Real (tested).** `scripts/mcp_mock.py` — a mock MCP layer that wraps the script surface (tenant-scoped, idempotent writes) to validate MCP-readiness without standing up a server. **Real (tested).**

Every script exposes a `--help` CLI; the deterministic helpers are unit-tested under
`scripts/tests/` (**241 tests**). Free-tier API keys load from your `secrets.env` (set what you
have; unset keys degrade gracefully — never fabricated). Adapters/lookups make outbound HTTPS
calls — a session must allow network for live data, else sources degrade to `unavailable`.
