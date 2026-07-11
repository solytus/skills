"""migrate_tacoma.py — one-time port of the standalone Tacoma store into Garage.

Reads the Tacoma event log + hard-coded schedule and writes a vehicle-keyed Garage
vehicle directory (events/, vehicle.json, schedule.json). Idempotent: re-running
reproduces identical files.

Per-event rewrites: add `vehicle_id`, fold `chassis_miles: N` into
`readings: chassis=N`, drop the vestigial `hash:` line (the mobile-reconcile
surface that used it is gone). seqs and correction/supersedes chains are preserved
1:1. The schedule's `clock_basis` ("chassis"/"engine") becomes a named `clock`,
and the swap odometer becomes the engine clock's offset.

    python migrate_tacoma.py --tacoma-state /path/Tacoma/state \
        --tacoma-schedule /path/Tacoma/skill/tacoma/scripts/schedule.py \
        --dest ~/.solytus/garage/data/vehicles/1995-toyota-tacoma
"""
from __future__ import annotations

import argparse
import sys
import importlib.util
import json
import os
from pathlib import Path

VEHICLE_ID = "1995-toyota-tacoma"
DISPLAY = "1995 Toyota Tacoma"


def transform_event(text: str, vehicle_id: str) -> str:
    """Rewrite one Tacoma event file into Garage form (pure)."""
    lines = text.splitlines()
    notes_idx = next((i for i, l in enumerate(lines) if l.startswith("notes:")), None)
    header = lines[:notes_idx] if notes_idx is not None else lines
    tail = lines[notes_idx:] if notes_idx is not None else []

    out: list[str] = []
    readings: dict[str, int] = {}
    vid_done = False
    for l in header:
        if l.startswith("hash:"):
            continue
        if l.startswith("chassis_miles:"):
            v = l.split(":", 1)[1].strip().replace(",", "")
            if v.lstrip("-").isdigit():
                readings["chassis"] = int(v)
            continue
        if l.startswith("engine_miles:"):
            continue  # engine is a derived clock — never logged
        out.append(l)
        if l.startswith("seq:") and not vid_done:
            out.append(f"vehicle_id: {vehicle_id}")
            vid_done = True
    if not vid_done:
        out.insert(0, f"vehicle_id: {vehicle_id}")
    if readings:
        out.append("readings: " + ", ".join(f"{k}={v}" for k, v in readings.items()))
    return "\n".join(out + tail) + "\n"


def _load_tacoma_schedule(path):
    spec = importlib.util.spec_from_file_location("tacoma_schedule", str(path))
    mod = importlib.util.module_from_spec(spec)
    # Register before exec so @dataclass can resolve the module via sys.modules.
    sys.modules["tacoma_schedule"] = mod
    spec.loader.exec_module(mod)
    return mod


def translate_schedule(tacoma_schedule_path, vehicle_id: str) -> dict:
    """Translate Tacoma's hard-coded SCHEDULE into a Garage schedule.json dict.

    clock_basis -> clock; estimate -> tier (inference if estimate else community,
    carrying the provenance string as the source). The locator-bearing-source gate
    for OEM items is applied later when the schedule is re-researched (Phase 2).
    """
    mod = _load_tacoma_schedule(tacoma_schedule_path)
    items = []
    for it in mod.SCHEDULE:
        items.append({
            "key": it.key, "label": it.label, "service_slug": it.service_slug,
            "clock": it.clock_basis,
            "mileage_interval": it.mileage_interval, "time_interval_months": it.time_interval_months,
            "safety_critical": it.safety_critical, "baseline_tier": it.baseline_tier,
            "is_fluid": it.is_fluid, "provenance": it.provenance, "estimate": it.estimate,
            "tier": "inference" if it.estimate else "community",
            "source": it.provenance,
            "aliases": list(it.aliases),
        })
    return {"schema_version": 1, "vehicle_id": vehicle_id, "items": items}


