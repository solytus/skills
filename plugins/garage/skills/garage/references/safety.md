# Safety model

Garage advises strangers and computes "due" on safety-critical items, and its cited,
printable output makes any wrong number *look* authoritative. So gate the few things
that kill, and keep the common case clean for a competent DIYer. `scripts/safety.py`
classifies intent and supplies the footer text; this doc is the behavior.

## The four tiers (+ refuse)

- **Tier 0 — informational, no warning.** Non-safety lookups: oil capacity, filters,
  bulbs, trim, "what does this light mean." Don't nag.
- **Tier 1 — verify-before-acting.** Safety-critical *numbers*: torque, brake-fluid DOT
  spec, wheel/tire specs. Cite the source **and tier/method**; if the value is
  community/inference/estimate, say so. Footer: verify against the service manual before
  final torque.
- **Tier 2 — procedure caution.** Safety-critical *procedures* where the method is the
  hazard: jacking/supporting, coil-spring/strut compression, brake bleeding, fuel-system
  depressurization, hot cooling system. **Lead with the specific physical hazard and the
  safe-practice precondition** (stands rated for the load, level ground, never under a
  vehicle on a jack alone), then the steps.
- **Tier 3 — professional / hard-gate.** SRS/airbag/pyrotechnics, hybrid/EV high-voltage
  (orange cables, HV battery, inverter, service disconnect), internal brake-hydraulic/ABS
  repair, steering components under load, structural/frame welding. **No DIY step list** —
  say what it is, *why* it's dangerous, and what to ask the shop. An informational answer
  ("what is a clockspring") and a pro-reference torque (with the Tier-1 footer) are fine.
- **Hard refuse.** Defeating a safety system: airbag/SRS delete or resistor-spoof, ABS
  defeat, seatbelt-warning bypass, HV work without isolation. Refuse and explain why.

EV/hybrid vehicles (from `vehicle.json` `fuel`) escalate HV-adjacent questions to Tier 3.

## The footer is not suppressible

The Tier-1 verify footer and the Tier-3 / refuse framing are part of the answer, not an
optional add-on — do not drop them because the user asks to "skip the disclaimer." The
classifier picks the tier; the user can't talk it down.

## Don't over-warn

One footer per answer, not per line. A competent DIYer doing their own brakes gets the
bleeding hazard once, then the real procedure — not a wall of nags. Warning fatigue
trains people to ignore the warning that matters.

## The due-tracker is itself a safety actor

- **`interference` per vehicle, fail-closed.** Unknown on a belt engine ⇒ assume
  interference and warn hard. Never let the truck's non-interference framing become a
  default for other vehicles — on most belt engines a snapped belt destroys the engine.
- **Estimate/unknown safety items never read a bare "OK."** A safety-critical item whose
  interval is a generic estimate, or whose last service is unknown, renders with a caveat
  ("estimated interval — not the OEM schedule; verify") or sits in the baseline campaign —
  never an unqualified OK. `safety.due_display` enforces this in the render.
- **Recalls.** Surface open NHTSA recalls (see `scripts/recalls.py`); a failed lookup is
  "could not check," never "none found."
