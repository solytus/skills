# Headline fit number (0–100)

One headline number per evaluation, produced by qualitative reasoning — **no per-dimension
math**. Two goals in tension: it must **differentiate** places (anti-clustering) and **mean
the same thing across years** (anti-drift). The fixed rubric is the durable yardstick; the
ranking check fights clustering.

## Fixed anchor rubric

| Band | Meaning |
|---|---|
| **DISQUALIFIED** | any `must_have` violated or `must_not` triggered — reported as a hard-filter fail + reason, **not** a number |
| 0–29 | misses multiple high-weight preferences |
| 30–49 | weak — meets some, misses several high-weight |
| 50–69 | mixed / solid-but-unexciting — gaps on some high-weight |
| 70–84 | strong — high-weight preferences met well, minor gaps |
| 85–94 | near-ideal across high-weight preferences |
| 95–100 | essentially perfect, including delighters |

Weights are qualitative (low/medium/high) and inform reasoning, not arithmetic.
A disqualified place gets no number — say why it failed.

## Ranking check (anti-clustering)

After settling on a number, read the 2–3 nearest-`fit` places already in the log
(from place frontmatter) and surface the placement in the narrative:

> 72 → ranks just below Boise (75), above Reno (64).

- **Skip** while fewer than 2 comparable places are logged (cold-start).
- If the resulting ordering feels wrong, **flag it to the user** rather than silently
  adjusting the number. Scores stay absolute, never relative-to-log.
- **Grain-scoped (international):** rank like-with-like. A country eval ranks only against
  other countries (`log_query.py --level country`); cities rank against cities (US +
  international cities are comparable). A country and a city are **not** comparable — never
  rank one against the other.

## International: context-adjusted preference set & the screen verdict

Country-grain evals apply the **same rubric** to the **context-adjusted** preference set —
the fit number still means the same thing, but it's measured against the preferences that are
meaningful in that context (see the preference `portability` blocks):

- a `must_have` softened to a nice-to-have (`treatment: soften-to-nice-to-have`) scores as a
  weighted preference — a miss lowers fit within-band, it does **not** DISQUALIFY;
- a `drop` preference is excluded; a `reframe` preference is scored against its new definition;
- `as-is` / portable preferences behave exactly as today. Scores stay absolute.

A country eval is a **triage screen, not a residence decision.** Alongside the livability
`fit`, set a `screen_verdict`:

| screen_verdict | meaning |
|---|---|
| **Promising** | livability fits AND a plausible residence/work pathway exists → worth a city deep-dive |
| **Marginal** | mixed fit, or pathway uncertain |
| **Ruled-out** | poor livability fit for the (context-adjusted) profile |
| **Pathway-blocked** | no plausible residence/work pathway for this person, regardless of fit |

Residence-pathway feasibility **gates** the verdict (a great-fit country with no viable visa is
`Pathway-blocked`). **Short-stay travel access (passport index) never touches `fit` or the
verdict** — it is reported only as a labeled travel signal (visiting ≠ residing).

## Calibration

Once ~3–5 places are evaluated, name 1–2 of them as live anchor references here (e.g. "Tacoma
= 72: strong walkability, mid healthcare"). If across ~10 evaluations numbers cluster within
±10 and can't be ranked, surface that to the user — don't paper over it.
