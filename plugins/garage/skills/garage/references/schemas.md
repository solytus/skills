# Schemas

All state is per vehicle under `<data_root>/vehicles/<slug>/`. Scripts read the JSON
cards; Claude reads/writes the markdown. `vehicle.json` is the machine source of truth
(clocks, VIN/plate for the export denylist); the rendered VEHICLE summary is
event-sourced; `identity.md` is the human narrative.

## Event file (`events/<seq>-<yyyy-mm-dd>-<type>-<slug>`)

Header of `key: value` lines + optional trailing `notes:` block. The filename seq is
authoritative. Append-only.

```
seq: 8
vehicle_id: 1995-toyota-tacoma
type: maintenance            # maintenance | baseline | build-sheet | correction | verified-spec
date: 2026-05-03
readings: chassis=260233     # name=int pairs; only INDEPENDENT clocks are logged (derived are computed)
service: oil-change
parts: Toyota 90915-YZZD1
fluids: Mobil 1 EP 5W-30, 5.5 qt
summary: Oil + filter
```

- **maintenance** — work done. **baseline** — historical/pre-ownership service.
- **build-sheet** — `field` (`vehicle` | `mods` | `known_issues` | `backlog`) + `value`
  (`+x` adds to a list; `+resolved: x` records a resolution).
- **correction** — `supersedes: <seq>` voids a prior event (never edit/delete).
- **verified-spec** — owner-confirmed spec from a document: `key`, `value`, `applies_to`,
  `source_doc`, `confirmed`. Feeds the `verified_specs` projection.

Reading semantics live in `scripts/project.py` (`reduce_events`). Never log a derived
clock (e.g. `engine=`) — it's computed from its base.

## vehicle.json

`schema_version`, `vehicle_id`/`slug`, `display`, year/make/model/trim, `engine_code`,
`drivetrain`, `transmission`, `fuel`, `market`, `vin`, `plate`, `nicknames`,
`interference` (true/false/null — fail-closed), `usage_profile` (severe/normal),
and `clocks[]`:

```json
{"name": "engine", "kind": "derived", "unit": "mi", "base": "chassis", "offset": 210870}
```

`scripts/clocks.py` validates the set and rejects what it can't model (hours clocks,
chained/second-swap derived clocks). v1 supports one odometer base + single-segment
derived mileage clocks.

## schedule.json

`schema_version`, `vehicle_id`, `items[]`. Each item: `key`, `label`, `service_slug`,
`clock` (a declared clock name), `mileage_interval`, `time_interval_months`, optional
`severe_*` intervals, `safety_critical`, `baseline_tier`, `is_fluid`, `estimate`,
`tier`, `source`, `aliases`, `include_if` (config predicates). `scripts/schedule.py`
validates clock-reference integrity and the estimate⟺inference biconditional;
`kb_lint.lint_schedule` gates claimed-OEM sources.

## KB facts table

8 columns: `key | value | applies-to | tier | conf | safety | method | source`. See
[kb-conventions.md](kb-conventions.md).
