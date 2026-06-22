"""Tests for the mock MCP readiness layer (tenant scoping + idempotency)."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from mcp_mock import MockMCP


class TestMockMCP(unittest.TestCase):
    def setUp(self):
        self.mcp = MockMCP({
            "tok-alice": {"tenant_id": "alice", "data_root": "/data/alice"},
            "tok-bob": {"tenant_id": "bob", "data_root": "/data/bob"},
        })

    def test_unknown_principal_rejected(self):
        with self.assertRaises(PermissionError):
            self.mcp.get_data_root("tok-nobody")

    def test_tenants_isolated(self):
        self.assertEqual(self.mcp.get_data_root("tok-alice")["data_root"], "/data/alice")
        self.assertEqual(self.mcp.get_data_root("tok-bob")["data_root"], "/data/bob")

    def test_wraps_real_script_unchanged(self):
        out = self.mcp.build_place_key("tok-alice", "city", "Tacoma WA", "47.2529,-122.4443")
        self.assertEqual(out["place_key"], "city::tacoma-wa::47.2529,-122.4443")

    def test_write_idempotent_within_tenant(self):
        first = self.mcp.log_event("tok-alice", "evt-1", {"x": 1})
        second = self.mcp.log_event("tok-alice", "evt-1", {"x": 1})
        self.assertEqual(first["status"], "written")
        self.assertEqual(second["status"], "duplicate")

    def test_same_key_different_tenant_not_deduped(self):
        self.mcp.log_event("tok-alice", "evt-1", {})
        out = self.mcp.log_event("tok-bob", "evt-1", {})
        self.assertEqual(out["status"], "written")


if __name__ == "__main__":
    unittest.main()
