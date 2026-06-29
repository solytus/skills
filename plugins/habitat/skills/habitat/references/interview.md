# Interview

A responsive, inspiration-seeded interview that refines the profile over time. Claude conducts
it interactively. Recommended model: **Opus** for initial / deep-dive interviews, Sonnet for
routine refreshes.

## Procedure

1. **Load context.** Read `data/profile/profile.md` (current preferences + version). Skim
   the 2–3 most recent `data/interviews/*.md` and any recent `data/evaluations/**`
   relevant to the seed, so you can pressure-test stated vs. revealed preferences.
2. **Open on the seed.** Take the user's free-form trigger and run a creative session
   shaped around it. Do not walk a script.
3. **Choose techniques** as the conversation warrants:
   - Day-in-the-life scenarios
   - Forced-choice tradeoffs
   - Pressure-testing prior answers (stated vs. revealed)
4. **Cover opportunistically** (never read the list aloud): climate · cost · walkability ·
   safety · healthcare · education · nature · social fit · political · family distance ·
   airport · internet — plus **natural-hazard / home insurability** and **residential
   property-tax tolerance**. Record only what the user actually expresses.
5. **Compose the diff.** At session end, build the structured `changes` list
   (`op ∈ add | edit | remove | flag`), each with a one-line rationale (`schemas.md`).
6. **Cherry-pick.** Present a numbered atomic-change list with rationales:
   ```
   Proposed changes this session:
    1. + "walkable to a bakery I love" (weight: high)
    2. ~ climate weight  medium -> high
    3. + must-not: HOA-governed
    4. - drop "near a ski resort"
   Reply: all / none / 1,3 / all but 4
   ```
   Never silently override.
7. **Commit (crash-safe order)** once the user replies:
   1. Compute the new profile state (apply accepted changes; new `version` = old + 1).
   2. Write `data/profile/versions/<YYYY-MM-DD-HHMM>.md` — the full new profile.
   3. Write `data/interviews/<YYYY-MM-DD-HHMM>.md` — frontmatter (`changes` with `applied`
      flags, `seed`, version before/after, `summary`) + body (full transcript).
   4. **Then** overwrite `data/profile/profile.md` with the new state (bump `version`, set
      `updated_at`).

   Until step 4, `profile.md` still holds the prior valid version. If **no** changes are
   accepted, write only the interview record — no snapshot, no version bump.
8. **Confirm** what changed in a line or two.

## Measuring drift

The `versions/` snapshots let you quantify how much the profile has actually moved. Read the
two profile YAMLs and pass their `preferences` lists to `profile_diff`:

```
python3 scripts/profile_diff.py --before @v1.json --after @vN.json --threshold 30
```

It returns added / removed / changed preferences and a `delta_pct` — a measurable read on how
much an interview moved the profile, instead of an eyeballed guess. `--threshold` adds an
`exceeds_threshold` flag when the change is larger than the given percentage.
