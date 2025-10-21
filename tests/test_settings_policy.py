import json
from pathlib import Path
import unittest


class SettingsPolicyTest(unittest.TestCase):
    SETTINGS_PATH = Path(__file__).resolve().parents[1] / ".claude" / "settings.json"

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

    def test_hooks_guard_sensitive_operations(self):
        data = self.load_settings()
        hooks = data.get("hooks", {})
        pre_hooks = hooks.get("PreToolUse", [])
        post_hooks = hooks.get("PostToolUse", [])

        self.assertTrue(pre_hooks, "PreToolUse hook list should not be empty")
        self.assertTrue(post_hooks, "PostToolUse hook list should not be empty")

        pre_commands = {h.get("hooks", [{}])[0].get("command") for h in pre_hooks}
        post_commands = {h.get("hooks", [{}])[0].get("command") for h in post_hooks}

        self.assertIn("\"$CLAUDE_PROJECT_DIR\"/.claude/hooks/gate-workflow.sh", pre_commands)
        self.assertIn("\"$CLAUDE_PROJECT_DIR\"/.claude/hooks/format-and-test.sh", post_commands)


if __name__ == "__main__":
    unittest.main()
