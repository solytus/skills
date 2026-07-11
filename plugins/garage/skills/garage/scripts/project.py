"""
project.py — deterministic projection core for the Garage skill. Pure, no I/O.

Carries forward Tacoma's event-sourced reduce. Event file format: a header of
`key: value` lines + an optional trailing `notes:` block. Authority = seq
(ascending). Append-only; corrections are new events, never edits.

Two generalizations from the single-vehicle original:
  - every event carries a `vehicle_id`, and
  - mileage is recorded in a multi-clock `readings:` field (`name=int` pairs)
    instead of the fixed `chassis_miles`/`engine_miles` columns. Derived clocks
    (e.g. a swapped engine) are computed from their base, never logged.
"""
import re
from typing import Any

_INT_FIELDS = {"seq", "cost", "supersedes"}
_LIST_FIELDS = {"mods", "known_issues", "backlog"}

# Defense from the retired Drive-Docs era (markdown-escaped round-trips). No-op on
# clean local events; kept cheap for any event that ever passed through Docs.
_MD_ESCAPE = re.compile(r"\\([\\`*_{}\[\]()#+.!~=<>-])")


def _unescape(s: str) -> str:
    return _MD_ESCAPE.sub(r"\1", s)


_READING_RE = re.compile(r"([A-Za-z_]\w*)\s*=\s*(-?[\d,]+)")


def parse_readings(raw: str | None) -> dict[str, int]:
    """Parse a `readings:` value ("chassis=260233, engine=20000") into {name: int}.

    Anchored on `name=number` tokens so a thousands-comma inside a number
    ("260,233") and a comma between pairs are both handled. Non-numeric values are
    ignored; an empty or missing value yields {}.
    """
    out: dict[str, int] = {}
    for name, val in _READING_RE.findall(raw or ""):
        digits = val.replace(",", "")
        if digits.lstrip("-").isdigit():
            out[name] = int(digits)
    return out


def parse_event(text: str) -> dict[str, Any]:
    """Parse one event file's text into a typed dict.

    Integer fields (seq, cost, supersedes) are cast (commas stripped, empty ->
    None). `readings` is parsed into a {name: int} dict. The `notes:` block is the
    remainder after the `notes:` line. Other empty values -> None.
    """
    lines = text.splitlines()
    header_lines: list[str] = []
    notes_start: int | None = None
    for i, line in enumerate(lines):
        if line.startswith("notes:"):
            notes_start = i
            break
        header_lines.append(line)

    result: dict[str, Any] = {}
    for line in header_lines:
        if ":" not in line:
            continue
        key, _, raw_val = line.partition(":")
        key = _unescape(key.strip())
        raw_val = _unescape(raw_val.strip())
        if key in _INT_FIELDS:
            if raw_val == "":
                result[key] = None
            else:
                try:
                    result[key] = int(raw_val.replace(",", ""))
                except ValueError:
                    result[key] = None
        else:
            result[key] = raw_val if raw_val != "" else None

    result["readings"] = parse_readings(result.get("readings"))

    if notes_start is not None:
        note_lines = [l.lstrip() for l in lines[notes_start + 1:]]
        notes_text = _unescape("\n".join(note_lines).strip())
        result["notes"] = notes_text if notes_text else None
    else:
        result["notes"] = None
    return result


def parse_seq_from_filename(name: str) -> int:
    """Extract the leading integer seq from an event filename (the authority)."""
    m = re.match(r"^(\d+)-", name)
    if not m:
        raise ValueError(f"Filename {name!r} does not start with a '<digits>-' prefix")
    return int(m.group(1))


