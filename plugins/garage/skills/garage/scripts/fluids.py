"""fluids.py — block dangerous cross-standard fluid substitutions. Pure, no I/O.

The wrong fluid is catastrophic and non-recoverable: Toyota WS in a box that wants
Dexron (or vice-versa), a regular ATF in a CVT, GL-5 attacking yellow-metal
synchros that need GL-4, DOT 5 silicone mixed into a glycol brake system. The skill
must refuse to suggest one standard where another is specified.

`substitution_blocked(have, want)` classifies each fluid into a category's mutually
incompatible standard and blocks when they differ. Intermixable grades within a
standard (DOT 3 / 4 / 5.1 glycol) are allowed.
"""
from __future__ import annotations

import re

# (category, [(pattern, canonical)]) — first match wins, so list specific before general.
_CATEGORIES = [
    ("brake fluid", [
        (r"dot\s*5\.1", "glycol"),
        (r"dot\s*5", "silicone"),
        (r"dot\s*4", "glycol"),
        (r"dot\s*3", "glycol"),
    ]),
    ("transmission fluid", [
        (r"hcf-?2", "cvt"),
        (r"\bns-?[23]\b", "cvt"),
        (r"\bcvt\b", "cvt"),
        (r"\bws\b|world standard", "ws"),
        (r"dexron|dex\s*vi|dex\s*iii", "dexron"),
        (r"mercon", "mercon"),
        (r"atf\s*\+\s*4|atf4", "atf+4"),
        (r"type\s*f", "type-f"),
        (r"\bz1\b", "z1"),
        (r"\bdw-?1\b", "dw-1"),
    ]),
    ("gear oil", [
        (r"gl-?4", "gl-4"),
        (r"gl-?5", "gl-5"),
    ]),
    ("coolant", [
        (r"\boat\b|sllc|dex-?cool", "oat"),
        (r"\bhoat\b|g-?05", "hoat"),
        (r"\biat\b", "iat"),
    ]),
]


def _classify(text: str, patterns) -> str | None:
    t = text.lower()
    for pattern, canonical in patterns:
        if re.search(pattern, t):
            return canonical
    return None


def substitution_blocked(have: str, want: str) -> tuple[bool, str]:
    """Return (blocked, reason). Blocked when `have` and `want` name different,
    non-interchangeable standards in the same fluid category."""
    for category, patterns in _CATEGORIES:
        h = _classify(have, patterns)
        w = _classify(want, patterns)
        if h and w and h != w:
            return True, (f"{have!r} and {want!r} are different {category} standards "
                          f"({h} vs {w}) — NOT interchangeable; using the wrong one can destroy "
                          "the system. Use the exact specified fluid.")
    return False, ""
