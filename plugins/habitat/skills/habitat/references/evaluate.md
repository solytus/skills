# Evaluate a place (UC3)

Single-place evaluation. Recommended model: **Sonnet**. Phase 2 runs on placeholder
adapter data (stubs return `unavailable`); Phase 3 wires the real fetches.

## Procedure

0. **Country / abroad? Delegate.** If the user names a country or asks about living abroad
   (`level == country`), stop and follow `references/evaluate-country.md` instead — that path
   runs the preference-portability gate, the residence-pathway-gated screen verdict, and the
   country-grain data backbone. The rest of this file is the US city/neighborhood/property path.

1. **Resolve the `place_key`.** Determine `level` (city / neighborhood / property /
   county / state) and the name. For **city grain**, snap to the canonical Census place
   centroid first, so the same city always resolves to one stable `place_key` + geocode
   (shared cache, no coordinate-fork):
   ```
   python3 scripts/lookups.py place_centroid --location "<City, ST>"
   ```
   Use the returned `geocode` + `normalized_name` for the place_key, the place file, and
   every adapter/lookup `--geocode` below. If it returns `{}` (no match) or the grain is
   neighborhood/property, use a specific provided/known coordinate instead. Then:
   ```
   python3 scripts/placekey.py --level <level> --name "<name>" --geocode "<lat,lon>"
   ```
   Note any natural-language **refresh modifier** ("with fresh data", "force refresh") →
   pass `--force-refresh` to the adapters/lookups below.
2. **Load the profile** (`data/profile/profile.md`).
3. **Hard filters.** For each `must_have` / `must_not` preference, check for violation
   (via the relevant adapter / lookup / reason-with-search). Any violation ⇒
   `hard_filter: fail` + the failed preference name(s); skip scoring but still write the
   record and offer a verdict.
4. **Gather cached + lookup data** (each emits one JSON record — collect them):
   ```
   python3 scripts/adapters/{climate,cost,safety,airquality,social,dynamism}.py \
     --data-root <data> --place-key <key> --geocode "<lat,lon>" --level <level> [--force-refresh]
   python3 scripts/lookups.py {family_distance|internet_quality|airport_access|walkability|hazard} \
     --data-root <data> --place-key <key> --geocode "<lat,lon>" --level <level> \
     [--family "<loc>" ...] [--force-refresh]
   ```
   All 5 lookups are deterministic — **walkability + hazard were promoted from
   reason-with-search in Phase 3a**. Pass `--data-root` so internet / walkability / hazard
   cache; internet + hazard then share one FCC coordinate lookup and cost + dynamism share
   one Census geocode, so a cold eval resolves each coordinate once, not four times.
5. **Reason-with-search** the rest (healthcare, education, nature, political, commercial
   rent / industries / tax incl. **residential property tax**, home insurability, + any
   margins) per `reason-with-search.md`. Walkability and natural-hazard exposure are now
   deterministic lookups (step 4) — reason only to *supplement* them (e.g. insurer
   availability on top of the FEMA hazard scores). Never fabricate; mark grain fallbacks honestly.
6. **Score** per `scoring.md`: on hard-filter pass, write a narrative + a headline fit
   (0–100) using the anchor rubric, then run the nearest-neighbor ranking check against the
   log (`scripts/log_query.py`).
7. **Commercial vitality block** (always-on, 4 components): rent / sale ranges · growth ·
   business formation + dominant industries · tax + incentive. N/A-with-reason where the
   grain doesn't support a value.
8. **Sources footer.** Collect the cached/lookup records into a JSON array (each with
   `label`, `source`, `fetched_at`, `data_status`, optional `note`), then:
   ```
   python3 scripts/render_footer.py --records <file> --reasoned "<dims>" --lookups "<names>"
   ```
9. **Write the evaluation** `data/evaluations/<place-slug>/<YYYY-MM-DD-HHMM>.md`
   (frontmatter per `schemas.md`; body order: Hard filters → Narrative + fit → Commercial
   vitality → Social signals → Sources footer).
10. **Update the place file** `data/places/<level>/<slug>.md`. The file is keyed by `<slug>`
    (= `normalized_name`), so the canonical slug from step 1 means a re-eval reuses the same
    file. To be safe against a fork under a different coordinate, check first:
    ```
    python3 scripts/log_query.py --data-root <data> --level <level> --find <normalized_name>
    ```
    Reuse any returned file rather than creating a new one. Set `status`, `fit`,
    `last_touched`, `last_eval`; preserve `verdict` / `verdict_history`. Then prompt the
    user for a verdict.
   If the place **passed hard filters but is a near-miss** (fit roughly 45–69) with one
   clearly-dominant drag, set `gem_blocker` to that axis (vocab: `cost | crime | belonging |
   mosquitoes | airport | cannabis | nature | size`), else `none`; add a short
   `gem_blocker_note` if useful. This is the seed for `gem-hunt.md`'s fix-the-flaw-twin search.
