"""clocks.py — the multi-clock model. Pure Python, no I/O.

A vehicle tracks one or more named clocks. v1 supports exactly:
  - one primary `odometer` BASE clock (`mi` or `km`), and
  - zero-or-more single-segment `derived` mileage clocks, where
        derived_reading = base_reading - offset   (offset >= 0, same unit as base).

A derived clock models a component installed partway through the vehicle's life
(a swapped engine, a rebuilt transmission) so its service items track the
component's own miles, not the chassis odometer. The offset cancels in any
`current - record` delta, so due-math on a derived clock equals the same math on
its base — the derived value only matters for display and the pre-clock cutoff.

`validate_clocks` REJECTS anything outside this model (hours clocks, chained
derived clocks, a second swap needing a piecewise offset, unknown base, more than
one base) with a clear error rather than silently miscomputing. Those cases are
deferred to a later version.
"""
from __future__ import annotations

from dataclasses import dataclass

VALID_UNITS = ("mi", "km")
BASE_KIND = "odometer"
DERIVED_KIND = "derived"


class ClockConfigError(Exception):
    """A vehicle's clock configuration is malformed or unsupported in this version."""


@dataclass(frozen=True)
class Clock:
    name: str
    kind: str                 # "odometer" (base) | "derived"
    unit: str                 # "mi" | "km"
    base: str | None = None   # derived clocks only: the base clock name
    offset: int = 0           # derived clocks only: base - offset
    label: str = ""
    primary: bool = False
    note: str = ""


def load_clocks(vehicle: dict) -> list[Clock]:
    """Build Clock objects from a vehicle.json dict's `clocks` list.

    A vehicle with no declared clocks gets one primary `chassis` odometer (mi).
    """
    raw = vehicle.get("clocks") or []
    if not raw:
        return [Clock(name="chassis", kind=BASE_KIND, unit="mi",
                      label="Chassis odometer", primary=True)]
    return [Clock(
        name=c["name"],
        kind=c.get("kind", BASE_KIND),
        unit=c.get("unit", "mi"),
        base=c.get("base"),
        offset=int(c.get("offset", 0)),
        label=c.get("label", ""),
        primary=bool(c.get("primary", False)),
        note=c.get("note", ""),
    ) for c in raw]


def clocks_by_name(clocks: list[Clock]) -> dict[str, Clock]:
    return {c.name: c for c in clocks}


def _resolve(clock: Clock, readings: dict, by_name: dict[str, Clock]) -> int | None:
    """Resolve a clock to an integer reading from a `name=int` readings dict.

    Independent (base) clocks read straight from the dict; a derived clock reads
    its base and subtracts the offset. Unknown base reading -> None.
    """
    if clock.kind == DERIVED_KIND:
        base = by_name.get(clock.base)
        if base is None:
            return None
        base_val = _resolve(base, readings, by_name)
        return None if base_val is None else base_val - clock.offset
    return readings.get(clock.name)


def current_reading(clock: Clock, clock_readings: dict, by_name: dict[str, Clock]) -> int | None:
    """The clock's current reading given the latest reading per base clock."""
    return _resolve(clock, clock_readings, by_name)


def record_reading(clock: Clock, rec_readings: dict, by_name: dict[str, Clock]) -> int | None:
    """The clock's reading at the time of one event (its `readings` dict)."""
    return _resolve(clock, rec_readings, by_name)


def is_pre_clock(clock: Clock, rec_readings: dict, by_name: dict[str, Clock]) -> bool:
    """True if this record predates a derived clock (base reading < offset).

    Such a record was made before the component existed (e.g. a timing belt on
    the *previous* engine), so it must not satisfy a derived-clock service item.
    Base clocks are never pre-clock.
    """
    if clock.kind != DERIVED_KIND:
        return False
    base = by_name.get(clock.base)
    if base is None:
        return False
    base_val = _resolve(base, rec_readings, by_name)
    return base_val is not None and base_val < clock.offset


def is_backwards(prev: int, curr: int) -> bool:
    """True if a later base reading is lower than an earlier one (fat-finger / rollover)."""
    return curr < prev


def validate_clocks(clocks: list[Clock]) -> None:
    """Raise ClockConfigError unless `clocks` fits the v1-supported model."""
    names = [c.name for c in clocks]
    if len(names) != len(set(names)):
        raise ClockConfigError("duplicate clock name")

    by_name = clocks_by_name(clocks)
    bases = [c for c in clocks if c.kind == BASE_KIND]
    if len(bases) != 1:
        raise ClockConfigError(
            f"exactly one base odometer clock is required; found {len(bases)}")

    for c in clocks:
        if c.unit not in VALID_UNITS:
            raise ClockConfigError(f"{c.name}: unsupported unit {c.unit!r}")
        if c.kind == BASE_KIND:
            continue
        if c.kind != DERIVED_KIND:
            raise ClockConfigError(
                f"{c.name}: clock kind {c.kind!r} is not supported in this version")
        # derived-clock rules
        base = by_name.get(c.base)
        if base is None:
            raise ClockConfigError(f"{c.name}: derived base {c.base!r} is not a declared clock")
        if base.kind != BASE_KIND:
            raise ClockConfigError(
                f"{c.name}: derived clocks must reference the base odometer, "
                f"not another derived clock (chained/piecewise clocks are not supported)")
        if c.unit != base.unit:
            raise ClockConfigError(f"{c.name}: derived unit {c.unit!r} != base unit {base.unit!r}")
        if c.offset < 0:
            raise ClockConfigError(f"{c.name}: derived offset must be >= 0")