def reduce_events(events: list[dict[str, Any]]) -> dict[str, Any]:
    """Fold parsed events into current state. Pure, deterministic, idempotent.

    Output: vehicle{summary}, mods[], known_issues[], backlog[], service_history[],
    last_done{slug: record}, verified_specs{key: {...}}, max_seq.
    Each service_history record carries a `readings` {clock: int} dict.
    """
    empty = {
        "vehicle": {"summary": None}, "mods": [], "known_issues": [], "backlog": [],
        "service_history": [], "last_done": {}, "verified_specs": {}, "max_seq": 0,
    }
    if not events:
        return empty

    sorted_events = sorted(events, key=lambda e: (e.get("seq") or 0))
    voided: set[int] = set()
    for ev in sorted_events:
        if ev.get("type") == "correction" and isinstance(ev.get("supersedes"), int):
            voided.add(ev["supersedes"])

    vehicle_summary: str | None = None
    mods: list[str] = []
    known_issues: list[str] = []
    backlog: list[str] = []
    service_history: list[dict] = []
    last_done: dict[str, dict] = {}
    verified_specs: dict[str, dict] = {}
    max_seq = 0

    for ev in sorted_events:
        seq = ev.get("seq") or 0
        max_seq = max(max_seq, seq)
        ev_type = ev.get("type")
        if seq in voided or ev_type == "correction":
            continue

        if ev_type in ("maintenance", "baseline"):
            service = ev.get("service")
            if service:
                record = {
                    "seq": ev.get("seq"),
                    "service": service,
                    "date": ev.get("date"),
                    "readings": ev.get("readings") or {},
                    "parts": ev.get("parts"),
                    "fluids": ev.get("fluids"),
                    "cost": ev.get("cost"),
                    "summary": ev.get("summary"),
                }
                service_history.append(record)
                last_done[service] = record

        elif ev_type == "build-sheet":
            field = ev.get("field")
            value = ev.get("value") or ""
            clean = value.lstrip("+") if value.startswith("+") else value
            if not clean:
                continue
            if field == "vehicle":
                vehicle_summary = clean
            elif field in _LIST_FIELDS:
                target = {"mods": mods, "known_issues": known_issues, "backlog": backlog}[field]
                if clean not in target:
                    target.append(clean)

        elif ev_type == "verified-spec":
            key = ev.get("key")
            if not key:
                continue
            spec_seq = ev.get("seq")
            existing = verified_specs.get(key)
            if existing is None or (spec_seq or 0) > (existing.get("seq") or 0):
                verified_specs[key] = {
                    "value": ev.get("value"),
                    "applies_to": ev.get("applies_to"),
                    "source_doc": ev.get("source_doc"),
                    "seq": spec_seq,
                    "confirmed": ev.get("confirmed"),
                }

    return {
        "vehicle": {"summary": vehicle_summary},
        "mods": mods, "known_issues": known_issues, "backlog": backlog,
        "service_history": service_history, "last_done": last_done,
        "verified_specs": verified_specs, "max_seq": max_seq,
    }


def validate_events(events: list[dict[str, Any]], expected_vehicle_id: str | None = None,
                    by_name: dict | None = None) -> list[str]:
    """Return a list of integrity problems (empty = clean).

    Checks: duplicate seq; correction with missing/dangling supersedes; (when
    expected_vehicle_id given) a misfiled event; (when by_name given) a `readings`
    entry for a derived or undeclared clock — only independent base clocks are
    ever logged.
    """
    problems: list[str] = []
    seq_counts: dict[int, int] = {}
    all_seqs: set[int] = set()
    for ev in events:
        seq = ev.get("seq")
        if isinstance(seq, int):
            seq_counts[seq] = seq_counts.get(seq, 0) + 1
            all_seqs.add(seq)
    for seq, count in seq_counts.items():
        if count > 1:
            problems.append(f"Duplicate seq: {seq} appears {count} times")

    for ev in events:
        ev_seq = ev.get("seq")
        if ev.get("type") == "correction":
            sup = ev.get("supersedes")
            if sup is None:
                problems.append(f"Correction (seq {ev_seq}) has no supersedes value")
            elif sup not in all_seqs:
                problems.append(f"Correction (seq {ev_seq}) supersedes seq {sup}, not found")

        if expected_vehicle_id is not None:
            vid = ev.get("vehicle_id")
            if vid is not None and vid != expected_vehicle_id:
                problems.append(
                    f"Event (seq {ev_seq}) has vehicle_id {vid!r}, expected {expected_vehicle_id!r}")

        if by_name is not None:
            for clock_name in (ev.get("readings") or {}):
                c = by_name.get(clock_name)
                if c is None:
                    problems.append(f"Event (seq {ev_seq}) logs an undeclared clock {clock_name!r}")
                elif getattr(c, "kind", None) != "odometer":
                    problems.append(
                        f"Event (seq {ev_seq}) logs derived clock {clock_name!r} "
                        "directly — derived clocks are computed, never logged")
    return problems


def check_monotonic(events: list[dict[str, Any]], base_name: str) -> list[str]:
    """Warn (don't reject) when a base-clock reading steps backwards over time.

    Catches a fat-fingered odometer or a 5/6-digit rollover. Considers
    maintenance/baseline events carrying a reading for `base_name`, in date order.
    """
    rows = []
    for ev in events:
        if ev.get("type") not in ("maintenance", "baseline"):
            continue
        val = (ev.get("readings") or {}).get(base_name)
        if val is None:
            continue
        rows.append((ev.get("date") or "", ev.get("seq") or 0, val))
    rows.sort(key=lambda r: (r[0], r[1]))
    warnings: list[str] = []
    prev = None
    for date_s, seq, val in rows:
        if prev is not None and val < prev:
            warnings.append(
                f"{base_name} reading {val:,} (seq {seq}, {date_s}) is below the prior "
                f"reading {prev:,} — possible odometer rollback or rollover")
        prev = max(prev, val) if prev is not None else val
    return warnings


def next_seq(events: list[dict[str, Any]]) -> int:
    """The next monotonic seq to assign (max + 1; empty store starts at 1)."""
    seqs = [e.get("seq") for e in events if isinstance(e.get("seq"), int)]
    return (max(seqs) + 1) if seqs else 1
