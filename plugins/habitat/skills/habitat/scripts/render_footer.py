"""Sources-footer composer. Deterministic; see references/footer.md for the spec.

render(cached_records, reasoned_dimensions, lookup_names, now) -> the compact `Sources`
block. Cached adapters/lookups that were fetched get one line each (relative time +
marker only when data_status != fresh); reasoned dimensions and real-time lookups get
one summary line each. Empty sections are omitted.
"""
from __future__ import annotations

from datetime import datetime

_DEFAULT_MARKER = {
    "stale": "stale: TTL expired, fresh fetch failed",
    "degraded": "degraded",
    "unavailable": "unavailable",
}


def relative_time(fetched_at, now):
    secs = (now - datetime.fromisoformat(fetched_at)).total_seconds()
    if secs < 3600:
        return "just now"
    if secs < 86400:
        return f"{int(secs // 3600)} h ago"
    return f"{int(secs // 86400)} d ago"


def _marker(record):
    note = record.get("note")
    if note:
        return f" [{note}]"
    status = record.get("data_status", "fresh")
    if status == "fresh":
        return ""
    return f" [{_DEFAULT_MARKER.get(status, status)}]"


def render(cached_records, reasoned_dimensions, lookup_names, now):
    lines = ["Sources:"]
    for r in cached_records:
        rel = relative_time(r["fetched_at"], now)
        lines.append(f"- {r['label']}: {r['source']} • fetched {rel}{_marker(r)}")
    if reasoned_dimensions:
        lines.append(f"- {', '.join(reasoned_dimensions)}: reasoned via WebFetch (real-time)")
    if lookup_names:
        lines.append(f"- {', '.join(lookup_names)}: utility lookups (real-time)")
    return "\n".join(lines)


def _main(argv=None):
    import argparse
    import json

    ap = argparse.ArgumentParser(description="Render the Sources footer block.")
    ap.add_argument("--records", help="path to a JSON array of cached-source records")
    ap.add_argument("--reasoned", default="", help="comma-separated reasoned dimensions")
    ap.add_argument("--lookups", default="", help="comma-separated lookup names")
    ap.add_argument("--now", default=None, help="ISO datetime; default = now")
    a = ap.parse_args(argv)
    if a.records:
        with open(a.records) as f:
            cached = json.load(f)
    else:
        cached = []
    split = lambda s: [x.strip() for x in s.split(",") if x.strip()]  # noqa: E731
    now = datetime.fromisoformat(a.now) if a.now else datetime.now()
    print(render(cached, split(a.reasoned), split(a.lookups), now))


if __name__ == "__main__":
    _main()
