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
profile, with free-tier, API-backed context from country down to property — US at
city/neighborhood/property grain, plus international country-grain triage. All state
is local and human-readable.

Free-tier API keys live in your `secrets.env` (never committed). Every adapter degrades
gracefully when its key is unset, and the skill never fabricates a missing value. Reddit's
half of Social activates when `REDDIT_*` creds are present; Google News RSS works without
keys. A few sub-fields are honest gaps (humidity, business formation, broadband speeds) —
marked, not invented.

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
- `adapters.md` — the 6 cached adapters + 5 utility lookups, with sources, TTLs, and fallback chains.
- `scoring.md` — the fixed headline-fit anchor rubric + ranking check.
- `footer.md` — the compact Sources-footer render spec.
- `reason-with-search.md` — the reason-with-search scaffold, never-fabricate rule, token discipline, source hints.
- `setup.md` — first-run setup (instance config + data-root scaffold + key registration).
- `api-keys-guide.md` — how to register each free-tier API key.
- `propose-improvement.md` — *(opt-in)* turn a gap you hit into a structured upstream contribution (a diff to the generic logic + the failing case). See also the repo `CONTRIBUTING.md`.

## Scripts

Deterministic data work — no LLM, no token cost. Python stdlib only; each takes
`--data-root`, emits JSON to stdout, and exits non-zero with a reason on stderr on hard
failure. Every script has `--help`. Adapters and lookups make outbound HTTPS calls, so a
session needs network for live data — otherwise sources degrade to `unavailable`. Keys load
from your `secrets.env`; unset keys degrade gracefully, never fabricated.

**Division of labor:** scripts read/write only the **JSON cache** and take **explicit CLI
args**. Claude owns the human-facing markdown + YAML (profile, places, evaluations,
interviews, `config.yaml`) and passes scripts the values they need. The one bounded
exception: `log_query.py` reads a fixed set of place-frontmatter scalars (status / verdict /
fit / last_touched / level) for the log index. Otherwise scripts never parse YAML or markdown.

- `scripts/adapter_base.py` — atomic cache R/W, TTL freshness, 3-tier fallback, record envelope, shared adapter CLI.
- `scripts/placekey.py` — `normalize_name` + `build_place_key` (4-decimal geocode).
- `scripts/render_footer.py` — Sources-footer composer.
- `scripts/log_query.py` — frontmatter-scalar reader + log filters (status / verdict / fit / last_touched / level / stale) + `--find` (dedupe by level+name).
- `scripts/profile_diff.py` — diffs two profile versions (added/removed/changed preferences + `delta_pct`) to measure how far an interview moved the profile. Takes the two `preferences` lists as JSON args.
- `scripts/adapters/*.py` — the 6 US cached adapters: climate (Open-Meteo) · cost (Census ACS) · safety (FBI CDE, US-only — `unavailable` at country grain) · airquality (AirNow + Open-Meteo, Open-Meteo path when international) · dynamism (BLS LAUS) · social (Google News RSS, plus Reddit when keyed). Plus `scripts/adapters/worldbank.py`, the country-grain workhorse (World Bank, no auth): economy / labor / cost-coarse / governance (WGI) / internet / health, per-indicator, empty→degrade.
- `scripts/lookups.py` — US family-distance / internet / airport / walkability / hazard, plus `place_centroid` and `nearby_places` (gem-finder engine: overlooked places within a radius of an anchor, from the bundled gazetteer + ACS population; bundled data, no network).
- `scripts/country_lookups.py` — country-grain lookups: `resolve_country` (identity/centroid/currency/tz), `gpi` (safety), `diaspora` (belonging, origin×dest), `passport` (short-stay TRAVEL access only — firewalled from fit), `fx` (home-currency, Frankfurter). `gpi`/`diaspora` await verified data drops (`datasets/SOURCES.md`) and degrade to `unavailable` until then.
- `scripts/geo.py` — Census FIPS resolver (lat/lon → state/county/place/tract) + haversine. Shared by cost/dynamism/safety and the distance lookups.
- `scripts/verify_keys.py` — live per-key probe (OK / FAIL / SKIP). `scripts/bundle_datasets.py` — refresh the `datasets/` CSVs (US: OurAirports + Census Gazetteer; international: `country_centroids.csv` from mledoze/countries, `passport_index.csv` from ilyankou); `--check-stale` reports each dataset's vintage from `datasets/SOURCES.md`.
- `scripts/config.py` — resolve the instance config: data root + `tenant_id` + schema `version` (env → `~/.solytus/habitat/config.yaml` → default). `scripts/mcp_mock.py` — a mock MCP layer over the script surface (tenant-scoped, idempotent writes) to check MCP-readiness without a server.
