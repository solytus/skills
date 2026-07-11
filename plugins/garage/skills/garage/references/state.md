# Viewing state (read-only)

To show a vehicle's current state, **rebuild first, every time**
(`python scripts/build_state.py --vehicle-dir <vehicle dir>`), then read the rendered
`current-state.md` — time-based due (brake fluid, tire DOT age, belt months) drifts with the
calendar even when no event changed, so a stale render can miss a newly-overdue safety item. It holds the
VEHICLE summary, MODS / KNOWN ISSUES / BACKLOG, SERVICE HISTORY, LAST DONE, VERIFIED SPECS,
WHAT'S DUE, and the BASELINE CAMPAIGN — all computed from `events/`.

For "the garage" / across all vehicles, list them with `scripts/select_vehicle.list_vehicles`
and show each vehicle's identity line plus its top OVERDUE / DUE-SOON items.

This is a READ path — never hand-edit `current-state.md` (it's regenerated). To change
anything, append an event (see [log.md](log.md) / [build-sheet.md](build-sheet.md)).
`current-state.md` is home-private and may contain VIN/plate; redaction happens only at
export.
