# Contributing to Solytus

Solytus skills are designed to be *improved by the people who use them*. If you cloned a skill, hit a gap, and found a better way — that improvement is worth sending back so everyone benefits.

> **Early-project note:** this is a young repo maintained by one person on limited, variable time. Reviews are batched (target turnaround: a few weeks). Thoughtful, sourced, narrowly-scoped proposals get merged fastest.

## The install-and-update model

You don't fork-and-diverge. Your **data lives outside the skill** (in your own `~/.solytus/<skill>/` config + a data directory you choose), so you can `git pull` upstream improvements without merge pain. That's the whole point of the three-tier split — it keeps *your* stuff yours and *the skill* updatable.

## Two ways to contribute

1. **Propose an improvement from inside the skill (preferred).** Many skills have an opt-in "propose an improvement" flow: when you hit a gap, the skill helps you produce a *structured* proposal — a focused diff to the generic logic plus the concrete case it fixes. That becomes a PR using our template.
2. **Open an issue or PR directly** using the templates in [`.github`](.github).

## What gets merged (review rubric)

A proposal is most likely to be accepted when it is:

- **Generalizable** — it helps more users than just you (instance-specific tweaks belong in *your* Tier-3 data/config, not the shipped logic).
- **Sourced & honest** — any factual/reference data cites where it came from; unverified data is marked, not asserted. (Especially important for anything safety-relevant.)
- **Tested** — it doesn't regress the skill's test suite; new behavior comes with a test.
- **Narrow** — one clear change with a clear rationale beats a sweeping refactor.
- **In-pattern** — it respects the Tier-1/2/3 boundaries (generic logic / config / data).

## Local checks

Each skill has its own test suite (stdlib-only Python). Run it before opening a PR:

```bash
cd skills/<skill> && python -m pytest
```

By contributing you agree your contribution is licensed under the repo's [MIT License](LICENSE).
