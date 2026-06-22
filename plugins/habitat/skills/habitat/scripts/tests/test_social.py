"""TDD tests for the social adapter (Google News RSS parse + query derivation).
Run: python3 scripts/tests/test_social.py -v"""
import sys
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(SCRIPTS / "adapters"))
import social

RSS = """<?xml version="1.0"?><rss version="2.0"><channel>
<title>Tacoma WA - Google News</title>
<item><title>Tacoma council approves budget</title><link>https://news.google.com/x</link>
<pubDate>Tue, 27 May 2026 09:00:00 GMT</pubDate>
<source url="https://thenewstribune.com">The News Tribune</source></item>
<item><title>New bakery opens downtown</title><link>https://news.google.com/y</link>
<pubDate>Mon, 26 May 2026 18:00:00 GMT</pubDate><source url="https://kuow.org">KUOW</source></item>
</channel></rss>"""


class ParseNewsRssTest(unittest.TestCase):
    def test_extracts_items(self):
        items = social._parse_news_rss(RSS)
        self.assertEqual(len(items), 2)
        self.assertEqual(items[0]["title"], "Tacoma council approves budget")
        self.assertEqual(items[0]["source"], "The News Tribune")
        self.assertIn("27 May 2026", items[0]["published"])

    def test_limit_caps_items(self):
        self.assertEqual(len(social._parse_news_rss(RSS, limit=1)), 1)

    def test_empty_feed_is_empty_list(self):
        empty = '<?xml version="1.0"?><rss version="2.0"><channel></channel></rss>'
        self.assertEqual(social._parse_news_rss(empty), [])


class NewsQueryTest(unittest.TestCase):
    def test_derives_query_from_place_key(self):
        self.assertEqual(
            social._news_query_from_place_key("city::tacoma-wa::47.25,-122.44"), "tacoma wa")

    def test_neighborhood_name(self):
        self.assertEqual(
            social._news_query_from_place_key("neighborhood::capitol-hill-seattle::47.6,-122.3"),
            "capitol hill seattle")


if __name__ == "__main__":
    unittest.main()
