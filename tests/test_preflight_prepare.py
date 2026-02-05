import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from tests.helpers import cli_cmd, cli_env, ensure_project_root, write_active_state, write_tasklist_ready


class PreflightPrepareTests(unittest.TestCase):
    def test_preflight_prepare_generates_maps_and_template(self) -> None:
        with tempfile.TemporaryDirectory(prefix="preflight-prepare-") as tmpdir:
            root = ensure_project_root(Path(tmpdir))
            ticket = "DEMO-PF"
            scope_key = "iteration_id_I1"
            work_item_key = "iteration_id=I1"
            write_active_state(root, ticket=ticket, stage="implement", work_item=work_item_key)
            write_tasklist_ready(root, ticket)
            tasklist_path = root / "docs" / "tasklist" / f"{ticket}.md"
            tasklist_text = tasklist_path.read_text(encoding="utf-8")
            tasklist_text = tasklist_text.replace(
                f"- Boundaries: docs/tasklist/{ticket}.md",
                "- Boundaries: src/feature/**",
                1,
            )
            tasklist_path.write_text(tasklist_text, encoding="utf-8")

            base = f"reports/actions/{ticket}/{scope_key}"
            result = subprocess.run(
                cli_cmd(
                    "preflight-prepare",
                    "--ticket",
                    ticket,
                    "--scope-key",
                    scope_key,
                    "--work-item-key",
                    work_item_key,
                    "--stage",
                    "implement",
                    "--actions-template",
                    f"{base}/implement.actions.template.json",
                    "--readmap-json",
                    f"{base}/readmap.json",
                    "--readmap-md",
                    f"{base}/readmap.md",
                    "--writemap-json",
                    f"{base}/writemap.json",
                    "--writemap-md",
                    f"{base}/writemap.md",
                    "--result",
                    f"{base}/stage.preflight.result.json",
                ),
                cwd=root,
                env=cli_env(),
                text=True,
                capture_output=True,
            )

            self.assertEqual(result.returncode, 0, msg=result.stderr)

            readmap = root / base / "readmap.json"
            writemap = root / base / "writemap.json"
            actions_template = root / base / "implement.actions.template.json"
            preflight_result = root / base / "stage.preflight.result.json"

            self.assertTrue(readmap.exists(), "readmap.json must be generated")
            self.assertTrue(writemap.exists(), "writemap.json must be generated")
            self.assertTrue(actions_template.exists(), "actions template must be generated")
            self.assertTrue(preflight_result.exists(), "preflight result must be generated")

            readmap_payload = json.loads(readmap.read_text(encoding="utf-8"))
            writemap_payload = json.loads(writemap.read_text(encoding="utf-8"))
            actions_payload = json.loads(actions_template.read_text(encoding="utf-8"))
            result_payload = json.loads(preflight_result.read_text(encoding="utf-8"))

            self.assertEqual(readmap_payload.get("schema"), "aidd.readmap.v1")
            self.assertEqual(writemap_payload.get("schema"), "aidd.writemap.v1")
            self.assertEqual(actions_payload.get("schema_version"), "aidd.actions.v1")
            self.assertEqual(result_payload.get("schema"), "aidd.stage_result.preflight.v1")
            self.assertEqual(result_payload.get("status"), "ok")
            self.assertIn("src/feature/**", writemap_payload.get("allowed_paths", []))

    def test_preflight_prepare_blocks_without_work_item_key(self) -> None:
        with tempfile.TemporaryDirectory(prefix="preflight-prepare-") as tmpdir:
            root = ensure_project_root(Path(tmpdir))
            ticket = "DEMO-PF-BLOCK"
            scope_key = "iteration_id_I1"
            write_active_state(root, ticket=ticket, stage="implement", work_item="")
            write_tasklist_ready(root, ticket)

            base = f"reports/actions/{ticket}/{scope_key}"
            result = subprocess.run(
                cli_cmd(
                    "preflight-prepare",
                    "--ticket",
                    ticket,
                    "--scope-key",
                    scope_key,
                    "--work-item-key",
                    "",
                    "--stage",
                    "implement",
                    "--actions-template",
                    f"{base}/implement.actions.template.json",
                    "--readmap-json",
                    f"{base}/readmap.json",
                    "--readmap-md",
                    f"{base}/readmap.md",
                    "--writemap-json",
                    f"{base}/writemap.json",
                    "--writemap-md",
                    f"{base}/writemap.md",
                    "--result",
                    f"{base}/stage.preflight.result.json",
                ),
                cwd=root,
                env=cli_env(),
                text=True,
                capture_output=True,
            )

            self.assertNotEqual(result.returncode, 0)
            preflight_result = root / base / "stage.preflight.result.json"
            self.assertTrue(preflight_result.exists(), "blocked preflight must still write preflight result")
            payload = json.loads(preflight_result.read_text(encoding="utf-8"))
            self.assertEqual(payload.get("status"), "blocked")
            self.assertEqual(payload.get("reason_code"), "work_item_key_missing")

    def test_preflight_prepare_blocks_with_invalid_contract(self) -> None:
        with tempfile.TemporaryDirectory(prefix="preflight-prepare-") as tmpdir:
            root = ensure_project_root(Path(tmpdir))
            ticket = "DEMO-PF-BAD-CONTRACT"
            scope_key = "iteration_id_I1"
            work_item_key = "iteration_id=I1"
            write_active_state(root, ticket=ticket, stage="implement", work_item=work_item_key)
            write_tasklist_ready(root, ticket)

            bad_contract = root / "reports" / "context" / "bad-contract.yaml"
            bad_contract.parent.mkdir(parents=True, exist_ok=True)
            bad_contract.write_text("{ this-is: not-valid-json: [\n", encoding="utf-8")

            base = f"reports/actions/{ticket}/{scope_key}"
            result = subprocess.run(
                cli_cmd(
                    "preflight-prepare",
                    "--ticket",
                    ticket,
                    "--scope-key",
                    scope_key,
                    "--work-item-key",
                    work_item_key,
                    "--stage",
                    "implement",
                    "--contract",
                    str(bad_contract),
                    "--actions-template",
                    f"{base}/implement.actions.template.json",
                    "--readmap-json",
                    f"{base}/readmap.json",
                    "--readmap-md",
                    f"{base}/readmap.md",
                    "--writemap-json",
                    f"{base}/writemap.json",
                    "--writemap-md",
                    f"{base}/writemap.md",
                    "--result",
                    f"{base}/stage.preflight.result.json",
                ),
                cwd=root,
                env=cli_env(),
                text=True,
                capture_output=True,
            )

            self.assertNotEqual(result.returncode, 0)
            preflight_result = root / base / "stage.preflight.result.json"
            self.assertTrue(preflight_result.exists())
            payload = json.loads(preflight_result.read_text(encoding="utf-8"))
            self.assertEqual(payload.get("status"), "blocked")
            self.assertEqual(payload.get("reason_code"), "contract_invalid")


if __name__ == "__main__":
    unittest.main()
