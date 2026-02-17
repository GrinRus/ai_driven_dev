import json
import io
import os
import time
import subprocess
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from aidd_runtime import loop_run as loop_run_module
from tests.helpers import REPO_ROOT, cli_cmd, cli_env, ensure_project_root, tasklist_ready_text, write_active_state, write_file


FIXTURES = Path(__file__).resolve().parent / "fixtures" / "loop_step"


def _fixture_json(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


class LoopRunTests(unittest.TestCase):
    def test_loop_run_ship_clears_state(self) -> None:
        with tempfile.TemporaryDirectory(prefix="loop-run-") as tmpdir:
            root = ensure_project_root(Path(tmpdir))
            write_active_state(root, ticket="DEMO-1", stage="review", work_item="iteration_id=I1")
            write_file(root, "docs/.active_mode", "loop")
            stage_result = {
                "schema": "aidd.stage_result.v1",
                "ticket": "DEMO-1",
                "stage": "review",
                "scope_key": "iteration_id_I1",
                "result": "done",
                "updated_at": "2024-01-02T00:00:00Z",
            }
            write_file(
                root,
                "reports/loops/DEMO-1/iteration_id_I1/stage.review.result.json",
                json.dumps(stage_result),
            )
            review_pack = "---\nschema: aidd.review_pack.v2\nupdated_at: 2024-01-02T00:00:00Z\n---\n"
            write_file(root, "reports/loops/DEMO-1/iteration_id_I1/review.latest.pack.md", review_pack)

            result = subprocess.run(
                cli_cmd("loop-run", "--ticket", "DEMO-1", "--max-iterations", "2", "--format", "json"),
                text=True,
                capture_output=True,
                cwd=root,
                env=cli_env({"AIDD_LOOP_RUNNER_LABEL": "local"}),
            )
            self.assertEqual(result.returncode, 0, msg=result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload.get("status"), "ship")
            self.assertFalse((root / "docs" / ".active_mode").exists())
            log_path = root / "reports" / "loops" / "DEMO-1" / "loop.run.log"
            self.assertTrue(log_path.exists())
            self.assertIn("runner=local", log_path.read_text(encoding="utf-8"))
            cli_logs = list((root / "reports" / "loops" / "DEMO-1").glob("cli.loop-run.*.log"))
            self.assertTrue(cli_logs, "cli.loop-run log should be written")

    def test_loop_run_blocked(self) -> None:
        with tempfile.TemporaryDirectory(prefix="loop-run-") as tmpdir:
            root = ensure_project_root(Path(tmpdir))
            write_active_state(root, stage="review", work_item="iteration_id=I1")

            result = subprocess.run(
                cli_cmd("loop-run", "--ticket", "DEMO-2", "--max-iterations", "1", "--format", "json"),
                text=True,
                capture_output=True,
                cwd=root,
                env=cli_env(),
            )
            self.assertEqual(result.returncode, 20, msg=result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload.get("status"), "blocked")

    def test_loop_run_ralph_retries_recoverable_block(self) -> None:
        with tempfile.TemporaryDirectory(prefix="loop-run-") as tmpdir:
            root = ensure_project_root(Path(tmpdir))
            ticket = "DEMO-RALPH-RECOVER"
            write_active_state(root, ticket=ticket, stage="implement", work_item="iteration_id=I1")

            fake_result = subprocess.CompletedProcess(
                args=["loop-step"],
                returncode=20,
                stdout=json.dumps(
                    {
                        "status": "blocked",
                        "stage": "implement",
                        "scope_key": "iteration_id_I1",
                        "work_item_key": "iteration_id=I1",
                        "reason_code": "stage_result_missing_or_invalid",
                        "reason": "stage result missing",
                    }
                ),
                stderr="",
            )
            captured = io.StringIO()
            cwd = os.getcwd()
            try:
                os.chdir(root.parent)
                with patch.dict(os.environ, {"CLAUDE_PLUGIN_ROOT": str(REPO_ROOT)}, clear=False):
                    with patch("aidd_runtime.loop_run.run_loop_step", return_value=fake_result):
                        with redirect_stdout(captured):
                            code = loop_run_module.main(
                                [
                                    "--ticket",
                                    ticket,
                                    "--work-item-key",
                                    "iteration_id=I1",
                                    "--max-iterations",
                                    "1",
                                    "--blocked-policy",
                                    "ralph",
                                    "--recoverable-block-retries",
                                    "1",
                                    "--format",
                                    "json",
                                ]
                            )
            finally:
                os.chdir(cwd)

            self.assertEqual(code, 11)
            payload = json.loads(captured.getvalue())
            self.assertEqual(payload.get("status"), "max-iterations")
            self.assertEqual(payload.get("blocked_policy"), "ralph")
            self.assertEqual(payload.get("retry_attempt"), 1)
            self.assertEqual(payload.get("recoverable_retry_budget"), 1)
            self.assertIn(payload.get("last_recovery_path"), {"retry_implement", "retry_active_stage"})
            last_step = payload.get("last_step") or {}
            self.assertEqual(last_step.get("recoverable_blocked"), True)
            self.assertEqual(last_step.get("retry_attempt"), 1)

    def test_loop_run_ralph_retries_blocking_findings(self) -> None:
        with tempfile.TemporaryDirectory(prefix="loop-run-") as tmpdir:
            root = ensure_project_root(Path(tmpdir))
            ticket = "DEMO-RALPH-FINDINGS"
            write_active_state(root, ticket=ticket, stage="review", work_item="iteration_id=I1")

            fake_result = subprocess.CompletedProcess(
                args=["loop-step"],
                returncode=20,
                stdout=json.dumps(
                    {
                        "status": "blocked",
                        "stage": "review",
                        "scope_key": "iteration_id_I1",
                        "work_item_key": "iteration_id=I1",
                        "reason_code": "blocking_findings",
                        "reason": "blocking review findings present",
                    }
                ),
                stderr="",
            )
            captured = io.StringIO()
            cwd = os.getcwd()
            try:
                os.chdir(root.parent)
                with patch.dict(os.environ, {"CLAUDE_PLUGIN_ROOT": str(REPO_ROOT)}, clear=False):
                    with patch("aidd_runtime.loop_run.run_loop_step", return_value=fake_result):
                        with redirect_stdout(captured):
                            code = loop_run_module.main(
                                [
                                    "--ticket",
                                    ticket,
                                    "--work-item-key",
                                    "iteration_id=I1",
                                    "--max-iterations",
                                    "1",
                                    "--blocked-policy",
                                    "ralph",
                                    "--recoverable-block-retries",
                                    "1",
                                    "--format",
                                    "json",
                                ]
                            )
            finally:
                os.chdir(cwd)

            self.assertEqual(code, 11)
            payload = json.loads(captured.getvalue())
            self.assertEqual(payload.get("status"), "max-iterations")
            self.assertEqual(payload.get("blocked_policy"), "ralph")
            self.assertEqual(payload.get("retry_attempt"), 1)
            self.assertEqual(payload.get("recoverable_retry_budget"), 1)
            last_step = payload.get("last_step") or {}
            self.assertEqual(last_step.get("recoverable_blocked"), True)
            self.assertEqual(last_step.get("retry_attempt"), 1)
            self.assertEqual(last_step.get("reason_code"), "blocking_findings")

    def test_loop_run_ralph_does_not_retry_hard_block(self) -> None:
        with tempfile.TemporaryDirectory(prefix="loop-run-") as tmpdir:
            root = ensure_project_root(Path(tmpdir))
            ticket = "DEMO-RALPH-HARD"
            write_active_state(root, ticket=ticket, stage="implement", work_item="iteration_id=I1")

            fake_result = subprocess.CompletedProcess(
                args=["loop-step"],
                returncode=20,
                stdout=json.dumps(
                    {
                        "status": "blocked",
                        "stage": "implement",
                        "scope_key": "iteration_id_I1",
                        "work_item_key": "iteration_id=I1",
                        "reason_code": "user_approval_required",
                        "reason": "manual approval required",
                    }
                ),
                stderr="",
            )
            captured = io.StringIO()
            cwd = os.getcwd()
            try:
                os.chdir(root.parent)
                with patch.dict(os.environ, {"CLAUDE_PLUGIN_ROOT": str(REPO_ROOT)}, clear=False):
                    with patch("aidd_runtime.loop_run.run_loop_step", return_value=fake_result):
                        with redirect_stdout(captured):
                            code = loop_run_module.main(
                                [
                                    "--ticket",
                                    ticket,
                                    "--work-item-key",
                                    "iteration_id=I1",
                                    "--max-iterations",
                                    "1",
                                    "--blocked-policy",
                                    "ralph",
                                    "--recoverable-block-retries",
                                    "2",
                                    "--format",
                                    "json",
                                ]
                            )
            finally:
                os.chdir(cwd)

            self.assertEqual(code, 20)
            payload = json.loads(captured.getvalue())
            self.assertEqual(payload.get("status"), "blocked")
            self.assertEqual(payload.get("blocked_policy"), "ralph")
            self.assertEqual(payload.get("recoverable_blocked"), False)
            self.assertEqual(payload.get("retry_attempt"), 0)
            self.assertEqual(payload.get("reason_code"), "user_approval_required")

    def test_loop_run_ralph_does_not_retry_prompt_flow_blocker(self) -> None:
        with tempfile.TemporaryDirectory(prefix="loop-run-") as tmpdir:
            root = ensure_project_root(Path(tmpdir))
            ticket = "DEMO-RALPH-PROMPT-BLOCK"
            write_active_state(root, ticket=ticket, stage="implement", work_item="iteration_id=I1")

            fake_result = subprocess.CompletedProcess(
                args=["loop-step"],
                returncode=20,
                stdout=json.dumps(
                    {
                        "status": "blocked",
                        "stage": "implement",
                        "scope_key": "iteration_id_I1",
                        "work_item_key": "iteration_id=I1",
                        "reason_code": "prompt_flow_blocker",
                        "reason": "question retry exhausted",
                    }
                ),
                stderr="",
            )
            captured = io.StringIO()
            cwd = os.getcwd()
            try:
                os.chdir(root.parent)
                with patch.dict(os.environ, {"CLAUDE_PLUGIN_ROOT": str(REPO_ROOT)}, clear=False):
                    with patch("aidd_runtime.loop_run.run_loop_step", return_value=fake_result):
                        with redirect_stdout(captured):
                            code = loop_run_module.main(
                                [
                                    "--ticket",
                                    ticket,
                                    "--work-item-key",
                                    "iteration_id=I1",
                                    "--max-iterations",
                                    "1",
                                    "--blocked-policy",
                                    "ralph",
                                    "--recoverable-block-retries",
                                    "2",
                                    "--format",
                                    "json",
                                ]
                            )
            finally:
                os.chdir(cwd)

            self.assertEqual(code, 20)
            payload = json.loads(captured.getvalue())
            self.assertEqual(payload.get("status"), "blocked")
            self.assertEqual(payload.get("reason_code"), "prompt_flow_blocker")
            self.assertEqual(payload.get("recoverable_blocked"), False)
            self.assertEqual(payload.get("retry_attempt"), 0)

    def test_loop_run_rejects_invalid_work_item_key_override(self) -> None:
        with tempfile.TemporaryDirectory(prefix="loop-run-") as tmpdir:
            root = ensure_project_root(Path(tmpdir))

            result = subprocess.run(
                cli_cmd(
                    "loop-run",
                    "--ticket",
                    "DEMO-INVALID",
                    "--work-item-key",
                    "I1",
                    "--max-iterations",
                    "1",
                    "--format",
                    "json",
                ),
                text=True,
                capture_output=True,
                cwd=root,
                env=cli_env(),
            )
            self.assertEqual(result.returncode, 20, msg=result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload.get("status"), "blocked")
            self.assertEqual(payload.get("reason_code"), "work_item_invalid_format")

    def test_loop_run_auto_selects_open_work_item_when_active_missing(self) -> None:
        with tempfile.TemporaryDirectory(prefix="loop-run-") as tmpdir:
            root = ensure_project_root(Path(tmpdir))
            ticket = "DEMO-AUTO"
            write_file(root, f"docs/tasklist/{ticket}.md", tasklist_ready_text(ticket))

            result = subprocess.run(
                cli_cmd("loop-run", "--ticket", ticket, "--max-iterations", "1", "--format", "json"),
                text=True,
                capture_output=True,
                cwd=root,
                env=cli_env(),
            )
            self.assertEqual(result.returncode, 20, msg=result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload.get("status"), "blocked")
            self.assertNotEqual(payload.get("reason_code"), "work_item_missing")
            self.assertEqual(payload.get("scope_key"), "iteration_id_I1")

            active_state = json.loads((root / "docs" / ".active.json").read_text(encoding="utf-8"))
            self.assertEqual(active_state.get("work_item"), "iteration_id=I1")

    def test_loop_run_blocked_uses_reason_code_fallback_when_stage_result_present(self) -> None:
        with tempfile.TemporaryDirectory(prefix="loop-run-") as tmpdir:
            root = ensure_project_root(Path(tmpdir))
            write_active_state(root, ticket="DEMO-FALLBACK", stage="implement", work_item="iteration_id=I7")
            write_file(
                root,
                "reports/loops/DEMO-FALLBACK/iteration_id_I7/stage.implement.result.json",
                json.dumps(
                    {
                        "schema": "aidd.stage_result.v1",
                        "ticket": "DEMO-FALLBACK",
                        "stage": "implement",
                        "scope_key": "iteration_id_I7",
                        "work_item_key": "iteration_id=I7",
                        "result": "blocked",
                        "updated_at": "2024-01-02T00:00:00Z",
                    }
                ),
            )
            result = subprocess.run(
                cli_cmd("loop-run", "--ticket", "DEMO-FALLBACK", "--max-iterations", "1", "--format", "json"),
                text=True,
                capture_output=True,
                cwd=root,
                env=cli_env({"AIDD_SKIP_STAGE_WRAPPERS": "1"}),
            )
            self.assertEqual(result.returncode, 20, msg=result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload.get("status"), "blocked")
            self.assertEqual(payload.get("reason_code"), "stage_result_blocked")
            self.assertTrue(payload.get("stage_result_path"))
            self.assertTrue(payload.get("step_log_path"))
            loop_log = (root / "reports" / "loops" / "DEMO-FALLBACK" / "loop.run.log").read_text(encoding="utf-8")
            self.assertIn("reason_code=stage_result_blocked", loop_log)
            self.assertIn("log_path=", loop_log)

    def test_loop_run_blocked_when_loop_step_payload_is_invalid_json(self) -> None:
        with tempfile.TemporaryDirectory(prefix="loop-run-") as tmpdir:
            root = ensure_project_root(Path(tmpdir))
            ticket = "DEMO-BROKEN-JSON"
            write_active_state(root, ticket=ticket, stage="implement", work_item="iteration_id=I1")

            fake_result = subprocess.CompletedProcess(
                args=["loop-step"],
                returncode=20,
                stdout="{broken-json",
                stderr="",
            )
            captured = io.StringIO()
            cwd = os.getcwd()
            try:
                os.chdir(root.parent)
                with patch.dict(os.environ, {"CLAUDE_PLUGIN_ROOT": str(REPO_ROOT)}, clear=False):
                    with patch("aidd_runtime.loop_run.run_loop_step", return_value=fake_result):
                        with redirect_stdout(captured):
                            code = loop_run_module.main(
                                ["--ticket", ticket, "--max-iterations", "1", "--format", "json"]
                            )
            finally:
                os.chdir(cwd)

            self.assertEqual(code, 20)
            payload = json.loads(captured.getvalue())
            self.assertEqual(payload.get("status"), "blocked")
            self.assertEqual(payload.get("reason_code"), "blocked_without_reason")
            self.assertIn("invalid JSON payload", str(payload.get("reason") or ""))

    def test_loop_run_blocks_when_loop_stage_payload_missing_work_item_key(self) -> None:
        with tempfile.TemporaryDirectory(prefix="loop-run-") as tmpdir:
            root = ensure_project_root(Path(tmpdir))
            ticket = "DEMO-WORK-ITEM-MISSING"
            write_active_state(root, ticket=ticket, stage="implement", work_item="iteration_id=I1")

            fake_result = subprocess.CompletedProcess(
                args=["loop-step"],
                returncode=20,
                stdout=json.dumps(
                    {
                        "status": "blocked",
                        "stage": "implement",
                        "scope_key": "iteration_id_I1",
                        "work_item_key": None,
                        "reason_code": "stage_result_missing_or_invalid",
                        "reason": "stage result missing",
                    }
                ),
                stderr="",
            )
            captured = io.StringIO()
            cwd = os.getcwd()
            try:
                os.chdir(root.parent)
                with patch.dict(os.environ, {"CLAUDE_PLUGIN_ROOT": str(REPO_ROOT)}, clear=False):
                    with patch("aidd_runtime.loop_run.run_loop_step", return_value=fake_result):
                        with redirect_stdout(captured):
                            code = loop_run_module.main(
                                [
                                    "--ticket",
                                    ticket,
                                    "--work-item-key",
                                    "iteration_id=I1",
                                    "--max-iterations",
                                    "1",
                                    "--blocked-policy",
                                    "ralph",
                                    "--recoverable-block-retries",
                                    "2",
                                    "--format",
                                    "json",
                                ]
                            )
            finally:
                os.chdir(cwd)

            self.assertEqual(code, 20)
            payload = json.loads(captured.getvalue())
            self.assertEqual(payload.get("status"), "blocked")
            self.assertEqual(payload.get("reason_code"), "work_item_resolution_failed")
            self.assertEqual(payload.get("recoverable_blocked"), False)
            self.assertEqual(payload.get("work_item_key"), None)
            loop_log = (root / "reports" / "loops" / ticket / "loop.run.log").read_text(encoding="utf-8")
            self.assertIn("reason_code=work_item_resolution_failed", loop_log)

    def test_loop_run_tst001_rca_fixture_reason_precedence_strict(self) -> None:
        with tempfile.TemporaryDirectory(prefix="loop-run-") as tmpdir:
            root = ensure_project_root(Path(tmpdir))
            ticket = "TST001-RCA-STRICT"
            write_active_state(root, ticket=ticket, stage="implement", work_item="iteration_id=I1")
            fixture_payload = _fixture_json("tst001_loop_run_blocked_payload.json")
            fake_result = subprocess.CompletedProcess(
                args=["loop-step"],
                returncode=20,
                stdout=json.dumps(fixture_payload),
                stderr="",
            )
            captured = io.StringIO()
            cwd = os.getcwd()
            try:
                os.chdir(root.parent)
                with patch.dict(os.environ, {"CLAUDE_PLUGIN_ROOT": str(REPO_ROOT)}, clear=False):
                    with patch("aidd_runtime.loop_run.run_loop_step", return_value=fake_result):
                        with redirect_stdout(captured):
                            code = loop_run_module.main(
                                [
                                    "--ticket",
                                    ticket,
                                    "--work-item-key",
                                    "iteration_id=I1",
                                    "--max-iterations",
                                    "1",
                                    "--blocked-policy",
                                    "strict",
                                    "--format",
                                    "json",
                                ]
                            )
            finally:
                os.chdir(cwd)

            self.assertEqual(code, 20)
            payload = json.loads(captured.getvalue())
            self.assertEqual(payload.get("status"), "blocked")
            self.assertEqual(payload.get("reason_code"), "work_item_resolution_failed")
            self.assertEqual(payload.get("active_stage_before"), "idea")
            self.assertEqual(payload.get("active_stage_after"), "implement")
            self.assertEqual(payload.get("active_stage_sync_applied"), True)
            self.assertEqual(payload.get("retry_attempt"), 0)
            loop_log = (root / "reports" / "loops" / ticket / "loop.run.log").read_text(encoding="utf-8")
            self.assertIn("reason_code=work_item_resolution_failed", loop_log)
            self.assertIn("active_stage_before=idea", loop_log)
            self.assertIn("work_item_key=null", loop_log)

    def test_loop_run_tst001_rca_fixture_reason_precedence_ralph(self) -> None:
        with tempfile.TemporaryDirectory(prefix="loop-run-") as tmpdir:
            root = ensure_project_root(Path(tmpdir))
            ticket = "TST001-RCA-RALPH"
            write_active_state(root, ticket=ticket, stage="implement", work_item="iteration_id=I1")
            fixture_payload = _fixture_json("tst001_loop_run_blocked_payload.json")
            fake_result = subprocess.CompletedProcess(
                args=["loop-step"],
                returncode=20,
                stdout=json.dumps(fixture_payload),
                stderr="",
            )
            captured = io.StringIO()
            cwd = os.getcwd()
            try:
                os.chdir(root.parent)
                with patch.dict(os.environ, {"CLAUDE_PLUGIN_ROOT": str(REPO_ROOT)}, clear=False):
                    with patch("aidd_runtime.loop_run.run_loop_step", return_value=fake_result):
                        with redirect_stdout(captured):
                            code = loop_run_module.main(
                                [
                                    "--ticket",
                                    ticket,
                                    "--work-item-key",
                                    "iteration_id=I1",
                                    "--max-iterations",
                                    "1",
                                    "--blocked-policy",
                                    "ralph",
                                    "--recoverable-block-retries",
                                    "2",
                                    "--format",
                                    "json",
                                ]
                            )
            finally:
                os.chdir(cwd)

            self.assertEqual(code, 20)
            payload = json.loads(captured.getvalue())
            self.assertEqual(payload.get("status"), "blocked")
            self.assertEqual(payload.get("reason_code"), "work_item_resolution_failed")
            self.assertEqual(payload.get("blocked_policy"), "ralph")
            self.assertEqual(payload.get("recoverable_blocked"), False)
            self.assertEqual(payload.get("retry_attempt"), 0)

    def test_loop_run_marks_marker_report_noise_without_signal(self) -> None:
        with tempfile.TemporaryDirectory(prefix="loop-run-") as tmpdir:
            root = ensure_project_root(Path(tmpdir))
            ticket = "DEMO-MARKER-NOISE"
            write_active_state(root, ticket=ticket, stage="implement", work_item="iteration_id=I1")
            fake_result = subprocess.CompletedProcess(
                args=["loop-step"],
                returncode=20,
                stdout=json.dumps(
                    {
                        "status": "blocked",
                        "stage": "implement",
                        "scope_key": "iteration_id_I1",
                        "work_item_key": "iteration_id=I1",
                        "reason_code": "stage_result_missing_or_invalid",
                        "reason": "candidate:aidd/docs/tasklist/templates/loop.seed.md:id=review:template",
                        "stage_result_diagnostics": "candidate:aidd/docs/tasklist/TST-001.md.bak:id_review_backup",
                    }
                ),
                stderr="",
            )
            captured = io.StringIO()
            cwd = os.getcwd()
            try:
                os.chdir(root.parent)
                with patch.dict(os.environ, {"CLAUDE_PLUGIN_ROOT": str(REPO_ROOT)}, clear=False):
                    with patch("aidd_runtime.loop_run.run_loop_step", return_value=fake_result):
                        with redirect_stdout(captured):
                            code = loop_run_module.main(
                                [
                                    "--ticket",
                                    ticket,
                                    "--work-item-key",
                                    "iteration_id=I1",
                                    "--max-iterations",
                                    "1",
                                    "--format",
                                    "json",
                                ]
                            )
            finally:
                os.chdir(cwd)

            self.assertEqual(code, 20)
            payload = json.loads(captured.getvalue())
            self.assertEqual(payload.get("report_noise"), "marker_semantics_noise_only")
            self.assertEqual(payload.get("marker_signal_events"), [])
            self.assertTrue(payload.get("report_noise_events"))
            loop_log = (root / "reports" / "loops" / ticket / "loop.run.log").read_text(encoding="utf-8")
            self.assertIn("marker_signals=0", loop_log)
            self.assertIn("marker_noise=2", loop_log)

    def test_run_loop_step_timeout_returns_scope_aware_blocked_payload(self) -> None:
        with tempfile.TemporaryDirectory(prefix="loop-run-") as tmpdir:
            root = ensure_project_root(Path(tmpdir))
            ticket = "DEMO-SEED-STALL"
            write_active_state(root, ticket=ticket, stage="review", work_item="iteration_id=I3")
            write_file(
                root,
                f"reports/loops/{ticket}/iteration_id_I3/stage.review.result.json",
                json.dumps(
                    {
                        "schema": "aidd.stage_result.v1",
                        "ticket": ticket,
                        "stage": "review",
                        "scope_key": "iteration_id_I3",
                        "result": "continue",
                        "updated_at": "2024-01-02T00:00:00Z",
                    }
                ),
            )
            with patch("subprocess.run", side_effect=subprocess.TimeoutExpired(cmd=["loop-step"], timeout=1)):
                result = loop_run_module.run_loop_step(
                    REPO_ROOT,
                    root.parent,
                    root,
                    ticket,
                    None,
                    from_qa=None,
                    work_item_key=None,
                    select_qa_handoff=False,
                    stream_mode=None,
                    timeout_seconds=1,
                )

            self.assertEqual(result.returncode, 20)
            payload = json.loads(result.stdout)
            self.assertEqual(payload.get("status"), "blocked")
            self.assertEqual(payload.get("reason_code"), "seed_stage_silent_stall")
            self.assertEqual(payload.get("scope_key"), "iteration_id_I3")
            diagnostics = json.loads(payload.get("stage_result_diagnostics") or "{}")
            self.assertEqual(diagnostics.get("active_stage"), "review")
            self.assertEqual(diagnostics.get("scope_key"), "iteration_id_I3")
            self.assertTrue(diagnostics.get("last_valid_stage_result_path"))

    def test_run_loop_step_timeout_uses_active_stream_artifacts_for_liveness(self) -> None:
        with tempfile.TemporaryDirectory(prefix="loop-run-") as tmpdir:
            root = ensure_project_root(Path(tmpdir))
            ticket = "DEMO-SEED-STREAM"
            write_active_state(root, ticket=ticket, stage="implement", work_item="iteration_id=I1")
            stream_log = write_file(root, f"reports/loops/{ticket}/cli.loop-step.seed.stream.log", "stream-active\n")
            stream_jsonl = write_file(root, f"reports/loops/{ticket}/cli.loop-step.seed.stream.jsonl", '{"type":"init"}\n')
            # Simulate stream activity from the current run window.
            future = time.time() + 3
            os.utime(stream_log, (future, future))
            os.utime(stream_jsonl, (future, future))
            with patch("subprocess.run", side_effect=subprocess.TimeoutExpired(cmd=["loop-step"], timeout=1)):
                result = loop_run_module.run_loop_step(
                    REPO_ROOT,
                    root.parent,
                    root,
                    ticket,
                    None,
                    from_qa=None,
                    work_item_key=None,
                    select_qa_handoff=False,
                    stream_mode="text",
                    timeout_seconds=1,
                )

            self.assertEqual(result.returncode, 20)
            payload = json.loads(result.stdout)
            self.assertEqual(payload.get("status"), "blocked")
            self.assertEqual(payload.get("reason_code"), "seed_stage_active_stream_timeout")
            self.assertTrue(str(payload.get("stream_log_path") or "").endswith(".stream.log"))
            self.assertTrue(str(payload.get("stream_jsonl_path") or "").endswith(".stream.jsonl"))
            stream_liveness = payload.get("stream_liveness") or {}
            self.assertGreater(int(stream_liveness.get("step_stream_log_bytes") or 0), 0)
            self.assertGreater(int(stream_liveness.get("step_stream_jsonl_bytes") or 0), 0)

    def test_run_loop_step_timeout_ignores_stale_stream_artifacts(self) -> None:
        with tempfile.TemporaryDirectory(prefix="loop-run-") as tmpdir:
            root = ensure_project_root(Path(tmpdir))
            ticket = "DEMO-SEED-STALE-STREAM"
            write_active_state(root, ticket=ticket, stage="implement", work_item="iteration_id=I1")
            stream_log = write_file(root, f"reports/loops/{ticket}/cli.loop-step.seed.stream.log", "stale\n")
            stream_jsonl = write_file(root, f"reports/loops/{ticket}/cli.loop-step.seed.stream.jsonl", '{"type":"old"}\n')
            old = max(time.time() - 3600, 1)
            os.utime(stream_log, (old, old))
            os.utime(stream_jsonl, (old, old))
            with patch("subprocess.run", side_effect=subprocess.TimeoutExpired(cmd=["loop-step"], timeout=1)):
                result = loop_run_module.run_loop_step(
                    REPO_ROOT,
                    root.parent,
                    root,
                    ticket,
                    None,
                    from_qa=None,
                    work_item_key=None,
                    select_qa_handoff=False,
                    stream_mode="text",
                    timeout_seconds=1,
                )

            self.assertEqual(result.returncode, 20)
            payload = json.loads(result.stdout)
            self.assertEqual(payload.get("reason_code"), "seed_stage_silent_stall")
            stream_liveness = payload.get("stream_liveness") or {}
            self.assertEqual(stream_liveness.get("active_source"), "none")

    def test_loop_run_blocked_promotes_permission_reason_code(self) -> None:
        with tempfile.TemporaryDirectory(prefix="loop-run-") as tmpdir:
            root = ensure_project_root(Path(tmpdir))
            ticket = "DEMO-PERM-PRIO"
            write_active_state(root, ticket=ticket, stage="implement", work_item="iteration_id=I1")

            fake_result = subprocess.CompletedProcess(
                args=["loop-step"],
                returncode=20,
                stdout=json.dumps(
                    {
                        "status": "blocked",
                        "stage": "implement",
                        "scope_key": "iteration_id_I1",
                        "work_item_key": "iteration_id=I1",
                        "reason_code": "stage_result_missing_or_invalid",
                        "reason": "command requires approval in current mode",
                        "stage_result_diagnostics": '{"permissionMode":"default"}',
                        "runner_effective": "claude -p /feature-dev-aidd:implement DEMO-PERM-PRIO",
                    }
                ),
                stderr="",
            )
            captured = io.StringIO()
            cwd = os.getcwd()
            try:
                os.chdir(root.parent)
                with patch.dict(os.environ, {"CLAUDE_PLUGIN_ROOT": str(REPO_ROOT)}, clear=False):
                    with patch("aidd_runtime.loop_run.run_loop_step", return_value=fake_result):
                        with redirect_stdout(captured):
                            code = loop_run_module.main(
                                [
                                    "--ticket",
                                    ticket,
                                    "--work-item-key",
                                    "iteration_id=I1",
                                    "--max-iterations",
                                    "1",
                                    "--format",
                                    "json",
                                ]
                            )
            finally:
                os.chdir(cwd)

            self.assertEqual(code, 20)
            payload = json.loads(captured.getvalue())
            self.assertEqual(payload.get("status"), "blocked")
            self.assertEqual(payload.get("reason_code"), "loop_runner_permissions")
            loop_log = (root / "reports" / "loops" / ticket / "loop.run.log").read_text(encoding="utf-8")
            self.assertIn("reason_code=loop_runner_permissions", loop_log)

    def test_loop_run_blocked_payload_includes_stream_liveness(self) -> None:
        with tempfile.TemporaryDirectory(prefix="loop-run-") as tmpdir:
            root = ensure_project_root(Path(tmpdir))
            ticket = "DEMO-STREAM-LIVE"
            write_active_state(root, ticket=ticket, stage="implement", work_item="iteration_id=I1")
            step_stream_log_rel = f"aidd/reports/loops/{ticket}/cli.loop-step.demo.stream.log"
            step_stream_jsonl_rel = f"aidd/reports/loops/{ticket}/cli.loop-step.demo.stream.jsonl"
            write_file(root, f"reports/loops/{ticket}/cli.loop-step.demo.stream.log", "stage-stream-log\n")
            write_file(root, f"reports/loops/{ticket}/cli.loop-step.demo.stream.jsonl", '{"type":"init"}\n')

            fake_result = subprocess.CompletedProcess(
                args=["loop-step"],
                returncode=20,
                stdout=json.dumps(
                    {
                        "status": "blocked",
                        "stage": "implement",
                        "scope_key": "iteration_id_I1",
                        "work_item_key": "iteration_id=I1",
                        "reason_code": "stage_result_missing_or_invalid",
                        "reason": "stage result missing",
                        "stream_log_path": step_stream_log_rel,
                        "stream_jsonl_path": step_stream_jsonl_rel,
                        "runner_effective": "claude --dangerously-skip-permissions -p /feature-dev-aidd:implement DEMO-STREAM-LIVE",
                    }
                ),
                stderr="",
            )
            captured = io.StringIO()
            cwd = os.getcwd()
            try:
                os.chdir(root.parent)
                with patch.dict(os.environ, {"CLAUDE_PLUGIN_ROOT": str(REPO_ROOT)}, clear=False):
                    with patch("aidd_runtime.loop_run.run_loop_step", return_value=fake_result):
                        with redirect_stdout(captured):
                            code = loop_run_module.main(
                                [
                                    "--ticket",
                                    ticket,
                                    "--work-item-key",
                                    "iteration_id=I1",
                                    "--max-iterations",
                                    "1",
                                    "--stream",
                                    "text",
                                    "--format",
                                    "json",
                                ]
                            )
            finally:
                os.chdir(cwd)

            self.assertEqual(code, 20)
            payload = json.loads(captured.getvalue())
            self.assertEqual(payload.get("status"), "blocked")
            self.assertEqual(payload.get("step_stream_log_path"), step_stream_log_rel)
            self.assertEqual(payload.get("step_stream_jsonl_path"), step_stream_jsonl_rel)
            stream_liveness = payload.get("stream_liveness") or {}
            self.assertGreater(int(stream_liveness.get("step_stream_log_bytes") or 0), 0)
            self.assertGreater(int(stream_liveness.get("step_stream_jsonl_bytes") or 0), 0)
            self.assertEqual(stream_liveness.get("active_source"), "stream")
            self.assertEqual(stream_liveness.get("observability_degraded"), False)

    def test_loop_run_marks_observability_degraded_when_stream_paths_missing(self) -> None:
        with tempfile.TemporaryDirectory(prefix="loop-run-") as tmpdir:
            root = ensure_project_root(Path(tmpdir))
            ticket = "DEMO-STREAM-DEGRADED"
            write_active_state(root, ticket=ticket, stage="implement", work_item="iteration_id=I1")
            step_log_rel = f"aidd/reports/loops/{ticket}/cli.implement.synthetic.log"
            write_file(root, f"reports/loops/{ticket}/cli.implement.synthetic.log", "synthetic-main-log\n")

            fake_result = subprocess.CompletedProcess(
                args=["loop-step"],
                returncode=20,
                stdout=json.dumps(
                    {
                        "status": "blocked",
                        "stage": "implement",
                        "scope_key": "iteration_id_I1",
                        "work_item_key": "iteration_id=I1",
                        "reason_code": "stage_result_missing_or_invalid",
                        "reason": "stage result missing",
                        "log_path": step_log_rel,
                        "runner_effective": "claude --dangerously-skip-permissions -p /feature-dev-aidd:implement DEMO-STREAM-DEGRADED",
                    }
                ),
                stderr="",
            )
            captured = io.StringIO()
            cwd = os.getcwd()
            try:
                os.chdir(root.parent)
                with patch.dict(os.environ, {"CLAUDE_PLUGIN_ROOT": str(REPO_ROOT)}, clear=False):
                    with patch("aidd_runtime.loop_run.run_loop_step", return_value=fake_result):
                        with redirect_stdout(captured):
                            code = loop_run_module.main(
                                [
                                    "--ticket",
                                    ticket,
                                    "--work-item-key",
                                    "iteration_id=I1",
                                    "--max-iterations",
                                    "1",
                                    "--stream",
                                    "text",
                                    "--format",
                                    "json",
                                ]
                            )
            finally:
                os.chdir(cwd)

            self.assertEqual(code, 20)
            payload = json.loads(captured.getvalue())
            stream_liveness = payload.get("stream_liveness") or {}
            self.assertEqual(stream_liveness.get("active_source"), "main_log")
            self.assertEqual(stream_liveness.get("observability_degraded"), True)
            self.assertEqual(stream_liveness.get("degraded_reason"), "stream_paths_missing")
            loop_log = (root / "reports" / "loops" / ticket / "loop.run.log").read_text(encoding="utf-8")
            self.assertIn("observability_degraded=1", loop_log)

    def test_loop_run_max_iterations(self) -> None:
        with tempfile.TemporaryDirectory(prefix="loop-run-") as tmpdir:
            root = ensure_project_root(Path(tmpdir))
            write_active_state(root, work_item="iteration_id=I1")
            stage_result = {
                "schema": "aidd.stage_result.v1",
                "ticket": "DEMO-3",
                "stage": "implement",
                "scope_key": "iteration_id_I1",
                "result": "continue",
                "updated_at": "2024-01-02T00:00:00Z",
            }
            write_file(
                root,
                "reports/loops/DEMO-3/iteration_id_I1/stage.implement.result.json",
                json.dumps(stage_result),
            )
            runner = FIXTURES / "runner.sh"
            log_path = root / "runner.log"
            env = cli_env({"AIDD_LOOP_RUNNER_LOG": str(log_path), "AIDD_SKIP_STAGE_WRAPPERS": "1"})
            result = subprocess.run(
                cli_cmd(
                    "loop-run",
                    "--ticket",
                    "DEMO-3",
                    "--max-iterations",
                    "1",
                    "--runner",
                    f"bash {runner}",
                    "--format",
                    "json",
                ),
                text=True,
                capture_output=True,
                cwd=root,
                env=env,
            )
            self.assertEqual(result.returncode, 11, msg=result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload.get("status"), "max-iterations")

    def test_loop_run_stream_creates_jsonl(self) -> None:
        with tempfile.TemporaryDirectory(prefix="loop-run-") as tmpdir:
            root = ensure_project_root(Path(tmpdir))
            write_active_state(root, ticket="DEMO-STREAM", work_item="iteration_id=I1")
            stage_result = {
                "schema": "aidd.stage_result.v1",
                "ticket": "DEMO-STREAM",
                "stage": "implement",
                "scope_key": "iteration_id_I1",
                "result": "continue",
                "updated_at": "2024-01-02T00:00:00Z",
            }
            write_file(
                root,
                "reports/loops/DEMO-STREAM/iteration_id_I1/stage.implement.result.json",
                json.dumps(stage_result),
            )
            runner = FIXTURES / "runner.sh"
            log_path = root / "runner.log"
            env = cli_env({"AIDD_LOOP_RUNNER_LOG": str(log_path), "AIDD_SKIP_STAGE_WRAPPERS": "1"})
            result = subprocess.run(
                cli_cmd(
                    "loop-run",
                    "--ticket",
                    "DEMO-STREAM",
                    "--max-iterations",
                    "1",
                    "--runner",
                    f"bash {runner}",
                    "--stream",
                    "text",
                    "--format",
                    "json",
                ),
                text=True,
                capture_output=True,
                cwd=root,
                env=env,
            )
            self.assertEqual(result.returncode, 11, msg=result.stderr)
            payload = json.loads(result.stdout)
            stream_jsonl = payload.get("stream_jsonl_path")
            self.assertTrue(stream_jsonl, "stream_jsonl_path should be in payload")
            workspace_root = root.parent
            self.assertTrue((workspace_root / str(stream_jsonl)).exists(), "stream jsonl file should exist")

    def test_loop_run_logs_scope_mismatch_warning(self) -> None:
        with tempfile.TemporaryDirectory(prefix="loop-run-") as tmpdir:
            root = ensure_project_root(Path(tmpdir))
            write_active_state(root, ticket="DEMO-MISMATCH", stage="review", work_item="iteration_id=I2")
            write_file(
                root,
                "reports/loops/DEMO-MISMATCH/iteration_id_I4/stage.implement.result.json",
                json.dumps(
                    {
                        "schema": "aidd.stage_result.v1",
                        "ticket": "DEMO-MISMATCH",
                        "stage": "implement",
                        "scope_key": "iteration_id_I4",
                        "result": "continue",
                        "updated_at": "2024-01-02T00:00:00Z",
                    }
                ),
            )
            write_file(
                root,
                "reports/loops/DEMO-MISMATCH/iteration_id_I4/stage.review.result.json",
                json.dumps(
                    {
                        "schema": "aidd.stage_result.v1",
                        "ticket": "DEMO-MISMATCH",
                        "stage": "review",
                        "scope_key": "iteration_id_I4",
                        "result": "continue",
                        "updated_at": "2024-01-02T00:00:01Z",
                    }
                ),
            )
            write_file(
                root,
                "reports/loops/DEMO-MISMATCH/iteration_id_I4/review.latest.pack.md",
                "---\nschema: aidd.review_pack.v2\nupdated_at: 2024-01-02T00:00:01Z\n---\n",
            )
            runner = FIXTURES / "runner.sh"
            runner_log = root / "runner.log"
            env = cli_env({"AIDD_LOOP_RUNNER_LOG": str(runner_log), "AIDD_SKIP_STAGE_WRAPPERS": "1"})
            result = subprocess.run(
                cli_cmd(
                    "loop-run",
                    "--ticket",
                    "DEMO-MISMATCH",
                    "--max-iterations",
                    "1",
                    "--runner",
                    f"bash {runner}",
                    "--format",
                    "json",
                ),
                text=True,
                capture_output=True,
                cwd=root,
                env=env,
            )
            self.assertEqual(result.returncode, 11, msg=result.stderr)
            loop_log = (root / "reports" / "loops" / "DEMO-MISMATCH" / "loop.run.log").read_text(encoding="utf-8")
            self.assertIn("scope_key_mismatch_warn=1", loop_log)

    def test_loop_run_recovers_non_loop_stage_with_iteration_work_item(self) -> None:
        with tempfile.TemporaryDirectory(prefix="loop-run-") as tmpdir:
            root = ensure_project_root(Path(tmpdir))
            ticket = "DEMO-TASKLIST-RECOVER"
            write_active_state(root, ticket=ticket, stage="tasklist", work_item="iteration_id=I3")
            write_file(
                root,
                f"reports/loops/{ticket}/iteration_id_I3/stage.implement.result.json",
                json.dumps(
                    {
                        "schema": "aidd.stage_result.v1",
                        "ticket": ticket,
                        "stage": "implement",
                        "scope_key": "iteration_id_I3",
                        "result": "continue",
                        "updated_at": "2024-01-02T00:00:00Z",
                    }
                ),
            )
            runner = FIXTURES / "runner.sh"
            runner_log = root / "runner.log"
            env = cli_env({"AIDD_LOOP_RUNNER_LOG": str(runner_log), "AIDD_SKIP_STAGE_WRAPPERS": "1"})
            result = subprocess.run(
                cli_cmd(
                    "loop-run",
                    "--ticket",
                    ticket,
                    "--max-iterations",
                    "1",
                    "--runner",
                    f"bash {runner}",
                    "--format",
                    "json",
                ),
                text=True,
                capture_output=True,
                cwd=root,
                env=env,
            )
            self.assertEqual(result.returncode, 11, msg=result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload.get("status"), "max-iterations")
            last_step = payload.get("last_step") or {}
            self.assertEqual(last_step.get("stage"), "implement")
            self.assertEqual(last_step.get("repair_reason_code"), "non_loop_stage_recovered")
            loop_log = (root / "reports" / "loops" / ticket / "loop.run.log").read_text(encoding="utf-8")
            self.assertIn("reason_code=non_loop_stage_recovered", loop_log)

    def test_loop_run_from_qa_skips_work_item_autoselect_and_repairs(self) -> None:
        with tempfile.TemporaryDirectory(prefix="loop-run-") as tmpdir:
            root = ensure_project_root(Path(tmpdir))
            ticket = "DEMO-QA-REPAIR"
            write_active_state(root, ticket=ticket, stage="qa", work_item="iteration_id=I2")
            write_file(
                root,
                f"reports/loops/{ticket}/iteration_id_I2/stage.qa.result.json",
                json.dumps(
                    {
                        "schema": "aidd.stage_result.v1",
                        "ticket": ticket,
                        "stage": "qa",
                        "scope_key": "iteration_id_I2",
                        "work_item_key": "iteration_id=I2",
                        "result": "blocked",
                        "updated_at": "2024-01-02T00:00:00Z",
                    }
                ),
            )
            write_file(
                root,
                f"reports/loops/{ticket}/iteration_id_I2/stage.implement.result.json",
                json.dumps(
                    {
                        "schema": "aidd.stage_result.v1",
                        "ticket": ticket,
                        "stage": "implement",
                        "scope_key": "iteration_id_I2",
                        "result": "continue",
                        "updated_at": "2024-01-02T00:00:01Z",
                    }
                ),
            )
            tasklist = """<!-- handoff:qa start -->
- [ ] Fix A (id: qa:A1) (Priority: high) (Blocking: true) (scope: iteration_id=I2)
<!-- handoff:qa end -->
"""
            write_file(root, f"docs/tasklist/{ticket}.md", tasklist)

            runner = FIXTURES / "runner.sh"
            runner_log = root / "runner.log"
            env = cli_env({"AIDD_LOOP_RUNNER_LOG": str(runner_log), "AIDD_SKIP_STAGE_WRAPPERS": "1"})
            result = subprocess.run(
                cli_cmd(
                    "loop-run",
                    "--ticket",
                    ticket,
                    "--max-iterations",
                    "1",
                    "--runner",
                    f"bash {runner}",
                    "--from-qa",
                    "auto",
                    "--format",
                    "json",
                ),
                text=True,
                capture_output=True,
                cwd=root,
                env=env,
            )
            self.assertEqual(result.returncode, 11, msg=result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload.get("status"), "max-iterations")
            last_step = payload.get("last_step") or {}
            self.assertEqual(last_step.get("stage"), "implement")
            self.assertEqual(last_step.get("repair_reason_code"), "qa_repair")
            self.assertNotEqual(last_step.get("reason_code"), "qa_repair_invalid_stage")
            loop_log = (root / "reports" / "loops" / ticket / "loop.run.log").read_text(encoding="utf-8")
            self.assertNotIn("event=auto-select-work-item", loop_log)

    def test_loop_run_stops_on_user_approval_required(self) -> None:
        with tempfile.TemporaryDirectory(prefix="loop-run-") as tmpdir:
            root = ensure_project_root(Path(tmpdir))
            write_active_state(root, ticket="DEMO-APPROVAL", stage="implement", work_item="iteration_id=M4")
            write_file(
                root,
                "reports/loops/DEMO-APPROVAL/iteration_id_M4/stage.implement.result.json",
                json.dumps(
                    {
                        "schema": "aidd.stage_result.v1",
                        "ticket": "DEMO-APPROVAL",
                        "stage": "implement",
                        "scope_key": "iteration_id_M4",
                        "work_item_key": "iteration_id=M4",
                        "result": "continue",
                        "reason_code": "user_approval_required",
                        "reason": "manual approval is required",
                        "updated_at": "2024-01-02T00:00:00Z",
                    }
                ),
            )
            runner = FIXTURES / "runner.sh"
            runner_log = root / "runner.log"
            env = cli_env({"AIDD_LOOP_RUNNER_LOG": str(runner_log), "AIDD_SKIP_STAGE_WRAPPERS": "1"})
            result = subprocess.run(
                cli_cmd(
                    "loop-run",
                    "--ticket",
                    "DEMO-APPROVAL",
                    "--max-iterations",
                    "2",
                    "--runner",
                    f"bash {runner}",
                    "--format",
                    "json",
                ),
                text=True,
                capture_output=True,
                cwd=root,
                env=env,
            )
            self.assertEqual(result.returncode, 20, msg=result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload.get("status"), "blocked")
            self.assertEqual(payload.get("reason_code"), "user_approval_required")
            self.assertEqual(payload.get("scope_key"), "iteration_id_M4")
            loop_log = (root / "reports" / "loops" / "DEMO-APPROVAL" / "loop.run.log").read_text(encoding="utf-8")
            self.assertIn("stage=implement", loop_log)
            self.assertIn("reason_code=user_approval_required", loop_log)


if __name__ == "__main__":
    unittest.main()
