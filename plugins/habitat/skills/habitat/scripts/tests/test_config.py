"""TDD tests for config.py instance-config discovery. Run: python3 scripts/tests/test_config.py -v"""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config as cfgmod


class TestConfig(unittest.TestCase):
    def _write(self, text):
        d = tempfile.mkdtemp()
        p = Path(d) / "config.yaml"
        p.write_text(text)
        return str(p)

    # --- flat reader ---
    def test_reads_key_value(self):
        c = cfgmod.load_instance_config(self._write("data_root: /tmp/x\ntenant_id: alice\n"))
        self.assertEqual(c["data_root"], "/tmp/x")
        self.assertEqual(c["tenant_id"], "alice")

    def test_ignores_comments_and_blanks(self):
        c = cfgmod.load_instance_config(self._write("# header\n\ndata_root: /tmp/x\n  # note\n"))
        self.assertEqual(c["data_root"], "/tmp/x")

    def test_strips_inline_comment(self):
        c = cfgmod.load_instance_config(self._write("data_root: /tmp/x   # where data lives\n"))
        self.assertEqual(c["data_root"], "/tmp/x")

    def test_strips_quotes(self):
        c = cfgmod.load_instance_config(self._write('data_root: "/tmp/a b"\n'))
        self.assertEqual(c["data_root"], "/tmp/a b")

    def test_missing_file_returns_empty(self):
        self.assertEqual(cfgmod.load_instance_config("/no/such/config.yaml"), {})

    # --- version validation ---
    def test_version_equal_ok(self):
        self.assertEqual(cfgmod.load_instance_config(self._write("version: 1\n"))["version"], "1")

    def test_version_newer_raises(self):
        with self.assertRaises(cfgmod.ConfigError):
            cfgmod.load_instance_config(self._write("version: 99\n"))

    def test_version_noninteger_raises(self):
        with self.assertRaises(cfgmod.ConfigError):
            cfgmod.load_instance_config(self._write("version: abc\n"))

    # --- data root resolution order ---
    def test_data_root_env_wins(self):
        p = self._write("data_root: /from/config\n")
        self.assertEqual(str(cfgmod.resolve_data_root(p, env={"HABITAT_DATA_ROOT": "/from/env"})), "/from/env")

    def test_data_root_config_second(self):
        p = self._write("data_root: /from/config\n")
        self.assertEqual(str(cfgmod.resolve_data_root(p, env={})), "/from/config")

    def test_data_root_default_last(self):
        p = self._write("tenant_id: x\n")  # no data_root
        self.assertEqual(cfgmod.resolve_data_root(p, env={}), cfgmod.DEFAULT_DATA_ROOT)

    # --- tenant resolution order ---
    def test_tenant_env_wins(self):
        p = self._write("tenant_id: fromconfig\n")
        self.assertEqual(cfgmod.resolve_tenant_id(p, env={"HABITAT_TENANT_ID": "fromenv"}), "fromenv")

    def test_tenant_config_second(self):
        p = self._write("tenant_id: fromconfig\n")
        self.assertEqual(cfgmod.resolve_tenant_id(p, env={}), "fromconfig")

    def test_tenant_default_local(self):
        p = self._write("data_root: /tmp/x\n")
        self.assertEqual(cfgmod.resolve_tenant_id(p, env={}), "local")


if __name__ == "__main__":
    unittest.main()
