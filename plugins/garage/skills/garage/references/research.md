# KB research + enrichment

How a vehicle's cited knowledge base gets built and grown. Two flows; both end at
the same gate — **nothing lands until `scripts/kb_lint.py` passes** (and for the
schedule, `kb_lint.lint_schedule`). Follow [kb-conventions.md](kb-conventions.md)
for the fact format and the citation contract.

Answer precedence everywhere: **owner-confirmed `verified_specs` > cached KB fact >
fresh web search**. A web result enters as `community`/`inference`, never auto-promoted
to `official`, never overrides an owner-confirmed value.

## A. Seed + big enrichment → the deep-research skill

On onboarding, and whenever a whole topic is researched, use the **deep-research**
skill (multi-source, adversarially verified). Build a prompt from the vehicle's
config (`vehicle.json`: year/make/model/trim/engine_code/drivetrain/market) plus the
researcher contract from [kb-conventions.md](kb-conventions.md): return only the topic
file's content; cite every fact; tier official > manual > community; no real source ⇒ Gap.

Seed core (onboarding) = three topics: `identity` (from VIN-decode), `schedule-and-fluids`
(the OEM maintenance schedule + fluid types/capacities), `torque-specs` (safety-critical
torque). The schedule research is dual-purpose: it writes the cited
`knowledge/schedule-and-fluids.md` AND you derive `schedule.json` items from it. Where no
authoritative schedule is found, fill the remaining items from
`datasets/generic_schedule.json` with `estimate: true` (tier `inference`) intact — never
let a heuristic masquerade as OEM.

## B. Lazy single-fact enrichment → lightweight loop

The first time a fact is asked that isn't in `verified_specs` or the cached KB:

1. Web search; fetch the most authoritative source.
2. Apply the tier/citation contract. A single forum hit is `lazy-single` / `conf: low`
   / **provisional**.
3. **Safety facts need corroboration.** A `safety: yes` value from one community source
   is not enough — fetch a second independent source, or refuse-to-assert and offer the
   candidate-plus-verify. Beware forum citation-incest: the same number echoed across
   threads is one source, not three.
4. Append the row to the matching `knowledge/<topic>.md`, store the verbatim supporting
   quote with the citation, and run `python scripts/kb_lint.py <file>`. On a violation,
   fix it or downgrade the row to `## Gaps`. Only a clean file is cached.

Write KB `INDEX.md` updates one at a time (serialize) — two facts researched in one turn
must not both rewrite the index and clobber each other.

## Schedule provenance

Schedule items carry the same `tier`/`source` discipline as facts. A third-party
transcribed interval (KBB/Edmunds/a repair site) is `community`, never `official`,
even though it was "found." Run `kb_lint.lint_schedule(items)` after researching a
schedule: a claimed-OEM (`estimate: false`) interval needs a real locator source.
Flag when a schedule's market or engine doesn't match the vehicle's actual config
(the swap case): a US-market schedule researched against the factory engine may not
fit a JDM-swapped one.

## VIN-decode is a starting point, not the truth

vPIC decodes the *factory* engine/trim and is thin on older vehicles. Confirm the
decoded config with the owner before it drives research — especially "is this the
original engine, or has it been swapped?" Any spec researched against an unconfirmed
engine inherits provisional status.
