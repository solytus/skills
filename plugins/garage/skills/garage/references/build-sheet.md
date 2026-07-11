# Updating the build sheet

Mods, known issues, the project backlog, and the vehicle identity narrative are
event-sourced as `build-sheet` events on the active vehicle.

- Add to a list: `field: mods | known_issues | backlog`, `value: +<text>`.
- Update the identity summary: `field: vehicle`, `value: <new summary>` (latest wins; it
  renders as the VEHICLE block).
- Record a resolution (keeps the history): `field: known_issues`, `value: +resolved: <issue>`.

Confirm the vehicle by name, pick the next seq (`scripts/project.next_seq`), write
`<seq>-<date>-build-sheet-<slug>`, then rebuild with `scripts/build_state.py`. A material
identity change that affects safety (a swap, a regear, a tire-size change that scales the
odometer) should also update `vehicle.json` (clocks, `interference`) and may change which
KB answers apply.
