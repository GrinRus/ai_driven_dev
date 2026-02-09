import sys
import tempfile
import unittest
from pathlib import Path

from tests.helpers import REPO_ROOT

PROJECT_ROOT = REPO_ROOT
SRC_ROOT = PROJECT_ROOT
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from aidd_runtime import runtime  # noqa: E402
from aidd_runtime.resources import DEFAULT_PROJECT_SUBDIR, resolve_project_root  # noqa: E402


class ResourcesTests(unittest.TestCase):
    def test_resolve_project_root_treats_target_as_workspace(self) -> None:
        with tempfile.TemporaryDirectory(prefix="resources-") as tmp:
            workspace = Path(tmp) / "workspace"
            workspace.mkdir()
            (workspace / ".git").mkdir()

            workspace_root, project_root = resolve_project_root(workspace)

            self.assertEqual(workspace_root, workspace.resolve())
            self.assertEqual(project_root, workspace.resolve() / DEFAULT_PROJECT_SUBDIR)

    def test_resolve_project_root_when_target_is_project_dir(self) -> None:
        with tempfile.TemporaryDirectory(prefix="resources-") as tmp:
            project_dir = Path(tmp) / "workspace" / DEFAULT_PROJECT_SUBDIR
            project_dir.mkdir(parents=True)
            (project_dir.parent / ".git").mkdir()

            workspace_root, project_root = resolve_project_root(project_dir)

            self.assertEqual(workspace_root, project_dir.parent.resolve())
            self.assertEqual(project_root, project_dir.resolve())

    def test_resolve_project_root_from_nested_path(self) -> None:
        with tempfile.TemporaryDirectory(prefix="resources-") as tmp:
            workspace = Path(tmp) / "workspace"
            project_dir = workspace / DEFAULT_PROJECT_SUBDIR
            nested = project_dir / "docs" / "prd"
            nested.mkdir(parents=True)
            (workspace / ".git").mkdir()

            workspace_root, project_root = resolve_project_root(nested)

            self.assertEqual(workspace_root, workspace.resolve())
            self.assertEqual(project_root, project_dir.resolve())

    def test_require_workflow_root_errors_when_missing_payload(self) -> None:
        with tempfile.TemporaryDirectory(prefix="resources-") as tmp:
            workspace = Path(tmp) / "ws"
            workspace.mkdir()
            (workspace / ".git").mkdir()
            project_root = workspace / DEFAULT_PROJECT_SUBDIR
            project_root.mkdir()

            with self.assertRaises(FileNotFoundError) as ctx:
                runtime.require_workflow_root(workspace)

            message = str(ctx.exception)
            self.assertIn(f"{project_root}/docs", message)
            self.assertIn("/feature-dev-aidd:aidd-init", message)

    def test_resolve_roots_creates_project_on_demand(self) -> None:
        with tempfile.TemporaryDirectory(prefix="resources-") as tmp:
            workspace = Path(tmp) / "ws"
            workspace.mkdir()
            (workspace / ".git").mkdir()

            workspace_root, project_root = runtime.resolve_roots(workspace, create=True)

            self.assertEqual(workspace_root, workspace.resolve())
            self.assertEqual(project_root, workspace.resolve() / DEFAULT_PROJECT_SUBDIR)
            self.assertTrue(project_root.is_dir())

    def test_resolve_roots_errors_when_project_missing(self) -> None:
        with tempfile.TemporaryDirectory(prefix="resources-") as tmp:
            workspace = Path(tmp) / "ws"
            workspace.mkdir()
            (workspace / ".git").mkdir()

            with self.assertRaises(FileNotFoundError) as ctx:
                runtime.resolve_roots(workspace, create=False)

            message = str(ctx.exception)
            self.assertIn("workflow not found at", message)
            self.assertIn("/feature-dev-aidd:aidd-init", message)


if __name__ == "__main__":
    unittest.main()
