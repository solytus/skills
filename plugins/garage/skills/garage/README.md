# Garage

An assistant for your car that gets smarter the longer you use it — a knowledge base of
everything it has researched and everything you've uploaded, and a maintenance record of
everything you've done. What's due is calculated from that history, never eyeballed. When
it can't confirm something, it says so rather than guess. All your state is local,
human-readable, and yours.

Garage is a research and record-keeping assistant, not a substitute for a qualified
mechanic — confirm anything safety-critical before you rely on it.

A [Solytus](../../../../README.md) skill. Built for **Claude Code**.

## Install (Claude Code)

Install from the **Solytus** plugin marketplace:

```text
/plugin marketplace add solytus/skills
/plugin install garage@solytus
```

Then do the one-time first-run setup (Tier-2 instance config + data scaffold) — copy the
templates from this repo into `~/.solytus/garage`:

```bash
mkdir -p ~/.solytus/garage
cp config.example.yaml     ~/.solytus/garage/config.yaml   # then set data_root
cp -r examples/data-root/. ~/.solytus/garage/data          # neutral starter tree
python3 scripts/config.py                                  # confirm discovery
```

Then invoke it by name: **"Garage, add my 2015 Civic"**, **"Garage, log an oil change"**,
**"Garage, what's due?"**, **"Garage, what's the front brake torque?"**, **"Garage, show my
service history"**.

No API keys required — every data source (NHTSA vPIC, NHTSA recalls, web search) is keyless,
and Garage won't guess: if it can't confirm a value, it says so.

## The three tiers (why updates are painless)

- **Tier 1 — this skill** (logic, references, scripts, public datasets). Shipped; `git pull` to update.
- **Tier 2 — `~/.solytus/garage/config.yaml`** (your data-root pointer, optional `tenant_id`).
- **Tier 3 — your data root** (each vehicle's events, knowledge, schedule, notes). Lives outside
  the skill, so pulling Tier-1 improvements never touches your data — no fork, no merge pain.

The data root is resolved on every run by `scripts/config.py`: `GARAGE_DATA_ROOT` env →
`~/.solytus/garage/config.yaml` → default `~/.solytus/garage/data`.

## Develop / test

Pure Python 3 stdlib — no build, no deps. From this dir:

- **All tests:** `python3 -m unittest discover -s scripts/tests -p 'test_*.py'`
- **One file:** `python3 scripts/tests/test_due.py -v`
- **TDD-first:** write the failing test before the implementation.

## Two architectural rules (don't break without a plan)

1. **Thin router + progressive disclosure.** `SKILL.md` picks the workflow and loads only that
   one `references/` file (plus `references/schemas.md` when writing state).
2. **Strict scripts/Claude division.** Scripts read and write only the JSON cache/state and take
   explicit CLI args; they never parse YAML or markdown. Claude owns all human-facing text — so
   "what's due" stays calculated, never guessed.

## Found a gap?

Garage is meant to be improved by the people who use it — see the repo
[`CONTRIBUTING.md`](../../../../CONTRIBUTING.md).
