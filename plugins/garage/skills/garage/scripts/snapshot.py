"""snapshot.py — render a vehicle's current-state projection to text. Pure, no I/O.

One vehicle's projection (from project.reduce_events) becomes the home-private
`current-state.md`. There is no published mirror, so this module renders the full
view only; the export subsystem applies PII redaction at the boundary where data
actually leaves the data root.

Service-history / last-done / verified-specs formatting is held identical to the
single-vehicle original so the migration reproduces the existing projection.
"""
from __future__ import annotations

from typing import Any

import clocks as ck


def _base_clock(clocks):
    if clocks:
        for c in clocks:
            if c.kind == ck.BASE_KIND:
                return c
    return ck.Clock(name="chassis", kind=ck.BASE_KIND, unit="mi", primary=True)


def _reading_str(record: dict, base) -> str:
    """Render the base-clock reading the way the single-vehicle tool did: 'N mi'."""
    m = (record.get("readings") or {}).get(base.name)
    return f"{m:,} {base.unit}" if isinstance(m, int) else f"— {base.unit}"


def render_full(projection: dict[str, Any], vehicle: dict | None = None, clocks=None) -> str:
    base = _base_clock(clocks)
    max_seq = projection.get("max_seq", 0)
    title = (vehicle or {}).get("display") or "GARAGE"
    lines: list[str] = [
        f"{title} — CURRENT STATE (seq {max_seq})",
        "Derived from events/ by project.reduce_events. Highest-seq snapshot is authoritative.",
        "",
    ]

    summary = (projection.get("vehicle") or {}).get("summary")
    lines += ["== VEHICLE ==", summary or "(unknown)", ""]

    def section(title: str, items: list[str]) -> None:
        lines.append(f"== {title} ==")
        lines.extend(f"- {it}" for it in items) if items else lines.append("(none)")
        lines.append("")

    section("MODS", projection.get("mods", []))
    section("KNOWN ISSUES", projection.get("known_issues", []))
    section("BACKLOG", projection.get("backlog", []))

    lines.append("== SERVICE HISTORY ==")
    history = projection.get("service_history", [])
    if history:
        for r in history:
            lines.append(
                f"- seq {r.get('seq')} | {r.get('service')} | {r.get('date') or '—'} | "
                f"{_reading_str(r, base)} | {r.get('parts') or '—'} | {r.get('fluids') or '—'} | "
                f"{r.get('summary') or '—'}"
            )
    else:
        lines.append("(none yet)")
    lines.append("")

    lines.append("== LAST DONE ==")
    last_done = projection.get("last_done", {})
    if last_done:
        for service in sorted(last_done):
            r = last_done[service]
            lines.append(f"- {service}: {r.get('date') or '—'} @ {_reading_str(r, base)} (seq {r.get('seq')})")
    else:
        lines.append("(none yet)")
    lines.append("")

    lines.append("== VERIFIED SPECS (owner-confirmed from documents) ==")
    specs = projection.get("verified_specs", {})
    if specs:
        for key in sorted(specs):
            s = specs[key]
            src = f" [{s.get('source_doc')}]" if s.get("source_doc") else ""
            applies = f" ({s.get('applies_to')})" if s.get("applies_to") else ""
            lines.append(f"- {key}: {s.get('value')}{applies}{src}")
    else:
        lines.append("(none yet)")
    lines.append("")

    lines.append(f"max_seq: {max_seq}")
    return "\n".join(lines)
