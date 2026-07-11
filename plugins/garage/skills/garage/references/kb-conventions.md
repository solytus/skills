# KB file format + citation contract

A vehicle's knowledge base lives at `<data_root>/vehicles/<slug>/knowledge/` — one
`<topic>.md` file per topic, plus an `INDEX.md` router. Every fact is cited and
provenance-graded. `scripts/kb_lint.py` enforces this contract; **no KB file is
saved until it passes `kb_lint`**.

## File structure

Each topic file has YAML frontmatter (`topic`, `applies_to`, `updated`) then:

- `## Facts` — the cited fact table (below).
- `## Procedures` — step lists; cite any spec inline.
- `## Conflicts` — sources that disagree, kept side by side (never averaged).
- `## Gaps` — values we could not cite. A gap is a success, not a guess.
- `## Owner-queue` — physical/manual checks the owner must do (axle code, FSM page).

## The Facts table (8 columns)

```
| key | value | applies-to | tier | conf | safety | method | source |
```

- **key** — stable snake_case id (matches a `verified_specs` key where one exists).
- **value** — the fact, with units. A torque value MUST carry a unit (ft-lb / Nm / in-lb).
- **applies-to** — the exact config this fact is for (e.g. `5VZ-FE 4WD auto`). Required
  for safety facts. The dominant automotive error is a correct value applied to the
  wrong config; pin it.
- **tier** — `official` (FSM / Toyota / NHTSA / Haynes-Chilton) > `community`
  (forum / vendor / engine-specs) > `inference` (derived; state the derivation).
- **conf** — `high | medium | low`.
- **safety** — `yes | no`. Torque, brake, steering, fuel, and fluid-spec facts are `yes`.
- **method** — how the fact was obtained (the provenance dimension, separate from conf):
  - `owner-confirmed` — owner physically verified it, or it came from an ingested document.
  - `fsm-ocr` — an owner-OCR'd factory manual page (FSM / Haynes / Chilton / body-repair manual).
  - `deep-research-verified` — survived the adversarial deep-research pass (multi-source).
  - `owner-supplied-list` — an owner-provided community-curated reference (e.g. the r/1stGenTacomas torque list).
  - `seed-web` — a general web source (forum / vendor / encyclopedia) captured during the initial seed, not adversarially verified.
  - `lazy-single` — a single on-demand web fetch; provisional, capped at `conf: low`.
  - `generic-heuristic` — a bundled fallback estimate, not a cited figure.
- **source** — a real locator: URL, FSM section, Haynes page, NHTSA/TSB id. Weasel
  sources (`standard`, `typical`, `commonly`, `manufacturer spec`) are illegal — a
  value with no real source is a **Gap**, not a Fact.

## Rules the linter enforces

- **Cite or move to Gaps.** Official/community facts need a non-weasel, locator-bearing source.
- **No confabulated manuals.** An `official` FSM/Haynes citation requires `method`
  `fsm-ocr` or `owner-confirmed` — you can't cite a manual you never ingested. A
  web-found FSM page number with method `lazy-single` is a confabulation, not a citation.
- **Lazy facts are provisional.** `method: lazy-single` must be `conf: low` until
  corroborated or owner-confirmed.
- **Safety facts pin config and corroborate.** `safety: yes` requires a non-empty
  `applies-to`; a `safety: yes` `lazy-single` fact needs ≥2 independent sources (or refuse).
- **Never average a conflict.** Keep both values in `## Conflicts` with precedence
  (official > Haynes > community-high > community).

## Refuse-to-assert

Do not state a definitive safety-critical value when: only a single community source
supports it; the exact config can't be pinned; units are ambiguous; or it's a
generic heuristic. Instead give the candidate and what to verify in the manual:
"candidate 80 ft-lb (community, unconfirmed) — verify against the FSM before relying
on it." A confident wrong number, laundered through a citation and a printout, is more
dangerous than an honest "I can't confirm this."

## Promotion to owner-confirmed

A fact reaches `method: owner-confirmed` two ways: document ingestion (a photo/OCR of
the FSM/Haynes/service record — see [ingest.md](ingest.md)), or the owner physically
verifying a config or value ("confirmed open rear diff via spin test"). Owner-confirmed
facts outrank everything and feed the `verified_specs` projection.
