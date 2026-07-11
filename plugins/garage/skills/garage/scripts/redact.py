"""redact.py — the PII guard, reused at the export boundary. Pure, no I/O.

State files are home-private and never published, so the guard runs where data
actually leaves the data root: exports. `assert_no_pii` is the structural backstop
(a VIN can't slip out even if scrubbing misses a spot); `scrub` does the redaction.
"""
from __future__ import annotations

import re

# A VIN is 17 chars from the VIN alphabet (no I, O, Q). Catches any VIN-shaped token.
_VIN_RE = re.compile(r"\b[A-HJ-NPR-Z0-9]{17}\b")
REDACTION = "«redacted»"


class PiiLeakError(Exception):
    """Raised when text destined to leave the data root still contains PII."""


def assert_no_pii(text: str, forbidden: tuple[str, ...] = ()) -> None:
    """Raise if `text` contains a VIN-shaped token or any forbidden string (plate, etc.)."""
    hits = [f for f in forbidden if f and f in text]
    m = _VIN_RE.search(text)
    if m and m.group(0) not in hits:
        hits.append(m.group(0))
    if hits:
        raise PiiLeakError("Export would expose PII: " + ", ".join(repr(h) for h in hits))


def scrub(text: str, forbidden: tuple[str, ...] = ()) -> str:
    """Replace forbidden strings and any VIN-shaped token with the redaction marker."""
    for f in forbidden:
        if f:
            text = text.replace(f, REDACTION)
    return _VIN_RE.sub(REDACTION, text)
