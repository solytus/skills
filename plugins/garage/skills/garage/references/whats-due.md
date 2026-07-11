# What's due

The due computation is deterministic — run it, never free-hand it.

1. Rebuild the vehicle: `python scripts/build_state.py --vehicle-dir <vehicle dir>` (add
   `--as-of YYYY-MM-DD` to pin time math). Read the `== WHAT'S DUE ==` and `== BASELINE
   CAMPAIGN ==` sections it writes into `current-state.md`.
2. Each item is scored against **its declared clock** — a derived-clock item (timing belt
   on a swapped engine) reads the component's miles, and a record made before that clock
   existed is excluded, so it reads `UNKNOWN`, never a false `OVERDUE`.
3. **Honesty rules the render enforces** (`scripts/safety.py`): a safety item on an
   estimated interval never shows a bare `OK` — it carries "estimated — not the OEM
   schedule; verify." With no service logged, items read `UNKNOWN` → the baseline campaign,
   ordered cheap-inspection → safety time-bombs → fluid baselines → component-clock items.
4. **Interference engines** warn hard on the timing belt, fail-closed when unknown.
5. If code execution is unavailable, do NOT assert due/overdue — show the subtraction and
   say it's uncomputed.

Severe vs. normal intervals follow the vehicle's `usage_profile` (default severe when
unknown). Config predicates drop items the vehicle doesn't have (a transfer case on a 2WD).
