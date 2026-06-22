"""Social-signals adapter — Google News RSS (keyless, local headlines) now; the Reddit
half activates automatically once REDDIT_CLIENT_ID/SECRET are present (access request
pending). One interface; Claude composes the tone/summary narrative from the raw items.
Keyless resident-sentiment fallbacks (AreaVibes / city-data / Numbeo / Patch) are
reason-with-WebFetch hints in references/adapters.md, not fetched by this script."""
import os
import sys
import xml.etree.ElementTree as ET
from datetime import datetime
from urllib.parse import quote

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import adapter_base as ab  # noqa: E402

SOURCE = "reddit+gnews"
TTL_DAYS = 3  # the news layer is the fastest-moving
PAYLOAD_FIELDS = ["reddit_threads", "reddit_tone", "news_headlines", "news_summary"]

_GNEWS_URL = "https://news.google.com/rss/search?q={q}&hl=en-US&gl=US&ceid=US:en"


def _news_query_from_place_key(place_key):
    """'city::tacoma-wa::geo' -> 'tacoma wa' (the human query for the news feed)."""
    parts = place_key.split("::")
    name = parts[1] if len(parts) > 1 else place_key
    return name.replace("-", " ")


def _parse_news_rss(text, limit=10):
    """Google News RSS XML -> [{title, source, published}] (most-recent-first as served)."""
    try:
        root = ET.fromstring(text)
    except ET.ParseError:
        return []
    items = []
    for it in root.iterfind(".//item"):
        src = it.find("source")
        items.append({
            "title": it.findtext("title"),
            "source": src.text if src is not None else None,
            "published": it.findtext("pubDate"),
        })
        if len(items) >= limit:
            break
    return items


def fetch(place_key, geocode, level, data_root, now=None, force_refresh=False):
    """Google News RSS headlines for the place. Reddit threads when creds are configured."""
    now = now or datetime.now()
    secrets = ab.load_secrets()
    has_reddit = bool(secrets.get("REDDIT_CLIENT_ID") and secrets.get("REDDIT_CLIENT_SECRET"))
    query = _news_query_from_place_key(place_key)

    def primary():
        url = _GNEWS_URL.format(q=quote(query))
        headlines = _parse_news_rss(ab.http_fetch(url, timeout=30))
        return {
            "news_headlines": headlines,
            "news_summary": None,        # Claude composes the tone/summary narrative
            "reddit_threads": None,      # pending REDDIT_* creds; wired as a TDD increment then
            "reddit_tone": None,
            "reddit_status": "configured" if has_reddit else "credentials pending",
        }

    return ab.fetch_with_cache(data_root, SOURCE, place_key, TTL_DAYS, primary,
                               now=now, place_grain=level, force_refresh=force_refresh)


if __name__ == "__main__":
    ab.adapter_cli(fetch)
