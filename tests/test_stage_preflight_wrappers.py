import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from tests.helpers import REPO_ROOT, cli_env, ensure_project_root, write_active_state, write_file, write_tasklist_ready


class StagePreflightWrapperTests(unittest.TestCase):
    def _run_preflight(self, stage: str) -> None:
        with tempfile.TemporaryDirectory(prefix=f"preflight-{stage}-") as tmpdir:
            root = ensure_project_root(Path(tmpdir))
            ticket = f"DEMO-{stage.upper()}"
            scope_key = "iteration_id_I1"
            work_item_key = "iteration_id=I1"

            write_active_state(root, ticket=ticket, stage=stage, work_item=work_item_key)
            write_tasklist_ready(root, ticket)
            write_file(root, f"docs/prd/{ticket}.prd.md", "Status: READY\n")

            runtime_entrypoint = REPO_ROOT / "skills" / "aidd-loop" / "runtime" / "preflight_prepare.py"
            actions_template = f"aidd/reports/actions/{ticket}/{scope_key}/{stage}.actions.template.json"
            readmap_json = f"aidd/reports/context/{ticket}/{scope_key}.readmap.json"
            readmap_md = f"aidd/reports/context/{ticket}/{scope_key}.readmap.md"
            writemap_json = f"aidd/reports/context/{ticket}/{scope_key}.writemap.json"
            writemap_md = f"aidd/reports/context/{ticket}/{scope_key}.writemap.md"
            result_path = f"aidd/reports/loops/{ticket}/{scope_key}/stage.preflight.result.json"
            result = subprocess.run(
                [
                    "python3",
                    str(runtime_entrypoint),
                    "--ticket",
                    ticket,
                    "--scope-key",
                    scope_key,
                    "--work-item-key",
                    work_item_key,
                    "--stage",
                    stage,
                    "--actions-template",
                    actions_template,
                    "--readmap-json",
                    readmap_json,
                    "--readmap-md",
                    readmap_md,
                    "--writemap-json",
                    writemap_json,
                    "--writemap-md",
                    writemap_md,
                    "--result",
                    result_path,
                ],
                cwd=root,
                env=cli_env(),
                text=True,
                capture_output=True,
            )
            self.assertEqual(result.returncode, 0, msg=result.stderr)
            stdout = result.stdout
            self.assertIn("readmap_path=", stdout)
            self.assertIn("writemap_path=", stdout)
            self.assertIn("preflight_result=", stdout)

            base = root / "reports" / "actions" / ticket / scope_key
            self.assertTrue((base / f"{stage}.actions.template.json").exists())
            self.assertTrue((root / "reports" / "context" / ticket / f"{scope_key}.readmap.json").exists())
            self.assertTrue((root / "reports" / "context" / ticket / f"{scope_key}.writemap.json").exists())
            self.assertTrue((root / "reports" / "loops" / ticket / scope_key / "stage.preflight.result.json").exists())

            canonical_result = root / "reports" / "loops" / ticket / scope_key / "stage.preflight.result.json"
            payload = json.loads(canonical_result.read_text(encoding="utf-8"))
            self.assertEqual(payload.get("schema"), "aidd.stage_result.preflight.v1")
            self.assertEqual(payload.get("status"), "ok")
            self.assertEqual(payload.get("stage"), stage)

    def test_implement_preflight(self) -> None:
        self._run_preflight("implement")

    def test_review_preflight(self) -> None:
        self._run_preflight("review")

    def test_qa_preflight(self) -> None:
        self._run_preflight("qa")


if __name__ == "__main__":
    unittest.main()
