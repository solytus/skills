"""TDD tests for adapter_base.load_secrets. Run: python3 scripts/tests/test_load_secrets.py -v"""
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import adapter_base as ab


class TestLoadSecrets(unittest.TestCase):
    def _write(self, text):
        d = tempfile.mkdtemp()
        p = Path(d) / "secrets.env"
        p.write_text(text)
        return str(p)

    def test_parses_key_value_pairs(self):
        p = self._write("FOO=abc123\nBAR=xyz789\n")
        secrets = ab.load_secrets(p)
        self.assertEqual(secrets["FOO"], "abc123")
        self.assertEqual(secrets["BAR"], "xyz789")

    def test_ignores_comments_and_blank_lines(self):
        p = self._write("# a comment\n\nFOO=abc\n   # indented comment\n\n")
        self.assertEqual(ab.load_secrets(p), {"FOO": "abc"})

    def test_strips_whitespace_around_key_and_value(self):
        p = self._write("  FOO = abc  \n")
        self.assertEqual(ab.load_secrets(p)["FOO"], "abc")

    def test_strips_surrounding_quotes(self):
        p = self._write('FOO="abc"\nBAR=\'xyz\'\n')
        s = ab.load_secrets(p)
        self.assertEqual(s["FOO"], "abc")
        self.assertEqual(s["BAR"], "xyz")

    def test_value_may_contain_equals(self):
        p = self._write("TOKEN=a=b=c\n")
        self.assertEqual(ab.load_secrets(p)["TOKEN"], "a=b=c")

    def test_blank_value_is_empty_string(self):
        p = self._write("EMPTY=\nFOO=abc\n")
        self.assertEqual(ab.load_secrets(p)["EMPTY"], "")

    def test_missing_file_returns_empty_dict(self):
        self.assertEqual(ab.load_secrets("/no/such/path/secrets.env"), {})

    def test_env_override_when_no_path_given(self):
        p = self._write("FOO=fromenv\n")
        old = os.environ.get("HABITAT_SECRETS")
        os.environ["HABITAT_SECRETS"] = p
        try:
            self.assertEqual(ab.load_secrets()["FOO"], "fromenv")
        finally:
            if old is None:
                del os.environ["HABITAT_SECRETS"]
            else:
                os.environ["HABITAT_SECRETS"] = old

    def _tier2_home(self, text):
        """Make a fake home with ~/.solytus/habitat/secrets.env (Tier-2)."""
        home = tempfile.mkdtemp()
        t2 = Path(home) / ".solytus" / "habitat"
        t2.mkdir(parents=True)
        (t2 / "secrets.env").write_text(text)
        return home

    def test_tier2_default_used_when_present_and_no_env(self):
        # ~/.solytus/habitat/secrets.env is the default Tier-2 location (survives
        # plugin updates) when no explicit path and no $HABITAT_SECRETS are given.
        home = self._tier2_home("FOO=fromtier2\n")
        old = os.environ.pop("HABITAT_SECRETS", None)
        try:
            self.assertEqual(ab.load_secrets(home=home)["FOO"], "fromtier2")
        finally:
            if old is not None:
                os.environ["HABITAT_SECRETS"] = old

    def test_env_overrides_tier2(self):
        envp = self._write("FOO=fromenv\n")
        home = self._tier2_home("FOO=fromtier2\n")
        old = os.environ.get("HABITAT_SECRETS")
        os.environ["HABITAT_SECRETS"] = envp
        try:
            self.assertEqual(ab.load_secrets(home=home)["FOO"], "fromenv")
        finally:
            if old is None:
                os.environ.pop("HABITAT_SECRETS", None)
            else:
                os.environ["HABITAT_SECRETS"] = old

    def test_explicit_path_overrides_env_and_tier2(self):
        explicit = self._write("FOO=explicit\n")
        envp = self._write("FOO=fromenv\n")
        home = self._tier2_home("FOO=fromtier2\n")
        old = os.environ.get("HABITAT_SECRETS")
        os.environ["HABITAT_SECRETS"] = envp
        try:
            self.assertEqual(ab.load_secrets(explicit, home=home)["FOO"], "explicit")
        finally:
            if old is None:
                os.environ.pop("HABITAT_SECRETS", None)
            else:
                os.environ["HABITAT_SECRETS"] = old

    def test_no_tier2_no_env_resolves_to_beside_skill(self):
        # Empty home + no env -> resolution falls back to the beside-skill path.
        # Assert the resolved PATH (not contents) so the test never reads a real
        # secrets.env that may exist beside the skill during local dev.
        home = tempfile.mkdtemp()
        old = os.environ.pop("HABITAT_SECRETS", None)
        try:
            resolved = ab._resolve_secrets_path(home=home)
            beside = str(Path(ab.__file__).resolve().parent.parent / "secrets.env")
            self.assertEqual(resolved, beside)
        finally:
            if old is not None:
                os.environ["HABITAT_SECRETS"] = old


if __name__ == "__main__":
    unittest.main()
