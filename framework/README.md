# The Solytus pattern (candidate)

> **Status: candidate, not yet proven generic.** This pattern is *extracted from* working skills, not prescribed ahead of them. It earns the name "framework" once it has cleanly survived a second independent skill. Until then, treat it as "how Habitat is built," documented so the next skill can reuse it.
>
> **No sub-brand yet, on purpose.** The skills live under the plain **Solytus** umbrella. A family name for the skill collection (a "skill network / mesh / collective") is deliberately deferred until the work proves out publicly — naming a family before it exists is the premature-abstraction trap. Keeping the umbrella plain also leaves Solytus open for non-skill projects later.

A Solytus skill is split into three tiers so that the same skill can be installed by anyone, pointed at their own data, and updated without merge pain.

## The three tiers

| Tier | What it is | Where it lives | Who owns it |
|---|---|---|---|
| **Tier 1 — generic logic** | SKILL.md, reference workflows, deterministic `scripts/`, *public* reference datasets | the skill repo (shipped) | the project |
| **Tier 2 — instance config** | the knobs that make the skill *yours*: data-root location, identity/preferences, secret locations, `tenant_id` | `~/.solytus/<skill>/config.yaml` (+ gitignored `secrets.env`) | the user |
| **Tier 3 — instance data** | append-only state/events, profile, cache, per-instance knowledge | a data directory the user chooses, **outside** the skill | the user |

**Why it matters:** because Tier-3 data lives outside the skill, a user can `git pull` Tier-1 improvements without touching their own data — the install-and-update model, no fork-and-diverge.

## Open design questions (resolved per-skill, generalized at the Phase-2 retro)

These are the choices that *don't* yet have a single framework answer — the retro decision-tree will capture them:

- **Config taxonomy:** secrets vs. user preferences vs. system pointers — which are mutable, which are bundled, which are schema-validated?
- **State-ownership model:** does Claude own state (reads/writes files, passes to scripts), or does a script own state (atomic writes, crash-safe log), or is state externalized (e.g. a private GitHub repo)?
- **Surface constraint:** filesystem-based Tier-3 works on **Claude Code**. It does **not** work on claude.ai/mobile (ephemeral sandbox, no durable `$HOME`) — that surface needs a hosted MCP server or GitHub-API-backed state. Solytus targets Claude Code first by design.

## Conventions

- **Versioned config & APIs** — see [SCHEMA_VERSIONING.md](SCHEMA_VERSIONING.md).
- **Deterministic core** — math, scheduling, and state writes are stdlib-only Python with tests; the model supplies judgment, not arithmetic.
- **Honest grain** — cite sources, mark unverified, degrade gracefully; never fabricate.
- **Discovery-optimized SKILL.md** — the description says *when to use* the skill, not what it does internally; keep frequently-loaded content lean.

## Reference implementation

[`plugins/habitat`](../plugins/habitat) — the pilot. Read it as the worked example of the tiers above.
