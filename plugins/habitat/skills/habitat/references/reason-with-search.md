# Reason-with-search

For dimensions with no cached adapter: Claude WebFetches and reasons per evaluation.
The saved evaluation record is the place-scoped freshness anchor (no separate cache).

Applies to: **walkability, healthcare, education, nature access, political alignment,
commercial rent, commercial dominant-industries narrative, commercial + residential
tax/incentives** — and **all margins** (user-added preferences outside the seed
taxonomy), always.

## Scaffold

```
reason_with_search(dimension, place, source_hints, profile_context):
  state dimension + place + target grain
  search → WebFetch the most targeted page(s) from source_hints → extract
           (preference `source_hint` overrides the defaults below)
  reason → short narrative finding + data_status + the sources touched
  NEVER fabricate: if grain/data is insufficient → "insufficient data at this grain"
  emit a normalized record (same envelope as adapters) so the footer treats it uniformly
```

## Never-fabricate rule

Either cite a value with its grain, or say `insufficient data at this grain`. Do not
invent numbers, and do not present a city-level figure as if it were neighborhood-level
— mark the fallback. Honesty over completeness, always.

## Token discipline (the dominant per-eval cost)

Reason-with-search is the largest share of a single evaluation's token budget. For each
dimension: **search → fetch the most targeted page(s) → extract** — never WebFetch broad pages
and dump them into context. Prefer a focused search result over a sprawling source page, and cap
fetches per dimension. This is the single biggest lever on per-eval cost.

## Default source hints

| Dimension | Suggested primary sources |
|---|---|
| Walkability | OSM Overpass (POI density ~1 km), neighborhood walkability narratives, `r/<city>` threads |
| Healthcare | CMS Hospital Compare, HRSA Health Center finder, local healthcare-access news |
| Education | NCES school directory + scores, district sites, parent-forum signal |
| Nature access | OSM parks/trails, USGS / NPS / state parks, AllTrails public pages |
| Political alignment | Census voting data, FEC summaries, local election results |
| Commercial rent | Broker quarterly reports (CBRE/JLL/Cushman) primary; sparse LoopNet/Crexi supplementary; Census Economic Surveys floor |
| Dominant industries (narrative) | Census BFS web + local economic-development authority pages |
| Tax + incentives — **commercial** | Tax Foundation, state DOR, federal Opportunity Zone maps, state Enterprise Zone / EDA programs |
| Tax + incentives — **residential** | Residential **property tax + effective total household tax burden** (often the decision-driving tax for a home): Tax Foundation state/local tables, county assessor effective-rate data, state DOR. Keep distinct from the commercial read. |
| Natural hazard + insurability *(margin)* | FEMA National Risk Index + flood maps; wildfire/wind exposure; whether insurers are still writing policies there |

## International (country grain) source hints

Country evals cap reasoning at **≤3 passes / ≤6 fetches** (World Bank supplies economy/labor/
cost-coarse/governance/internet/health — never reason those). Mark every value
`[reasoned estimate — re-verify]`.

| Pass | Suggested primary sources |
|---|---|
| Residence & work pathway *(gates the verdict)* | Official government immigration portals (the authority's own pages); EU Immigration Portal / Blue Card; MIPEX (mipex.eu) + OECD International Migration / Talent-Attractiveness as integration anchors; double-tax-treaty & social-security totalization lists. **Qualitative buckets only — no numeric points/CRS scores.** Cite page + fetch date; add the not-legal-advice disclaimer. |
| Relocation friction | Non-citizen healthcare enrollment (health ministry), international-school cost/waitlist, foreigner property/banking rules, driving-license recognition, pet-import, dominant language. No free structured source — labeled estimate. |
| Nature | OSM protected-area/parks, UNESCO/IUCN, national park systems, AllTrails public pages. |
| Belonging (city layer, V2) | Koreatown / H-Mart-equivalent / diaspora-org presence (the *country* number comes from the `diaspora` lookup). |

**Visit ≠ reside:** passport/short-stay travel access is a deterministic lookup, reported as a
labeled travel signal — never reasoned into, and never part of, the fit or the verdict.

## LoopNet/Crexi ToS hygiene

Only when an active user evaluation is running (never background/batch); cap <5 page
fetches per evaluation session; user-agent identifies honestly; fetched content is never
stored beyond the saved evaluation record.
