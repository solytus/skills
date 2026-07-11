"""due.py — deterministic 'what's due' compute, generalized to named clocks.

Pure functions, no I/O. The model never does this arithmetic free-hand; it calls
compute_due.

Each schedule item names the CLOCK it tracks. The clock's current reading and the
reading at the last service both flow through clocks.py, so a derived clock (a
swapped engine, a rebuilt transmission) is resolved from its base automatically —
and a record made before that clock existed is excluded, never read as a false
OVERDUE off the chassis odometer.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import clocks as ck

DUE_SOON_MILEAGE_FRAC = 0.10
DUE_SOON_TIME_MONTHS = 2.0
_DAYS_PER_MONTH = 30.44


def _months_between(last_date_str: str, current: date) -> float:
    return (current - date.fromisoformat(last_date_str)).days / _DAYS_PER_MONTH


def _classify_mileage(remaining: int, interval: int) -> str:
    if remaining < 0:
        return "OVERDUE"
    if remaining <= DUE_SOON_MILEAGE_FRAC * interval:
        return "DUE SOON"
    return "OK"


def _classify_time(months_remaining: float) -> str:
    if months_remaining < 0:
        return "OVERDUE"
    if months_remaining <= DUE_SOON_TIME_MONTHS:
        return "DUE SOON"
    return "OK"


@dataclass
class DueItem:
    key: str
    label: str
    status: str                 # OVERDUE | DUE SOON | OK | UNKNOWN
    safety_critical: bool
    clock: str
    miles_remaining: int | None
    months_remaining: float | None
    governing: str | None       # "mileage" | "time" | None
    last: dict | None
    note: str
    baseline_tier: str | None
    estimate: bool
    tier: str
    service_slug: str = ""


_STATUS_RANK = {"OVERDUE": 3, "DUE SOON": 2, "OK": 1}
_SORT_RANK = {"OVERDUE": 0, "DUE SOON": 1, "UNKNOWN": 2, "OK": 3}


def _base_name(by_name) -> str | None:
    for name, c in by_name.items():
        if c.kind == ck.BASE_KIND:
            return name
    return None


def _resolve_record(item, last_done, by_name):
    """Most recent record satisfying this item: its slug OR any alias.

    Ties broken by (date, base-clock reading, seq) — newest wins.
    """
    base = _base_name(by_name)
    slugs = (item.service_slug, *item.aliases)
    recs = [last_done[s] for s in slugs if last_done.get(s)]
    if not recs:
        return None
    return max(recs, key=lambda r: (
        r.get("date") or "",
        (r.get("readings") or {}).get(base, -1) if base else -1,
        r.get("seq") or -1,
    ))


def compute_due_item(item, last_done, clock_readings, by_name, current_date) -> DueItem:
    clock = by_name[item.clock]
    rec = _resolve_record(item, last_done, by_name)
    needs_miles = item.mileage_interval is not None
    rec_readings = (rec or {}).get("readings") or {}
    rec_miles = ck.record_reading(clock, rec_readings, by_name) if rec else None
    valid = bool(rec) and rec.get("date") and (not needs_miles or rec_miles is not None)
    # Exclude records made before a derived clock existed (e.g. pre-swap service).
    if valid and ck.is_pre_clock(clock, rec_readings, by_name):
        valid = False

    if not valid:
        note = item.provenance
        if clock.kind == ck.DERIVED_KIND:
            cur = ck.current_reading(clock, clock_readings, by_name)
            cur_s = f"~{cur:,} {clock.unit}" if cur is not None else "unknown"
            note += (f" | {clock.name} {cur_s} (est.); "
                     f"no post-{clock.name} record - baseline recommended")
        elif item.is_fluid:
            note += " | unknown fluid age - baseline due now"
        else:
            note += " | no record - baseline recommended"
        return DueItem(item.key, item.label, "UNKNOWN", item.safety_critical, item.clock,
                       None, None, None, None, note, item.baseline_tier, item.estimate, item.tier,
                       item.service_slug)

    candidates = []
    miles_remaining = None
    if item.mileage_interval is not None:
        cur_miles = ck.current_reading(clock, clock_readings, by_name)
        miles_remaining = item.mileage_interval - (cur_miles - rec_miles)
        candidates.append((_classify_mileage(miles_remaining, item.mileage_interval), "mileage"))
    months_remaining = None
    if item.time_interval_months is not None:
        months_remaining = item.time_interval_months - _months_between(rec["date"], current_date)
        candidates.append((_classify_time(months_remaining), "time"))

    status, governing = max(candidates, key=lambda c: _STATUS_RANK[c[0]])
    return DueItem(item.key, item.label, status, item.safety_critical, item.clock,
                   miles_remaining, months_remaining, governing, rec, item.provenance,
                   item.baseline_tier, item.estimate, item.tier, item.service_slug)


def compute_due(schedule_items, last_done, clock_readings, by_name, current_date) -> list[DueItem]:
    rows = [compute_due_item(i, last_done, clock_readings, by_name, current_date)
            for i in schedule_items]
    rows.sort(key=lambda r: (_SORT_RANK[r.status], not r.safety_critical, r.label))
    return rows
