"""recalls.py — NHTSA recall lookup by vehicle. Stdlib only, no API key.

A tool that knows the vehicle and stays silent on open recalls is negligent by
omission, so this is run at onboarding and on a recurring check. The fetch is
network I/O; the parser is pure. An empty or failed fetch is NOT 'no recalls' — it
is 'could not check', and callers must say so rather than imply the vehicle is clear.

API: https://api.nhtsa.gov/recalls/recallsByVehicle?make=&model=&modelYear=
"""
from __future__ import annotations

import json
import urllib.parse
import urllib.request

_BASE = "https://api.nhtsa.gov/recalls/recallsByVehicle"


def parse_recalls(payload) -> list[dict]:
    """Extract a clean recall list from the NHTSA response (pure)."""
    if not isinstance(payload, dict):
        return []
    out = []
    for r in payload.get("results") or []:
        out.append({
            "campaign": r.get("NHTSACampaignNumber", ""),
            "component": r.get("Component", ""),
            "summary": r.get("Summary", ""),
            "consequence": r.get("Consequence", ""),
            "remedy": r.get("Remedy", ""),
        })
    return out


def fetch_recalls(year, make, model, timeout: int = 10) -> tuple[list[dict], str | None]:
    """Return (recalls, error). On any network/parse failure, error is set and the
    list is empty — the caller must report 'could not check', never 'none found'."""
    q = urllib.parse.urlencode({"make": make, "model": model, "modelYear": year})
    try:
        with urllib.request.urlopen(f"{_BASE}?{q}", timeout=timeout) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
        return parse_recalls(payload), None
    except Exception as e:  # noqa: BLE001 — any failure means "could not check"
        return [], f"recall lookup failed: {e}"
