import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from aidd_runtime import loop_step as loop_step_module
from tests.helpers import cli_cmd, cli_env, ensure_project_root, write_active_state, write_file, write_json, write_tasklist_ready


FIXTURES = Path(__file__).resolve().parent / "fixtures" / "loop_step"


class LoopStepTests(unittest.TestCase):
    def run_loop_step(self, root: Path, ticket: str, log_path: Path, extra_env: dict | None = None, *args: str):
        runner = FIXTURES / "runner.sh"
        env = cli_env({"AIDD_LOOP_RUNNER_LOG": str(log_path), "AIDD_SKIP_STAGE_WRAPPERS": "1"})
        if extra_env:
            env.update(extra_env)
        return subprocess.run(
            cli_cmd("loop-step", "--ticket", ticket, "--runner", f"bash {runner}", *args),
            text=True,
            capture_output=True,
            cwd=root,
            env=env,
        )

    def test_loop_step_runs_implement_when_stage_missing(self) -> None:
        with tempfile.TemporaryDirectory(prefix="loop-step-") as tmpdir:
            root = ensure_project_root(Path(tmpdir))
            write_active_state(root, work_item="iteration_id=I1")
            stage_result = {
                "schema": "aidd.stage_result.v1",
                "ticket": "DEMO-1",
                "stage": "implement",
                "scope_key": "iteration_id_I1",
                "result": "continue",
                "updated_at": "2024-01-02T00:00:00Z",
            }
            write_file(
                root,
                "reports/loops/DEMO-1/iteration_id_I1/stage.implement.result.json",
                json.dumps(stage_result),
            )
            log_path = root / "runner.log"
            result = self.run_loop_step(root, "DEMO-1", log_path)
            self.assertEqual(result.returncode, 10, msg=result.stderr)
            self.assertTrue(log_path.exists())
            log_text = log_path.read_text(encoding="utf-8")
            self.assertIn("-p /feature-dev-aidd:implement DEMO-1", log_text)
            self.assertIn("--plugin-dir", log_text)
            self.assertIn("--add-dir", log_text)
            self.assertEqual((root / "docs" / ".active_mode").read_text(encoding="utf-8").strip(), "loop")
            cli_logs = list((root / "reports" / "loops" / "DEMO-1").glob("cli.loop-step.*.log"))
            self.assertTrue(cli_logs, "cli.loop-step log should be written")

    def test_loop_step_user_approval_required_blocks_same_stage(self) -> None:
        with tempfile.TemporaryDirectory(prefix="loop-step-") as tmpdir:
            root = ensure_project_root(Path(tmpdir))
            write_active_state(root, ticket="DEMO-APPROVAL", stage="implement", work_item="iteration_id=M4")
            stage_result = {
                "schema": "aidd.stage_result.v1",
                "ticket": "DEMO-APPROVAL",
                "stage": "implement",
                "scope_key": "iteration_id_M4",
                "result": "continue",
                "reason_code": "user_approval_required",
                "reason": "manual approval is required",
                "updated_at": "2024-01-02T00:00:00Z",
            }
            write_file(
                root,
                "reports/loops/DEMO-APPROVAL/iteration_id_M4/stage.implement.result.json",
                json.dumps(stage_result),
            )
            log_path = root / "runner.log"
            result = self.run_loop_step(root, "DEMO-APPROVAL", log_path, None, "--format", "json")
            self.assertEqual(result.returncode, 20, msg=result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload.get("status"), "blocked")
            self.assertEqual(payload.get("stage"), "implement")
            self.assertEqual(payload.get("reason_code"), "user_approval_required")
            if log_path.exists():
                self.assertEqual(log_path.read_text(encoding="utf-8").strip(), "")

    def test_loop_step_blocks_when_wrappers_skipped_in_strict_mode(self) -> None:
        with tempfile.TemporaryDirectory(prefix="loop-step-") as tmpdir:
            root = ensure_project_root(Path(tmpdir))
            write_active_state(root, ticket="DEMO-SKIP", work_item="iteration_id=I1")
            log_path = root / "runner.log"
            result = self.run_loop_step(
                root,
                "DEMO-SKIP",
                log_path,
                {"AIDD_HOOKS_MODE": "strict", "AIDD_SKIP_STAGE_WRAPPERS": "1"},
                "--format",
                "json",
            )
            self.assertEqual(result.returncode, 20, msg=result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload.get("status"), "blocked")
            self.assertEqual(payload.get("stage"), "implement")
            self.assertEqual(payload.get("reason_code"), "wrappers_skipped_unsafe")
            self.assertIn("AIDD_SKIP_STAGE_WRAPPERS=1", str(payload.get("reason") or ""))
            if log_path.exists():
                self.assertEqual(log_path.read_text(encoding="utf-8").strip(), "")

    def test_loop_step_blocks_on_output_contract_warn_in_strict_mode(self) -> None:
        with tempfile.TemporaryDirectory(prefix="loop-step-wrap-strict-") as tmpdir:
            root = ensure_project_root(Path(tmpdir))
            ticket = "DEMO-WRAP-STRICT"
            scope_key = "iteration_id_I1"
            work_item_key = "iteration_id=I1"
            write_active_state(root, ticket=ticket, work_item=work_item_key)
            write_tasklist_ready(root, ticket)
            write_file(root, f"docs/prd/{ticket}.prd.md", "Status: READY\n")
            stage_result = {
                "schema": "aidd.stage_result.v1",
                "ticket": ticket,
                "stage": "implement",
                "scope_key": scope_key,
                "work_item_key": work_item_key,
                "result": "continue",
                "updated_at": "2024-01-02T00:00:00Z",
            }
            write_file(
                root,
                f"reports/loops/{ticket}/{scope_key}/stage.implement.result.json",
                json.dumps(stage_result),
            )
            log_path = root / "runner.log"
            result = self.run_loop_step(
                root,
                ticket,
                log_path,
                {"AIDD_SKIP_STAGE_WRAPPERS": "0", "AIDD_HOOKS_MODE": "strict"},
                "--format",
                "json",
            )
            self.assertEqual(result.returncode, 20, msg=result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload.get("status"), "blocked")
            self.assertEqual(payload.get("reason_code"), "output_contract_warn")
            self.assertEqual(payload.get("output_contract_status"), "warn")
            self.assertTrue(payload.get("output_contract_path"))

    def test_loop_step_runner_with_wrappers_produces_required_artifacts(self) -> None:
        with tempfile.TemporaryDirectory(prefix="loop-step-wrap-") as tmpdir:
            root = ensure_project_root(Path(tmpdir))
            ticket = "DEMO-WRAP"
            scope_key = "iteration_id_I1"
            work_item_key = "iteration_id=I1"
            write_active_state(root, ticket=ticket, work_item=work_item_key)
            write_tasklist_ready(root, ticket)
            write_file(root, f"docs/prd/{ticket}.prd.md", "Status: READY\n")
            stage_result = {
                "schema": "aidd.stage_result.v1",
                "ticket": ticket,
                "stage": "implement",
                "scope_key": scope_key,
                "work_item_key": work_item_key,
                "result": "continue",
                "updated_at": "2024-01-02T00:00:00Z",
            }
            write_file(
                root,
                f"reports/loops/{ticket}/{scope_key}/stage.implement.result.json",
                json.dumps(stage_result),
            )

            log_path = root / "runner.log"
            result = self.run_loop_step(
                root,
                ticket,
                log_path,
                {"AIDD_SKIP_STAGE_WRAPPERS": "0"},
                "--format",
                "json",
            )
            self.assertEqual(result.returncode, 10, msg=result.stderr)
            payload = json.loads(result.stdout)
            actions_log_rel = str(payload.get("actions_log_path") or "")
            self.assertTrue(actions_log_rel)
            actions_log_abs = (root.parent / actions_log_rel).resolve()
            self.assertTrue(actions_log_abs.exists())

            actions_dir = root / "reports" / "actions" / ticket / scope_key
            self.assertTrue((actions_dir / "implement.actions.template.json").exists())
            self.assertTrue((actions_dir / "implement.actions.json").exists())
            self.assertTrue((root / "reports" / "context" / ticket / f"{scope_key}.readmap.json").exists())
            self.assertTrue((root / "reports" / "context" / ticket / f"{scope_key}.readmap.md").exists())
            self.assertTrue((root / "reports" / "context" / ticket / f"{scope_key}.writemap.json").exists())
            self.assertTrue((root / "reports" / "context" / ticket / f"{scope_key}.writemap.md").exists())
            self.assertTrue((root / "reports" / "loops" / ticket / scope_key / "stage.preflight.result.json").exists())
            wrapper_logs = list((root / "reports" / "logs" / "implement" / ticket / scope_key).glob("wrapper.*.log"))
            self.assertGreaterEqual(len(wrapper_logs), 3)

    def test_loop_step_runs_review_when_stage_implement(self) -> None:
        with tempfile.TemporaryDirectory(prefix="loop-step-") as tmpdir:
            root = ensure_project_root(Path(tmpdir))
            write_active_state(root, stage="implement")
            write_active_state(root, work_item="iteration_id=I1")
            write_tasklist_ready(root, "DEMO-2")
            write_file(root, "docs/prd/DEMO-2.prd.md", "Status: READY\n")
            write_file(root, "reports/context/DEMO-2.pack.md", "# Context pack\n\nStatus: READY\n")
            stage_result = {
                "schema": "aidd.stage_result.v1",
                "ticket": "DEMO-2",
                "stage": "implement",
                "scope_key": "iteration_id_I1",
                "result": "blocked",
                "reason_code": "out_of_scope_warn",
                "updated_at": "2024-01-02T00:00:00Z",
            }
            write_file(
                root,
                "reports/loops/DEMO-2/iteration_id_I1/stage.implement.result.json",
                json.dumps(stage_result),
            )
            review_pack = "---\nschema: aidd.review_pack.v2\nupdated_at: 2024-01-02T00:00:00Z\n---\n"
            write_file(root, "reports/loops/DEMO-2/iteration_id_I1/review.latest.pack.md", review_pack)
            review_result = {
                "schema": "aidd.stage_result.v1",
                "ticket": "DEMO-2",
                "stage": "review",
                "scope_key": "iteration_id_I1",
                "result": "continue",
                "updated_at": "2024-01-02T00:00:00Z",
            }
            write_file(
                root,
                "reports/loops/DEMO-2/iteration_id_I1/stage.review.result.json",
                json.dumps(review_result),
            )
            log_path = root / "runner.log"
            result = self.run_loop_step(root, "DEMO-2", log_path, {"AIDD_SKIP_STAGE_WRAPPERS": "0"})
            self.assertEqual(result.returncode, 10, msg=result.stderr)
            self.assertIn("-p /feature-dev-aidd:review DEMO-2", log_path.read_text(encoding="utf-8"))

    def test_loop_step_ship_returns_done(self) -> None:
        with tempfile.TemporaryDirectory(prefix="loop-step-") as tmpdir:
            root = ensure_project_root(Path(tmpdir))
            write_active_state(root, stage="review")
            write_active_state(root, work_item="iteration_id=I1")
            stage_result = {
                "schema": "aidd.stage_result.v1",
                "ticket": "DEMO-3",
                "stage": "review",
                "scope_key": "iteration_id_I1",
                "result": "done",
                "updated_at": "2024-01-02T00:00:00Z",
            }
            write_file(
                root,
                "reports/loops/DEMO-3/iteration_id_I1/stage.review.result.json",
                json.dumps(stage_result),
            )
            review_pack = "---\nschema: aidd.review_pack.v2\nupdated_at: 2024-01-02T00:00:00Z\n---\n"
            write_file(root, "reports/loops/DEMO-3/iteration_id_I1/review.latest.pack.md", review_pack)
            log_path = root / "runner.log"
            result = self.run_loop_step(root, "DEMO-3", log_path)
            self.assertEqual(result.returncode, 0, msg=result.stderr)
            if log_path.exists():
                self.assertEqual(log_path.read_text(encoding="utf-8").strip(), "")

    def test_validate_review_pack_regens_when_stale(self) -> None:
        with tempfile.TemporaryDirectory(prefix="loop-step-") as tmpdir:
            root = ensure_project_root(Path(tmpdir))
            ticket = "DEMO-STALE"
            write_active_state(root, ticket=ticket, stage="review", work_item="iteration_id=I1")
            loop_pack = (
                "---\n"
                "schema: aidd.loop_pack.v1\n"
                "updated_at: 2024-01-01T00:00:00Z\n"
                f"ticket: {ticket}\n"
                "work_item_id: I1\n"
                "work_item_key: iteration_id=I1\n"
                "scope_key: iteration_id_I1\n"
                "---\n"
            )
            write_file(root, f"reports/loops/{ticket}/iteration_id_I1.loop.pack.md", loop_pack)
            review_report = {
                "schema": "aidd.review_report.v1",
                "updated_at": "2024-01-03T00:00:00Z",
                "ticket": ticket,
                "scope_key": "iteration_id_I1",
                "work_item_key": "iteration_id=I1",
                "status": "READY",
                "findings": [],
            }
            write_file(
                root,
                f"reports/reviewer/{ticket}/iteration_id_I1.json",
                json.dumps(review_report),
            )
            stale_pack = (
                "---\n"
                "schema: aidd.review_pack.v2\n"
                "updated_at: 2024-01-02T00:00:00Z\n"
                "verdict: SHIP\n"
                "work_item_key: iteration_id=I1\n"
                "scope_key: iteration_id_I1\n"
                "---\n"
            )
            write_file(
                root,
                f"reports/loops/{ticket}/iteration_id_I1/review.latest.pack.md",
                stale_pack,
            )
            cwd = os.getcwd()
            try:
                os.chdir(root.parent)
                ok, message, code = loop_step_module.validate_review_pack(
                    root,
                    ticket=ticket,
                    slug_hint=ticket,
                    scope_key="iteration_id_I1",
                )
            finally:
                os.chdir(cwd)
            self.assertTrue(ok, msg=f"{code}: {message}")

    def test_loop_step_blocked_without_review_pack(self) -> None:
        with tempfile.TemporaryDirectory(prefix="loop-step-") as tmpdir:
            root = ensure_project_root(Path(tmpdir))
            write_active_state(root, stage="review")
            write_active_state(root, work_item="iteration_id=I1")
            log_path = root / "runner.log"
            result = self.run_loop_step(root, "DEMO-4", log_path)
            self.assertEqual(result.returncode, 20, msg=result.stderr)

    def test_loop_step_revise_runs_implement(self) -> None:
        with tempfile.TemporaryDirectory(prefix="loop-step-") as tmpdir:
            root = ensure_project_root(Path(tmpdir))
            write_active_state(root, stage="review")
            write_active_state(root, work_item="iteration_id=I1")
            stage_result = {
                "schema": "aidd.stage_result.v1",
                "ticket": "DEMO-6",
                "stage": "review",
                "scope_key": "iteration_id_I1",
                "result": "continue",
                "updated_at": "2024-01-02T00:00:00Z",
            }
            write_file(
                root,
                "reports/loops/DEMO-6/iteration_id_I1/stage.review.result.json",
                json.dumps(stage_result),
            )
            review_pack = (
                "---\n"
                "schema: aidd.review_pack.v2\n"
                "updated_at: 2024-01-02T00:00:00Z\n"
                "verdict: REVISE\n"
                "work_item_key: iteration_id=I1\n"
                "scope_key: iteration_id_I1\n"
                "---\n"
            )
            write_file(root, "reports/loops/DEMO-6/iteration_id_I1/review.latest.pack.md", review_pack)
            fix_plan = {
                "schema": "aidd.review_fix_plan.v1",
                "updated_at": "2024-01-02T00:00:00Z",
                "ticket": "DEMO-6",
                "work_item_key": "iteration_id=I1",
                "scope_key": "iteration_id_I1",
                "fix_plan": {
                    "steps": ["Fix review:F1"],
                    "commands": [],
                    "tests": ["see AIDD:TEST_EXECUTION"],
                    "expected_paths": ["src/**"],
                    "acceptance_check": "Blocking findings resolved: review:F1",
                    "links": [],
                    "fixes": ["review:F1"],
                },
            }
            write_file(
                root,
                "reports/loops/DEMO-6/iteration_id_I1/review.fix_plan.json",
                json.dumps(fix_plan),
            )
            implement_result = {
                "schema": "aidd.stage_result.v1",
                "ticket": "DEMO-6",
                "stage": "implement",
                "scope_key": "iteration_id_I1",
                "result": "continue",
                "updated_at": "2024-01-02T00:00:00Z",
            }
            write_file(
                root,
                "reports/loops/DEMO-6/iteration_id_I1/stage.implement.result.json",
                json.dumps(implement_result),
            )
            log_path = root / "runner.log"
            result = self.run_loop_step(root, "DEMO-6", log_path, None, "--format", "json")
            self.assertEqual(result.returncode, 10, msg=result.stderr)
            self.assertIn("-p /feature-dev-aidd:implement DEMO-6", log_path.read_text(encoding="utf-8"))
            payload = json.loads(result.stdout)
            self.assertEqual(payload.get("scope_key"), "iteration_id_I1")

    def test_loop_step_blocks_when_fix_plan_missing(self) -> None:
        with tempfile.TemporaryDirectory(prefix="loop-step-") as tmpdir:
            root = ensure_project_root(Path(tmpdir))
            write_active_state(root, stage="review")
            write_active_state(root, work_item="iteration_id=I1")
            stage_result = {
                "schema": "aidd.stage_result.v1",
                "ticket": "DEMO-7",
                "stage": "review",
                "scope_key": "iteration_id_I1",
                "result": "continue",
                "updated_at": "2024-01-02T00:00:00Z",
            }
            write_file(
                root,
                "reports/loops/DEMO-7/iteration_id_I1/stage.review.result.json",
                json.dumps(stage_result),
            )
            review_pack = (
                "---\n"
                "schema: aidd.review_pack.v2\n"
                "updated_at: 2024-01-02T00:00:00Z\n"
                "verdict: REVISE\n"
                "work_item_key: iteration_id=I1\n"
                "scope_key: iteration_id_I1\n"
                "---\n"
            )
            write_file(root, "reports/loops/DEMO-7/iteration_id_I1/review.latest.pack.md", review_pack)

            log_path = root / "runner.log"
            result = self.run_loop_step(root, "DEMO-7", log_path)
            self.assertEqual(result.returncode, 20, msg=result.stderr)

    def test_loop_step_blocks_on_stale_review_pack(self) -> None:
        with tempfile.TemporaryDirectory(prefix="loop-step-") as tmpdir:
            root = ensure_project_root(Path(tmpdir))
            write_active_state(root, stage="review")
            write_active_state(root, work_item="iteration_id=I1")
            stage_result = {
                "schema": "aidd.stage_result.v0",
                "ticket": "DEMO-5",
                "stage": "review",
                "scope_key": "iteration_id_I1",
                "result": "done",
                "updated_at": "2024-01-02T00:00:00Z",
            }
            write_file(
                root,
                "reports/loops/DEMO-5/iteration_id_I1/stage.review.result.json",
                json.dumps(stage_result),
            )
            log_path = root / "runner.log"

            result = self.run_loop_step(root, "DEMO-5", log_path)
            self.assertEqual(result.returncode, 20, msg=result.stderr)
            if log_path.exists():
                self.assertEqual(log_path.read_text(encoding="utf-8").strip(), "")

    def test_loop_step_blocks_on_qa_without_repair(self) -> None:
        with tempfile.TemporaryDirectory(prefix="loop-step-") as tmpdir:
            root = ensure_project_root(Path(tmpdir))
            write_active_state(root, stage="qa")
            write_active_state(root, ticket="DEMO-QA")
            stage_result = {
                "schema": "aidd.stage_result.v1",
                "ticket": "DEMO-QA",
                "stage": "qa",
                "scope_key": "DEMO-QA",
                "result": "blocked",
                "updated_at": "2024-01-02T00:00:00Z",
            }
            write_file(
                root,
                "reports/loops/DEMO-QA/DEMO-QA/stage.qa.result.json",
                json.dumps(stage_result),
            )
            log_path = root / "runner.log"
            result = self.run_loop_step(root, "DEMO-QA", log_path)
            self.assertEqual(result.returncode, 20, msg=result.stderr)

    def test_loop_step_qa_repair_with_work_item(self) -> None:
        with tempfile.TemporaryDirectory(prefix="loop-step-") as tmpdir:
            root = ensure_project_root(Path(tmpdir))
            write_active_state(root, stage="qa")
            write_active_state(root, ticket="DEMO-QA2")
            stage_result = {
                "schema": "aidd.stage_result.v1",
                "ticket": "DEMO-QA2",
                "stage": "qa",
                "scope_key": "DEMO-QA2",
                "result": "blocked",
                "updated_at": "2024-01-02T00:00:00Z",
            }
            write_file(
                root,
                "reports/loops/DEMO-QA2/DEMO-QA2/stage.qa.result.json",
                json.dumps(stage_result),
            )
            implement_result = {
                "schema": "aidd.stage_result.v1",
                "ticket": "DEMO-QA2",
                "stage": "implement",
                "scope_key": "iteration_id_I2",
                "result": "continue",
                "updated_at": "2024-01-02T00:00:00Z",
            }
            write_file(
                root,
                "reports/loops/DEMO-QA2/iteration_id_I2/stage.implement.result.json",
                json.dumps(implement_result),
            )
            log_path = root / "runner.log"
            result = self.run_loop_step(
                root,
                "DEMO-QA2",
                log_path,
                None,
                "--from-qa",
                "--work-item-key",
                "iteration_id=I2",
                "--format",
                "json",
            )
            self.assertEqual(result.returncode, 10, msg=result.stderr)
            self.assertIn("-p /feature-dev-aidd:implement DEMO-QA2", log_path.read_text(encoding="utf-8"))
            active_payload = json.loads((root / "docs" / ".active.json").read_text(encoding="utf-8"))
            self.assertEqual(active_payload.get("stage"), "implement")
            self.assertEqual(active_payload.get("work_item"), "iteration_id=I2")

    def test_loop_step_qa_repair_auto_select_blocks_on_multiple(self) -> None:
        with tempfile.TemporaryDirectory(prefix="loop-step-") as tmpdir:
            root = ensure_project_root(Path(tmpdir))
            write_active_state(root, stage="qa")
            write_active_state(root, ticket="DEMO-QA3")
            stage_result = {
                "schema": "aidd.stage_result.v1",
                "ticket": "DEMO-QA3",
                "stage": "qa",
                "scope_key": "DEMO-QA3",
                "result": "blocked",
                "updated_at": "2024-01-02T00:00:00Z",
            }
            write_file(
                root,
                "reports/loops/DEMO-QA3/DEMO-QA3/stage.qa.result.json",
                json.dumps(stage_result),
            )
            tasklist = """<!-- handoff:qa start -->
- [ ] Fix A (id: qa:A1) (Priority: high) (Blocking: true) (scope: iteration_id=I2)
- [ ] Fix B (id: qa:A2) (Priority: high) (Blocking: true) (scope: iteration_id=I3)
<!-- handoff:qa end -->
"""
            write_file(root, "docs/tasklist/DEMO-QA3.md", tasklist)
            log_path = root / "runner.log"
            result = self.run_loop_step(
                root,
                "DEMO-QA3",
                log_path,
                None,
                "--from-qa",
                "auto",
                "--format",
                "json",
            )
            self.assertEqual(result.returncode, 20, msg=result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload.get("reason_code"), "qa_repair_multiple_handoffs")

    def test_loop_step_qa_repair_auto_config(self) -> None:
        with tempfile.TemporaryDirectory(prefix="loop-step-") as tmpdir:
            root = ensure_project_root(Path(tmpdir))
            write_active_state(root, stage="qa")
            write_active_state(root, ticket="DEMO-QA4")
            write_json(root, "config/gates.json", {"loop": {"auto_repair_from_qa": True}})
            stage_result = {
                "schema": "aidd.stage_result.v1",
                "ticket": "DEMO-QA4",
                "stage": "qa",
                "scope_key": "DEMO-QA4",
                "result": "blocked",
                "updated_at": "2024-01-02T00:00:00Z",
            }
            write_file(
                root,
                "reports/loops/DEMO-QA4/DEMO-QA4/stage.qa.result.json",
                json.dumps(stage_result),
            )
            tasklist = """<!-- handoff:qa start -->
- [ ] Fix A (id: qa:A1) (Priority: high) (Blocking: true) (scope: iteration_id=I2)
<!-- handoff:qa end -->
"""
            write_file(root, "docs/tasklist/DEMO-QA4.md", tasklist)
            implement_result = {
                "schema": "aidd.stage_result.v1",
                "ticket": "DEMO-QA4",
                "stage": "implement",
                "scope_key": "iteration_id_I2",
                "result": "continue",
                "updated_at": "2024-01-02T00:00:00Z",
            }
            write_file(
                root,
                "reports/loops/DEMO-QA4/iteration_id_I2/stage.implement.result.json",
                json.dumps(implement_result),
            )
            log_path = root / "runner.log"
            result = self.run_loop_step(root, "DEMO-QA4", log_path, None, "--format", "json")
            self.assertEqual(result.returncode, 10, msg=result.stderr)
            self.assertIn("-p /feature-dev-aidd:implement DEMO-QA4", log_path.read_text(encoding="utf-8"))

    def test_loop_step_wires_stage_runtime_chain(self) -> None:
        with tempfile.TemporaryDirectory(prefix="loop-step-") as tmpdir:
            root = ensure_project_root(Path(tmpdir))
            ticket = "DEMO-WRAP"
            scope_key = "iteration_id_I1"
            write_active_state(root, work_item="iteration_id=I1")
            write_tasklist_ready(root, ticket)
            write_file(root, f"docs/prd/{ticket}.prd.md", "Status: READY\n")
            implement_result = {
                "schema": "aidd.stage_result.v1",
                "ticket": ticket,
                "stage": "implement",
                "scope_key": scope_key,
                "result": "continue",
                "updated_at": "2024-01-02T00:00:00Z",
            }
            write_file(
                root,
                f"reports/loops/{ticket}/{scope_key}/stage.implement.result.json",
                json.dumps(implement_result),
            )
            log_path = root / "runner.log"
            result = self.run_loop_step(
                root,
                ticket,
                log_path,
                {"AIDD_SKIP_STAGE_WRAPPERS": "0"},
                "--format",
                "json",
            )
            self.assertEqual(result.returncode, 10, msg=result.stderr)
            payload = json.loads(result.stdout)
            self.assertTrue(payload.get("actions_log_path"))
            self.assertTrue((root / "reports" / "actions" / ticket / scope_key / "implement.actions.template.json").exists())
            self.assertTrue((root / "reports" / "actions" / ticket / scope_key / "implement.actions.json").exists())
            self.assertTrue((root / "reports" / "context" / ticket / f"{scope_key}.readmap.json").exists())
            self.assertTrue((root / "reports" / "context" / ticket / f"{scope_key}.writemap.json").exists())
            self.assertTrue((root / "reports" / "loops" / ticket / scope_key / "stage.preflight.result.json").exists())
            self.assertTrue(payload.get("wrapper_logs"))

    def test_loop_step_blocks_invalid_loop_work_item_key(self) -> None:
        with tempfile.TemporaryDirectory(prefix="loop-step-") as tmpdir:
            root = ensure_project_root(Path(tmpdir))
            write_active_state(root, stage="implement")
            write_active_state(root, work_item="id=review:report-1")
            log_path = root / "runner.log"
            result = self.run_loop_step(root, "DEMO-BAD-WORK", log_path, None, "--format", "json")
            self.assertEqual(result.returncode, 20, msg=result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload.get("reason_code"), "invalid_work_item_key")

    def test_loop_step_recovers_scope_from_stage_result(self) -> None:
        with tempfile.TemporaryDirectory(prefix="loop-step-") as tmpdir:
            root = ensure_project_root(Path(tmpdir))
            write_active_state(root, work_item="iteration_id=I2")
            implement_result = {
                "schema": "aidd.stage_result.v1",
                "ticket": "DEMO-MISMATCH",
                "stage": "implement",
                "scope_key": "iteration_id_I4",
                "result": "continue",
                "updated_at": "2024-01-02T00:00:00Z",
            }
            review_result = {
                "schema": "aidd.stage_result.v1",
                "ticket": "DEMO-MISMATCH",
                "stage": "review",
                "scope_key": "iteration_id_I4",
                "result": "continue",
                "updated_at": "2024-01-02T00:00:01Z",
            }
            write_file(
                root,
                "reports/loops/DEMO-MISMATCH/iteration_id_I4/stage.implement.result.json",
                json.dumps(implement_result),
            )
            write_file(
                root,
                "reports/loops/DEMO-MISMATCH/iteration_id_I4/stage.review.result.json",
                json.dumps(review_result),
            )
            write_file(
                root,
                "reports/loops/DEMO-MISMATCH/iteration_id_I4/review.latest.pack.md",
                "---\nschema: aidd.review_pack.v2\nupdated_at: 2024-01-02T00:00:01Z\n---\n",
            )
            log_path = root / "runner.log"
            result = self.run_loop_step(
                root,
                "DEMO-MISMATCH",
                log_path,
                None,
                "--format",
                "json",
            )
            self.assertEqual(result.returncode, 10, msg=result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload.get("scope_key"), "iteration_id_I4")
            self.assertEqual(payload.get("scope_key_mismatch_warn"), "1")

    def test_loop_step_realigns_actions_log_scope_on_mismatch(self) -> None:
        with tempfile.TemporaryDirectory(prefix="loop-step-") as tmpdir:
            root = ensure_project_root(Path(tmpdir))
            write_active_state(root, work_item="iteration_id=I2")
            write_tasklist_ready(root, "DEMO-ACTIONS-MISMATCH")
            write_file(root, "docs/prd/DEMO-ACTIONS-MISMATCH.prd.md", "Status: READY\n")
            implement_result = {
                "schema": "aidd.stage_result.v1",
                "ticket": "DEMO-ACTIONS-MISMATCH",
                "stage": "implement",
                "scope_key": "iteration_id_I4",
                "result": "continue",
                "updated_at": "2024-01-02T00:00:00Z",
            }
            write_file(
                root,
                "reports/loops/DEMO-ACTIONS-MISMATCH/iteration_id_I4/stage.implement.result.json",
                json.dumps(implement_result),
            )
            write_file(
                root,
                "reports/actions/DEMO-ACTIONS-MISMATCH/iteration_id_I4/implement.actions.json",
                '{"schema_version":"aidd.actions.v1","stage":"implement","ticket":"DEMO-ACTIONS-MISMATCH","scope_key":"iteration_id_I4","work_item_key":"iteration_id=I4","allowed_action_types":[],"actions":[]}',
            )
            log_path = root / "runner.log"
            result = self.run_loop_step(
                root,
                "DEMO-ACTIONS-MISMATCH",
                log_path,
                {"AIDD_SKIP_STAGE_WRAPPERS": "0"},
                "--format",
                "json",
            )
            self.assertEqual(result.returncode, 10, msg=result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload.get("scope_key"), "iteration_id_I4")
            self.assertEqual(payload.get("scope_key_mismatch_warn"), "1")
            self.assertEqual(
                payload.get("actions_log_path"),
                "aidd/reports/actions/DEMO-ACTIONS-MISMATCH/iteration_id_I4/implement.actions.json",
            )


if __name__ == "__main__":
    unittest.main()
