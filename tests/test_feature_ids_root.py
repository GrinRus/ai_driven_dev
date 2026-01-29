import os
import sys
import tempfile
import unittest
from pathlib import Path

from tests.helpers import REPO_ROOT

SRC_ROOT = REPO_ROOT
if str(SRC_ROOT) not in sys.path:  # pragma: no cover - test bootstrap
    sys.path.insert(0, str(SRC_ROOT))

from tools.feature_ids import resolve_aidd_root


class FeatureIdsRootTests(unittest.TestCase):
    def setUp(self) -> None:
        self._env_backup = os.environ.copy()
        os.environ.pop("CLAUDE_PLUGIN_ROOT", None)

    def tearDown(self) -> None:
        os.environ.clear()
        os.environ.update(self._env_backup)

    def test_ignores_plugin_root(self) -> None:
        with tempfile.TemporaryDirectory(prefix="feature-ids-") as tmp:
            base = Path(tmp)
            plugin = base / "plugin"
            workspace = base / "workspace"
            (plugin / "docs").mkdir(parents=True)
            (workspace / "aidd" / "docs").mkdir(parents=True)
            (workspace / ".git").mkdir()
            os.environ["CLAUDE_PLUGIN_ROOT"] = str(plugin)

            resolved = resolve_aidd_root(workspace)

            self.assertEqual(resolved, (workspace / "aidd").resolve())

    def test_uses_cwd_when_already_aidd(self) -> None:
        with tempfile.TemporaryDirectory(prefix="feature-ids-") as tmp:
            base = Path(tmp) / "aidd"
            (base / "docs").mkdir(parents=True)

            resolved = resolve_aidd_root(base)

            self.assertEqual(resolved, base.resolve())

    def test_prefers_aidd_subdir_when_present(self) -> None:
        with tempfile.TemporaryDirectory(prefix="feature-ids-") as tmp:
            base = Path(tmp)
            aidd = base / "aidd"
            (aidd / "docs").mkdir(parents=True)

            resolved = resolve_aidd_root(base)

            self.assertEqual(resolved, aidd.resolve())

    def test_defaults_to_aidd_subdir(self) -> None:
        with tempfile.TemporaryDirectory(prefix="feature-ids-") as tmp:
            base = Path(tmp)
            (base / "docs").mkdir(parents=True)
            (base / ".git").mkdir()

            resolved = resolve_aidd_root(base)

            self.assertEqual(resolved, (base / "aidd").resolve())

if __name__ == "__main__":
    unittest.main()
