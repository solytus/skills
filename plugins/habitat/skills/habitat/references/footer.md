# Sources footer

Every evaluation ends with one compact `Sources` block. **No inline citations** in the
narrative — keep the prose clean. Emitted deterministically by
`scripts/render_footer.py` from the collected source records.

## Rules

- One line per cached adapter and utility lookup actually used: `source • fetched N ago`.
- One summary line listing the dimensions reasoned via WebFetch (real-time).
- Relative times (`fetched 12 d ago`, `fetched 6 h ago`).
- **Markers appear inline only when something is wrong** — `data_status != fresh`:
  - `[stale: TTL expired, fresh fetch failed]`
  - `[degraded: <reason>]` (e.g. served from an alternative source)
  - `[stale FBI: data inherently lags ~18 months]` for the safety lag case
  - `[city-level fallback]` / `[neighborhood-level fallback]` when `place_grain` fell back
- **International markers** (country grain) — these mark *coarseness/recency*, not failure, and
  apply even on `fresh` records:
  - `[country-centroid: coarse single-point]` — climate/air read at one centroid for a whole country
  - `[annual dataset: vintage YYYY]` — bundled annual sources (GPI, diaspora); vintage from `SOURCES.md`
  - `[reasoned estimate — re-verify]` — any reason-with-search value (visa, friction, nature)
  - `[VISA DATA STALE — re-verify]` — residence/visa pass older than 90 days (fast-changing rules)
  - `[short-stay TRAVEL access only — not residence]` — on the passport-index line
- **Country evals lead with a freshness header line** above the narrative:
  `N measured · M reasoned · oldest input YYYY-MM` — so the reader sees at a glance how much
  is structured vs. reasoned and how old the oldest input is.

## Sample

```
[narrative body reads naturally with no inline citation clutter]

Sources:
- Climate: NOAA CDO • fetched 12 d ago
- Cost: Census ACS • fetched 4 d ago
- Safety: FBI Crime Data • fetched 65 d ago  [stale FBI: data inherently lags ~18 months]
- Air quality: EPA AirNow • fetched 6 h ago
- Social: Reddit • fetched 3 d ago; Google News RSS • fetched 1 d ago
- Dynamism: BLS + Census BFS • fetched 18 d ago
- Walkability, healthcare, education, nature, political, commercial rent/industries/tax: reasoned via WebFetch (real-time)
- Family distance, internet, airport: utility lookups (real-time)
```

Input contract: `render_footer.py` takes a JSON array of source records
(`{source, fetched_at, place_grain, data_status}`) plus a list of reasoned dimension
names, and prints the block. See `schemas.md` for the record envelope.
