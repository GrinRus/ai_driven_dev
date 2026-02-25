import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from tests.helpers import cli_cmd, cli_env, ensure_gates_config, ensure_project_root, write_active_state, write_file


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
                        "aidd/reports/loops/DEMO-OUT/iteration_id_I1.loop.pack.md (reason: loop pack); "
                        "aidd/reports/memory/DEMO-OUT.semantic.pack.json (reason: memory-semantic-pack)",
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
            self.assertIn("read_order_context_before_memory", warnings)

    def test_output_contract_optional_ast_fallback_warns(self) -> None:
        with tempfile.TemporaryDirectory(prefix="output-contract-ast-soft-") as tmpdir:
            root = ensure_project_root(Path(tmpdir))
            ensure_gates_config(root, {"ast_index": {"mode": "auto", "required": False}})
            write_active_state(root, ticket="DEMO-AST", stage="implement", work_item="iteration_id=I1")
            stage_result = {
                "schema": "aidd.stage_result.v1",
                "ticket": "DEMO-AST",
                "stage": "implement",
                "scope_key": "iteration_id_I1",
                "work_item_key": "iteration_id=I1",
                "result": "continue",
                "updated_at": "2024-01-02T00:00:00Z",
            }
            write_file(
                root,
                "reports/loops/DEMO-AST/iteration_id_I1/stage.implement.result.json",
                json.dumps(stage_result),
            )
            actions_log = root / "reports" / "actions" / "DEMO-AST" / "iteration_id_I1" / "implement.actions.json"
            actions_log.parent.mkdir(parents=True, exist_ok=True)
            actions_log.write_text("[]\n", encoding="utf-8")
            log_path = root / "reports" / "loops" / "DEMO-AST" / "cli.implement.ast-soft.log"
            log_path.parent.mkdir(parents=True, exist_ok=True)
            log_path.write_text(
                "\n".join(
                    [
                        "Status: WARN",
                        "Work item key: iteration_id=I1",
                        "Artifacts updated: src/demo.py",
                        "Tests: skipped reason_code=manual_skip",
                        "Blockers/Handoff: none",
                        "Next actions: none",
                        f"AIDD:ACTIONS_LOG: {actions_log.relative_to(root).as_posix()}",
                        "AIDD:READ_LOG: aidd/reports/loops/DEMO-AST/iteration_id_I1.loop.pack.md (reason: loop pack); "
                        "aidd/reports/research/DEMO-AST-ast.pack.json (reason: reason_code=ast_index_binary_missing)",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            result = subprocess.run(
                cli_cmd(
                    "output-contract",
                    "--ticket",
                    "DEMO-AST",
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
            self.assertEqual(payload.get("reason_code"), "output_contract_warn")
            warnings = payload.get("warnings") or []
            self.assertIn("ast_index_fallback_warn", warnings)

    def test_output_contract_required_ast_fallback_blocks(self) -> None:
        with tempfile.TemporaryDirectory(prefix="output-contract-ast-hard-") as tmpdir:
            root = ensure_project_root(Path(tmpdir))
            ensure_gates_config(root, {"ast_index": {"mode": "required", "required": True}})
            write_active_state(root, ticket="DEMO-AST-REQ", stage="implement", work_item="iteration_id=I1")
            stage_result = {
                "schema": "aidd.stage_result.v1",
                "ticket": "DEMO-AST-REQ",
                "stage": "implement",
                "scope_key": "iteration_id_I1",
                "work_item_key": "iteration_id=I1",
                "result": "continue",
                "updated_at": "2024-01-02T00:00:00Z",
            }
            write_file(
                root,
                "reports/loops/DEMO-AST-REQ/iteration_id_I1/stage.implement.result.json",
                json.dumps(stage_result),
            )
            actions_log = root / "reports" / "actions" / "DEMO-AST-REQ" / "iteration_id_I1" / "implement.actions.json"
            actions_log.parent.mkdir(parents=True, exist_ok=True)
            actions_log.write_text("[]\n", encoding="utf-8")
            log_path = root / "reports" / "loops" / "DEMO-AST-REQ" / "cli.implement.ast-hard.log"
            log_path.parent.mkdir(parents=True, exist_ok=True)
            log_path.write_text(
                "\n".join(
                    [
                        "Status: WARN",
                        "Work item key: iteration_id=I1",
                        "Artifacts updated: src/demo.py",
                        "Tests: skipped reason_code=manual_skip",
                        "Blockers/Handoff: none",
                        "Next actions: none",
                        f"AIDD:ACTIONS_LOG: {actions_log.relative_to(root).as_posix()}",
                        "AIDD:READ_LOG: aidd/reports/loops/DEMO-AST-REQ/iteration_id_I1.loop.pack.md (reason: loop pack); "
                        "aidd/reports/research/DEMO-AST-REQ-ast.pack.json (reason: reason_code=ast_index_binary_missing)",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            result = subprocess.run(
                cli_cmd(
                    "output-contract",
                    "--ticket",
                    "DEMO-AST-REQ",
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
            self.assertEqual(payload.get("status"), "blocked")
            self.assertEqual(payload.get("reason_code"), "ast_index_binary_missing")
            self.assertIn("ast_index_required_fallback", payload.get("warnings") or [])
            self.assertTrue(payload.get("next_action"))

    def test_output_contract_warns_when_memory_slice_manifest_missing(self) -> None:
        with tempfile.TemporaryDirectory(prefix="output-contract-memory-warn-") as tmpdir:
            root = ensure_project_root(Path(tmpdir))
            ensure_gates_config(
                root,
                {
                    "memory": {
                        "slice_enforcement": "warn",
                        "enforce_stages": ["implement"],
                        "max_slice_age_minutes": 240,
                    }
                },
            )
            write_active_state(root, ticket="DEMO-MEM-WARN", stage="implement", work_item="iteration_id=I1")
            stage_result = {
                "schema": "aidd.stage_result.v1",
                "ticket": "DEMO-MEM-WARN",
                "stage": "implement",
                "scope_key": "iteration_id_I1",
                "work_item_key": "iteration_id=I1",
                "result": "continue",
                "updated_at": "2024-01-02T00:00:00Z",
            }
            write_file(
                root,
                "reports/loops/DEMO-MEM-WARN/iteration_id_I1/stage.implement.result.json",
                json.dumps(stage_result),
            )
            actions_log = root / "reports" / "actions" / "DEMO-MEM-WARN" / "iteration_id_I1" / "implement.actions.json"
            actions_log.parent.mkdir(parents=True, exist_ok=True)
            actions_log.write_text("[]\n", encoding="utf-8")
            log_path = root / "reports" / "loops" / "DEMO-MEM-WARN" / "cli.implement.mem-warn.log"
            log_path.parent.mkdir(parents=True, exist_ok=True)
            log_path.write_text(
                "\n".join(
                    [
                        "Status: WARN",
                        "Work item key: iteration_id=I1",
                        "Artifacts updated: src/demo.py",
                        "Tests: skipped reason_code=manual_skip",
                        "Blockers/Handoff: none",
                        "Next actions: none",
                        f"AIDD:ACTIONS_LOG: {actions_log.relative_to(root).as_posix()}",
                        "AIDD:READ_LOG: aidd/reports/loops/DEMO-MEM-WARN/iteration_id_I1.loop.pack.md (reason: loop pack); "
                        "aidd/docs/prd/DEMO-MEM-WARN.prd.md (reason: missing field)",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            result = subprocess.run(
                cli_cmd(
                    "output-contract",
                    "--ticket",
                    "DEMO-MEM-WARN",
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
            self.assertEqual(payload.get("reason_code"), "output_contract_warn")
            warnings = payload.get("warnings") or []
            self.assertIn("memory_slice_missing", warnings)
            self.assertIn("memory_slice_manifest_missing", warnings)

    def test_output_contract_blocks_when_memory_slice_manifest_missing_in_hard_mode(self) -> None:
        with tempfile.TemporaryDirectory(prefix="output-contract-memory-hard-") as tmpdir:
            root = ensure_project_root(Path(tmpdir))
            ensure_gates_config(
                root,
                {
                    "memory": {
                        "slice_enforcement": "hard",
                        "enforce_stages": ["implement"],
                        "max_slice_age_minutes": 240,
                    }
                },
            )
            write_active_state(root, ticket="DEMO-MEM-HARD", stage="implement", work_item="iteration_id=I1")
            stage_result = {
                "schema": "aidd.stage_result.v1",
                "ticket": "DEMO-MEM-HARD",
                "stage": "implement",
                "scope_key": "iteration_id_I1",
                "work_item_key": "iteration_id=I1",
                "result": "continue",
                "updated_at": "2024-01-02T00:00:00Z",
            }
            write_file(
                root,
                "reports/loops/DEMO-MEM-HARD/iteration_id_I1/stage.implement.result.json",
                json.dumps(stage_result),
            )
            actions_log = root / "reports" / "actions" / "DEMO-MEM-HARD" / "iteration_id_I1" / "implement.actions.json"
            actions_log.parent.mkdir(parents=True, exist_ok=True)
            actions_log.write_text("[]\n", encoding="utf-8")
            log_path = root / "reports" / "loops" / "DEMO-MEM-HARD" / "cli.implement.mem-hard.log"
            log_path.parent.mkdir(parents=True, exist_ok=True)
            log_path.write_text(
                "\n".join(
                    [
                        "Status: WARN",
                        "Work item key: iteration_id=I1",
                        "Artifacts updated: src/demo.py",
                        "Tests: skipped reason_code=manual_skip",
                        "Blockers/Handoff: none",
                        "Next actions: none",
                        f"AIDD:ACTIONS_LOG: {actions_log.relative_to(root).as_posix()}",
                        "AIDD:READ_LOG: aidd/reports/loops/DEMO-MEM-HARD/iteration_id_I1.loop.pack.md (reason: loop pack); "
                        "aidd/docs/prd/DEMO-MEM-HARD.prd.md (reason: missing field)",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            result = subprocess.run(
                cli_cmd(
                    "output-contract",
                    "--ticket",
                    "DEMO-MEM-HARD",
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
            self.assertEqual(payload.get("status"), "blocked")
            self.assertEqual(payload.get("reason_code"), "memory_slice_manifest_missing")
            self.assertIn("memory_autoslice.py", str(payload.get("next_action") or ""))

    def test_output_contract_blocks_when_memory_slice_manifest_invalid_in_hard_mode(self) -> None:
        with tempfile.TemporaryDirectory(prefix="output-contract-memory-invalid-hard-") as tmpdir:
            root = ensure_project_root(Path(tmpdir))
            ensure_gates_config(
                root,
                {
                    "memory": {
                        "slice_enforcement": "hard",
                        "enforce_stages": ["implement"],
                        "max_slice_age_minutes": 240,
                    }
                },
            )
            ticket = "DEMO-MEM-INVALID"
            scope_key = "iteration_id_I1"
            write_active_state(root, ticket=ticket, stage="implement", work_item="iteration_id=I1")
            stage_result = {
                "schema": "aidd.stage_result.v1",
                "ticket": ticket,
                "stage": "implement",
                "scope_key": scope_key,
                "work_item_key": "iteration_id=I1",
                "result": "continue",
                "updated_at": "2024-01-02T00:00:00Z",
            }
            write_file(
                root,
                f"reports/loops/{ticket}/{scope_key}/stage.implement.result.json",
                json.dumps(stage_result),
            )
            actions_log = root / "reports" / "actions" / ticket / scope_key / "implement.actions.json"
            actions_log.parent.mkdir(parents=True, exist_ok=True)
            actions_log.write_text("[]\n", encoding="utf-8")
            invalid_manifest_path = root / "reports" / "context" / f"{ticket}-memory-slices.implement.{scope_key}.pack.json"
            invalid_manifest_path.parent.mkdir(parents=True, exist_ok=True)
            invalid_manifest_path.write_text("{\"schema\":\"invalid\"}\n", encoding="utf-8")

            log_path = root / "reports" / "loops" / ticket / "cli.implement.mem-invalid-hard.log"
            log_path.parent.mkdir(parents=True, exist_ok=True)
            log_path.write_text(
                "\n".join(
                    [
                        "Status: WARN",
                        "Work item key: iteration_id=I1",
                        "Artifacts updated: src/demo.py",
                        "Tests: skipped reason_code=manual_skip",
                        "Blockers/Handoff: none",
                        "Next actions: none",
                        f"AIDD:ACTIONS_LOG: {actions_log.relative_to(root).as_posix()}",
                        "AIDD:READ_LOG: "
                        f"aidd/reports/loops/{ticket}/{scope_key}.loop.pack.md (reason: loop pack); "
                        f"aidd/reports/context/{ticket}-memory-slices.implement.{scope_key}.pack.json (reason: memory-slice-manifest); "
                        f"aidd/reports/context/{ticket}.pack.md (reason: rolling context)",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            result = subprocess.run(
                cli_cmd(
                    "output-contract",
                    "--ticket",
                    ticket,
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
            self.assertEqual(payload.get("status"), "blocked")
            self.assertEqual(payload.get("reason_code"), "memory_slice_manifest_missing")

    def test_output_contract_qa_allows_slice_first_read_order(self) -> None:
        with tempfile.TemporaryDirectory(prefix="output-contract-qa-slice-first-") as tmpdir:
            root = ensure_project_root(Path(tmpdir))
            ensure_gates_config(
                root,
                {
                    "memory": {
                        "slice_enforcement": "warn",
                        "enforce_stages": ["qa"],
                        "max_slice_age_minutes": 240,
                    }
                },
            )
            write_active_state(root, ticket="DEMO-QA", stage="qa", work_item="iteration_id=I9")
            scope_key = "qa_scope"
            actions_log = root / "reports" / "actions" / "DEMO-QA" / scope_key / "qa.actions.json"
            actions_log.parent.mkdir(parents=True, exist_ok=True)
            actions_log.write_text("[]\n", encoding="utf-8")
            manifest_path = root / "reports" / "context" / f"DEMO-QA-memory-slices.qa.{scope_key}.pack.json"
            manifest_path.parent.mkdir(parents=True, exist_ok=True)
            manifest_path.write_text(
                json.dumps(
                    {
                        "schema": "aidd.memory.slices.manifest.v1",
                        "schema_version": "aidd.memory.slices.manifest.v1",
                        "ticket": "DEMO-QA",
                        "stage": "qa",
                        "scope_key": scope_key,
                        "generated_at": "2099-01-01T00:00:00Z",
                        "updated_at": "2099-01-01T00:00:00Z",
                        "slices": {
                            "cols": ["query", "slice_pack", "latest_alias", "hits"],
                            "rows": [],
                        },
                    }
                ),
                encoding="utf-8",
            )

            log_path = root / "reports" / "loops" / "DEMO-QA" / "cli.qa.slice-first.log"
            log_path.parent.mkdir(parents=True, exist_ok=True)
            log_path.write_text(
                "\n".join(
                    [
                        "Status: READY",
                        "Work item key: iteration_id=I9",
                        "Artifacts updated: aidd/reports/qa/DEMO-QA.json",
                        "Tests: completed",
                        "Blockers/Handoff: none",
                        "Next actions: none",
                        f"AIDD:ACTIONS_LOG: {actions_log.relative_to(root).as_posix()}",
                        "AIDD:READ_LOG: "
                        "aidd/reports/loops/DEMO-QA/qa_scope.loop.pack.md (reason: loop pack); "
                        "aidd/reports/loops/DEMO-QA/qa_scope/review.latest.pack.md (reason: review pack); "
                        "aidd/reports/memory/DEMO-QA.semantic.pack.json (reason: memory-semantic-pack); "
                        f"aidd/reports/context/DEMO-QA-memory-slices.qa.{scope_key}.pack.json (reason: memory-slice-manifest); "
                        "aidd/reports/context/DEMO-QA.pack.md (reason: rolling context)",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            result = subprocess.run(
                cli_cmd(
                    "output-contract",
                    "--ticket",
                    "DEMO-QA",
                    "--stage",
                    "qa",
                    "--scope-key",
                    scope_key,
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
            self.assertEqual(payload.get("status"), "ok")
            warnings = payload.get("warnings") or []
            self.assertNotIn("read_order_context_not_first", warnings)
            self.assertNotIn("read_order_context_before_memory", warnings)


if __name__ == "__main__":
    unittest.main()
