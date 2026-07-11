# Logging maintenance

Append a `maintenance` (or `baseline` for pre-ownership) event to the active vehicle's
`events/`.

1. **Confirm the vehicle by name** before writing ("Logging to **1995 Toyota Tacoma**:…").
2. Gather: date, the clock reading(s) (`readings: chassis=<odo>` — only independent
   clocks; never log a derived clock), `service` (a slug matching a schedule item where
   one applies), `parts`, `fluids`, `cost`, `summary`. Unknown mileage stays unknown —
   never invent it.
3. Capture torque-to-yield / single-use details in `notes:` (e.g. "head bolts 25 ft-lb
   +90° +90°, NEW bolts").
4. Pick the next seq with `scripts/project.next_seq` over the loaded events; the filename
   seq is authoritative. Write the file as `<seq>-<date>-maintenance-<slug>`.
5. Rebuild: `python scripts/build_state.py --vehicle-dir <vehicle dir>`.

To fix a logged event, append a `correction` with `supersedes: <seq>` (never edit or
delete). To record a resolved issue, append a `build-sheet` `value: +resolved: <issue>`.

A fluid change that crosses a standard is a safety stop — check
`scripts/fluids.substitution_blocked(have, want)` before recommending a different fluid.
