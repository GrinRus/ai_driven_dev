import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from tests.helpers import cli_cmd, cli_env, ensure_project_root, write_active_state, write_file


class StatusSummaryTests(unittest.TestCase):
    def test_status_summary_accepts_legacy_stage_result_schema(self) -> None:
        with tempfile.TemporaryDirectory(prefix="status-summary-") as tmpdir:
            root = ensure_project_root(Path(tmpdir))
            write_active_state(root, ticket="DEMO-STATUS-LEGACY", stage="review", work_item="iteration_id=I1")
            write_file(
                root,
                "reports/loops/DEMO-STATUS-LEGACY/iteration_id_I1/stage.review.result.json",
                json.dumps(
                    {
                        "schema": "aidd.stage_result.review.v1",
                        "ticket": "DEMO-STATUS-LEGACY",
                        "stage": "review",
                        "scope_key": "iteration_id_I1",
                        "status": "ok",
                        "updated_at": "2024-01-02T00:00:00Z",
                    }
                ),
            )

            result = subprocess.run(
                cli_cmd(
                    "status-summary",
                    "--ticket",
                    "DEMO-STATUS-LEGACY",
                    "--stage",
                    "review",
                    "--work-item-key",
                    "iteration_id=I1",
                    "--format",
                    "json",
                ),
                text=True,
                capture_output=True,
                cwd=root,
                env=cli_env(),
            )
            self.assertEqual(result.returncode, 0, msg=result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload.get("status"), "WARN")
            self.assertEqual(payload.get("result"), "continue")
            self.assertEqual(
                payload.get("stage_result_path"),
                "aidd/reports/loops/DEMO-STATUS-LEGACY/iteration_id_I1/stage.review.result.json",
            )

    def test_status_summary_blocks_canonical_stage_result_without_result(self) -> None:
        with tempfile.TemporaryDirectory(prefix="status-summary-") as tmpdir:
            root = ensure_project_root(Path(tmpdir))
            write_active_state(root, ticket="DEMO-STATUS-CANON", stage="review", work_item="iteration_id=I1")
            write_file(
                root,
                "reports/loops/DEMO-STATUS-CANON/iteration_id_I1/stage.review.result.json",
                json.dumps(
                    {
                        "schema": "aidd.stage_result.v1",
                        "ticket": "DEMO-STATUS-CANON",
                        "stage": "review",
                        "scope_key": "iteration_id_I1",
                        "status": "ok",
                        "updated_at": "2024-01-02T00:00:00Z",
                    }
                ),
            )

            result = subprocess.run(
                cli_cmd(
                    "status-summary",
                    "--ticket",
                    "DEMO-STATUS-CANON",
                    "--stage",
                    "review",
                    "--work-item-key",
                    "iteration_id=I1",
                    "--format",
                    "json",
                ),
                text=True,
                capture_output=True,
                cwd=root,
                env=cli_env(),
            )
            self.assertEqual(result.returncode, 1, msg=result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload.get("status"), "BLOCKED")
            self.assertEqual(payload.get("reason_code"), "stage_result_missing")


if __name__ == "__main__":
    unittest.main()
