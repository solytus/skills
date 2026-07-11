"""schedule.py — per-vehicle maintenance schedule as cited DATA. Pure, no I/O.

The single-vehicle hard-coded SCHEDULE becomes a loader/validator over a
per-vehicle `schedule.json`. Each item names the CLOCK it tracks (so a timing
belt on a swapped engine reads the engine clock, not the chassis odometer),
carries provenance (`tier` + `source`), and flags generic-heuristic fallbacks as
`estimate: true`.

`validate_schedule` enforces the integrity the due-tracker depends on. The
locator-bearing-source gate for claimed-OEM (`estimate: false`) items is applied
separately by the KB linter when the schedule is researched (Phase 2).
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

TIERS = ("official", "community", "inference")
BASELINE_TIERS = ("inspect", "safety", "fluid", "engine", None)
SCHEMA_VERSION = 1


@dataclass(frozen=True)
class ScheduleItem:
    key: str
    label: str
    service_slug: str
    clock: str                      # a declared clock name (e.g. "chassis" | "engine")
    mileage_interval: int | None
    time_interval_months: int | None
    safety_critical: bool
    baseline_tier: str | None       # "inspect" | "safety" | "fluid" | "engine" | None
    is_fluid: bool
    provenance: str
    estimate: bool                  # True = generic heuristic / set-by-us, not a cited figure
    tier: str                       # official | community | inference
    source: str
    aliases: tuple[str, ...] = ()
    severe_mileage_interval: int | None = None
    severe_time_interval_months: int | None = None
    include_if: tuple = ()          # (("drivetrain", ("4WD", "AWD")), ...) config predicates


def _to_item(d: dict) -> ScheduleItem:
    return ScheduleItem(
        key=d["key"], label=d["label"], service_slug=d["service_slug"], clock=d["clock"],
        mileage_interval=d.get("mileage_interval"), time_interval_months=d.get("time_interval_months"),
        safety_critical=bool(d.get("safety_critical", False)), baseline_tier=d.get("baseline_tier"),
        is_fluid=bool(d.get("is_fluid", False)), provenance=d.get("provenance", ""),
        estimate=bool(d.get("estimate", False)), tier=d.get("tier", "inference"),
        source=d.get("source", ""), aliases=tuple(d.get("aliases") or ()),
        severe_mileage_interval=d.get("severe_mileage_interval"),
        severe_time_interval_months=d.get("severe_time_interval_months"),
        include_if=tuple((k, tuple(v)) for k, v in (d.get("include_if") or {}).items()),
    )


def applies_to_vehicle(item: ScheduleItem, vehicle: dict) -> bool:
    """True unless a config predicate excludes this item (e.g. a transfer case on a 2WD)."""
    for field, allowed in item.include_if:
        vval = str(vehicle.get(field, "")).lower()
        if not any(str(a).lower() in vval for a in allowed):
            return False
    return True


def effective_intervals(item: ScheduleItem, usage_profile: str | None) -> tuple[int | None, int | None]:
    """Pick the interval set for a usage profile. Default to SEVERE when unknown — the
    severe triggers (short trips, towing, cold, dust, stop-and-go) catch most real drivers,
    and the long 'normal' interval is the unsafe default to pick blind."""
    use_severe = usage_profile != "normal"
    m = item.mileage_interval
    t = item.time_interval_months
    if use_severe and item.severe_mileage_interval is not None:
        m = item.severe_mileage_interval
    if use_severe and item.severe_time_interval_months is not None:
        t = item.severe_time_interval_months
    return m, t


def load_schedule(source) -> list[ScheduleItem]:
    """Load a schedule from a dict, a JSON string, or a path to a schedule.json."""
    if isinstance(source, dict):
        data = source
    elif isinstance(source, (str, Path)) and Path(str(source)).exists():
        data = json.loads(Path(source).read_text())
    else:
        data = json.loads(source)
    return [_to_item(i) for i in data.get("items", [])]


def validate_schedule(items: list[ScheduleItem], clocks: list) -> None:
    """Raise ValueError on any structural or provenance-consistency defect."""
    clock_names = {getattr(c, "name", c) for c in clocks}
    seen_keys: set[str] = set()
    seen_slugs: set[str] = set()
    for i in items:
        if i.key in seen_keys:
            raise ValueError(f"duplicate key: {i.key}")
        if i.service_slug in seen_slugs:
            raise ValueError(f"duplicate slug: {i.service_slug}")
        seen_keys.add(i.key)
        seen_slugs.add(i.service_slug)
        if i.clock not in clock_names:
            raise ValueError(f"{i.key}: clock {i.clock!r} is not a declared clock")
        if i.baseline_tier not in BASELINE_TIERS:
            raise ValueError(f"{i.key}: bad baseline_tier {i.baseline_tier!r}")
        if i.tier not in TIERS:
            raise ValueError(f"{i.key}: bad tier {i.tier!r}")
        if i.mileage_interval is None and i.time_interval_months is None:
            raise ValueError(f"{i.key}: needs at least one interval")
        if i.is_fluid and i.time_interval_months is None:
            raise ValueError(f"{i.key}: fluid with no time interval")
        # estimate <-> inference biconditional: a guessed interval must read as inference,
        # and a cited interval must not masquerade as a guess.
        if i.estimate and i.tier != "inference":
            raise ValueError(f"{i.key}: estimate=True requires tier 'inference', got {i.tier!r}")
        if not i.estimate and i.tier == "inference":
            raise ValueError(f"{i.key}: tier 'inference' requires estimate=True")
