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
            log_path = root / "runner.log"
            result = self.run_loop_step(root, "DEMO-2", log_path)
            self.assertEqual(result.returncode, 10, msg=result.stderr)
            self.assertIn("/feature-dev-aidd:review DEMO-2", log_path.read_text(encoding="utf-8"))

    def test_loop_step_ship_returns_done(self) -> None:
        with tempfile.TemporaryDirectory(prefix="loop-step-") as tmpdir:
            root = ensure_project_root(Path(tmpdir))
            write_file(root, "docs/.active_stage", "review")
            review_pack = "---\nschema: aidd.review_pack.v1\nverdict: SHIP\n---\n"
            write_file(root, "reports/loops/DEMO-3/review.latest.pack.md", review_pack)
            log_path = root / "runner.log"
            result = self.run_loop_step(root, "DEMO-3", log_path)
            self.assertEqual(result.returncode, 0, msg=result.stderr)
            if log_path.exists():
                self.assertEqual(log_path.read_text(encoding="utf-8").strip(), "")

    def test_loop_step_blocked_without_review_pack(self) -> None:
        with tempfile.TemporaryDirectory(prefix="loop-step-") as tmpdir:
            root = ensure_project_root(Path(tmpdir))
            write_file(root, "docs/.active_stage", "review")
            log_path = root / "runner.log"
            result = self.run_loop_step(root, "DEMO-4", log_path)
            self.assertEqual(result.returncode, 20, msg=result.stderr)

    def test_loop_step_revise_runs_implement(self) -> None:
        with tempfile.TemporaryDirectory(prefix="loop-step-") as tmpdir:
            root = ensure_project_root(Path(tmpdir))
            write_file(root, "docs/.active_stage", "review")
            review_pack = (
                "---\n"
                "schema: aidd.review_pack.v1\n"
                "updated_at: 2024-01-02T00:00:00Z\n"
                "verdict: REVISE\n"
                "---\n"
            )
            write_file(root, "reports/loops/DEMO-6/review.latest.pack.md", review_pack)
            review_report = {
                "status": "WARN",
                "updated_at": "2024-01-02T00:00:00Z",
                "findings": [{"id": "review:F1", "severity": "minor", "title": "Fix typo"}],
            }
            write_file(root, "reports/reviewer/DEMO-6.json", json.dumps(review_report))
            log_path = root / "runner.log"
            result = self.run_loop_step(root, "DEMO-6", log_path)
            self.assertEqual(result.returncode, 10, msg=result.stderr)
            self.assertIn("/feature-dev-aidd:implement DEMO-6", log_path.read_text(encoding="utf-8"))

    def test_loop_step_blocks_on_stale_review_pack(self) -> None:
        with tempfile.TemporaryDirectory(prefix="loop-step-") as tmpdir:
            root = ensure_project_root(Path(tmpdir))
            write_file(root, "docs/.active_stage", "review")
            review_pack = (
                "---\n"
                "schema: aidd.review_pack.v1\n"
                "updated_at: 2024-01-01T00:00:00Z\n"
                "verdict: SHIP\n"
                "---\n"
            )
            write_file(root, "reports/loops/DEMO-5/review.latest.pack.md", review_pack)
            review_report = {
                "status": "READY",
                "updated_at": "2024-01-02T00:00:00Z",
                "findings": [],
            }
            write_file(root, "reports/reviewer/DEMO-5.json", json.dumps(review_report))
            log_path = root / "runner.log"

            result = self.run_loop_step(root, "DEMO-5", log_path)
            self.assertEqual(result.returncode, 20, msg=result.stderr)
            if log_path.exists():
                self.assertEqual(log_path.read_text(encoding="utf-8").strip(), "")


if __name__ == "__main__":
    unittest.main()
