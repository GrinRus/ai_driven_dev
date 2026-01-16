import os
import tempfile
import unittest
from pathlib import Path

from aidd_runtime.feature_ids import resolve_project_root


class FeatureIdsRootTests(unittest.TestCase):
    def setUp(self) -> None:
        self._env_backup = os.environ.copy()
        os.environ.pop("CLAUDE_PLUGIN_ROOT", None)
        os.environ.pop("CLAUDE_PROJECT_DIR", None)

    def tearDown(self) -> None:
        os.environ.clear()
        os.environ.update(self._env_backup)

    def test_prefers_plugin_root(self) -> None:
        with tempfile.TemporaryDirectory(prefix="feature-ids-") as tmp:
            base = Path(tmp)
            plugin = base / "aidd"
            (plugin / "docs").mkdir(parents=True)
            os.environ["CLAUDE_PLUGIN_ROOT"] = str(plugin)

            resolved = resolve_project_root(base)

            self.assertEqual(resolved, plugin.resolve())

    def test_prefers_aidd_subdir_when_present(self) -> None:
        with tempfile.TemporaryDirectory(prefix="feature-ids-") as tmp:
            base = Path(tmp)
            aidd = base / "aidd"
            (aidd / "docs").mkdir(parents=True)

            resolved = resolve_project_root(base)

            self.assertEqual(resolved, aidd.resolve())

    def test_falls_back_to_cwd_docs(self) -> None:
        with tempfile.TemporaryDirectory(prefix="feature-ids-") as tmp:
            base = Path(tmp)
            (base / "docs").mkdir(parents=True)

            resolved = resolve_project_root(base)

            self.assertEqual(resolved, base.resolve())

    def test_uses_project_dir_as_last_resort(self) -> None:
        with tempfile.TemporaryDirectory(prefix="feature-ids-") as tmp:
            base = Path(tmp)
            project = base / "project-root"
            (project / "docs").mkdir(parents=True)
            os.environ["CLAUDE_PROJECT_DIR"] = str(project)

            resolved = resolve_project_root(base)

            self.assertEqual(resolved, project.resolve())


if __name__ == "__main__":
    unittest.main()
