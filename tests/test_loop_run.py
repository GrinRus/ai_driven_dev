import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from tests.helpers import cli_cmd, cli_env, ensure_project_root, write_active_state, write_file


FIXTURES = Path(__file__).resolve().parent / "fixtures" / "loop_step"


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
