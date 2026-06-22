# Solytus

Open, installable [Claude](https://claude.com/claude-code) skills — and the pattern behind them.

Solytus skills start as personal tools, then get generalized so anyone can install them, point them at their own data, and make them their own. Each ships with tests, honest sourcing, and an opt-in way to propose improvements back upstream.

> **Status: early.** The first skill ([Habitat](plugins/habitat)) is being generalized as the proof-of-pattern. The reusable "framework" is still an *emergent, candidate* pattern — it earns a name once it has survived a second skill. Expect rough edges.

## What's here

| Path | What it is |
|---|---|
| [`plugins/habitat`](plugins/habitat) | **Habitat** — find & track places to live that fit an evolving preference profile. (Pilot skill, packaged as a single-skill plugin.) |
| [`framework/`](framework) | The Tier-1/2/3 productization pattern + skill-dev hygiene notes. Candidate, not yet proven generic. |
| [`site/`](site) | Static showcase site (build-in-public devlog — gated until there's a real-usage signal). |

## Install target

Built for **Claude Code** first: clone the repo, keep your secrets in a local file, point the skill at your own data directory, and `git pull` to get improvements. A frictionless **claude.ai / mobile** install (which needs a small hosted MCP server) is a deliberately deferred later branch.

## Design principles

- **Three tiers, cleanly separated:** generic logic (shipped) / your config (`~/.solytus/<skill>/`) / your data (outside the skill, never overwritten by updates).
- **Deterministic where it matters:** math, scheduling, and state writes live in tested, stdlib-only Python — not in the model.
- **Honest grain:** cite sources, mark unverified, degrade gracefully — never fabricate.
- **Self-improving:** an opt-in "propose an improvement" flow turns a gap you hit into a structured contribution.

## License

[MIT](LICENSE) © Sean Park (Solytus)
