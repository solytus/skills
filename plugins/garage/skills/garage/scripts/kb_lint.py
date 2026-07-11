#!/usr/bin/env python3
"""kb_lint.py — deterministic citation gate for KB files, with provenance teeth.

Reads a knowledge/<topic>.md file, parses the `## Facts` markdown table, and
enforces the provenance contract. A well-formed citation is necessary but not
sufficient: this gate also checks that a fact's PROVENANCE matches its claim.

Facts table columns (8):
    key | value | applies-to | tier | conf | safety | method | source

Beyond the format rules carried forward from the single-vehicle original, it
enforces:
  - method is a real provenance (owner-confirmed / fsm-ocr / deep-research-verified
    / lazy-single / generic-heuristic);
  - a claimed-official FSM/Haynes citation must be backed by an INGESTED document
    (method fsm-ocr or owner-confirmed) — you can't cite a manual you never read;
  - a single-fetch lazy fact is provisional (conf=low);
  - a safety fact must pin its config (applies-to) and, when lazily sourced, be
    corroborated across >=2 sources;
  - a torque value carries an explicit unit;
  - a torque fact can't suppress its own safety flag;
  - (optional) applies-to does not contradict the vehicle's known config.

Usage:  python kb_lint.py <file.md> [<file.md> ...]
Exit:   0 if all clean, 1 if any violations.
"""
import re
import sys

TIERS = {"official", "community", "inference"}
CONF = {"high", "medium", "low"}
SAFETY = {"yes", "no"}
METHODS = {"owner-confirmed", "fsm-ocr", "deep-research-verified", "lazy-single",
           "generic-heuristic", "owner-supplied-list", "seed-web"}
# Methods that count as having ingested a manual (satisfy the confabulation guard).
# owner-supplied-list / seed-web deliberately do NOT — a web/list row can't claim an FSM cite.
INGESTED_METHODS = {"fsm-ocr", "owner-confirmed"}
# Methods authoritative enough to justify tier=official (ingested manual or adversarially verified).
AUTHORITATIVE_METHODS = {"fsm-ocr", "owner-confirmed", "deep-research-verified"}

WEASEL = ["general knowledge", "common knowledge", "standard practice", "standard",
          "typical", "commonly", "manufacturer spec", "manufacturer specification",
          "approximate", "estimate", "n/a", "none", "-", "tbd", "unknown"]

_LOCATOR = re.compile(r"https?://|FSM|Haynes|Chilton|§|p\.\d|NHTSA|TSB|recall|owner|\.com|\.net|\.org", re.I)
_MANUAL_CITE = re.compile(r"\bFSM\b|Haynes|Chilton", re.I)
_TORQUE_UNIT = re.compile(r"ft[\s·.-]?lb|lb[\s·.-]?ft|n[\s·.-]?m|in[\s·.-]?lb", re.I)
# Engine-OUTPUT torque (a power-curve figure @ rpm) is a performance spec, not a fastener spec.
_ENGINE_OUTPUT = re.compile(r"@\s*[\d,]+\s*rpm|\brpm\b", re.I)
# Opposite-token sets per config dimension, for contradiction checks.
_DRIVETRAIN = {"2wd", "4wd", "awd", "fwd", "rwd"}
_TRANS = {"manual", "automatic"}
_FUEL = {"gasoline", "diesel", "hybrid", "electric"}


_DOMAIN = re.compile(r"([a-z0-9-]+\.(?:com|net|org|edu|gov|io|co))", re.I)


def _distinct_sources(source: str) -> int:
    """Count independent sources in a source cell: distinct web domains (so two links from
    the SAME forum collapse to one — the citation-incest the research contract warns of), plus
    one for any manual/authority locator (FSM/Haynes/NHTSA/TSB)."""
    n = len({d.lower() for d in _DOMAIN.findall(source)})
    if re.search(r"\bFSM\b|Haynes|Chilton|NHTSA|TSB", source, re.I):
        n += 1
    return n


def parse_facts(text):
    """Return [(rownum, cells)] for rows under a '## Facts' heading table."""
    in_facts = False
    rows = []
    for i, ln in enumerate(text.splitlines(), 1):
        if ln.strip().lower().startswith("## "):
            in_facts = ln.strip().lower().startswith("## facts")
            continue
        if not in_facts:
            continue
        s = ln.strip()
        if not s.startswith("|"):
            continue
        cells = [c.strip() for c in s.strip("|").split("|")]
        if cells and cells[0].lower() == "key":
            continue
        if set("".join(cells)) <= set("-: "):
            continue
        rows.append((i, cells))
    return rows


def _contradicts(applies, vehicle):
    """Return a reason string if applies-to contradicts the vehicle's config, else None."""
    a = applies.lower()
    for field, tokens in (("drivetrain", _DRIVETRAIN), ("transmission", _TRANS), ("fuel", _FUEL)):
        vval = str(vehicle.get(field, "")).lower()
        own = {t for t in tokens if t in vval}
        if not own:
            continue
        named = {t for t in tokens if re.search(rf"\b{re.escape(t)}\b", a)}
        conflicting = named - own
        if conflicting and not (named & own):
            return f"applies-to names {sorted(conflicting)} but vehicle {field} is {sorted(own)}"
    return None


