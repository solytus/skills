# Hunt for hidden gems (UC: find what the standard search missed)

A deliberate hunt for **overlooked** places — small/satellite/twin towns near an anchor — that
the headline `surface` workflow doesn't generate. Recommended model: **Sonnet** (Opus if pairing
with deep design reasoning).

## When to load this (intent, not keywords)
Activate whenever the user signals they want to find what we might have **missed / overlooked /
discounted** — *with or without the word "gems."* Examples: "what are we missing", "any blind
spots", "are we being too narrow / preemptively discounting", "hidden gems", "under-the-radar /
off the beaten path", "look harder / dig deeper near X", "smaller towns near X", "did we dismiss
anything too quickly", "give it a second look", "push the boundaries".

**Disambiguate from `surface`:** `surface` = generate a fresh shortlist from the profile
("top places for me", "surface the West"). `gem-hunt` = find what the standard search *overlooked*
(satellite / small-town / dismissed-too-quickly / "near a known good thing"). If genuinely
ambiguous, ask which — or run `surface` first, then a gem-hunt around its top results.

## Procedure
1. **Pick anchors** from three sources (auto-derive from the log + profile, or honor a
   user-named anchor like "near Clovis" / "near my parents"):
   - **Winners** — top-fit log places (`log_query.py` → Shortlist / fit ≥ ~68).
   - **Flawed near-misses** — log places carrying a `gem_blocker` (the twin targets).
   - **Fixed good points** — the profile's `family_locations` (from `profile/config.yaml`) and
     known belonging hubs (e.g. diaspora-community anchors). "Satellite of a fixed good thing."
2. **Enumerate neighbors** of each anchor, tuned to the pattern:
   ```
   python3 scripts/lookups.py nearby_places --geocode "<lat,lon>" --radius <mi> \
     [--min-pop N] [--max-pop N] [--exclude-within <mi>] [--limit N]
   ```
   - *Satellite / small-town:* radius ~35–45 (a commute), `--max-pop ~150000` to skip the metro,
     `--min-pop ~8000` to skip hamlets, `--exclude-within ~8` to drop the anchor itself.
   - *Twin of a metro near-miss:* same, centered on the flawed place.
3. **Dedupe** vs the log: `python3 scripts/log_query.py --data-root <data> --level city --find <normalized_name>` — drop anything already evaluated.
4. **Cheap pre-rank** (reason, no API): keep candidates that **share the anchor's strength**
   (same belonging hub within drive / same airport / drivable to parents) **AND plausibly fix the
   anchor's `gem_blocker`** (cheaper / safer / calmer / smaller). Pick the top ~5.
5. **Evaluate** the top candidates via `references/evaluate.md` (full battery).
6. **Present** as gems with **provenance** — "derived from <anchor> by fixing `<blocker>`"
   (e.g. "Riverton (crime) → Hillcrest"). Offer to save; set verdicts.

Honor the never-fabricate + honest-grain rules (`reason-with-search.md`). `nearby_places` is free
bundled data (no token cost); the cost is only the top-N evaluations.
