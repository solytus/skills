"""Mock MCP layer over the Habitat script surface — a readiness check, not a server.

Demonstrates the deterministic scripts can be wrapped as MCP-style tools without
changing their signatures: a principal (auth token) resolves to a tenant ->
data_root, every call is tenant-scoped, and writes carry an idempotency key (so a
retried tool call doesn't double-write). No network, no real auth.

This exists so the tool surface is *validated* before any real server is built —
the cheap MCP-readiness check from the Solytus schema/versioning policy. If you
ever stand up a real MCP server, it wraps these same script functions; the shape
here is the contract.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import placekey  # a real Tier-1 script, wrapped unchanged


class MockMCP:
    def __init__(self, principals):
        # principals: {principal_token: {"tenant_id": str, "data_root": str}}
        self.principals = dict(principals)
        self._writes = set()  # (tenant_id, idempotency_key) already applied

    def _ctx(self, principal):
        if principal not in self.principals:
            raise PermissionError(f"unknown principal: {principal!r}")
        return self.principals[principal]

    # --- read tool: wraps placekey.build_place_key unchanged ---
    def build_place_key(self, principal, level, name, geocode):
        self._ctx(principal)  # auth required even for pure reads
        return {"place_key": placekey.build_place_key(level, name, geocode)}

    # --- tenant-scoped resolution: principals never see each other's data_root ---
    def get_data_root(self, principal):
        ctx = self._ctx(principal)
        return {"tenant_id": ctx["tenant_id"], "data_root": ctx["data_root"]}

    # --- write tool: idempotent — a replayed key within a tenant is a no-op ---
    def log_event(self, principal, idempotency_key, event):
        ctx = self._ctx(principal)
        key = (ctx["tenant_id"], idempotency_key)
        if key in self._writes:
            return {"status": "duplicate", "tenant_id": ctx["tenant_id"]}
        self._writes.add(key)
        return {"status": "written", "tenant_id": ctx["tenant_id"], "event": event}
