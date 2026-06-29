# Evaluate a country (international triage)

Country-grain **triage screen**, not a residence decision: "is this country worth a city
deep-dive?" Recommended model: **Sonnet** (Opus for the first renegotiation of a profile).
Free-tier only. Honor the never-fabricate + honest-grain rules (`reason-with-search.md`).

Two firewalls run through this whole workflow:
- **Visit ≠ reside.** Passport/short-stay travel access is reported as a labeled travel
  signal only — it never enters the fit number or the screen verdict.
- **Triage, not decision.** Country grain describes nowhere anyone actually lives; the output
  is a `screen_verdict` (Promising / Marginal / Ruled-out / Pathway-blocked) + a livability
  `fit`, with a "no city evaluated yet" note. City detail is V2.

## Procedure

1. **Resolve identity.** `python3 scripts/country_lookups.py resolve_country --country "<name or ISO>"`
   → `{iso2, iso3, name, normalized_name, geocode, tz, currency}`. Build the key:
   `python3 scripts/placekey.py --level country --name "<Name>, <ISO2>" --geocode "<lat,lon>"`
   (= `country::<name>-<iso2>::<centroid>`). If `resolve_country` returns `{}`, ask the user to
   confirm the country / ISO code.

2. **Load profile** (`data/profile/profile.md`) and the optional `immigration_profile`,
   `home_currency`, `work_timezone` from `data/profile/config.yaml` (absent ⇒ generic mode).

3. **Portability gate (renegotiation).** Determine which preferences can't be measured/applied
   at international/country grain, using this inline source-portability table:

   | `source_hint` | international? |
   |---|---|
   | `auto:cost` (Census), `auto:safety` (FBI), `auto:internet` (FCC) | **not measurable** abroad → flag |
   | `auto:climate`, `auto:airport` | portable (global sources) |
   | `reason` | portable by default (search works anywhere) — unless its `portability` block says otherwise |

   For each flagged preference whose `portability.international.status` is **not** `resolved`,
   surface a numbered renegotiation prompt (same UX as `interview.md` step 6: accept all / N /
   reframe N as … / drop N / keep as-is). Then **write the resolved `treatment` + `rationale`
   + `resolved_at`** back into that preference's `portability.international` block in
   `profile.md`. If a renegotiation materially changes the profile, bump `version` and write a
   `versions/<ts>.md` snapshot first (reuse `interview.md` step 7 ordering); an annotation-only
   change is a single additive edit. A `resolved` preference is not re-prompted on re-eval.
   - *First instance:* the "Asian ≥3% (city/metro grain)" must-have → **soften to a
     nice-to-have** internationally — now read against real `diaspora` data (step 5), not vibes.

4. **Residence-pathway feasibility (gates the verdict).** Reason-with-search ONE consolidated
   pass over official government immigration pages (+ MIPEX / OECD migration as integration
   anchors): residency & work-visa options, right-to-work, remote-income/digital-nomad routes
   + double-tax-treaty / totalization existence, foreigner business formation. **Generic** by
   default; **personalized** when `immigration_profile` is present (match occupation/age/
   savings/remote-income/family to specific pathways). Report **qualitative buckets only**
   (`likely-eligible` / `marginal` / `no-obvious-pathway`) — NO numeric points/CRS scores;
   cite each official page + fetch date. Standing disclaimer: *"AI-summarized from official
   pages on <date>; not legal advice; rules change — confirm with the authority."* This pass is
   re-verify-stamped (≤90 days; see footer).

5. **Structured backbone** (no reasoning tokens — each emits one JSON record):
   ```
   python3 scripts/adapters/worldbank.py --data-root <data> --place-key <key> --geocode "<lat,lon>" --level country
   python3 scripts/adapters/climate.py    --data-root <data> --place-key <key> --geocode "<lat,lon>" --level country
   python3 scripts/adapters/airquality.py --data-root <data> --place-key <key> --geocode "<lat,lon>" --level country
   python3 scripts/country_lookups.py gpi      --place-key <key> --iso2 <ISO2>
   python3 scripts/country_lookups.py diaspora --place-key <key> --iso2 <ISO2> --origin KR --origin CN --origin JP   # belonging-origin set from the profile
   python3 scripts/country_lookups.py passport --place-key <key> --iso2 <ISO2> [--citizenship US ...]                # TRAVEL access only
   python3 scripts/country_lookups.py fx       --place-key <key> --base <home_currency> --dest-ccy <country currency>
   ```
   World Bank covers economy / labor health / cost-coarse (GDP-PPP, inflation) / governance
   (WGI 0–100) / internet / health — **never reason these.** climate/air are `country-centroid`
   (coarse; say so). `gpi`/`diaspora` degrade to `unavailable` until their data drops land
   (`datasets/SOURCES.md`) — then supplement via reason-with-search.

6. **Hard filters** over the **context-adjusted** preference set (step 3): a softened
   must-have no longer disqualifies (a miss lowers fit instead); a dropped one is excluded; a
   reframed one is checked against its new definition. Record `hard_filter` + any failures.

7. **Capped reasoned passes (≤3 total, ≤6 fetches):** (a) residence & work pathway = step 4
   (already done); (b) **relocation friction** — one labeled-estimate pass: non-citizen
   healthcare access, dependent schooling / international schools, foreigner property & banking
   access, driving-license recognition, pet import, language barrier; (c) **nature** —
   protected-area / UNESCO / trail summary. Mark every reasoned value
   `[reasoned estimate — re-verify]`. Don't reason anything World Bank already supplied.

8. **Score + verdict** (`scoring.md`): livability **fit** (0–100) over the context-adjusted
   set; **screen_verdict** gated by step 4's residence feasibility (no pathway ⇒
   `Pathway-blocked` regardless of fit). Run the **grain-scoped** ranking check
   (`log_query.py --level country` — skip while <2 countries logged).

9. **Sources footer.** Collect the records into a JSON array and render
   (`render_footer.py`). Markers: `[country-centroid: coarse]` (climate/air),
   `[annual dataset: vintage YYYY]` (gpi/diaspora), `[reasoned estimate — re-verify]`,
   `[VISA DATA STALE — re-verify]` once the residence pass is >90 days old. Lead the eval with
   a one-line header: **"N measured · M reasoned · oldest input YYYY-MM."**

10. **Write eval + place.** Eval `data/evaluations/<slug>/<YYYY-MM-DD-HHMM>.md`. Place
    `data/places/country/<slug>.md` with `country_code`, `grain_class: international`,
    `screen_verdict`, `fit`, and a **"no city evaluated yet"** body note. Check
    `log_query.py --data-root <data> --level country --find <normalized_name>` first to reuse an
    existing file. Then prompt the user for a verdict (and whether to deep-dive a city → V2).
