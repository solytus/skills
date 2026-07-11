# Changelog

All notable changes to the Garage skill are documented here. Format follows
[Keep a Changelog](https://keepachangelog.com); versions follow SemVer.

## [1.0.0] - 2026-06-30

### Added
- Multi-vehicle, vehicle-keyed store under a Tier-3 data root (`GARAGE_DATA_ROOT`
  env → `config.yaml` → `~/.solytus/garage/data`); event-sourced per vehicle.
- Independent named clocks per vehicle: a primary odometer plus derived mileage
  clocks (a swapped engine, a rebuilt component) that specific service items track
  instead of the chassis odometer. The config validator rejects a clock setup it
  can't model rather than miscompute it.
- Maintenance schedules stored as cited data — a rough estimate is never dressed up
  as the factory schedule.
- Cited knowledge base that tracks how each fact was established, ties it to the
  specific vehicle, won't cite a manual that was never ingested, marks single-source
  facts as provisional, and refuses to assert a safety-critical value it can't confirm.
- Proportionate safety model: informational → verify before acting → procedure
  caution → professional / hard stop, an interference-engine flag that errs toward
  caution, NHTSA recall lookup by vehicle, and a fluid-substitution guard (the wrong
  ATF, coolant, brake fluid, or gear oil is refused).
- Document ingestion, lightweight field capture with desktop reconcile, and Markdown
  export of reports, checklists, and guides with identity redacted by default.
- One-way migrator from the standalone Tacoma skill into a Garage vehicle.
