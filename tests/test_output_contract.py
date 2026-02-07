import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from tests.helpers import cli_cmd, cli_env, ensure_project_root, write_active_state, write_file


class OutputContractTests(unittest.TestCase):
    def test_output_contract_warns_on_status_mismatch_and_read_order(self) -> None:
        with tempfile.TemporaryDirectory(prefix="output-contract-") as tmpdir:
            root = ensure_project_root(Path(tmpdir))
            write_active_state(root, ticket="DEMO-OUT", stage="implement", work_item="iteration_id=I1")
            stage_result = {
                "schema": "aidd.stage_result.v1",
                "ticket": "DEMO-OUT",
                "stage": "implement",
                "scope_key": "iteration_id_I1",
                "work_item_key": "iteration_id=I1",
                "result": "continue",
                "updated_at": "2024-01-02T00:00:00Z",
            }
            write_file(
                root,
                "reports/loops/DEMO-OUT/iteration_id_I1/stage.implement.result.json",
                json.dumps(stage_result),
            )
            log_path = root / "reports" / "loops" / "DEMO-OUT" / "cli.implement.test.log"
            log_path.parent.mkdir(parents=True, exist_ok=True)
            log_path.write_text(
                "\n".join(
                    [
                        "Status: READY",
                        "Work item key: iteration_id=I1",
                        "Artifacts updated: src/demo.py",
                        "Tests: skipped reason_code=manual_skip",
                        "Blockers/Handoff: none",
                        "Next actions: none",
                        "AIDD:READ_LOG: aidd/reports/context/DEMO-OUT.pack.md (reason: rolling context); "
                        "aidd/reports/loops/DEMO-OUT/iteration_id_I1.loop.pack.md (reason: loop pack)",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            result = subprocess.run(
                cli_cmd(
                    "output-contract",
                    "--ticket",
                    "DEMO-OUT",
                    "--stage",
                    "implement",
                    "--log",
                    str(log_path),
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
            self.assertEqual(payload.get("status"), "warn")
            warnings = payload.get("warnings") or []
            self.assertIn("status_mismatch_stage_result", warnings)
            self.assertIn("read_order_context_before_loop", warnings)


if __name__ == "__main__":
    unittest.main()
