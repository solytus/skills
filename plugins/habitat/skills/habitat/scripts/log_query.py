"""Log query: read a fixed set of place-frontmatter scalars and filter the log.

A constrained reader for the log index (status / verdict / fit / last_touched / level /
place_key / normalized_name) — NOT a general YAML parser. Token-free filtering at scale.
"""
from __future__ import annotations

import argparse
import json
import re
from datetime import date, datetime
from pathlib import Path

SCALAR_KEYS = {"place_key", "level", "normalized_name", "status", "verdict", "fit",
               "last_touched", "country_code", "grain_class"}
INT_KEYS = {"fit"}
_FM = re.compile(r"^---\n(.*?)\n---", re.DOTALL)
_LINE = re.compile(r"^([A-Za-z_]\w*):\s*(.*)$")  # column-0 key only; skips indented/nested lines


def _strip_quotes(v):
    v = v.strip()
    if len(v) >= 2 and v[0] in "\"'" and v[-1] == v[0]:
        return v[1:-1]
    return v


def read_place_frontmatter(path):
    """Return the fixed scalar fields from a place file's frontmatter (others ignored)."""
    m = _FM.match(Path(path).read_text())
    fm = {}
    if not m:
        return fm
    for line in m.group(1).splitlines():
        mm = _LINE.match(line)
        if not mm:
            continue
        key, val = mm.group(1), _strip_quotes(mm.group(2))
        if key not in SCALAR_KEYS or val == "":
            continue
        if key in INT_KEYS:
            try:
                val = int(val)
            except ValueError:
                continue
        fm[key] = val
    return fm


def _as_date(dt):
    return dt.date() if isinstance(dt, datetime) else dt


def query_places(data_root, *, status=None, verdict=None, level=None,
                 fit_min=None, fit_max=None, stale_days=None, now=None,
                 country=None, grain_class=None):
    """Filtered list of place frontmatter dicts (each with `path`). Filters are AND-ed.

    `grain_class` defaults to 'domestic' for any place lacking the field, so the 19
    pre-international places (which carry no grain_class) read as domestic and a
    `grain_class='domestic'` filter still includes them.
    """
    results = []
    for p in sorted(Path(data_root).glob("places/**/*.md")):
        fm = read_place_frontmatter(p)
        if not fm:
            continue
        if status and fm.get("status") != status:
            continue
        if verdict and fm.get("verdict") != verdict:
            continue
        if level and fm.get("level") != level:
            continue
        if country and fm.get("country_code") != country:
            continue
        if grain_class and (fm.get("grain_class") or "domestic") != grain_class:
            continue
        fit = fm.get("fit")
        if fit_min is not None and (fit is None or fit < fit_min):
            continue
        if fit_max is not None and (fit is None or fit > fit_max):
            continue
        if stale_days is not None:
            lt = fm.get("last_touched")
            if lt is None:
                continue
            age = (_as_date(now or datetime.now()) - date.fromisoformat(lt)).days
            if age <= stale_days:  # stale = not touched in more than stale_days
                continue
        fm["path"] = str(p)
        results.append(fm)
    return results


def find_place(data_root, level, normalized_name):
    """Existing place file(s) matching (level, normalized_name), each with `path`.
    Supports dedupe: re-evaluating a place reuses its file instead of forking a new one."""
    out = []
    for p in sorted(Path(data_root).glob(f"places/{level}/*.md")):
        fm = read_place_frontmatter(p)
        if fm.get("normalized_name") == normalized_name:
            fm["path"] = str(p)
            out.append(fm)
    return out


def _main(argv=None):
    ap = argparse.ArgumentParser(description="Query the Habitat place log.")
    ap.add_argument("--data-root", required=True)
    ap.add_argument("--status")
    ap.add_argument("--verdict")
    ap.add_argument("--level")
    ap.add_argument("--country", help="filter by country_code (ISO alpha-2, e.g. PT)")
    ap.add_argument("--grain-class", choices=["domestic", "international"],
                    help="filter by grain class (places without the field read as domestic)")
    ap.add_argument("--fit-min", type=int)
    ap.add_argument("--fit-max", type=int)
    ap.add_argument("--stale", action="store_true", help="only places stale per --stale-days")
    ap.add_argument("--stale-days", type=int, default=90)
    ap.add_argument("--find", metavar="NORMALIZED_NAME",
                    help="dedupe: list existing place file(s) at --level with this normalized_name")
    a = ap.parse_args(argv)
    if a.find:
        if not a.level:
            ap.error("--find requires --level")
        print(json.dumps(find_place(a.data_root, a.level, a.find), indent=2))
        return
    res = query_places(
        a.data_root, status=a.status, verdict=a.verdict, level=a.level,
        fit_min=a.fit_min, fit_max=a.fit_max,
        stale_days=a.stale_days if a.stale else None,
        country=a.country, grain_class=a.grain_class,
    )
    print(json.dumps(res, indent=2))


if __name__ == "__main__":
    _main()
