import os
import subprocess
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

    def test_resolve_roots_does_not_migrate_root_docs_when_project_missing(self) -> None:
        with tempfile.TemporaryDirectory(prefix="resources-") as tmp:
            workspace = Path(tmp) / "ws"
            workspace.mkdir()
            (workspace / ".git").mkdir()
            (workspace / "docs" / "prd").mkdir(parents=True)
            (workspace / "config").mkdir()
            (workspace / "docs" / "prd" / "demo.prd.md").write_text("# PRD\n", encoding="utf-8")

            with self.assertRaises(FileNotFoundError) as ctx:
                runtime.resolve_roots(workspace, create=False)

            self.assertIn("/feature-dev-aidd:aidd-init", str(ctx.exception))
            self.assertTrue((workspace / "docs" / "prd" / "demo.prd.md").exists())
            self.assertFalse((workspace / "aidd" / "docs").exists())

    def test_resolve_roots_uses_canonical_aidd_and_ignores_root_docs(self) -> None:
        with tempfile.TemporaryDirectory(prefix="resources-") as tmp:
            workspace = Path(tmp) / "ws"
            workspace.mkdir()
            (workspace / ".git").mkdir()
            (workspace / "docs" / "prd").mkdir(parents=True)
            (workspace / "config").mkdir()
            (workspace / "aidd" / "docs" / "prd").mkdir(parents=True)
            (workspace / "aidd" / "config").mkdir(parents=True)
            (workspace / "docs" / "prd" / "demo.prd.md").write_text("# legacy\n", encoding="utf-8")
            (workspace / "aidd" / "docs" / "prd" / "demo.prd.md").write_text("# canonical\n", encoding="utf-8")

            workspace_root, project_root = runtime.resolve_roots(workspace, create=False)
            self.assertEqual(workspace_root, workspace.resolve())
            self.assertEqual(project_root, (workspace / "aidd").resolve())
            self.assertEqual((workspace / "docs" / "prd" / "demo.prd.md").read_text(encoding="utf-8"), "# legacy\n")
            self.assertEqual(
                (workspace / "aidd" / "docs" / "prd" / "demo.prd.md").read_text(encoding="utf-8"),
                "# canonical\n",
            )

    def test_status_runtime_does_not_migrate_root_docs_when_aidd_missing(self) -> None:
        with tempfile.TemporaryDirectory(prefix="resources-") as tmp:
            workspace = Path(tmp) / "ws"
            workspace.mkdir()
            (workspace / ".git").mkdir()
            legacy_prd = workspace / "docs" / "prd" / "demo.prd.md"
            legacy_prd.parent.mkdir(parents=True, exist_ok=True)
            legacy_prd.write_text("# Legacy PRD\n", encoding="utf-8")

            env = os.environ.copy()
            env["CLAUDE_PLUGIN_ROOT"] = str(REPO_ROOT)
            env["PYTHONPATH"] = str(REPO_ROOT)
            env["PYTHONDONTWRITEBYTECODE"] = "1"
            result = subprocess.run(
                [sys.executable, str(REPO_ROOT / "skills" / "status" / "runtime" / "status.py"), "--ticket", "TST-001"],
                cwd=workspace,
                env=env,
                text=True,
                capture_output=True,
            )

            self.assertEqual(result.returncode, 0)
            self.assertIn("/feature-dev-aidd:aidd-init", result.stdout)
            self.assertIn("read-only", result.stdout)
            self.assertTrue(legacy_prd.exists())
            self.assertFalse((workspace / "aidd" / "docs").exists())

    def test_status_runtime_is_read_only_when_index_missing(self) -> None:
        with tempfile.TemporaryDirectory(prefix="resources-") as tmp:
            workspace = Path(tmp) / "ws"
            project_root = workspace / "aidd"
            project_root.mkdir(parents=True)
            (workspace / ".git").mkdir()
            (project_root / "docs" / "prd").mkdir(parents=True, exist_ok=True)
            (project_root / "docs" / "prd" / "TST-001.prd.md").write_text("# PRD\n", encoding="utf-8")

            env = os.environ.copy()
            env["CLAUDE_PLUGIN_ROOT"] = str(REPO_ROOT)
            env["PYTHONPATH"] = str(REPO_ROOT)
            env["PYTHONDONTWRITEBYTECODE"] = "1"
            result = subprocess.run(
                [sys.executable, str(REPO_ROOT / "skills" / "status" / "runtime" / "status.py"), "--ticket", "TST-001"],
                cwd=workspace,
                env=env,
                text=True,
                capture_output=True,
            )

            self.assertEqual(result.returncode, 0)
            self.assertIn("Index snapshot missing", result.stdout)
            self.assertIn("--refresh", result.stdout)
            self.assertFalse((project_root / "docs" / "index" / "TST-001.json").exists())

    def test_status_runtime_refresh_rebuilds_index_explicitly(self) -> None:
        with tempfile.TemporaryDirectory(prefix="resources-") as tmp:
            workspace = Path(tmp) / "ws"
            project_root = workspace / "aidd"
            project_root.mkdir(parents=True)
            (workspace / ".git").mkdir()
            (project_root / "docs" / "prd").mkdir(parents=True, exist_ok=True)
            (project_root / "docs" / "prd" / "TST-001.prd.md").write_text(
                "# PRD\n\nStatus: READY\n",
                encoding="utf-8",
            )

            env = os.environ.copy()
            env["CLAUDE_PLUGIN_ROOT"] = str(REPO_ROOT)
            env["PYTHONPATH"] = str(REPO_ROOT)
            env["PYTHONDONTWRITEBYTECODE"] = "1"
            result = subprocess.run(
                [
                    sys.executable,
                    str(REPO_ROOT / "skills" / "status" / "runtime" / "status.py"),
                    "--ticket",
                    "TST-001",
                    "--refresh",
                ],
                cwd=workspace,
                env=env,
                text=True,
                capture_output=True,
            )

            self.assertEqual(result.returncode, 0, msg=(result.stdout or "") + (result.stderr or ""))
            self.assertTrue((project_root / "docs" / "index" / "TST-001.json").exists())


if __name__ == "__main__":
    unittest.main()
