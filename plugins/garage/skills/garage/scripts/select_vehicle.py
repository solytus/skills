"""select_vehicle.py — infer which vehicle a command refers to. Pure resolver + I/O lister.

The skill infers the target from context and prompts to pick only when genuinely
ambiguous. Match precedence: exact slug -> nickname -> make/model token -> the only
vehicle -> (ambiguous). The model handles the prompt; this just resolves or defers.
"""
from __future__ import annotations

import json
from pathlib import Path


def list_vehicles(data_root) -> list[dict]:
    """List vehicles under <data_root>/vehicles/ with a last_touched date from events."""
    out = []
    vroot = Path(data_root) / "vehicles"
    if not vroot.is_dir():
        return out
    for vdir in sorted(vroot.iterdir()):
        vj_path = vdir / "vehicle.json"
        if not vj_path.is_file():
            continue
        vj = json.loads(vj_path.read_text())
        events = vdir / "events"
        last = ""
        if events.is_dir():
            names = sorted(p.name for p in events.iterdir() if p.name[:1].isdigit())
            # event filename is <seq>-<yyyy-mm-dd>-...
            dates = [n.split("-", 1)[1][:10] for n in names if "-" in n]
            last = max(dates) if dates else ""
        out.append({"slug": vj.get("slug", vdir.name), "display": vj.get("display", vdir.name),
                    "nicknames": vj.get("nicknames", []), "last_touched": last})
    return out


def resolve_vehicle(query: str, vehicles: list[dict]):
    """Return the matched vehicle dict, the string 'AMBIGUOUS', or None.

    None  -> no vehicles exist.
    dict  -> a confident match (named, or the only vehicle).
    'AMBIGUOUS' -> more than one vehicle and nothing in the query disambiguates.
    """
    if not vehicles:
        return None
    q = (query or "").lower()

    for v in vehicles:
        if v.get("slug", "").lower() in q:
            return v
    for v in vehicles:
        if any(n.lower() in q for n in v.get("nicknames", [])):
            return v
    token_matches = []
    for v in vehicles:
        tokens = [t for t in v.get("display", "").lower().split() if not t.isdigit()]
        if any(t in q for t in tokens):
            token_matches.append(v)
    if len(token_matches) == 1:
        return token_matches[0]
    if len(token_matches) > 1:
        return "AMBIGUOUS"  # e.g. two Hondas + "the Honda" — never silently pick one
    if len(vehicles) == 1:
        return vehicles[0]
    return "AMBIGUOUS"
