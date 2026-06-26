# Habitat

Find and track places to live that fit an evolving preference profile — with free-tier,
API-backed context from country down to property (US at city/neighborhood/property grain, plus
international country-grain triage). All your state is local, human-readable, and yours.

A [Solytus](../../../../README.md) skill. Built for **Claude Code**.

## Install (Claude Code)

Install from the **Solytus** plugin marketplace:

```text
/plugin marketplace add solytus/skills
/plugin install habitat@solytus
```

Then do the one-time **first-run setup** (Tier-2 instance config + data scaffold + optional keys) —
copy the templates from this repo into `~/.solytus/habitat`:

```bash
mkdir -p ~/.solytus/habitat
cp config.example.yaml      ~/.solytus/habitat/config.yaml   # then set data_root
cp -r examples/data-root/.  ~/.solytus/habitat/data          # neutral starter tree
cp secrets.env.example      ~/.solytus/habitat/secrets.env   # optional free-tier keys (Tier-2)
python3 scripts/config.py                                    # confirm discovery
```

<details><summary>Prefer clone + symlink (for local development)?</summary>

```bash
git clone https://github.com/solytus/skills.git
ln -s "$PWD/solytus/plugins/habitat/skills/habitat" ~/.claude/skills/habitat
cd solytus/plugins/habitat/skills/habitat    # then run the first-run setup above from here
```
</details>

Then just invoke it by name: **"Habitat, evaluate Boise"**, **"Habitat, let's do an interview"**,
**"Habitat, surface places for my profile"**, **"Habitat, show my log"**. Full walkthrough:
[`references/setup.md`](references/setup.md). Keys: [`references/api-keys-guide.md`](references/api-keys-guide.md)
(all optional — the skill degrades gracefully, never fabricates).

## The three tiers (why updates are painless)

- **Tier 1 — this skill** (logic, references, scripts, public datasets). Shipped; `git pull` to update.
- **Tier 2 — `~/.solytus/habitat/config.yaml`** (your data-root pointer, `tenant_id`) + `secrets.env` (your keys).
- **Tier 3 — your data root** (profile, places, evaluations, cache). Lives outside the skill, so
  pulling Tier-1 improvements never touches your data — no fork, no merge pain.

The data root is resolved on every run by `scripts/config.py`: `HABITAT_DATA_ROOT` env →
`~/.solytus/habitat/config.yaml` → default `~/.solytus/habitat/data`.

## Develop / test

Pure Python 3 stdlib — no build, no deps. From this dir:

- **All tests:** `python3 -m unittest discover -s scripts/tests -p 'test_*.py'` (241)
- **One file:** `python3 scripts/tests/test_cost.py -v`
- **Live run:** `set -a && . ./secrets.env && set +a` then run any adapter (`--help` on each).
- **Verify keys:** `python3 scripts/verify_keys.py` · **Refresh datasets:** `python3 scripts/bundle_datasets.py`
- **TDD-first:** write the failing test before the implementation.

## Two architectural rules (don't break without a plan)

1. **Thin router + progressive disclosure.** `SKILL.md` picks the workflow and loads *only* that
   one `references/` file + `references/schemas.md`.
2. **Strict scripts/Claude division.** Scripts read/write **only the JSON cache** and take
   **explicit CLI args**; they never parse YAML/markdown (bounded exceptions: `log_query.py`
   reads fixed frontmatter scalars; `config.py` reads the flat system config). Claude owns all
   human-facing markdown + YAML. This keeps scripts stdlib-only.

## Found a gap?

Habitat is meant to be improved by the people who use it — see
[`references/propose-improvement.md`](references/propose-improvement.md) and the repo
[`CONTRIBUTING.md`](../../CONTRIBUTING.md).
