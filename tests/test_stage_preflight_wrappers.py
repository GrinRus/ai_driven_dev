import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from tests.helpers import REPO_ROOT, cli_env, ensure_project_root, write_active_state, write_file, write_tasklist_ready


class StagePreflightWrapperTests(unittest.TestCase):
    def _run_wrapper(self, stage: str) -> None:
        with tempfile.TemporaryDirectory(prefix=f"preflight-{stage}-") as tmpdir:
            root = ensure_project_root(Path(tmpdir))
            ticket = f"DEMO-{stage.upper()}"
            scope_key = "iteration_id_I1"
            work_item_key = "iteration_id=I1"

            write_active_state(root, ticket=ticket, stage=stage, work_item=work_item_key)
            write_tasklist_ready(root, ticket)
            write_file(root, f"docs/prd/{ticket}.prd.md", "Status: READY\n")

            script = REPO_ROOT / "skills" / stage / "scripts" / "preflight.sh"
            result = subprocess.run(
                [
                    str(script),
                    "--ticket",
                    ticket,
                    "--scope-key",
                    scope_key,
                    "--work-item-key",
                    work_item_key,
                    "--stage",
                    stage,
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
            self.assertTrue((base / "readmap.json").exists())
            self.assertTrue((base / "writemap.json").exists())
            self.assertTrue((base / "stage.preflight.result.json").exists())
            self.assertTrue((base / f"{stage}.actions.template.json").exists())
            self.assertTrue((root / "reports" / "context" / ticket / f"{scope_key}.readmap.json").exists())
            self.assertTrue((root / "reports" / "context" / ticket / f"{scope_key}.writemap.json").exists())
            self.assertTrue((root / "reports" / "loops" / ticket / scope_key / "stage.preflight.result.json").exists())

            payload = json.loads((base / "stage.preflight.result.json").read_text(encoding="utf-8"))
            self.assertEqual(payload.get("schema"), "aidd.stage_result.preflight.v1")
            self.assertEqual(payload.get("status"), "ok")
            self.assertEqual(payload.get("stage"), stage)

    def test_implement_preflight_wrapper(self) -> None:
        self._run_wrapper("implement")

    def test_review_preflight_wrapper(self) -> None:
        self._run_wrapper("review")

    def test_qa_preflight_wrapper(self) -> None:
        self._run_wrapper("qa")


if __name__ == "__main__":
    unittest.main()
