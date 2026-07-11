# Onboarding a vehicle

Stand up a new vehicle with a cited core, then grow on demand.

1. **Capture make / model / year first** (fast, conversational). Scaffold the vehicle:
   `python scripts/new_vehicle.py --data-root <root> --make … --model … --year …`. This
   writes `vehicle.json` (one primary chassis odometer), empty `events/` + `knowledge/`,
   and the seq-1 identity event.
2. **Offer VIN-decode enrichment** (optional, recommended): `python scripts/vin_decode.py
   <VIN>` fills engine/trim/drivetrain/fuel and stores the VIN. **It decodes the factory
   engine and is thin on older vehicles — confirm with the owner before it drives
   research: "is this the original engine, or has it been swapped?"** Mark the vehicle's
   `interference` (researched; fail-closed to unknown) and declare a derived clock if a
   component was swapped (see [schemas.md](schemas.md)).
3. **Check recalls**: `python scripts/recalls.py` (year/make/model). Surface open recalls
   prominently; a failed lookup is "could not check," never "none found."
4. **Research the seed core** via the deep-research skill (see
   [research.md](research.md)): identity, the OEM maintenance schedule + fluids, and
   safety-critical torque. Write the cited `knowledge/` files and derive `schedule.json`
   items; fill any unresearched items from `datasets/generic_schedule.json` with
   `estimate: true` intact.
5. **Set `usage_profile`** (severe/normal) from how the owner drives — default to severe
   when unknown.
6. State the scope + disclaimer once: informational, not professional advice; estimated
   intervals aren't the OEM schedule; the skill doesn't cover SRS/HV/structural work.

Then rebuild state: `python scripts/build_state.py --vehicle-dir <vehicle dir>`.
