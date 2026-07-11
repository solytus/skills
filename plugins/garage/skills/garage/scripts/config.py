"""Garage instance config (Tier-2): resolve the data root + tenant id and
validate the config schema version. Stdlib-only.

The instance config is a small FLAT yaml file (default
`~/.solytus/habitat/config.yaml`) holding *system pointers* — where your data
lives, who you are. It is NOT the rich preference config (which lives in the
data root as `profile/config.yaml` and is owned by Claude). This reader handles
flat `key: value` lines only, mirroring `adapter_base.load_secrets`; the
preference config keeps its nesting and is read by Claude, never by a script.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

CONFIG_VERSION = 1  # current supported instance-config schema version

DEFAULT_CONFIG_PATH = Path.home() / ".solytus" / "garage" / "config.yaml"
DEFAULT_DATA_ROOT = Path.home() / ".solytus" / "garage" / "data"


class ConfigError(Exception):
    """Instance config is unreadable, malformed, or a newer version than supported."""


def _read_flat_yaml(path):
    """Minimal flat-yaml reader: `key: value` lines + `#` comments. Missing file -> {}.
    Not a general YAML parser (no nesting/lists) — by design (stdlib-only, system
    pointers only)."""
    result = {}
    p = Path(path)
    if not p.exists():
        return result
    for raw in p.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or ":" not in line:
            continue
        key, _, val = line.partition(":")
        key = key.strip()
        val = val.strip()
        if " #" in val and val[:1] not in ("'", '"'):  # strip a real inline comment
            val = val.split(" #", 1)[0].rstrip()
        if len(val) >= 2 and val[0] == val[-1] and val[0] in ("'", '"'):  # unquote
            val = val[1:-1]
        if key:
            result[key] = val
    return result


def load_instance_config(config_path=None):
    """Read + validate the instance config. Returns a dict (possibly empty).
    Raises ConfigError if `version` is non-integer or newer than this skill supports."""
    path = Path(config_path) if config_path else DEFAULT_CONFIG_PATH
    cfg = _read_flat_yaml(path)
    if "version" in cfg:
        try:
            v = int(cfg["version"])
        except (TypeError, ValueError):
            raise ConfigError(f"config 'version' must be an integer, got {cfg['version']!r}")
        if v > CONFIG_VERSION:
            raise ConfigError(
                f"config version {v} is newer than this skill supports (v{CONFIG_VERSION}); "
                "update the skill (`git pull`)."
            )
        # v < CONFIG_VERSION would run the forward migration chain; v == 1 today, so no-op.
        cfg["version"] = str(v)
    return cfg


def resolve_data_root(config_path=None, env=None):
    """data root: GARAGE_DATA_ROOT env -> config `data_root` -> default."""
    env = os.environ if env is None else env
    if env.get("GARAGE_DATA_ROOT"):
        return Path(env["GARAGE_DATA_ROOT"]).expanduser()
    cfg = load_instance_config(config_path)
    if cfg.get("data_root"):
        return Path(cfg["data_root"]).expanduser()
    return DEFAULT_DATA_ROOT


def resolve_tenant_id(config_path=None, env=None):
    """tenant id: GARAGE_TENANT_ID env -> config `tenant_id` -> 'local'.

    Reserved for the future multi-tenant / MCP path. Per-user isolation today is
    the data root itself; the on-disk cache is intentionally cross-tenant (it
    holds public place data keyed by place_key, shared to save API calls), so
    tenant_id does NOT gate the cache key. A real MCP server would enforce tenant
    scoping at the tool boundary (see mcp_mock.py)."""
    env = os.environ if env is None else env
    if env.get("GARAGE_TENANT_ID"):
        return env["GARAGE_TENANT_ID"]
    cfg = load_instance_config(config_path)
    return cfg.get("tenant_id") or "local"


def _main(argv=None):
    import argparse
    import json

    ap = argparse.ArgumentParser(
        description="Resolve Garage instance config (data root, tenant, version)."
    )
    ap.add_argument("--config-path", default=None, help="override the instance config path")
    a = ap.parse_args(argv)
    path = Path(a.config_path) if a.config_path else DEFAULT_CONFIG_PATH
    try:
        cfg = load_instance_config(a.config_path)
        out = {
            "config_path": str(path),
            "config_exists": path.exists(),
            "version": int(cfg.get("version", CONFIG_VERSION)),
            "data_root": str(resolve_data_root(a.config_path)),
            "tenant_id": resolve_tenant_id(a.config_path),
        }
    except ConfigError as e:
        print(str(e), file=sys.stderr)
        return 2
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
