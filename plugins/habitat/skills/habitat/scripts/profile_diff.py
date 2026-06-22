"""Profile delta — quantify how much a profile changed between two versions, so the
F1 / F3 falsification thresholds (Bet 1 / Bet 3 — "preferences evolve materially") are
measurable instead of eyeballed at CP1 / CP3.

Division of labor: Claude reads the two profile YAMLs (it owns markdown/YAML) and passes
the `preferences` lists in as JSON; this script does only deterministic delta math and
never parses YAML. A preference is identified by `name` (case/space-insensitive); a change
is an added / removed preference, a weight change, or a must_have/must_not flag toggle.
`delta_pct` = (added + removed + changed) / (distinct preferences across both) * 100.
"""
from __future__ import annotations

import argparse
import json


def _key(p):
    return (p.get("name") or "").strip().lower()


def diff_preferences(before, after):
    """Structured delta between two preference lists (see module docstring for the model)."""
    b = {_key(p): p for p in before if _key(p)}
    a = {_key(p): p for p in after if _key(p)}
    added_keys = sorted(set(a) - set(b))
    removed_keys = sorted(set(b) - set(a))
    changed = []
    for k in sorted(set(a) & set(b)):
        fields = {}
        if b[k].get("weight") != a[k].get("weight"):
            fields["weight"] = [b[k].get("weight"), a[k].get("weight")]
        for flag in ("must_have", "must_not"):
            if bool(b[k].get(flag)) != bool(a[k].get(flag)):
                fields[flag] = [bool(b[k].get(flag)), bool(a[k].get(flag))]
        if fields:
            changed.append({"name": a[k].get("name"), "fields": fields})
    union = set(a) | set(b)
    total = len(added_keys) + len(removed_keys) + len(changed)
    return {
        "before_count": len(before),
        "after_count": len(after),
        "added": [a[k].get("name") for k in added_keys],
        "removed": [b[k].get("name") for k in removed_keys],
        "changed": changed,
        "added_n": len(added_keys),
        "removed_n": len(removed_keys),
        "changed_n": len(changed),
        "delta_pct": round(total / len(union) * 100, 1) if union else 0.0,
    }


def _load(v):
    """A JSON array inline, or @path to a JSON file."""
    if v.startswith("@"):
        with open(v[1:]) as f:
            return json.load(f)
    return json.loads(v)


def _main(argv=None):
    ap = argparse.ArgumentParser(
        description="Quantify profile change between two versions (F1/F3). Pass the two "
                    "`preferences` lists as JSON; Claude extracts them from the profile YAML "
                    "(this script never parses YAML).")
    ap.add_argument("--before", required=True, help="JSON array of preferences, or @file.json")
    ap.add_argument("--after", required=True, help="JSON array of preferences, or @file.json")
    ap.add_argument("--threshold", type=float,
                    help="optional F1/F3 threshold %% — adds an exceeds_threshold flag")
    a = ap.parse_args(argv)
    d = diff_preferences(_load(a.before), _load(a.after))
    if a.threshold is not None:
        d["threshold"] = a.threshold
        d["exceeds_threshold"] = d["delta_pct"] > a.threshold
    print(json.dumps(d, indent=2))


if __name__ == "__main__":
    _main()
