"""build_state.py — rebuild a vehicle's current-state from its event log.

The one I/O driver. For a vehicle directory under the data root it loads
vehicle.json (clocks) + schedule.json, reduces events/ with project.py, renders
the current-state with snapshot.py, computes WHAT'S DUE, and writes
current-state.md. There is no published mirror and no PII guard at this stage —
the state file is home-private; redaction happens at export.

`--as-of DATE` pins the date used for time-based due math so a rebuild (and the
migration acceptance test) is reproducible.

    python build_state.py --vehicle-dir ~/.solytus/garage/data/vehicles/1995-toyota-tacoma
"""
from __future__ import annotations

import argparse
import json
import dataclasses as _dc
import os
from datetime import date as _date
from pathlib import Path
from typing import Any

import clocks as ck
import due as _due
import project
import safety
import schedule as _sched
import snapshot

STATE_NAME = "current-state.md"
_STATUS_TAG = {"OVERDUE": "[OVERDUE]", "DUE SOON": "[DUE SOON]", "OK": "[ok]", "UNKNOWN": "[unknown]"}


def load_events(events_dir) -> list[dict[str, Any]]:
    """Parse every event file (filename seq is authority); skip non-event files."""
    events: list[dict[str, Any]] = []
    d = Path(events_dir)
    if not d.exists():
        return events
    for name in sorted(os.listdir(d)):
        path = d / name
        if not path.is_file():
            continue
        try:
            seq = project.parse_seq_from_filename(name)
        except ValueError:
            continue
        ev = project.parse_event(path.read_text())
        ev["seq"] = seq
        events.append(ev)
    return events


def current_clock_readings(projection, base_name) -> tuple[dict, str | None]:
    """Latest reading per base clock + the date of that reading (highest reading wins)."""
    recs = [r for r in projection.get("service_history", [])
            if (r.get("readings") or {}).get(base_name) is not None]
    if not recs:
        return {}, None
    latest = max(recs, key=lambda r: r["readings"][base_name])
    return {base_name: latest["readings"][base_name]}, latest.get("date")


_BASELINE_TIERS = [("inspect", "1. Inspect-to-clear (cheap looks)"),
                   ("safety", "2. Safety time-bombs"),
                   ("fluid", "3. Fluid baselines (drain + reveal condition)"),
                   ("engine", "4. Remaining component-clock items")]


def render_due_section(items, projection, clock_readings, by_name, asof_date, current_date,
                       vehicle=None) -> str:
    rows = _due.compute_due(items, projection.get("last_done", {}), clock_readings, by_name, current_date)
    base_now = next(iter(clock_readings.values()), None)
    odo_str = "unknown" if base_now is None else f"{base_now:,}"
    interference = safety.interference_warning(vehicle or {})
    has_belt = any(r.service_slug == "timing-belt" for r in rows)
    lines = ["== WHAT'S DUE ==",
             f"(computed against odo {odo_str} as of last log: {asof_date}; "
             f"actual miles likely higher. Time figures are as of this rebuild.)"]
    # Surface the interference warning prominently whenever the vehicle has a belt item —
    # even (especially) when the belt history is UNKNOWN or no odometer has been logged.
    if interference and has_belt:
        lines.append(f"⚠ {interference}")
    for r in rows:
        if r.status == "UNKNOWN":
            continue
        warn = " !! SAFETY" if (r.safety_critical and r.status == "OVERDUE") else (" (safety)" if r.safety_critical else "")
        bits = []
        if r.miles_remaining is not None:
            bits.append(f"{r.miles_remaining:,} mi")
        if r.months_remaining is not None:
            bits.append(f"{r.months_remaining:.1f} mo")
        rem = " / ".join(bits) if bits else "-"
        gov = f" [{r.governing}]" if r.governing else ""
        tag, caveat = safety.due_display(r)            # safety item on an estimate never reads bare OK
        cav = f" — {caveat}" if caveat else ""
        belt = f"  ⚠ {interference}" if (interference and r.service_slug == "timing-belt") else ""
        lines.append(f"- {tag} {r.label}{warn}: {rem} remaining{gov}{cav}{belt}")

    unknown = [r for r in rows if r.status == "UNKNOWN"]
    if unknown:
        lines += ["", "== BASELINE CAMPAIGN (unknown history - establish in this order) =="]
        for tier_key, tier_label in _BASELINE_TIERS:
            group = [r for r in unknown if r.baseline_tier == tier_key]
            if not group:
                continue
            lines.append(tier_label + ":")
            for r in group:
                warn = " !! SAFETY" if r.safety_critical else ""
                lines.append(f"  - {r.label}{warn} - {r.note}")
        leftover = [r for r in unknown if r.baseline_tier is None]
        if leftover:
            lines.append("Other:")
            for r in leftover:
                lines.append(f"  - {r.label} - {r.note}")
    return "\n".join(lines) + "\n"


