"""TDD tests for adapter_base HTTP helpers (real local server, no mocks).
Run: python3 scripts/tests/test_http.py -v"""
import sys
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import adapter_base as ab


class _Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):  # silence test-server logging
        pass

    def _respond(self):
        if self.path == "/notfound":
            self.send_response(404); self.end_headers(); self.wfile.write(b"nope"); return
        if self.path == "/json":
            self.send_response(200); self.end_headers()
            self.wfile.write(b'{"a": 1, "b": "two"}'); return
        if self.path == "/echo-header":
            self.send_response(200); self.end_headers()
            self.wfile.write(self.headers.get("X-Test", "").encode()); return
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length) if length else b""
        self.send_response(200); self.end_headers()
        self.wfile.write(self.command.encode() + b":" + body)

    do_GET = _respond
    do_POST = _respond


class HttpHelperTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = HTTPServer(("127.0.0.1", 0), _Handler)
        cls.port = cls.server.server_address[1]
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=2)

    def _url(self, path):
        return f"http://127.0.0.1:{self.port}{path}"

    def test_fetch_returns_body_on_200(self):
        self.assertEqual(ab.http_fetch(self._url("/")), "GET:")

    def test_json_parses_response(self):
        self.assertEqual(ab.http_json(self._url("/json")), {"a": 1, "b": "two"})

    def test_custom_headers_are_sent(self):
        body = ab.http_fetch(self._url("/echo-header"), headers={"X-Test": "habitat"})
        self.assertEqual(body, "habitat")

    def test_non_2xx_raises(self):
        import urllib.error
        with self.assertRaises(urllib.error.HTTPError):
            ab.http_fetch(self._url("/notfound"))

    def test_dict_data_posts_json_body(self):
        self.assertEqual(ab.http_fetch(self._url("/echo"), data={"k": "v"}),
                         'POST:{"k": "v"}')


if __name__ == "__main__":
    unittest.main()
