import subprocess
import tempfile
import unittest
import json
from pathlib import Path

from tests.helpers import (
    REPO_ROOT,
    bootstrap_workspace,
    cli_env,
    write_active_feature,
    write_active_stage,
    write_file,
    write_plan_iterations,
    write_tasklist_ready,
)


TASKS_NEW_SCRIPT = REPO_ROOT / "skills" / "tasks-new" / "runtime" / "tasks_new.py"
TASKS_NEW_SKILL = REPO_ROOT / "skills" / "tasks-new" / "SKILL.md"


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
            self.assertIn("category=upstream_blocker", result.stderr)
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

    def test_tasks_new_docs_only_allows_missing_project_test_contract(self) -> None:
        with tempfile.TemporaryDirectory(prefix="tasks-new-contract-missing-docs-only-") as tmpdir:
            workspace = Path(tmpdir) / "workspace"
            workspace.mkdir(parents=True, exist_ok=True)
            bootstrap_workspace(workspace)
            project_root = workspace / "aidd"
            ticket = "TASKS-CONTRACT-DOCS-1"
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

            result = self._run_tasks_new(workspace, "--ticket", ticket, "--docs-only")
            self.assertEqual(result.returncode, 0, msg=result.stderr)
            self.assertIn("docs_only_mode=1", result.stderr)
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

    def test_tasks_new_repairable_structure_emits_bounded_retry_guidance(self) -> None:
        with tempfile.TemporaryDirectory(prefix="tasks-new-repairable-") as tmpdir:
            workspace = Path(tmpdir) / "workspace"
            workspace.mkdir(parents=True, exist_ok=True)
            bootstrap_workspace(workspace)
            project_root = workspace / "aidd"
            ticket = "TASKS-REPAIR-1"
            write_active_feature(project_root, ticket)
            write_active_stage(project_root, "tasklist")
            write_plan_iterations(project_root, ticket)
            tasklist_path = write_tasklist_ready(project_root, ticket)
            text = tasklist_path.read_text(encoding="utf-8").replace(
                "- [ ] I3: Follow-up (iteration_id: I3)\n"
                "  - Goal: follow-up\n"
                "  - Outputs: follow-up tasks\n"
                "  - DoD: tasklist ready\n"
                "  - Expected paths:\n"
                f"    - docs/tasklist/{ticket}.md\n"
                "  - Size budget:\n"
                "    - max_files: 3\n"
                "    - max_loc: 120\n"
                f"  - Boundaries: docs/tasklist/{ticket}.md\n"
                "  - Steps:\n"
                "    - update tasklist\n"
                "    - verify gate\n"
                "    - record progress\n"
                "  - Tests:\n"
                "    - profile: none\n"
                "    - tasks: []\n"
                "    - filters: []\n"
                "  - Acceptance mapping: AC-3\n"
                "  - Risks & mitigations: low → none\n"
                "  - Dependencies: none\n\n",
                "",
                1,
            )
            tasklist_path.write_text(text, encoding="utf-8")

            result = self._run_tasks_new(workspace, "--ticket", ticket)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("category=repairable_structure", result.stderr)
            self.assertIn("bounded retry applies only once", result.stderr)

    def test_tasks_new_docs_only_continues_on_tasklist_check_error(self) -> None:
        with tempfile.TemporaryDirectory(prefix="tasks-new-docs-only-error-") as tmpdir:
            workspace = Path(tmpdir) / "workspace"
            workspace.mkdir(parents=True, exist_ok=True)
            bootstrap_workspace(workspace)
            project_root = workspace / "aidd"
            ticket = "TASKS-DOCS-ERR-1"
            write_active_feature(project_root, ticket)
            write_active_stage(project_root, "tasklist")
            write_file(project_root, f"docs/tasklist/{ticket}.md", "# broken tasklist\n")

            result = self._run_tasks_new(workspace, "--ticket", ticket, "--docs-only")
            self.assertEqual(result.returncode, 0, msg=result.stderr)
            self.assertIn("tasklist-check: error", result.stderr)
            self.assertIn("docs-only rewrite mode continues", result.stderr)
    def test_tasks_new_does_not_require_or_create_spec_yaml(self) -> None:
        with tempfile.TemporaryDirectory(prefix="tasks-new-no-spec-") as tmpdir:
            workspace = Path(tmpdir) / "workspace"
            workspace.mkdir(parents=True, exist_ok=True)
            bootstrap_workspace(workspace)
            project_root = workspace / "aidd"
            ticket = "TASKS-NO-SPEC-1"
            write_active_feature(project_root, ticket)
            write_active_stage(project_root, "tasklist")
            write_plan_iterations(project_root, ticket)
            write_tasklist_ready(project_root, ticket)

            result = self._run_tasks_new(workspace, "--ticket", ticket)

            self.assertEqual(result.returncode, 0, msg=result.stderr)
            self.assertNotIn("spec", result.stderr.lower())
            self.assertFalse((project_root / "docs" / "spec" / f"{ticket}.spec.yaml").exists())

    def test_tasks_new_truth_warnings_do_not_trigger_retry_guidance(self) -> None:
        with tempfile.TemporaryDirectory(prefix="tasks-new-truth-warn-") as tmpdir:
            workspace = Path(tmpdir) / "workspace"
            workspace.mkdir(parents=True, exist_ok=True)
            bootstrap_workspace(workspace)
            project_root = workspace / "aidd"
            ticket = "TASKS-TRUTH-1"
            write_active_feature(project_root, ticket)
            write_active_stage(project_root, "tasklist")
            write_plan_iterations(project_root, ticket)
            tasklist_path = write_tasklist_ready(project_root, ticket)
            text = tasklist_path.read_text(encoding="utf-8").replace(
                f"Plan: aidd/docs/plan/{ticket}.md\n",
                f"Plan: aidd/docs/plan/{ticket}.md\n"
                "ExpectedReports:\n"
                f"  qa: aidd/reports/qa/{ticket}.json\n",
                1,
            )
            tasklist_path.write_text(text, encoding="utf-8")

            result = self._run_tasks_new(workspace, "--ticket", ticket)

            self.assertEqual(result.returncode, 0, msg=result.stderr)
            self.assertIn("tasklist-check: warn", result.stderr)
            self.assertIn("category=advisory_truth", result.stderr)
            self.assertNotIn("bounded retry applies only once", result.stderr)
            self.assertNotIn("remediation:", result.stderr)

    def test_tasks_new_failure_guidance_does_not_suggest_runtime_source_self_diagnosis(self) -> None:
        with tempfile.TemporaryDirectory(prefix="tasks-new-no-self-diagnosis-") as tmpdir:
            workspace = Path(tmpdir) / "workspace"
            workspace.mkdir(parents=True, exist_ok=True)
            bootstrap_workspace(workspace)
            project_root = workspace / "aidd"
            ticket = "TASKS-NO-SELF-DIAG-1"
            write_active_feature(project_root, ticket)
            write_active_stage(project_root, "tasklist")
            write_file(project_root, f"docs/tasklist/{ticket}.md", "# broken tasklist\n")

            result = self._run_tasks_new(workspace, "--ticket", ticket)

            self.assertNotEqual(result.returncode, 0)
            stderr = result.stderr.lower()
            self.assertNotIn("skills/tasks-new/runtime", stderr)
            self.assertNotIn("tasklist_validate.py", stderr)
            self.assertNotIn("read runtime source", stderr)
            self.assertNotIn("create missing upstream artifacts manually", stderr)

    def test_tasks_new_skill_declares_bounded_retry_and_forbidden_repair_paths(self) -> None:
        text = TASKS_NEW_SKILL.read_text(encoding="utf-8")
        self.assertIn("allow at most one bounded retry", text)
        self.assertIn("Do not retry for `upstream_blocker`, env/policy errors, or truth/advisory warnings", text)
        self.assertIn("creating missing upstream artifacts", text)
        self.assertIn("reading runtime source files for self-diagnosis", text)
        self.assertIn("looping `tasks_new.py -> tasklist_check.py -> manual edits`", text)

    def test_tasks_new_migrates_legacy_reports_header_to_expected_reports(self) -> None:
        with tempfile.TemporaryDirectory(prefix="tasks-new-expected-reports-") as tmpdir:
            workspace = Path(tmpdir) / "workspace"
            workspace.mkdir(parents=True, exist_ok=True)
            bootstrap_workspace(workspace)
            project_root = workspace / "aidd"
            ticket = "TASKS-EXPECTED-1"
            write_active_feature(project_root, ticket)
            write_active_stage(project_root, "tasklist")
            write_plan_iterations(project_root, ticket)
            tasklist_path = write_tasklist_ready(project_root, ticket)
            text = tasklist_path.read_text(encoding="utf-8")
            text = text.replace(
                f"Plan: aidd/docs/plan/{ticket}.md\n",
                f"Plan: aidd/docs/plan/{ticket}.md\n"
                "Reports:\n"
                f"  qa: aidd/reports/qa/{ticket}.json\n",
                1,
            )
            tasklist_path.write_text(text, encoding="utf-8")

            result = self._run_tasks_new(workspace, "--ticket", ticket)
            self.assertEqual(result.returncode, 0, msg=result.stderr)

            updated = tasklist_path.read_text(encoding="utf-8")
            self.assertIn("ExpectedReports:", updated)
            self.assertNotIn("\nReports:\n", updated)


if __name__ == "__main__":
    unittest.main()
