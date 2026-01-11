import os
import tempfile
import unittest
from pathlib import Path

from claude_workflow_cli.feature_ids import resolve_project_root


class FeatureIdsRootTests(unittest.TestCase):
    def setUp(self) -> None:
        self._env_backup = os.environ.copy()
        os.environ.pop("AIDD_ROOT", None)
        os.environ.pop("CLAUDE_PLUGIN_ROOT", None)
        os.environ.pop("CLAUDE_PROJECT_DIR", None)

    def tearDown(self) -> None:
        os.environ.clear()
        os.environ.update(self._env_backup)

    def test_prefers_aidd_root_env(self) -> None:
        with tempfile.TemporaryDirectory(prefix="feature-ids-") as tmp:
            base = Path(tmp)
            root = base / "custom-root"
            (root / "docs").mkdir(parents=True)
            os.environ["AIDD_ROOT"] = str(root)

            resolved = resolve_project_root(base)

            self.assertEqual(resolved, root.resolve())

    def test_prefers_project_dir_aidd(self) -> None:
        with tempfile.TemporaryDirectory(prefix="feature-ids-") as tmp:
            base = Path(tmp)
            workspace = base / "workspace"
            aidd = workspace / "aidd"
            (aidd / "docs").mkdir(parents=True)
            os.environ["CLAUDE_PROJECT_DIR"] = str(workspace)

            resolved = resolve_project_root(base)

            self.assertEqual(resolved, aidd.resolve())

    def test_prefers_plugin_root_when_project_dir_missing(self) -> None:
        with tempfile.TemporaryDirectory(prefix="feature-ids-") as tmp:
            base = Path(tmp)
            plugin = base / "aidd"
            (plugin / "docs").mkdir(parents=True)
            os.environ["CLAUDE_PLUGIN_ROOT"] = str(plugin)

            resolved = resolve_project_root(base)

            self.assertEqual(resolved, plugin.resolve())

    def test_aidd_root_env_blocks_fallback(self) -> None:
        with tempfile.TemporaryDirectory(prefix="feature-ids-") as tmp:
            base = Path(tmp)
            plugin = base / "aidd"
            (plugin / "docs").mkdir(parents=True)
            os.environ["AIDD_ROOT"] = str(base / "missing-aidd")
            os.environ["CLAUDE_PLUGIN_ROOT"] = str(plugin)

            with self.assertRaises(FileNotFoundError):
                resolve_project_root(base)

    def test_raises_when_no_aidd_root_found(self) -> None:
        with tempfile.TemporaryDirectory(prefix="feature-ids-") as tmp:
            base = Path(tmp)
            with self.assertRaises(FileNotFoundError):
                resolve_project_root(base)


if __name__ == "__main__":
    unittest.main()
