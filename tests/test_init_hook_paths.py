import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from tests.helpers import PROJECT_SUBDIR

PAYLOAD_ROOT = Path(__file__).resolve().parents[1] / "src" / "claude_workflow_cli" / "data" / "payload" / PROJECT_SUBDIR


class InitHookCommandTest(unittest.TestCase):
    def test_hook_commands_use_absolute_project_path_after_init(self):
        with tempfile.TemporaryDirectory(prefix="claude-workflow-test-") as tmpdir:
            env = os.environ.copy()
            env["CLAUDE_TEMPLATE_DIR"] = str(PAYLOAD_ROOT)
            project_root = Path(tmpdir) / PROJECT_SUBDIR
            project_root.mkdir(parents=True, exist_ok=True)
            subprocess.run(
                ["bash", str(PAYLOAD_ROOT / "init-claude-workflow.sh"), "--commit-mode", "ticket-prefix"],
                cwd=project_root,
                env=env,
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            settings_path = project_root / ".claude" / "settings.json"
            self.assertTrue(settings_path.exists(), ".claude/settings.json must be created")
            data = json.loads(settings_path.read_text(encoding="utf-8"))

            plugins = data.get("enabledPlugins", {})
            self.assertTrue(
                plugins.get("feature-dev-aidd@aidd-local"),
                "feature-dev-aidd plugin must be enabled to supply hooks",
            )

            hooks_section = data.get("hooks", {})
            commands = []
            for key in ("PreToolUse", "PostToolUse"):
                entries = hooks_section.get(key, [])
                if isinstance(entries, list):
                    for entry in entries:
                        hooks = entry.get("hooks", [])
                        if isinstance(hooks, list):
                            commands.extend(
                                hook.get("command") for hook in hooks if isinstance(hook, dict) and "command" in hook
                            )
            self.assertFalse(commands, "hooks should be supplied by the plugin, not settings.json")


if __name__ == "__main__":
    unittest.main()
