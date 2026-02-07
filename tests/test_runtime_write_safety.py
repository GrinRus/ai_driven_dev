import os
import tempfile
import unittest
from pathlib import Path

from tools import runtime


class RuntimeWriteSafetyTests(unittest.TestCase):
    def setUp(self) -> None:
        self._env_backup = os.environ.copy()

    def tearDown(self) -> None:
        os.environ.clear()
        os.environ.update(self._env_backup)

    def test_rejects_plugin_repo_as_workspace(self) -> None:
        with tempfile.TemporaryDirectory(prefix="runtime-guard-") as tmpdir:
            plugin_root = Path(tmpdir) / "plugin"
            (plugin_root / ".claude-plugin").mkdir(parents=True, exist_ok=True)
            (plugin_root / ".git").mkdir(parents=True, exist_ok=True)
            (plugin_root / "aidd" / "docs").mkdir(parents=True, exist_ok=True)

            os.environ["CLAUDE_PLUGIN_ROOT"] = str(plugin_root)

            with self.assertRaises(RuntimeError):
                runtime.resolve_roots(plugin_root)

    def test_allows_plugin_workspace_with_override(self) -> None:
        with tempfile.TemporaryDirectory(prefix="runtime-guard-") as tmpdir:
            plugin_root = Path(tmpdir) / "plugin"
            (plugin_root / ".claude-plugin").mkdir(parents=True, exist_ok=True)
            (plugin_root / ".git").mkdir(parents=True, exist_ok=True)
            (plugin_root / "aidd" / "docs").mkdir(parents=True, exist_ok=True)

            os.environ["CLAUDE_PLUGIN_ROOT"] = str(plugin_root)
            os.environ["AIDD_ALLOW_PLUGIN_WORKSPACE"] = "1"

            workspace_root, project_root = runtime.resolve_roots(plugin_root)
            self.assertEqual(workspace_root, plugin_root.resolve())
            self.assertEqual(project_root, (plugin_root / "aidd").resolve())

    def test_prefers_explicit_workspace_target_over_plugin_cwd(self) -> None:
        with tempfile.TemporaryDirectory(prefix="runtime-guard-") as tmpdir:
            plugin_root = Path(tmpdir) / "plugin"
            workspace = Path(tmpdir) / "workspace"
            (plugin_root / ".claude-plugin").mkdir(parents=True, exist_ok=True)
            (plugin_root / ".git").mkdir(parents=True, exist_ok=True)
            (workspace / ".git").mkdir(parents=True, exist_ok=True)
            (workspace / "aidd" / "docs").mkdir(parents=True, exist_ok=True)

            os.environ["CLAUDE_PLUGIN_ROOT"] = str(plugin_root)

            workspace_root, project_root = runtime.resolve_roots(workspace)
            self.assertEqual(workspace_root, workspace.resolve())
            self.assertEqual(project_root, (workspace / "aidd").resolve())


if __name__ == "__main__":
    unittest.main()
