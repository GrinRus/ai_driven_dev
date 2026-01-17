import json
import unittest

from tests.helpers import REPO_ROOT


class InitHookCommandTest(unittest.TestCase):
    def test_hook_commands_use_plugin_root_variables(self):
        hooks_path = REPO_ROOT / "hooks" / "hooks.json"
        data = json.loads(hooks_path.read_text(encoding="utf-8"))

        commands = []
        hooks_section = data.get("hooks", {})
        for entries in hooks_section.values():
            if isinstance(entries, list):
                for entry in entries:
                    hooks = entry.get("hooks", [])
                    if isinstance(hooks, list):
                        commands.extend(
                            hook.get("command") for hook in hooks if isinstance(hook, dict) and "command" in hook
                        )

        context_hooks = [cmd for cmd in commands if "context-gc-" in cmd]
        self.assertTrue(context_hooks, "expected context-gc commands in hooks.json")
        self.assertTrue(
            all("${CLAUDE_PLUGIN_ROOT" in cmd for cmd in context_hooks),
            "context-gc commands must reference CLAUDE_PLUGIN_ROOT",
        )


if __name__ == "__main__":
    unittest.main()
