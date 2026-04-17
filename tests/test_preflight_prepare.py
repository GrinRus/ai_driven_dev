import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from aidd_runtime import preflight_prepare
from tests.helpers import cli_cmd, cli_env, ensure_project_root, write_active_state, write_tasklist_ready


class PreflightPrepareTests(unittest.TestCase):
    def test_preflight_prepare_sanitize_paths_drops_pseudopath_tokens(self) -> None:
        kept, dropped = preflight_prepare._sanitize_paths(
            [
                "aidd/reports/qa/TST-001.json",
                "domain/adapter/MCP",
                "<placeholder>",
                "src/**",
            ]
        )
        self.assertIn("aidd/reports/qa/TST-001.json", kept)
        self.assertIn("src/**", kept)
        self.assertIn("domain/adapter/MCP", dropped)
        self.assertIn("<placeholder>", dropped)

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

            actions_base = f"reports/actions/{ticket}/{scope_key}"
            context_base = f"reports/context/{ticket}"
            loops_base = f"reports/loops/{ticket}/{scope_key}"
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
                    f"{actions_base}/implement.actions.template.json",
                    "--readmap-json",
                    f"{context_base}/{scope_key}.readmap.json",
                    "--readmap-md",
                    f"{context_base}/{scope_key}.readmap.md",
                    "--writemap-json",
                    f"{context_base}/{scope_key}.writemap.json",
                    "--writemap-md",
                    f"{context_base}/{scope_key}.writemap.md",
                    "--result",
                    f"{loops_base}/stage.preflight.result.json",
                ),
                cwd=root,
                env=cli_env(),
                text=True,
                capture_output=True,
            )

            self.assertEqual(result.returncode, 0, msg=result.stderr)

            readmap = root / context_base / f"{scope_key}.readmap.json"
            writemap = root / context_base / f"{scope_key}.writemap.json"
            actions_template = root / actions_base / "implement.actions.template.json"
            preflight_result = root / loops_base / "stage.preflight.result.json"

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
            self.assertEqual(result_payload.get("schema"), "aidd.stage_result.v1")
            self.assertEqual(result_payload.get("stage"), "preflight")
            self.assertEqual(result_payload.get("result"), "done")
            self.assertEqual(result_payload.get("status"), "ok")
            details = result_payload.get("details") or {}
            self.assertEqual(details.get("target_stage"), "implement")
            self.assertTrue((details.get("artifacts") or {}).get("actions_template"))
            self.assertIn("src/feature/**", writemap_payload.get("allowed_paths", []))

    def test_preflight_prepare_blocks_without_work_item_key(self) -> None:
        with tempfile.TemporaryDirectory(prefix="preflight-prepare-") as tmpdir:
            root = ensure_project_root(Path(tmpdir))
            ticket = "DEMO-PF-BLOCK"
            scope_key = "iteration_id_I1"
            write_active_state(root, ticket=ticket, stage="implement", work_item="")
            write_tasklist_ready(root, ticket)

            actions_base = f"reports/actions/{ticket}/{scope_key}"
            context_base = f"reports/context/{ticket}"
            loops_base = f"reports/loops/{ticket}/{scope_key}"
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
                    f"{actions_base}/implement.actions.template.json",
                    "--readmap-json",
                    f"{context_base}/{scope_key}.readmap.json",
                    "--readmap-md",
                    f"{context_base}/{scope_key}.readmap.md",
                    "--writemap-json",
                    f"{context_base}/{scope_key}.writemap.json",
                    "--writemap-md",
                    f"{context_base}/{scope_key}.writemap.md",
                    "--result",
                    f"{loops_base}/stage.preflight.result.json",
                ),
                cwd=root,
                env=cli_env(),
                text=True,
                capture_output=True,
            )

            self.assertNotEqual(result.returncode, 0)
            preflight_result = root / loops_base / "stage.preflight.result.json"
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

            actions_base = f"reports/actions/{ticket}/{scope_key}"
            context_base = f"reports/context/{ticket}"
            loops_base = f"reports/loops/{ticket}/{scope_key}"
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
                    f"{actions_base}/implement.actions.template.json",
                    "--readmap-json",
                    f"{context_base}/{scope_key}.readmap.json",
                    "--readmap-md",
                    f"{context_base}/{scope_key}.readmap.md",
                    "--writemap-json",
                    f"{context_base}/{scope_key}.writemap.json",
                    "--writemap-md",
                    f"{context_base}/{scope_key}.writemap.md",
                    "--result",
                    f"{loops_base}/stage.preflight.result.json",
                ),
                cwd=root,
                env=cli_env(),
                text=True,
                capture_output=True,
            )

            self.assertNotEqual(result.returncode, 0)
            preflight_result = root / loops_base / "stage.preflight.result.json"
            self.assertTrue(preflight_result.exists())
            payload = json.loads(preflight_result.read_text(encoding="utf-8"))
            self.assertEqual(payload.get("status"), "blocked")
            self.assertEqual(payload.get("reason_code"), "contract_invalid")

    def test_preflight_prepare_blocks_non_canonical_artifact_paths(self) -> None:
        with tempfile.TemporaryDirectory(prefix="preflight-prepare-") as tmpdir:
            root = ensure_project_root(Path(tmpdir))
            ticket = "DEMO-PF-PATHS"
            scope_key = "iteration_id_I1"
            work_item_key = "iteration_id=I1"
            write_active_state(root, ticket=ticket, stage="implement", work_item=work_item_key)
            write_tasklist_ready(root, ticket)
            prd_file = root / "docs" / "prd" / f"{ticket}.prd.md"
            prd_file.parent.mkdir(parents=True, exist_ok=True)
            prd_file.write_text("Status: READY\n", encoding="utf-8")

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
                    f"reports/actions/{ticket}/I1/implement.actions.json",
                    "--readmap-json",
                    "reports/readmap.json",
                    "--readmap-md",
                    "reports/readmap.md",
                    "--writemap-json",
                    "reports/writemap.json",
                    "--writemap-md",
                    "reports/writemap.md",
                    "--result",
                    "reports/stage.preflight.result.json",
                ),
                cwd=root,
                env=cli_env(),
                text=True,
                capture_output=True,
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("artifact_path_mismatch", result.stdout + result.stderr)
            canonical_result = root / "reports" / "loops" / ticket / scope_key / "stage.preflight.result.json"
            self.assertTrue(canonical_result.exists(), "blocked preflight must write canonical result artifact")
            payload = json.loads(canonical_result.read_text(encoding="utf-8"))
            self.assertEqual(payload.get("status"), "blocked")
            self.assertEqual(payload.get("reason_code"), "artifact_path_mismatch")

    def test_preflight_prepare_blocks_invalid_work_item_key_format(self) -> None:
        with tempfile.TemporaryDirectory(prefix="preflight-prepare-") as tmpdir:
            root = ensure_project_root(Path(tmpdir))
            ticket = "DEMO-PF-WI-FORMAT"
            scope_key = "iteration_id_I1"
            work_item_key = "DEMO-PF-WI-FORMAT"
            write_active_state(root, ticket=ticket, stage="implement", work_item=work_item_key)
            write_tasklist_ready(root, ticket)
            prd_file = root / "docs" / "prd" / f"{ticket}.prd.md"
            prd_file.parent.mkdir(parents=True, exist_ok=True)
            prd_file.write_text("Status: READY\n", encoding="utf-8")

            actions_base = f"reports/actions/{ticket}/{scope_key}"
            context_base = f"reports/context/{ticket}"
            loops_base = f"reports/loops/{ticket}/{scope_key}"
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
                    f"{actions_base}/implement.actions.template.json",
                    "--readmap-json",
                    f"{context_base}/{scope_key}.readmap.json",
                    "--readmap-md",
                    f"{context_base}/{scope_key}.readmap.md",
                    "--writemap-json",
                    f"{context_base}/{scope_key}.writemap.json",
                    "--writemap-md",
                    f"{context_base}/{scope_key}.writemap.md",
                    "--result",
                    f"{loops_base}/stage.preflight.result.json",
                ),
                cwd=root,
                env=cli_env(),
                text=True,
                capture_output=True,
            )

            self.assertNotEqual(result.returncode, 0)
            canonical_result = root / loops_base / "stage.preflight.result.json"
            self.assertTrue(canonical_result.exists(), "blocked preflight must write canonical result artifact")
            payload = json.loads(canonical_result.read_text(encoding="utf-8"))
            self.assertEqual(payload.get("status"), "blocked")
            self.assertEqual(payload.get("reason_code"), "loop_pack_failed")
            self.assertIn("iteration_id=... or id=...", str(payload.get("reason") or ""))

    def test_preflight_prepare_blocks_non_canonical_iteration_scope_key(self) -> None:
        with tempfile.TemporaryDirectory(prefix="preflight-prepare-") as tmpdir:
            root = ensure_project_root(Path(tmpdir))
            ticket = "DEMO-PF-SCOPE-CANON"
            requested_scope = "I1"
            canonical_scope = "iteration_id_I1"
            work_item_key = "iteration_id=I1"
            write_active_state(root, ticket=ticket, stage="implement", work_item=work_item_key)
            write_tasklist_ready(root, ticket)
            prd_file = root / "docs" / "prd" / f"{ticket}.prd.md"
            prd_file.parent.mkdir(parents=True, exist_ok=True)
            prd_file.write_text("Status: READY\n", encoding="utf-8")

            actions_base = f"reports/actions/{ticket}/{requested_scope}"
            context_base = f"reports/context/{ticket}"
            loops_base = f"reports/loops/{ticket}/{requested_scope}"
            result = subprocess.run(
                cli_cmd(
                    "preflight-prepare",
                    "--ticket",
                    ticket,
                    "--scope-key",
                    requested_scope,
                    "--work-item-key",
                    work_item_key,
                    "--stage",
                    "implement",
                    "--actions-template",
                    f"{actions_base}/implement.actions.template.json",
                    "--readmap-json",
                    f"{context_base}/{requested_scope}.readmap.json",
                    "--readmap-md",
                    f"{context_base}/{requested_scope}.readmap.md",
                    "--writemap-json",
                    f"{context_base}/{requested_scope}.writemap.json",
                    "--writemap-md",
                    f"{context_base}/{requested_scope}.writemap.md",
                    "--result",
                    f"{loops_base}/stage.preflight.result.json",
                ),
                cwd=root,
                env=cli_env(),
                text=True,
                capture_output=True,
            )

            self.assertNotEqual(result.returncode, 0)
            canonical_result = root / "reports" / "loops" / ticket / canonical_scope / "stage.preflight.result.json"
            self.assertTrue(canonical_result.exists(), "blocked preflight must write canonical result artifact")
            payload = json.loads(canonical_result.read_text(encoding="utf-8"))
            self.assertEqual(payload.get("status"), "blocked")
            self.assertEqual(payload.get("reason_code"), "scope_key_not_canonical")
            self.assertIn("expected", str(payload.get("reason") or ""))
            self.assertIn(canonical_scope, str(payload.get("reason") or ""))

    def test_preflight_prepare_blocks_cross_iteration_with_stage_run_lock(self) -> None:
        with tempfile.TemporaryDirectory(prefix="preflight-prepare-") as tmpdir:
            root = ensure_project_root(Path(tmpdir))
            ticket = "DEMO-PF-SCOPE-LOCK"
            write_tasklist_ready(root, ticket)
            tasklist_path = root / "docs" / "tasklist" / f"{ticket}.md"
            tasklist_text = tasklist_path.read_text(encoding="utf-8")
            tasklist_text = tasklist_text.replace(
                f"- Boundaries: docs/tasklist/{ticket}.md",
                "- Boundaries: src/feature/**",
                1,
            )
            tasklist_path.write_text(tasklist_text, encoding="utf-8")

            common_args = [
                "--ticket",
                ticket,
                "--stage",
                "implement",
            ]
            run_lock_env = cli_env({"AIDD_STAGE_RUN_LOCK_ID": "06_implement_run1"})

            scope_i1 = "iteration_id_I1"
            work_item_i1 = "iteration_id=I1"
            write_active_state(root, ticket=ticket, stage="implement", work_item=work_item_i1)
            run1 = subprocess.run(
                cli_cmd(
                    "preflight-prepare",
                    *common_args,
                    "--scope-key",
                    scope_i1,
                    "--work-item-key",
                    work_item_i1,
                    "--actions-template",
                    f"reports/actions/{ticket}/{scope_i1}/implement.actions.template.json",
                    "--readmap-json",
                    f"reports/context/{ticket}/{scope_i1}.readmap.json",
                    "--readmap-md",
                    f"reports/context/{ticket}/{scope_i1}.readmap.md",
                    "--writemap-json",
                    f"reports/context/{ticket}/{scope_i1}.writemap.json",
                    "--writemap-md",
                    f"reports/context/{ticket}/{scope_i1}.writemap.md",
                    "--result",
                    f"reports/loops/{ticket}/{scope_i1}/stage.preflight.result.json",
                ),
                cwd=root,
                env=run_lock_env,
                text=True,
                capture_output=True,
            )
            self.assertEqual(run1.returncode, 0, msg=run1.stderr)

            scope_i2 = "iteration_id_I2"
            work_item_i2 = "iteration_id=I2"
            write_active_state(root, ticket=ticket, stage="implement", work_item=work_item_i2)
            run2 = subprocess.run(
                cli_cmd(
                    "preflight-prepare",
                    *common_args,
                    "--scope-key",
                    scope_i2,
                    "--work-item-key",
                    work_item_i2,
                    "--actions-template",
                    f"reports/actions/{ticket}/{scope_i2}/implement.actions.template.json",
                    "--readmap-json",
                    f"reports/context/{ticket}/{scope_i2}.readmap.json",
                    "--readmap-md",
                    f"reports/context/{ticket}/{scope_i2}.readmap.md",
                    "--writemap-json",
                    f"reports/context/{ticket}/{scope_i2}.writemap.json",
                    "--writemap-md",
                    f"reports/context/{ticket}/{scope_i2}.writemap.md",
                    "--result",
                    f"reports/loops/{ticket}/{scope_i2}/stage.preflight.result.json",
                ),
                cwd=root,
                env=run_lock_env,
                text=True,
                capture_output=True,
            )

            self.assertNotEqual(run2.returncode, 0)
            preflight_result = root / "reports" / "loops" / ticket / scope_i2 / "stage.preflight.result.json"
            self.assertTrue(preflight_result.exists(), "blocked preflight must write canonical result artifact")
            payload = json.loads(preflight_result.read_text(encoding="utf-8"))
            self.assertEqual(payload.get("status"), "blocked")
            self.assertEqual(payload.get("reason_code"), "seed_scope_cascade_detected")
            self.assertIn("expected scope=iteration_id_I1", str(payload.get("reason") or ""))
            self.assertIn("got scope=iteration_id_I2", str(payload.get("reason") or ""))

    def test_preflight_prepare_blocks_when_id_work_item_is_missing_in_tasklist(self) -> None:
        with tempfile.TemporaryDirectory(prefix="preflight-prepare-") as tmpdir:
            root = ensure_project_root(Path(tmpdir))
            ticket = "DEMO-PF-WI-NOTFOUND"
            scope_key = "rbac-live-enforcement"
            work_item_key = "id=TST-001"
            write_active_state(root, ticket=ticket, stage="qa", work_item=work_item_key)
            write_tasklist_ready(root, ticket)
            prd_file = root / "docs" / "prd" / f"{ticket}.prd.md"
            prd_file.parent.mkdir(parents=True, exist_ok=True)
            prd_file.write_text("Status: READY\n", encoding="utf-8")

            actions_base = f"reports/actions/{ticket}/{scope_key}"
            context_base = f"reports/context/{ticket}"
            loops_base = f"reports/loops/{ticket}/{scope_key}"
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
                    "qa",
                    "--actions-template",
                    f"{actions_base}/qa.actions.template.json",
                    "--readmap-json",
                    f"{context_base}/{scope_key}.readmap.json",
                    "--readmap-md",
                    f"{context_base}/{scope_key}.readmap.md",
                    "--writemap-json",
                    f"{context_base}/{scope_key}.writemap.json",
                    "--writemap-md",
                    f"{context_base}/{scope_key}.writemap.md",
                    "--result",
                    f"{loops_base}/stage.preflight.result.json",
                ),
                cwd=root,
                env=cli_env(),
                text=True,
                capture_output=True,
            )

            self.assertNotEqual(result.returncode, 0)
            canonical_result = root / loops_base / "stage.preflight.result.json"
            self.assertTrue(canonical_result.exists(), "blocked preflight must write canonical result artifact")
            payload = json.loads(canonical_result.read_text(encoding="utf-8"))
            self.assertEqual(payload.get("status"), "blocked")
            self.assertEqual(payload.get("reason_code"), "loop_pack_failed")
            self.assertIn("work item id=TST-001 not found in tasklist", str(payload.get("reason") or ""))


if __name__ == "__main__":
    unittest.main()
