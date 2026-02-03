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

    def test_review_skipped_tests_still_missing(self) -> None:
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
            self.assertEqual(payload.get("reason_code"), "missing_test_evidence")

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


if __name__ == "__main__":
    unittest.main()
