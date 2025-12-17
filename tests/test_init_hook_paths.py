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

            def collect_commands(entries):
                commands = []
                if not isinstance(entries, list):
                    return commands
                for entry in entries:
                    hooks = entry.get("hooks", [])
                    if not isinstance(hooks, list):
                        continue
                    for hook in hooks:
                        cmd = hook.get("command")
                        if isinstance(cmd, str):
                            commands.append(cmd)
                return commands

            hooks_section = data.get("hooks", {})
            commands = []
            commands += collect_commands(hooks_section.get("PreToolUse"))
            commands += collect_commands(hooks_section.get("PostToolUse"))
            presets = data.get("presets", {}).get("list", {})
            if isinstance(presets, dict):
                for preset in presets.values():
                    preset_hooks = preset.get("hooks", {})
                    commands += collect_commands(preset_hooks.get("PreToolUse"))
                    commands += collect_commands(preset_hooks.get("PostToolUse"))

            self.assertTrue(commands, "hook commands must not be empty")

            project_dir = project_root.resolve()
            project_prefix = f"\"{project_dir}\"/.claude/hooks"
            for cmd in commands:
                with self.subTest(command=cmd):
                    self.assertNotIn("$CLAUDE_PROJECT_DIR", cmd)
                    self.assertTrue(
                        cmd.startswith(project_prefix),
                        f"command should start with {project_prefix}",
                    )


if __name__ == "__main__":
    unittest.main()
