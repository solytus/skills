# Interview (UC1)

Inspiration-seeded, responsive interview that refines the profile over time — **Bet 1**,
the distinctive feature. Interactive: Claude conducts it. Recommended model: **Opus** for
initial / deep-dive interviews, Sonnet for routine refreshes.

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

## Measuring drift (F1 / F3)

The `versions/` snapshots are the raw material for the bet checks. To quantify how much the
profile has moved (Bet 1's "interview isn't theater"; Bet 3's "preferences evolve"), read the
two profile YAMLs and pass their `preferences` lists to `profile_diff`:

```
python3 scripts/profile_diff.py --before @v1.json --after @vN.json --threshold 30
```

It returns added / removed / changed preferences and a `delta_pct` — the measurable signal for
F1 (<~30% vs a one-sit-down form) and F3 (<15% over 12 months), replacing an eyeballed judgment.
