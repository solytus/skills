"""vin_decode.py — decode a VIN via NHTSA vPIC. Stdlib only, no API key.

vPIC is decent for make/model/year, thin on engine/trim for older vehicles, and
decodes the FACTORY engine — it cannot know about a swap. So the decoded config is
a starting point marked `confirmed: false`; the onboarding flow must confirm it with
the owner ("is this the original engine, or swapped?") before it drives any research.

API: https://vpic.nhtsa.dot.gov/api/vehicles/DecodeVinValues/<VIN>?format=json
"""
from __future__ import annotations

import json
import urllib.parse
import urllib.request

_BASE = "https://vpic.nhtsa.dot.gov/api/vehicles/DecodeVinValues"

_MAP = {
    "make": "Make", "model": "Model", "year": "ModelYear", "trim": "Trim",
    "engine_model": "EngineModel", "displacement_l": "DisplacementL",
    "body_class": "BodyClass", "drivetrain": "DriveType", "fuel": "FuelTypePrimary",
}


def parse_decode(payload) -> dict:
    """Extract the fields we use from a vPIC DecodeVinValues response (pure)."""
    if not isinstance(payload, dict):
        return {}
    results = payload.get("Results") or []
    if not results:
        return {}
    r = results[0]
    out = {k: (r.get(src) or "") for k, src in _MAP.items()}
    out["confirmed"] = False  # decode is never authoritative until owner-confirmed
    return out


def decode_vin(vin: str, timeout: int = 10) -> tuple[dict, str | None]:
    """Return (decoded, error). On failure, decoded is {} and error is set."""
    url = f"{_BASE}/{urllib.parse.quote(vin)}?format=json"
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
        return parse_decode(payload), None
    except Exception as e:  # noqa: BLE001
        return {}, f"VIN decode failed: {e}"
