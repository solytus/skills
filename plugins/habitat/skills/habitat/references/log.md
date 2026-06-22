# Review the log (UC4)

## Procedure

1. **Query** with `log_query.py`:
   ```
   python3 scripts/log_query.py --data-root <data> \
     [--status S] [--verdict V] [--level L] [--fit-min N] [--fit-max N] \
     [--stale [--stale-days 90]]
   ```
   Returns matching place frontmatter as JSON (filters are AND-ed; `--stale` flags places
   not touched in more than `--stale-days`, default 90).
2. **Present** the results as a scannable table: name · level · status · verdict · fit ·
   last_touched.
3. **Act on request:**
   - **Verdict transition:** append `{date, verdict, eval, note}` to the place's
     `verdict_history`, update `verdict` and `last_touched`. The optional eval pointer
     preserves the audit trail ("Disqualified 2026-06-15 based on the 2026-04-03 eval").
   - **Re-evaluate:** hand off to `evaluate.md` (e.g. for stale places).
   - **Archive / dedup:** dedup only on explicit request — propose merges, user confirms;
     never automatic. No proactive "would this flip now?" prompts in V1.

`stale_days` lives in `data/profile/config.yaml`. Claude reads it and passes `--stale-days`
to the script (scripts don't parse YAML).
