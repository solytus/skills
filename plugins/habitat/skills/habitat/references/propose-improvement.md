# Propose an improvement (opt-in)

Habitat is open-source and meant to be improved by the people who use it. When the user hits a
real gap — the skill got something wrong, missed a case, or there's a clearly better way — offer
to help them turn it into a **structured upstream proposal**. This is opt-in: only do it when the
user wants to contribute, never unprompted mid-task.

## What makes a good proposal

The aim is a *narrow, sourced, generalizable* change to the shipped (Tier-1) logic — not a tweak
that really belongs in the user's own Tier-3 data/config. Before drafting, sanity-check:

- **Is it generalizable?** Would it help other users, or is it specific to this person's
  preferences/data? (If specific → it belongs in their profile/config, not a PR.)
- **Is it sourced/honest?** Any factual or reference data must cite where it came from; mark
  anything unverified.
- **Is it in-pattern?** Does it respect the Tier-1/2/3 boundaries and the never-fabricate rule?

## Produce the artifact

Help the user assemble a proposal with these parts (this maps directly to the repo's
`.github/ISSUE_TEMPLATE/improvement_proposal.md` and PR template):

1. **The gap** — what fell short, in one or two sentences.
2. **The case that triggered it** — the concrete inputs/situation, ideally reproducible.
3. **The proposed change** — a focused diff to the generic logic, or a precise description of it.
4. **Sourcing** — citations for any new factual/reference data; unverified marked as such.
5. **Why it's generalizable** — why it helps beyond this one instance.

Then:

- If the change is small and clear, draft the actual diff and open it as a **PR** against the
  Solytus repo using the PR template.
- Otherwise, open an **issue** using the improvement-proposal template so it can be discussed
  first.

The maintainer reviews against the rubric in `CONTRIBUTING.md`; accepted changes ship to everyone,
and users pick them up with a `git pull` — their data is untouched (it lives in Tier-3).