def _insert_before_max_seq(body: str, block: str) -> str:
    idx = body.rfind("\nmax_seq:")
    return body + block if idx == -1 else body[:idx] + block + body[idx:]


def build_vehicle(vehicle_dir, as_of: _date | None = None, write: bool = True) -> dict:
    """Reduce a vehicle's events and render its current-state.

    Returns {body, problems, monotonic_warnings}. Raises ValueError on integrity
    problems (misfiled events, bad clocks/schedule).
    """
    vdir = Path(vehicle_dir)
    vj = json.loads((vdir / "vehicle.json").read_text())
    clocks = ck.load_clocks(vj)
    ck.validate_clocks(clocks)
    by_name = ck.clocks_by_name(clocks)
    base_name = next(c.name for c in clocks if c.kind == ck.BASE_KIND)

    events = load_events(vdir / "events")
    problems = project.validate_events(events, vj.get("vehicle_id"), by_name)
    if problems:
        raise ValueError("Event store integrity problems:\n- " + "\n- ".join(problems))

    projection = project.reduce_events(events)

    sched_path = vdir / "schedule.json"
    items = _sched.load_schedule(sched_path) if sched_path.exists() else []
    if items:
        _sched.validate_schedule(items, clocks)
        # Apply this vehicle's config predicates + usage profile (default severe when unknown).
        usage = vj.get("usage_profile")
        items = [_dc.replace(i, mileage_interval=_sched.effective_intervals(i, usage)[0],
                             time_interval_months=_sched.effective_intervals(i, usage)[1])
                 for i in items if _sched.applies_to_vehicle(i, vj)]

    readings, asof = current_clock_readings(projection, base_name)
    current_date = as_of or _date.today()
    body = snapshot.render_full(projection, vehicle={"display": vj.get("display")}, clocks=clocks)
    if items:  # render even with no logged reading — else the belt/interference warning is dropped
        body = _insert_before_max_seq(body, "\n" + render_due_section(
            items, projection, readings, by_name, asof, current_date, vehicle=vj))

    monotonic = project.check_monotonic(events, base_name)

    if write:
        (vdir / STATE_NAME).write_text(body if body.endswith("\n") else body + "\n")
    return {"body": body, "problems": problems, "monotonic_warnings": monotonic}


def _parse_as_of(s: str | None) -> _date | None:
    return _date.fromisoformat(s) if s else None


def main() -> None:
    ap = argparse.ArgumentParser(description="Rebuild a vehicle's current-state from its events.")
    ap.add_argument("--vehicle-dir", required=True)
    ap.add_argument("--as-of", default=None, help="YYYY-MM-DD to pin time-based due math")
    args = ap.parse_args()
    result = build_vehicle(args.vehicle_dir, as_of=_parse_as_of(args.as_of))
    for w in result["monotonic_warnings"]:
        print(f"  WARNING: {w}")
    seq_line = [l for l in result["body"].splitlines() if l.startswith("max_seq:")]
    print(f"Rebuilt {STATE_NAME} ({seq_line[0] if seq_line else 'max_seq: ?'})")


if __name__ == "__main__":
    main()
