# Answering a question

Answer precedence: **owner-confirmed `verified_specs` > cached KB fact > web search.**

1. Identify the vehicle and the exact config the question depends on (drivetrain,
   transmission, engine, market, year range). The most dangerous error is a correct value
   applied to the wrong config — pin it.
2. Check the projection's `verified_specs`, then the vehicle's `knowledge/<topic>.md`
   (grep `knowledge/INDEX.md` keywords for the right file).
3. If it's not cached, research it — a single fact via the lightweight provisional loop,
   a whole topic via deep-research (see [research.md](research.md)). Apply the citation
   contract ([kb-conventions.md](kb-conventions.md)) and run `kb_lint` before caching.
4. **Apply the safety model** ([safety.md](safety.md)): cite the source + tier on
   safety-critical numbers; lead with the hazard on a dangerous procedure; route
   professional/HV/SRS work to a shop; refuse to defeat a safety system. A torque/fluid
   value you can't pin or corroborate gets the candidate-plus-verify treatment, not a
   confident assertion.
5. Surface a relevant conflict (both values, with precedence) rather than averaging, and
   name any owner-queue check the answer depends on (axle code, an FSM page to ingest).

Promote a fact to owner-confirmed when the owner verifies it physically or via an
ingested document.

## Answer-time gates (not just write-time)

`kb_lint` gates KB *writes*; these bind every *answer*, because an answer can be spoken
without ever writing a KB row:

- **Cite or refuse.** On a safety-critical number, quote the backing row's tier + method —
  an uncited value is then visibly missing its provenance. No cited value ⇒ say it's a Gap
  and give a candidate-plus-verify, never a bare guess (even when the user says "a number is fine").
- **Pin config — including a *different* vehicle.** A value pinned `applies-to: 4WD` must not
  be handed for a 2WD (or another year/trans/market/engine); the write-time contradiction check
  never runs against a hypothetical vehicle, so this is on you.
- **Never average or collapse a conflict** into one number — not even when asked to "round it."
- **≥2 independent sources for a web-sourced safety value.** A single forum hit is provisional
  (candidate-plus-verify), not a confident fact.
- **"Lifetime" / "filled-for-life" fluids** are checked against a real service interval and never
  echoed back as "nothing due."
