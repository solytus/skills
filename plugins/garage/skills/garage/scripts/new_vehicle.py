"""new_vehicle.py — scaffold a vehicle directory at onboarding. Stdlib only.

Writes vehicle.json (one primary chassis odometer; the owner adds a derived clock
for a swap), empty events/ + knowledge/, and a seq-1 build-sheet identity event.
Make/model/year is captured first; VIN-decode enrichment + seed research fill the
rest (see references/onboarding.md).
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


def slugify(make: str, model: str, year) -> str:
    raw = f"{year}-{make}-{model}".lower()
    return re.sub(r"[^a-z0-9]+", "-", raw).strip("-")


def scaffold_vehicle(data_root, *, make: str, model: str, year, vin: str = "", plate: str = "",
                     trim: str = "", engine: str = "", drivetrain: str = "", fuel: str = "",
                     nicknames=None) -> Path:
    slug = slugify(make, model, year)
    vdir = Path(data_root) / "vehicles" / slug
    if vdir.exists():
        raise FileExistsError(f"{vdir} already exists")
    (vdir / "events").mkdir(parents=True)
    (vdir / "knowledge").mkdir()

    vehicle = {
        "schema_version": 1, "vehicle_id": slug, "slug": slug,
        "display": f"{year} {make} {model}".strip(),
        "year": year, "make": make, "model": model, "trim": trim,
        "engine": engine, "drivetrain": drivetrain, "fuel": fuel,
        "vin": vin, "plate": plate, "nicknames": nicknames or [],
        "interference": None,  # researched at onboarding; fail-closed until known
        "clocks": [{"name": "chassis", "kind": "odometer", "unit": "mi",
                    "label": "Chassis odometer", "primary": True}],
    }
    (vdir / "vehicle.json").write_text(json.dumps(vehicle, indent=2) + "\n")
    (vdir / "events" / f"00001-0000-00-00-build-sheet-vehicle-identity").write_text(
        f"seq: 1\nvehicle_id: {slug}\ntype: build-sheet\nfield: vehicle\n"
        f"value: {year} {make} {model}\n")
    return vdir


def main() -> None:
    ap = argparse.ArgumentParser(description="Scaffold a new vehicle directory.")
    ap.add_argument("--data-root", required=True)
    ap.add_argument("--make", required=True)
    ap.add_argument("--model", required=True)
    ap.add_argument("--year", required=True)
    ap.add_argument("--vin", default="")
    a = ap.parse_args()
    vdir = scaffold_vehicle(a.data_root, make=a.make, model=a.model, year=a.year, vin=a.vin)
    print(f"Scaffolded {vdir}")


if __name__ == "__main__":
    main()
