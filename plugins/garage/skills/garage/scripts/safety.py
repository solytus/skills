"""safety.py — the proportionate 4-tier safety model. Pure, no I/O.

A general automotive assistant advises strangers and computes 'due' on safety items,
and its cited/printable wrapper amplifies the authority of any wrong number. So the
model gates the few things that kill while keeping the common case clean for a
competent DIYer.

Tiers (ascending):
  TIER_INFO      — non-safety lookup; no warning.
  TIER_VERIFY    — safety-critical NUMBER (torque, fluid spec); footer: cite + verify.
  TIER_PROCEDURE — safety-critical PROCEDURE where the method is the hazard; lead with it.
  TIER_PRO       — professional / hard-gate (SRS, HV/EV, internal brake hydraulics,
                   steering under load, frame welding); no DIY step list.
  REFUSE         — defeating a safety system; refuse.
"""
from __future__ import annotations

import re

TIER_INFO, TIER_VERIFY, TIER_PROCEDURE, TIER_PRO, REFUSE = 0, 1, 2, 3, 4

# Defeating a safety system = a defeat verb (or resistor-spoof / clear-the-light trick)
# co-occurring with a safety-system noun.
_DEFEAT_VERBS = ("disable", "defeat", "bypass", "delete", "spoof")
_DEFEAT_SYSTEMS = ("abs", "airbag", "srs", "seatbelt", "seat belt", "traction control", "stability")
_DEFEAT_PHRASES = ("o2 simulator", "cat delete", "resistor trick")
# Tier 3 — professional / hard-gate, no DIY step list.
_PRO = ("airbag", "srs", "clockspring", "pretensioner", "pyrotechnic", "high voltage", "high-voltage",
        "hv battery", "traction battery", "inverter", "orange cable", "service disconnect",
        "abs module", "master cylinder rebuild", "proportioning valve",
        "frame weld", "weld the frame", "rack and pinion replace", "steering box replace")
# Genuinely high-voltage terms only — NOT a hybrid's ordinary 12 V battery / charging system.
_HV_WORDS = ("high voltage", "high-voltage", "traction battery", "hv battery", "orange cable",
             "service disconnect", "inverter", "rebalance", "cell balance")
# Tier 2 — procedure caution (lead with the hazard, then steps). Includes DIY-doable
# steering/suspension-under-load and brake-hydraulic work (must not silently drop to Tier 0).
_PROCEDURE = ("jack", "jack stand", "spring compress", "coil spring", "strut", "bleed the brake",
              "brake bleed", "fuel pressure", "depressurize", "under the truck", "under the car",
              "lift the truck", "lift the car", "tie rod", "ball joint", "control arm",
              "wheel bearing", "steering knuckle", "drag link", "pitman arm", "idler arm",
              "caliper", "brake line", "brake hose", "wheel cylinder")
_SPEC = ("torque", "ft-lb", "lb-ft", "dot 3", "dot 4", "dot 5", "dot spec", "fluid spec",
         "brake fluid", "lug nut", "tighten", "wheel nut")
_NM = re.compile(r"\bnm\b", re.I)  # word-anchored so it doesn't match alig(nm)ent / enviro(nm)ent


def _is_ev(fuel: str | None) -> bool:
    """True for any electrified fuel tag (hybrid/electric/phev/bev/mhev/ev/plug-in)."""
    return bool(fuel) and any(f in fuel.lower() for f in
                              ("hybrid", "electric", "phev", "bev", "mhev", "ev", "plug-in"))


def classify_intent(text: str, fuel: str | None = None) -> int:
    """Classify a user's question/intent into a safety tier (keyword-driven)."""
    t = (text or "").lower()
    # Hard refuse: defeating a safety system.
    if (any(p in t for p in _DEFEAT_PHRASES)
            or ("resistor" in t and any(s in t for s in _DEFEAT_SYSTEMS))
            or ("clear" in t and "airbag" in t and "light" in t)
            or (any(v in t for v in _DEFEAT_VERBS) and any(s in t for s in _DEFEAT_SYSTEMS))):
        return REFUSE
    if any(k in t for k in _PRO) or ("bleed" in t and "abs" in t):
        return TIER_PRO
    if _is_ev(fuel) and any(k in t for k in _HV_WORDS):
        return TIER_PRO
    if any(k in t for k in _PROCEDURE):
        return TIER_PROCEDURE
    if any(k in t for k in _SPEC) or _NM.search(t):
        return TIER_VERIFY
    return TIER_INFO


_FOOTERS = {
    TIER_INFO: "",
    TIER_VERIFY: "Cite the source and tier; verify against the service manual before final torque.",
    TIER_PROCEDURE: "Lead with the specific physical hazard and the safe-practice precondition "
                    "(stands rated for the load, level ground, never under a vehicle on a jack alone), "
                    "then the steps.",
    TIER_PRO: "This is professional / trained-tech work — explain what it is and why it's dangerous, "
              "and what to ask the shop, rather than a DIY step list.",
    REFUSE: "Refuse: this defeats a safety system. Explain why.",
}


def footer_for(tier: int) -> str:
    return _FOOTERS.get(tier, "")


_STATUS_TAG = {"OVERDUE": "[OVERDUE]", "DUE SOON": "[DUE SOON]", "OK": "[ok]", "UNKNOWN": "[unknown]"}


def due_display(row) -> tuple[str, str]:
    """(status tag, caveat). A safety item on an estimated interval never reads a bare 'OK'."""
    tag = _STATUS_TAG.get(row.status, f"[{row.status}]")
    if row.safety_critical and row.status == "OK" and getattr(row, "estimate", False):
        return tag, "estimated interval — not the OEM schedule; verify before relying on it"
    return tag, ""


def interference_warning(vehicle: dict) -> str:
    """Warn about an interference engine, fail-closed (unknown is treated as interference).

    Returns '' only when interference is explicitly False (non-interference).
    """
    interference = (vehicle or {}).get("interference", None)
    if interference is False:
        return ""
    qualifier = "" if interference is True else " (interference status unconfirmed — assume the worst)"
    return ("Interference engine" + qualifier + ": a snapped or skipped timing belt can DESTROY the "
            "engine (valves meet pistons) and cause sudden power loss. Do not defer the belt.")
