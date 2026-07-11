# Field capture → desktop reconcile

A maintenance log only stays useful if it actually gets fed — and you log work at the
vehicle, not the desk. So capture in the field cheaply and reconcile later.

**Capture (anywhere — a phone note, a pasted line).** A quick shorthand is enough:
`tacoma oil change 261140 mobil1 5w30 5.5qt + filter 90915-yzzd1`. Capture the vehicle, the
odometer, and what you did; don't worry about format.

**Reconcile (at the desk, with the skill).** Paste the captured line(s). For each:
1. Resolve the vehicle (`scripts/select_vehicle.py`) — confirm by name.
2. Parse it into a draft `maintenance` event (date = capture date or today; `readings`,
   `service`, `parts`, `fluids`, `summary`). **Echo the parsed event back for confirmation**
   before writing — a field note is terse and easy to misread.
3. On confirmation, append the event (next seq) and rebuild with `scripts/build_state.py`.

This is the same capture→reconcile split the single-vehicle tool used, without any mobile
sync infrastructure — the durable write always happens in Claude Code.
