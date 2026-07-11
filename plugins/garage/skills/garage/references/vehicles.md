# Managing vehicles

List, add, and switch between vehicles.

- **List:** `scripts/select_vehicle.list_vehicles(<data_root>)` → slug, display,
  nicknames, last-touched per vehicle.
- **Add:** see [onboarding.md](onboarding.md).
- **Pick the target for a command:** `scripts/select_vehicle.resolve_vehicle(query,
  vehicles)`. It returns a confident match (a named vehicle, or the only one),
  `"AMBIGUOUS"`, or `None` (no vehicles). On `AMBIGUOUS`, ask the user to pick from a short
  list — don't guess. Within a session it's fine to treat the last-used vehicle as the
  default ("we're working on the Civic"), but **always name the target in the confirmation
  before writing an event** — append-only mis-attribution is painful to undo.

Each vehicle is fully self-contained under `vehicles/<slug>/`, so adding or removing one
never touches the others. Per-vehicle config (a swap clock, `interference`,
`usage_profile`) lives in that vehicle's `vehicle.json`.
