import subprocess
import tempfile
import unittest
import json
from pathlib import Path

from tests.helpers import REPO_ROOT, bootstrap_workspace, cli_env, write_active_feature, write_active_stage, write_file


TASKS_NEW_SCRIPT = REPO_ROOT / "skills" / "tasks-new" / "runtime" / "tasks_new.py"


class TasksNewRuntimeTests(unittest.TestCase):
    def _run_tasks_new(
        self,
        workspace: Path,
        *args: str,
        extra_env: dict[str, str] | None = None,
    ) -> subprocess.CompletedProcess[str]:
        env = cli_env(extra_env or {})
        return subprocess.run(
            ["python3", str(TASKS_NEW_SCRIPT), *args],
            cwd=workspace,
            text=True,
            capture_output=True,
            env=env,
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

    def test_tasks_new_no_strict_still_fails_without_explicit_override(self) -> None:
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
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("tasklist-check: error", result.stderr)
            self.assertIn("remediation:", result.stderr)

    def test_tasks_new_no_strict_allows_error_with_explicit_override(self) -> None:
        with tempfile.TemporaryDirectory(prefix="tasks-new-no-strict-override-") as tmpdir:
            workspace = Path(tmpdir) / "workspace"
            workspace.mkdir(parents=True, exist_ok=True)
            bootstrap_workspace(workspace)
            project_root = workspace / "aidd"
            ticket = "TASKS-ERR-3"
            write_active_feature(project_root, ticket)
            write_active_stage(project_root, "tasklist")
            write_file(project_root, f"docs/tasklist/{ticket}.md", "# broken tasklist\n")

            result = self._run_tasks_new(
                workspace,
                "--ticket",
                ticket,
                "--no-strict",
                extra_env={"AIDD_ALLOW_TASKLIST_ERROR_SUCCESS": "1"},
            )
            self.assertEqual(result.returncode, 0)
            self.assertIn("tasklist-check: error", result.stderr)
            self.assertIn("AIDD_ALLOW_TASKLIST_ERROR_SUCCESS=1", result.stderr)

    def test_tasks_new_blocks_on_missing_project_test_contract(self) -> None:
        with tempfile.TemporaryDirectory(prefix="tasks-new-contract-missing-") as tmpdir:
            workspace = Path(tmpdir) / "workspace"
            workspace.mkdir(parents=True, exist_ok=True)
            bootstrap_workspace(workspace)
            project_root = workspace / "aidd"
            ticket = "TASKS-CONTRACT-1"
            write_active_feature(project_root, ticket)
            write_active_stage(project_root, "tasklist")
            gates_path = project_root / "config" / "gates.json"
            payload = json.loads(gates_path.read_text(encoding="utf-8"))
            payload.setdefault("qa", {}).setdefault("tests", {}).update(
                {
                    "profile_default": "targeted",
                    "commands": [],
                }
            )
            gates_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

            result = self._run_tasks_new(workspace, "--ticket", ticket)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("reason_code=project_contract_missing", result.stderr)

    def test_tasks_new_materializes_test_execution_from_contract(self) -> None:
        with tempfile.TemporaryDirectory(prefix="tasks-new-contract-materialize-") as tmpdir:
            workspace = Path(tmpdir) / "workspace"
            workspace.mkdir(parents=True, exist_ok=True)
            bootstrap_workspace(workspace)
            project_root = workspace / "aidd"
            ticket = "TASKS-CONTRACT-2"
            write_active_feature(project_root, ticket)
            write_active_stage(project_root, "tasklist")
            gates_path = project_root / "config" / "gates.json"
            payload = json.loads(gates_path.read_text(encoding="utf-8"))
            payload.setdefault("qa", {}).setdefault("tests", {}).update(
                {
                    "profile_default": "targeted",
                    "filters_default": ["Smoke"],
                    "when_default": "manual",
                    "reason_default": "contract materialization",
                    "commands": [
                        {
                            "id": "gradle_backend",
                            "command": ["./gradlew", "test"],
                            "cwd": "backend-mcp",
                            "profiles": ["targeted", "full"],
                        }
                    ],
                }
            )
            gates_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

            result = self._run_tasks_new(
                workspace,
                "--ticket",
                ticket,
                "--no-strict",
                extra_env={"AIDD_ALLOW_TASKLIST_ERROR_SUCCESS": "1"},
            )
            self.assertEqual(result.returncode, 0, msg=result.stderr)
            tasklist_path = project_root / "docs" / "tasklist" / f"{ticket}.md"
            text = tasklist_path.read_text(encoding="utf-8")
            self.assertIn("## AIDD:TEST_EXECUTION", text)
            self.assertIn("- profile: targeted", text)
            self.assertIn("./backend-mcp/gradlew test", text)

    def test_tasks_new_reports_cwd_wrong_with_deterministic_reason_code(self) -> None:
        with tempfile.TemporaryDirectory(prefix="tasks-new-cwd-wrong-") as tmpdir:
            plugin_root = Path(tmpdir) / "plugin-root"
            (plugin_root / ".claude-plugin").mkdir(parents=True, exist_ok=True)
            (plugin_root / "skills").mkdir(parents=True, exist_ok=True)

            result = self._run_tasks_new(
                plugin_root,
                "--ticket",
                "TASKS-CWD-1",
                extra_env={
                    "CLAUDE_PLUGIN_ROOT": str(plugin_root),
                    "AIDD_PLUGIN_DIR": str(plugin_root),
                },
            )
            self.assertEqual(result.returncode, 2)
            self.assertIn("reason_code=cwd_wrong", result.stderr)
            self.assertIn("ENV_MISCONFIG(cwd_wrong)", result.stderr)


if __name__ == "__main__":
    unittest.main()
