import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from tests.helpers import cli_cmd, cli_env, ensure_project_root, write_file


FIXTURES = Path(__file__).resolve().parent / "fixtures" / "loop_step"


class LoopStepTests(unittest.TestCase):
    def run_loop_step(self, root: Path, ticket: str, log_path: Path, extra_env: dict | None = None, *args: str):
        runner = FIXTURES / "runner.sh"
        env = cli_env({"AIDD_LOOP_RUNNER_LOG": str(log_path)})
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
            write_file(root, "docs/.active_work_item", "iteration_id=I1")
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
            self.assertIn("/feature-dev-aidd:implement DEMO-1", log_path.read_text(encoding="utf-8"))
            self.assertEqual((root / "docs" / ".active_mode").read_text(encoding="utf-8").strip(), "loop")

    def test_loop_step_runs_review_when_stage_implement(self) -> None:
        with tempfile.TemporaryDirectory(prefix="loop-step-") as tmpdir:
            root = ensure_project_root(Path(tmpdir))
            write_file(root, "docs/.active_stage", "implement")
            write_file(root, "docs/.active_work_item", "iteration_id=I1")
            stage_result = {
                "schema": "aidd.stage_result.v1",
                "ticket": "DEMO-2",
                "stage": "implement",
                "scope_key": "iteration_id_I1",
                "result": "continue",
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
            result = self.run_loop_step(root, "DEMO-2", log_path)
            self.assertEqual(result.returncode, 10, msg=result.stderr)
            self.assertIn("/feature-dev-aidd:review DEMO-2", log_path.read_text(encoding="utf-8"))

    def test_loop_step_ship_returns_done(self) -> None:
        with tempfile.TemporaryDirectory(prefix="loop-step-") as tmpdir:
            root = ensure_project_root(Path(tmpdir))
            write_file(root, "docs/.active_stage", "review")
            write_file(root, "docs/.active_work_item", "iteration_id=I1")
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

    def test_loop_step_blocked_without_review_pack(self) -> None:
        with tempfile.TemporaryDirectory(prefix="loop-step-") as tmpdir:
            root = ensure_project_root(Path(tmpdir))
            write_file(root, "docs/.active_stage", "review")
            write_file(root, "docs/.active_work_item", "iteration_id=I1")
            log_path = root / "runner.log"
            result = self.run_loop_step(root, "DEMO-4", log_path)
            self.assertEqual(result.returncode, 20, msg=result.stderr)

    def test_loop_step_revise_runs_implement(self) -> None:
        with tempfile.TemporaryDirectory(prefix="loop-step-") as tmpdir:
            root = ensure_project_root(Path(tmpdir))
            write_file(root, "docs/.active_stage", "review")
            write_file(root, "docs/.active_work_item", "iteration_id=I1")
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
            review_pack = "---\nschema: aidd.review_pack.v2\nupdated_at: 2024-01-02T00:00:00Z\n---\n"
            write_file(root, "reports/loops/DEMO-6/iteration_id_I1/review.latest.pack.md", review_pack)
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
            result = self.run_loop_step(root, "DEMO-6", log_path)
            self.assertEqual(result.returncode, 10, msg=result.stderr)
            self.assertIn("/feature-dev-aidd:implement DEMO-6", log_path.read_text(encoding="utf-8"))

    def test_loop_step_blocks_on_stale_review_pack(self) -> None:
        with tempfile.TemporaryDirectory(prefix="loop-step-") as tmpdir:
            root = ensure_project_root(Path(tmpdir))
            write_file(root, "docs/.active_stage", "review")
            write_file(root, "docs/.active_work_item", "iteration_id=I1")
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


if __name__ == "__main__":
    unittest.main()
