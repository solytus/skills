# Schema & API versioning

Once a config shape or a script signature ships and a user has a live instance, you can't change it casually — their config and their saved workflows depend on it. This is the policy that keeps updates safe.

## Config (`config.yaml`)

- Every `config.yaml` carries a top-level `version:` integer. v1 is the first shipped shape.
- The skill's config loader **checks `version` on every load**:
  - missing/older → run the migration chain up to current (migrations are forward-only and idempotent; a no-op migration is fine);
  - newer than the code understands → fail loudly, don't silently misread.
- **Additive changes** (new optional field with a default) do **not** bump the major version.
- **Structural changes** (rename, nest, remove, change meaning) **do** bump the version and **must** ship a migration.

## Script signatures = public API

The deterministic `scripts/` are the skill's tool surface — and the surface a future MCP server would wrap unchanged. Treat each `query_* / get_* / log_* / update_*` signature as a public contract:

- Don't rename or repurpose a parameter in place. Add new **optional** parameters; to change shape, introduce a new versioned entry point and deprecate the old one.
- **Writes are idempotent.** Stateful calls accept (or derive) an idempotency key so a retried call doesn't double-write — required for the eventual MCP/multi-tenant path.
- Carry an optional `tenant_id` (default: the local user) through every stateful call now, even while single-user, so multi-tenancy is never a retrofit.

## Support window

Support the current and previous major config version (**N-1**) for a reasonable window before dropping a migration path. Note removals in the changelog.

## Why now (not later)

Locking this in Phase 0 is the cheap insurance the MCP/platform review called for: a config or signature decided today becomes expensive to undo once external users have live instances. Versioning from v1 makes every later change a migration, not a break.
