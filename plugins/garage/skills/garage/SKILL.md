---
name: garage
description: >-
  Multi-vehicle personal automotive assistant + maintenance tracker. Use to add a
  vehicle and build its cited knowledge base, log maintenance work, track what
  service is due, ask cited questions about a vehicle, ingest documents (photos of
  the owner's manual / service records), or view current state and history. Usually
  invoked by name ("Garage, ...").
---

# Garage

A subject-matter expert and maintenance tracker for each vehicle you own. Per vehicle
it keeps a cited knowledge base, an event-sourced service history, and a deterministic
"what's due." All state is local and human-readable.

## Invariants (don't relitigate)

- **State is event-sourced, per vehicle, in the local data root.** Append-only;
  corrections are new events, never edits. The current state is *computed* from events
  by `scripts/build_state.py` — never hand-edited.
- **Never fabricate.** Answer precedence: owner-confirmed `verified_specs` > cited KB >
  web search. A web result enters as community/inference, never auto-promoted. If
  nothing reliable is found, say it's a gap — never guess a number. See
  [references/kb-conventions.md](references/kb-conventions.md).
- **Safety is gated, not just footnoted.** Apply the four-tier model in
  [references/safety.md](references/safety.md); a safety item on an estimated interval
  never reads a bare "OK"; an interference engine fails closed.
- **The model never does the due-math free-hand** — it runs `scripts/due.py` via
  `build_state.py`.
- **Cost: zero beyond your Claude plan.** Every data source (NHTSA vPIC, NHTSA recalls,
  web search) is keyless.

## Config & data root

Skill code (this directory — **Tier-1**, shipped) is separate from your **instance
config** (**Tier-2**, `~/.solytus/garage/config.yaml`) and your **data** (**Tier-3**).
Resolve the data root on every run via `scripts/config.py`: `GARAGE_DATA_ROOT` env →
config `data_root` → `~/.solytus/garage/data`. Each vehicle is a directory under
`vehicles/<slug>/` (events, knowledge, vehicle.json, schedule.json). Nothing personal
lives in the skill.

## Vehicle selection

Infer which vehicle a command refers to from context (a name/nickname/make-model the
user mentioned, the only vehicle, or the one just discussed — `scripts/select_vehicle.py`).
Prompt to pick (a short multiple-choice) only when genuinely ambiguous, and **always name
the target vehicle in the confirmation before writing an event** — append-only
mis-attribution is painful to undo. See [references/vehicles.md](references/vehicles.md).

## Router — load ONLY the matched reference (plus schemas.md when writing state)

| The user is… | Triggers | Load |
|---|---|---|
| adding a vehicle | "add my…", "new vehicle", first run | `references/onboarding.md` |
| logging work | "log…", "I changed/did/replaced…", a receipt photo | `references/log.md` |
| updating the vehicle | "added…", "fixed…", "want to do … next", a mod | `references/build-sheet.md` |
| asking a question | torque/spec/fluid, "why is…", a symptom | `references/knowledge.md` |
| ingesting a document | "photo of the manual / FSM / service record" | `references/ingest.md` |
| viewing state | "current state", "service history", "the garage" | `references/state.md` (READ) |
| what's due / overdue | "what's due", "am I due for…" | `references/whats-due.md` |
| capturing in the field | a one-line note to reconcile later | `references/reconcile.md` |
| exporting | "export / print a checklist / sell sheet / torque sheet" | `references/export.md` |

Schemas (event / vehicle.json / schedule.json / KB) are in
[references/schemas.md](references/schemas.md). Model: Sonnet for routine logging/lookup;
Opus for a big research seed or a tricky diagnosis. Never self-escalate mid-task.
