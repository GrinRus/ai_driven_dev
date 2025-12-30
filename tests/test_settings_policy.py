import json
from pathlib import Path
import unittest


class SettingsPolicyTest(unittest.TestCase):
    SETTINGS_PATH = (
        Path(__file__).resolve().parents[1]
        / "src"
        / "claude_workflow_cli"
        / "data"
        / "payload"
        / ".claude"
        / "settings.json"
    )

    @classmethod
    def setUpClass(cls):
        if not cls.SETTINGS_PATH.exists():
            raise unittest.SkipTest(f"{cls.SETTINGS_PATH} missing")

    def load_settings(self):
        with self.SETTINGS_PATH.open(encoding="utf-8") as fh:
            return json.load(fh)

    def test_permissions_contain_expected_policies(self):
        data = self.load_settings()
        perms = data.get("permissions")
        self.assertIsInstance(perms, dict, "permissions section must exist")

        allow = perms.get("allow", [])
        ask = perms.get("ask", [])
        deny = perms.get("deny", [])

        self.assertIn("Read", allow, "Read must be allowed")
        self.assertIn("Bash(git add:*)", ask, "git add should require explicit approval")
        self.assertIn("Bash(git commit:*)", ask, "git commit should require explicit approval")
        self.assertIn("Bash(git push:*)", ask, "git push should require explicit approval")
        self.assertIn("Bash(curl:*)", deny, "curl should be denied by default")
        self.assertIn("Write(./infra/prod/**)", deny, "production files must be protected")

    def test_hooks_delegated_to_plugin(self):
        data = self.load_settings()

        enabled = data.get("enabledPlugins", {})
        self.assertTrue(
            enabled.get("feature-dev-aidd@aidd-local"),
            "feature-dev-aidd plugin must be enabled to supply hooks",
        )

        hooks = data.get("hooks", {})
        self.assertFalse(
            hooks,
            "runtime hooks should be provided by the plugin (hooks/hooks.json), not duplicated in settings.json",
        )


if __name__ == "__main__":
    unittest.main()
