import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from tests.helpers import REPO_ROOT, cli_env, ensure_project_root, write_active_state, write_file, write_tasklist_ready


class StagePreflightWrapperTests(unittest.TestCase):
    def _run_wrapper(self, stage: str, *, write_legacy: bool = False) -> None:
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
                env=cli_env({"AIDD_WRITE_LEGACY_PREFLIGHT": "1"} if write_legacy else None),
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
            if write_legacy:
                self.assertTrue((base / "readmap.json").exists())
                self.assertTrue((base / "writemap.json").exists())
                self.assertTrue((base / "stage.preflight.result.json").exists())
            else:
                self.assertFalse((base / "readmap.json").exists())
                self.assertFalse((base / "writemap.json").exists())
                self.assertFalse((base / "stage.preflight.result.json").exists())

            canonical_result = root / "reports" / "loops" / ticket / scope_key / "stage.preflight.result.json"
            payload = json.loads(canonical_result.read_text(encoding="utf-8"))
            self.assertEqual(payload.get("schema"), "aidd.stage_result.preflight.v1")
            self.assertEqual(payload.get("status"), "ok")
            self.assertEqual(payload.get("stage"), stage)
            artifacts = payload.get("artifacts", {})
            self.assertEqual(
                artifacts.get("readmap_json"),
                f"aidd/reports/context/{ticket}/{scope_key}.readmap.json",
            )
            self.assertEqual(
                artifacts.get("writemap_json"),
                f"aidd/reports/context/{ticket}/{scope_key}.writemap.json",
            )
            self.assertEqual(
                artifacts.get("readmap_md"),
                f"aidd/reports/context/{ticket}/{scope_key}.readmap.md",
            )
            self.assertEqual(
                artifacts.get("writemap_md"),
                f"aidd/reports/context/{ticket}/{scope_key}.writemap.md",
            )
            self.assertNotIn(
                f"aidd/reports/actions/{ticket}/{scope_key}/readmap.json",
                artifacts.values(),
            )

    def test_implement_preflight_wrapper(self) -> None:
        self._run_wrapper("implement")

    def test_review_preflight_wrapper(self) -> None:
        self._run_wrapper("review")

    def test_qa_preflight_wrapper(self) -> None:
        self._run_wrapper("qa")

    def test_preflight_wrapper_can_emit_legacy_artifacts_when_enabled(self) -> None:
        self._run_wrapper("review", write_legacy=True)


if __name__ == "__main__":
    unittest.main()
