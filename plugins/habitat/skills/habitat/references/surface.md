# Surface matching places (UC2)

## Procedure

1. **Build the candidate pool** = Claude's US-cities knowledge (scoped by the profile +
   any qualifier such as "smaller cities" / "in the West") **∪** the existing log
   (`python3 scripts/log_query.py --data-root <data>`), especially `Curious`-verdict
   places. There is no maintained starter list.
2. **Cheap pre-rank.** Reason over the pool against the profile *without* API calls; pick a
   top-N (default ~10).
2b. **Satellite pass (always-on gem hook).** For the top 1–2 *qualifying* anchors from the
    pre-rank, also enumerate overlooked neighbors and fold any standout into the top-N:
    ```
    python3 scripts/lookups.py nearby_places --geocode "<anchor lat,lon>" --radius 40 \
      --min-pop 8000 --max-pop 150000 --exclude-within 8 --limit 10
    ```
    Dedupe vs the log (`log_query.py --find`), keep any that plausibly beat or complement the
    anchor, and add them to the evaluated set. This is the lightweight satellite-of-winner slice;
    the deliberate, fuller hunt (twins, parent/hub anchors) lives in `references/gem-hunt.md`.
3. **Evaluate the top-N** via `evaluate.md` — benefits from in-session prompt caching
   (first place full, the rest amortized).
4. **Present** a ranked shortlist: headline fit + a one-line narrative each. Offer to save
   any as places / set verdicts.

Narrowing through the hierarchy is a reasoning strategy, not an enforced funnel. Properties
are not auto-populated in V1.
