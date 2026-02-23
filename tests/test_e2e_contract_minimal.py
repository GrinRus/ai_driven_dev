import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from tests.helpers import cli_cmd, cli_env, ensure_project_root, write_active_state, write_file, write_tasklist_ready

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "loop_step"


class E2EContractMinimalTests(unittest.TestCase):
    def test_set_active_feature_keeps_slug_token_clean(self) -> None:
        with tempfile.TemporaryDirectory(prefix="e2e-contract-") as tmpdir:
            root = ensure_project_root(Path(tmpdir))
            result = subprocess.run(
                cli_cmd(
                    "set-active-feature",
                    "TST-001",
                    "--slug-note",
                    "tst-001-demo Audit backend workflow determinism",
                    "--skip-prd-scaffold",
                ),
                text=True,
                capture_output=True,
                cwd=root,
                env=cli_env(),
            )
            self.assertEqual(result.returncode, 0, msg=result.stderr)
            payload = json.loads((root / "docs" / ".active.json").read_text(encoding="utf-8"))
            self.assertEqual(payload.get("slug_hint"), "tst-001-demo")

    def test_loop_step_generates_stage_chain_contract_artifacts(self) -> None:
        with tempfile.TemporaryDirectory(prefix="e2e-contract-") as tmpdir:
            root = ensure_project_root(Path(tmpdir))
            ticket = "TST-001"
            scope_key = "iteration_id_I1"
            work_item_key = "iteration_id=I1"
            write_active_state(root, ticket=ticket, work_item=work_item_key)
            write_tasklist_ready(root, ticket)
            write_file(root, f"docs/prd/{ticket}.prd.md", "Status: READY\n")
            write_file(
                root,
                f"reports/loops/{ticket}/{scope_key}/stage.implement.result.json",
                json.dumps(
                    {
                        "schema": "aidd.stage_result.v1",
                        "ticket": ticket,
                        "stage": "implement",
                        "scope_key": scope_key,
                        "work_item_key": work_item_key,
                        "result": "continue",
                        "updated_at": "2024-01-02T00:00:00Z",
                    }
                ),
            )
            runner = FIXTURES / "runner.sh"
            runner_log = root / "runner.log"
            env = cli_env({"AIDD_LOOP_RUNNER_LOG": str(runner_log)})
            result = subprocess.run(
                cli_cmd("loop-step", "--ticket", ticket, "--runner", f"bash {runner}", "--format", "json"),
                text=True,
                capture_output=True,
                cwd=root,
                env=env,
            )
            self.assertEqual(result.returncode, 10, msg=result.stderr)
            payload = json.loads(result.stdout)
            actions_log_path = str(payload.get("actions_log_path") or "")
            self.assertTrue(actions_log_path)
            self.assertTrue((root.parent / actions_log_path).exists())
            self.assertTrue((root / "reports" / "actions" / ticket / scope_key / "implement.actions.template.json").exists())
            self.assertTrue((root / "reports" / "actions" / ticket / scope_key / "implement.actions.json").exists())
            self.assertTrue((root / "reports" / "context" / ticket / f"{scope_key}.readmap.json").exists())
            self.assertTrue((root / "reports" / "context" / ticket / f"{scope_key}.writemap.json").exists())
            self.assertTrue((root / "reports" / "loops" / ticket / scope_key / "stage.preflight.result.json").exists())
            stage_chain_logs = list((root / "reports" / "logs" / "implement" / ticket / scope_key).glob("stage.*.log"))
            self.assertTrue(stage_chain_logs)


if __name__ == "__main__":
    unittest.main()
