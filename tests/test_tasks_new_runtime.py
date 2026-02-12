import subprocess
import tempfile
import unittest
from pathlib import Path

from tests.helpers import REPO_ROOT, bootstrap_workspace, cli_env, write_active_feature, write_active_stage, write_file


TASKS_NEW_SCRIPT = REPO_ROOT / "skills" / "tasks-new" / "runtime" / "tasks_new.py"


class TasksNewRuntimeTests(unittest.TestCase):
    def _run_tasks_new(self, workspace: Path, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["python3", str(TASKS_NEW_SCRIPT), *args],
            cwd=workspace,
            text=True,
            capture_output=True,
            env=cli_env(),
            check=False,
        )

    def test_tasks_new_strict_by_default(self) -> None:
        with tempfile.TemporaryDirectory(prefix="tasks-new-default-strict-") as tmpdir:
            workspace = Path(tmpdir) / "workspace"
            workspace.mkdir(parents=True, exist_ok=True)
            bootstrap_workspace(workspace)
            project_root = workspace / "aidd"
            ticket = "TASKS-ERR-1"
            write_active_feature(project_root, ticket)
            write_active_stage(project_root, "tasklist")
            write_file(project_root, f"docs/tasklist/{ticket}.md", "# broken tasklist\n")

            result = self._run_tasks_new(workspace, "--ticket", ticket)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("tasklist-check: error", result.stderr)
            self.assertIn("plan not found", result.stderr)
            self.assertIn("remediation:", result.stderr)

    def test_tasks_new_no_strict_allows_error_exit_zero(self) -> None:
        with tempfile.TemporaryDirectory(prefix="tasks-new-no-strict-") as tmpdir:
            workspace = Path(tmpdir) / "workspace"
            workspace.mkdir(parents=True, exist_ok=True)
            bootstrap_workspace(workspace)
            project_root = workspace / "aidd"
            ticket = "TASKS-ERR-2"
            write_active_feature(project_root, ticket)
            write_active_stage(project_root, "tasklist")
            write_file(project_root, f"docs/tasklist/{ticket}.md", "# broken tasklist\n")

            result = self._run_tasks_new(workspace, "--ticket", ticket, "--no-strict")
            self.assertEqual(result.returncode, 0)
            self.assertIn("tasklist-check: error", result.stderr)
            self.assertIn("remediation:", result.stderr)


if __name__ == "__main__":
    unittest.main()
