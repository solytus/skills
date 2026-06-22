# Schemas — Habitat data store

Single source of truth for the on-disk shapes. Load this with every workflow.

**Format:** Markdown + YAML frontmatter, one file per entity. Pure JSON only under
`cache/` (machine-managed). Every record carries `schema_version` (currently `1`).

## `place_key`

```
place_key = "<level>::<normalized_name>::<geocode_truncated>"
```

- **level** — `country` | `state` | `county` | `city` | `neighborhood` | `property`
- **normalized_name** — lowercased, hyphenated, state suffix for cities/below
  (e.g. `tacoma-wa`, `capitol-hill-seattle`). Used in filenames + the log for readability.
  **International:** an ISO-3166 alpha-2 country suffix rides in the same slot — the country
  analog of the state suffix (`portugal-pt`, and when deepened, `lisbon-pt`).
- **geocode_truncated** — 4-decimal `lat,lon`. Domestic: Census Geocoder. International:
  a representative country centroid from `country_centroids.csv` (via
  `country_lookups.resolve_country`); a single point at country grain is intentionally coarse
  and the eval narrative says so.

Examples: `city::tacoma-wa::47.2529,-122.4443` · `country::portugal-pt::39.5000,-8.0000` · `state::washington::47.7511,-120.7401`

Cache filenames sanitize the key: `::` → `__`, `,` → `_`
(`city::tacoma-wa::47.25,-122.44` → `city__tacoma-wa__47.25_-122.44.json`).

## profile (`profile/profile.md`)

```yaml
schema_version: 1
owner: me                 # reserved for Phase 2 multi-profile; single profile in V1
version: 7                  # bumped on each committed interview
updated_at: 2026-05-26T14:32
preferences:
  - name: "walkable to a bakery I love"
    weight: high            # low | medium | high   (optional)
    must_have: false        # disqualifies a place when violated (optional)
    must_not: false         # disqualifies a place when present (optional)
    source_hint: reason     # reason | auto:<source>
    portability:            # OPTIONAL — per-context treatment (international extension)
      international:         #   absent => preference applies as-is everywhere
        measurable: false   #   can it be measured at this grain/region?
        status: resolved    #   portable | needs-renegotiation | resolved
        treatment: soften-to-nice-to-have  # as-is | soften-to-nice-to-have | reframe | drop
        rationale: "city-grain ethnic % unavailable free worldwide; read diaspora + search"
        resolved_at: 2026-05-29
narrative_directions:
  - "partner cares about teaching hospitals — factor in"
```
**Preference portability** (international): a preference may carry an optional `portability`
block keyed by context (`domestic`/`international`, or a country code for per-country
overrides). It records whether the preference can be measured in that context and how it was
renegotiated (soften / reframe / drop). Absent ⇒ portable everywhere (all existing
preferences are unaffected). Pure Claude-read memory — no script parses it.
Body: optional prose about who this profile is for. The ~12-dimension seed taxonomy is
**not** stored here — it is an interview coverage checklist only (`interview.md`).

## place (`places/<level>/<slug>.md`)

```yaml
schema_version: 1
place_key: "city::tacoma-wa::47.2529,-122.4443"
level: city
normalized_name: tacoma-wa
geocode: "47.2529,-122.4443"
parent_chain: ["state::washington::47.7511,-120.7401"]
country_code: US            # OPTIONAL ISO alpha-2 (international extension); absent ⇒ domestic
grain_class: domestic       # OPTIONAL domestic | international; absent ⇒ domestic
status: Researched          # Surfaced → Considered → Researched → Visited → Decided
verdict: Shortlist          # Curious | Shortlist | On hold | Disqualified | Decided-against | Decided-for
screen_verdict: Promising   # OPTIONAL, country grain only: Promising | Marginal | Ruled-out | Pathway-blocked
gem_blocker: cost            # OPTIONAL (gem-finder): the SINGLE dominant drag holding an
                             #   otherwise-good place down. Vocab: cost | crime | belonging |
                             #   mosquitoes | airport | cannabis | nature | size | none
gem_blocker_note: ""         # OPTIONAL free-text nuance for the blocker
fit: 72                     # latest fit, as of last_eval / profile_version (fast log queries)
last_touched: 2026-05-26
last_eval: "evaluations/tacoma-wa/2026-05-26-1432.md"
verdict_history:
  - {date: 2026-05-26, verdict: Shortlist, eval: "evaluations/tacoma-wa/2026-05-26-1432.md", note: ""}
owner: me
```
Body: short identity line + the latest eval's narrative snapshot (or pointer). Heavy
detail lives in evaluation files, keeping the log query path (frontmatter) light.

**`gem_blocker`** (gem-finder, optional): names the one dominant high-weight miss on a
near-miss place, so the gem-hunt can search its neighbors for the *fix* (e.g. Riverton
`gem_blocker: crime` → hunt nearby low-crime towns → Hillcrest). Bounded vocabulary only;
Claude sets it during `evaluate`. Additive — absent on old records, read as "unset".

## evaluation (`evaluations/<slug>/<timestamp>.md`)

```yaml
schema_version: 1
place_key: "city::tacoma-wa::47.2529,-122.4443"
evaluated_at: 2026-05-26T14:32
profile_version: 7
model: sonnet
refresh: false              # true if the user forced a cache bypass
hard_filter: pass           # pass | fail
hard_filter_failed: []      # preference names that disqualified, if any
fit: 72                     # omitted/null when hard_filter == fail
```
Body, fixed order: **Hard filters** → **Narrative + fit** (incl. ranking note) →
**Commercial vitality block** (4 components) → **Social signals** → **Sources footer**.

## interview (`interviews/<timestamp>.md`)

```yaml
schema_version: 1
interviewed_at: 2026-05-26T14:32
seed: "I keep thinking about smaller college towns"
model: opus
profile_version_before: 6
profile_version_after: 7    # equals _before when no change committed
changes:
  - {op: add,    target: preference, name: "...", weight: high, applied: true,  rationale: "..."}
  - {op: edit,   target: preference, name: "climate", field: weight, from: medium, to: high, applied: true, rationale: "..."}
  - {op: remove, target: preference, name: "near a ski resort", applied: false, rationale: "..."}
  - {op: flag,   target: preference, name: "HOA-governed", set: must_not, applied: true, rationale: "..."}
summary: "Human-readable what-changed-and-why."
```
Body: the full transcript. `applied` records the per-change cherry-pick outcome.

## Migration / evolution policy

- **Additive-only.** New frontmatter fields are optional; readers default missing
  fields. Never rename or remove a field in place — add new, leave old.
- **`schema_version`** on every record (V1 = 1). Records without it read as v1.
- **Cache is disposable, never migrated.** A payload-shape change clears `cache/<source>/`;
  data is rebuilt by re-fetch.
- **Config is additive with defaults.** Missing keys fall back to code defaults
  (`stale_days` → 90).

The year-5 layout is identical to year-1's; only contents differ.

## Indexing

Log queries glob `places/**/*.md` and parse frontmatter only (kilobytes total at
hundreds of places). No separate index in V1. Evaluations and transcripts live outside
the query path, so they accumulate without slowing log review.