def lint_file(path, vehicle=None):
    with open(path) as f:
        text = f.read()
    problems = []
    rows = parse_facts(text)
    if not rows:
        problems.append("no Facts rows found (file empty or table malformed)")
    for rownum, cells in rows:
        if len(cells) != 8:
            problems.append(f"L{rownum}: row has {len(cells)} columns, expected 8 -> {cells}")
            continue
        key, value, applies, tier, conf, safety, method, source = cells
        tag = f"L{rownum} [{key}]"
        if tier not in TIERS:
            problems.append(f"{tag}: tier '{tier}' not in {sorted(TIERS)}")
        if conf not in CONF:
            problems.append(f"{tag}: conf '{conf}' not in {sorted(CONF)}")
        if safety not in SAFETY:
            problems.append(f"{tag}: safety '{safety}' not in {sorted(SAFETY)}")
        if method not in METHODS:
            problems.append(f"{tag}: method '{method}' not in {sorted(METHODS)}")
        if not value:
            problems.append(f"{tag}: empty value")

        src_l = source.lower().strip()
        if tier in {"official", "community"}:
            if not src_l or src_l in WEASEL:
                problems.append(f"{tag}: tier={tier} but source is empty/weasel ('{source}') -> cite or move to Gaps")
            elif not _LOCATOR.search(source):
                problems.append(f"{tag}: tier={tier} source has no locator (URL/FSM §/Haynes p.) -> '{source}'")
        if tier == "inference" and not src_l:
            problems.append(f"{tag}: inference requires a stated derivation in source")

        # Confabulation guard: an FSM/Haynes citation must be backed by an ingested doc.
        if tier == "official" and _MANUAL_CITE.search(source) and method not in INGESTED_METHODS:
            problems.append(f"{tag}: official manual citation ('{source}') with method={method} -> "
                            "confabulation risk; an FSM/Haynes cite requires an ingested document "
                            "(method fsm-ocr/owner-confirmed)")

        # Tier honesty: an `official` fact must have an authoritative provenance — a web/forum/
        # vendor/encyclopedia source (seed-web / owner-supplied-list / lazy-single) can't be official.
        if tier == "official" and method not in AUTHORITATIVE_METHODS:
            problems.append(f"{tag}: tier=official requires an authoritative method "
                            f"({', '.join(sorted(AUTHORITATIVE_METHODS))}), got {method!r} -> "
                            "retier to community (a web/list source is not official)")

        # Lazy single-fetch facts are provisional.
        if method == "lazy-single" and conf != "low":
            problems.append(f"{tag}: method=lazy-single must be provisional (conf=low), got conf={conf}")

        if safety == "yes":
            if not applies:
                problems.append(f"{tag}: safety fact must pin its config (applies-to is empty)")
            if method == "lazy-single" and _distinct_sources(source) < 2:
                problems.append(f"{tag}: safety fact from a single lazy source needs >=2 independent "
                                f"corroborating sources (distinct domains) -> '{source}'")

        if "torque" in key.lower() and not _ENGINE_OUTPUT.search(value):
            if safety != "yes":
                problems.append(f"{tag}: a torque spec is safety-critical; safety must be 'yes'")
            if value and not _TORQUE_UNIT.search(value):
                problems.append(f"{tag}: torque value '{value}' has no unit (ft-lb / Nm / in-lb)")

        if vehicle and applies:
            reason = _contradicts(applies, vehicle)
            if reason:
                problems.append(f"{tag}: {reason}")
    return rows, problems


def lint_schedule(items) -> list[str]:
    """Gate a researched schedule's sources (the schedule.json citation gate).

    A claimed-OEM interval (estimate=False) needs a real, non-weasel, locator-bearing
    source; a generic-heuristic interval (estimate=True) is an honest inference and
    needs only a stated derivation. Run when a schedule is researched/edited — NOT at
    every build (a migrated schedule carries provisional sources until re-researched).
    """
    problems = []
    for it in items:
        src = (getattr(it, "source", "") or "")
        src_l = src.lower().strip()
        if not it.estimate:
            if not src_l or src_l in WEASEL:
                problems.append(f"{it.key}: estimate=False needs a real source, got '{src}'")
            elif not _LOCATOR.search(src):
                problems.append(f"{it.key}: estimate=False source has no locator -> '{src}'")
        elif not src_l:
            problems.append(f"{it.key}: estimate=True needs a stated derivation in source")
    return problems


def main(argv):
    any_fail = False
    for path in argv:
        rows, problems = lint_file(path)
        print(f"\n=== {path} ===")
        print(f"facts rows: {len(rows)}")
        if problems:
            any_fail = True
            print(f"VIOLATIONS ({len(problems)}):")
            for p in problems:
                print("  - " + p)
        else:
            print("CLEAN")
    return 1 if any_fail else 0


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("usage: python kb_lint.py <file.md> [...]")
        sys.exit(2)
    sys.exit(main(sys.argv[1:]))
