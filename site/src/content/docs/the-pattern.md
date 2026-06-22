---
title: The Solytus pattern
description: Tier-1/2/3 — how Solytus skills separate generic logic from your config and your data.
---

Solytus skills are built so the useful part ships, and the personal part stays
yours. Three tiers:

| Tier | What | Where it lives | Who owns it |
| --- | --- | --- | --- |
| **Tier 1** | Generic skill logic | The skill (shipped here) | The project |
| **Tier 2** | Instance config | `~/.solytus/<skill>/config.yaml` + a gitignored `secrets.env` | You |
| **Tier 3** | Instance data | A data directory you choose, outside the skill | You |

Because your data lives outside the skill, you can update a skill (or reinstall
it from the marketplace) without touching anything personal — install-and-update,
not fork-and-diverge.

A few principles every skill follows:

- **Deterministic core.** Math, scheduling, and state writes are plain
  standard-library Python with tests; the model supplies judgment, not arithmetic.
- **Honest grain.** Sources are cited, gaps are marked, results degrade
  gracefully — nothing is fabricated.
- **Versioned contracts.** Config carries a schema version with a forward-only
  migration check, so today's setup keeps working as skills evolve.

> This pattern is still *emergent* — it earns a name once it has survived a
> second skill. Expect rough edges.
