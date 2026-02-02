import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from tests.helpers import cli_cmd, cli_env, ensure_gates_config, ensure_project_root, write_file


class StageResultTests(unittest.TestCase):
    def test_review_missing_tests_soft_continues(self) -> None:
        with tempfile.TemporaryDirectory(prefix="stage-result-") as tmpdir:
            root = ensure_project_root(Path(tmpdir))
            ensure_gates_config(root, {"tests_required": "soft"})

            result = subprocess.run(
                cli_cmd(
                    "stage-result",
                    "--ticket",
                    "DEMO-1",
                    "--stage",
                    "review",
                    "--result",
                    "done",
                    "--work-item-key",
                    "iteration_id=I1",
                ),
                text=True,
                capture_output=True,
                cwd=root,
                env=cli_env(),
            )
            self.assertEqual(result.returncode, 0, msg=result.stdout + result.stderr)
            payload = json.loads(
                (root / "reports" / "loops" / "DEMO-1" / "iteration_id_I1" / "stage.review.result.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(payload.get("requested_result"), "done")
            self.assertEqual(payload.get("result"), "continue")
            self.assertEqual(payload.get("reason_code"), "missing_test_evidence")

    def test_review_missing_tests_hard_blocks(self) -> None:
        with tempfile.TemporaryDirectory(prefix="stage-result-") as tmpdir:
            root = ensure_project_root(Path(tmpdir))
            ensure_gates_config(root, {"tests_required": "hard"})

            result = subprocess.run(
                cli_cmd(
                    "stage-result",
                    "--ticket",
                    "DEMO-2",
                    "--stage",
                    "review",
                    "--result",
                    "done",
                    "--work-item-key",
                    "iteration_id=I2",
                ),
                text=True,
                capture_output=True,
                cwd=root,
                env=cli_env(),
            )
            self.assertEqual(result.returncode, 0, msg=result.stdout + result.stderr)
            payload = json.loads(
                (root / "reports" / "loops" / "DEMO-2" / "iteration_id_I2" / "stage.review.result.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(payload.get("requested_result"), "done")
            self.assertEqual(payload.get("result"), "blocked")
            self.assertEqual(payload.get("reason_code"), "missing_test_evidence")

    def test_review_skipped_tests_capture_reason(self) -> None:
        with tempfile.TemporaryDirectory(prefix="stage-result-") as tmpdir:
            root = ensure_project_root(Path(tmpdir))
            ensure_gates_config(root, {"tests_required": "soft"})
            write_file(
                root,
                "reports/tests/DEMO-3/iteration_id_I3.jsonl",
                json.dumps(
                    {
                        "schema": "aidd.tests_log.v1",
                        "updated_at": "2024-01-02T00:00:00Z",
                        "ticket": "DEMO-3",
                        "stage": "review",
                        "scope_key": "iteration_id_I3",
                        "status": "skipped",
                        "reason_code": "manual_skip",
                        "reason": "tests skipped",
                    }
                )
                + "\n",
            )

            result = subprocess.run(
                cli_cmd(
                    "stage-result",
                    "--ticket",
                    "DEMO-3",
                    "--stage",
                    "review",
                    "--result",
                    "done",
                    "--work-item-key",
                    "iteration_id=I3",
                ),
                text=True,
                capture_output=True,
                cwd=root,
                env=cli_env(),
            )
            self.assertEqual(result.returncode, 0, msg=result.stdout + result.stderr)
            payload = json.loads(
                (root / "reports" / "loops" / "DEMO-3" / "iteration_id_I3" / "stage.review.result.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(payload.get("result"), "continue")
            self.assertEqual(payload.get("reason_code"), "manual_skip")

    def test_review_uses_latest_pass_when_review_skipped(self) -> None:
        with tempfile.TemporaryDirectory(prefix="stage-result-") as tmpdir:
            root = ensure_project_root(Path(tmpdir))
            ensure_gates_config(root, {"tests_required": "hard"})
            write_file(
                root,
                "reports/tests/DEMO-4/iteration_id_I4.jsonl",
                "\n".join(
                    [
                        json.dumps(
                            {
                                "schema": "aidd.tests_log.v1",
                                "updated_at": "2024-01-02T00:00:00Z",
                                "ticket": "DEMO-4",
                                "stage": "implement",
                                "scope_key": "iteration_id_I4",
                                "status": "pass",
                            }
                        ),
                        json.dumps(
                            {
                                "schema": "aidd.tests_log.v1",
                                "updated_at": "2024-01-03T00:00:00Z",
                                "ticket": "DEMO-4",
                                "stage": "review",
                                "scope_key": "iteration_id_I4",
                                "status": "skipped",
                            }
                        ),
                    ]
                )
                + "\n",
            )

            result = subprocess.run(
                cli_cmd(
                    "stage-result",
                    "--ticket",
                    "DEMO-4",
                    "--stage",
                    "review",
                    "--result",
                    "done",
                    "--work-item-key",
                    "iteration_id=I4",
                ),
                text=True,
                capture_output=True,
                cwd=root,
                env=cli_env(),
            )
            self.assertEqual(result.returncode, 0, msg=result.stdout + result.stderr)
            payload = json.loads(
                (root / "reports" / "loops" / "DEMO-4" / "iteration_id_I4" / "stage.review.result.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(payload.get("result"), "done")
            self.assertEqual(payload.get("reason_code"), "")

    def test_review_skipped_tests_block_on_hard(self) -> None:
        with tempfile.TemporaryDirectory(prefix="stage-result-") as tmpdir:
            root = ensure_project_root(Path(tmpdir))
            ensure_gates_config(root, {"tests_required": "hard"})
            write_file(
                root,
                "reports/tests/DEMO-9/iteration_id_I9.jsonl",
                json.dumps(
                    {
                        "schema": "aidd.tests_log.v1",
                        "updated_at": "2024-01-02T00:00:00Z",
                        "ticket": "DEMO-9",
                        "stage": "review",
                        "scope_key": "iteration_id_I9",
                        "status": "skipped",
                        "reason_code": "manual_skip",
                        "reason": "tests skipped",
                    }
                )
                + "\n",
            )

            result = subprocess.run(
                cli_cmd(
                    "stage-result",
                    "--ticket",
                    "DEMO-9",
                    "--stage",
                    "review",
                    "--result",
                    "done",
                    "--work-item-key",
                    "iteration_id=I9",
                ),
                text=True,
                capture_output=True,
                cwd=root,
                env=cli_env(),
            )
            self.assertEqual(result.returncode, 0, msg=result.stdout + result.stderr)
            payload = json.loads(
                (root / "reports" / "loops" / "DEMO-9" / "iteration_id_I9" / "stage.review.result.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(payload.get("result"), "blocked")
            self.assertEqual(payload.get("reason_code"), "manual_skip")

    def test_review_stage_result_links_fix_plan(self) -> None:
        with tempfile.TemporaryDirectory(prefix="stage-result-") as tmpdir:
            root = ensure_project_root(Path(tmpdir))
            write_file(
                root,
                "reports/loops/DEMO-10/iteration_id_I10/review.fix_plan.json",
                json.dumps(
                    {
                        "schema": "aidd.review_fix_plan.v1",
                        "updated_at": "2024-01-02T00:00:00Z",
                        "ticket": "DEMO-10",
                        "work_item_key": "iteration_id=I10",
                        "scope_key": "iteration_id_I10",
                        "fix_plan": {},
                    }
                )
                + "\n",
            )

            result = subprocess.run(
                cli_cmd(
                    "stage-result",
                    "--ticket",
                    "DEMO-10",
                    "--stage",
                    "review",
                    "--result",
                    "continue",
                    "--work-item-key",
                    "iteration_id=I10",
                ),
                text=True,
                capture_output=True,
                cwd=root,
                env=cli_env(),
            )
            self.assertEqual(result.returncode, 0, msg=result.stdout + result.stderr)
            payload = json.loads(
                (root / "reports" / "loops" / "DEMO-10" / "iteration_id_I10" / "stage.review.result.json").read_text(
                    encoding="utf-8"
                )
            )
            evidence_links = payload.get("evidence_links") or {}
            self.assertEqual(
                evidence_links.get("fix_plan_json"),
                "aidd/reports/loops/DEMO-10/iteration_id_I10/review.fix_plan.json",
            )


if __name__ == "__main__":
    unittest.main()