def build_vehicle_json(tacoma_schedule_path, vehicle_id: str, display: str,
                       vin: str = "", plate: str = "") -> dict:
    mod = _load_tacoma_schedule(tacoma_schedule_path)
    offset = int(mod.SWAP_CHASSIS_ODO)
    return {
        "schema_version": 1, "vehicle_id": vehicle_id, "slug": vehicle_id, "display": display,
        "year": 1995, "make": "Toyota", "model": "Tacoma", "trim": "Xtracab 4x4",
        "engine_code": "5VZ-FE", "engine": "JDM 5VZ-FE 3.4L V6 (swap)",
        "drivetrain": "4WD", "transmission": "A340F automatic", "fuel": "gasoline",
        "market": "US-CA", "vin": vin, "plate": plate,
        # 5VZ-FE is non-interference (a snapped belt strands, no valve damage) — KB-confirmed.
        "interference": False,
        "clocks": [
            {"name": "chassis", "kind": "odometer", "unit": "mi", "label": "Chassis odometer", "primary": True},
            {"name": "engine", "kind": "derived", "unit": "mi", "base": "chassis", "offset": offset,
             "label": "Swapped JDM 5VZ-FE engine miles",
             "note": "engine = chassis - offset; approximate (donor pre-swap miles unknown)"},
        ],
    }


# The legacy conventions doc is superseded by references/kb-conventions.md (8-column
# format); everything else in knowledge/ is hand-curated and ports verbatim.
_SKIP_KB = {"_CONVENTIONS.md"}


def copy_knowledge(knowledge_dir, dest_vehicle_dir) -> int:
    """Copy the hand-curated KB verbatim. identity.md is also lifted to the vehicle root
    as the human identity card. Returns the count of KB files copied."""
    kdir = Path(knowledge_dir)
    dest = Path(dest_vehicle_dir)
    dest_kb = dest / "knowledge"
    dest_kb.mkdir(parents=True, exist_ok=True)
    if not kdir.is_dir():
        return 0
    count = 0
    for src in sorted(kdir.glob("*.md")):
        if src.name in _SKIP_KB:
            continue
        (dest_kb / src.name).write_text(src.read_text())
        count += 1
        if src.name == "identity.md":
            (dest / "identity.md").write_text(src.read_text())
    return count


def migrate(tacoma_state_dir, tacoma_schedule_path, dest_vehicle_dir, *,
            tacoma_knowledge_dir=None, vehicle_id: str = VEHICLE_ID, display: str = DISPLAY,
            vin: str = "", plate: str = "", force: bool = False) -> int:
    """Write the Garage vehicle dir. Returns the number of events ported."""
    src_events = Path(tacoma_state_dir) / "events"
    dest = Path(dest_vehicle_dir)
    dest_events = dest / "events"
    if dest_events.exists() and any(dest_events.iterdir()) and not force:
        raise FileExistsError(f"{dest_events} already populated; pass force=True to overwrite")
    dest_events.mkdir(parents=True, exist_ok=True)

    count = 0
    for name in sorted(os.listdir(src_events)):
        src = src_events / name
        if not src.is_file() or not name[0].isdigit():
            continue
        (dest_events / name).write_text(transform_event(src.read_text(), vehicle_id))
        count += 1

    (dest / "vehicle.json").write_text(
        json.dumps(build_vehicle_json(tacoma_schedule_path, vehicle_id, display, vin, plate), indent=2) + "\n")
    (dest / "schedule.json").write_text(
        json.dumps(translate_schedule(tacoma_schedule_path, vehicle_id), indent=2) + "\n")

    if tacoma_knowledge_dir is None:
        # schedule.py is in skill/tacoma/scripts/; knowledge/ is its sibling.
        tacoma_knowledge_dir = Path(tacoma_schedule_path).resolve().parent.parent / "knowledge"
    copy_knowledge(tacoma_knowledge_dir, dest)
    return count


def main() -> None:
    ap = argparse.ArgumentParser(description="Migrate the standalone Tacoma store into Garage.")
    ap.add_argument("--tacoma-state", required=True)
    ap.add_argument("--tacoma-schedule", required=True)
    ap.add_argument("--tacoma-knowledge", default=None, help="defaults to <schedule>/../knowledge")
    ap.add_argument("--dest", required=True)
    ap.add_argument("--vin", default="")
    ap.add_argument("--plate", default="")
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()
    n = migrate(args.tacoma_state, args.tacoma_schedule, args.dest,
                tacoma_knowledge_dir=args.tacoma_knowledge,
                vin=args.vin, plate=args.plate, force=args.force)
    print(f"Ported {n} events to {args.dest}")


if __name__ == "__main__":
    main()
