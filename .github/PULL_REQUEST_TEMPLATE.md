<!-- Thanks for improving a Solytus skill. Keep it narrow and sourced — see CONTRIBUTING.md. -->

## What this changes

<!-- One or two sentences. -->

## The case it fixes

<!-- The concrete situation where the current behavior fell short. A failing example is ideal. -->

## Which tier does this touch?

- [ ] Tier 1 — generic skill logic (shipped to everyone)
- [ ] Tier 2 — config convention / schema
- [ ] Docs / framework / site
- [ ] Other (explain)

> Instance-specific tweaks (your preferences, your data) belong in *your* Tier-3 data/config, not in shipped logic.

## Checklist

- [ ] Generalizable — helps more users than just me
- [ ] Sourced & honest — any reference/factual data cites its source; unverified data is marked, not asserted
- [ ] Tested — `python -m pytest` passes in the skill dir; new behavior has a test
- [ ] In-pattern — respects the Tier-1/2/3 boundaries
- [ ] Backward-compatible, or includes a config/schema migration (see `framework/SCHEMA_VERSIONING.md`)
