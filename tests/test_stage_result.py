import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from aidd_runtime import stage_result_contract
from tests.helpers import cli_cmd, cli_env, ensure_gates_config, ensure_project_root, write_active_state, write_file


def write_review_context_pack(root: Path, ticket: str) -> None:
    write_file(root, f"reports/context/{ticket}.pack.md", f"# Context Pack — {ticket}\n")


def write_review_context_pack_with_placeholder(root: Path, ticket: str) -> None:
    write_file(
        root,
        f"reports/context/{ticket}.pack.md",
        f"# Context Pack — {ticket}\n\nGoal: <stage-specific goal>\n",
    )


class StageResultTests(unittest.TestCase):
    def test_effective_stage_result_uses_requested_result_for_soft_block(self) -> None:
        payload = {
            "result": "blocked",
            "requested_result": "done",
            "reason_code": "output_contract_warn",
        }
        self.assertEqual(stage_result_contract.effective_stage_result(payload), "done")

    def test_effective_stage_result_keeps_explicit_blocked(self) -> None:
        payload = {
            "result": "blocked",
            "requested_result": "blocked",
            "reason_code": "user_approval_required",
        }
        self.assertEqual(stage_result_contract.effective_stage_result(payload), "blocked")

    def test_stage_result_writer_keeps_canonical_schema_field(self) -> None:
        with tempfile.TemporaryDirectory(prefix="stage-result-") as tmpdir:
            root = ensure_project_root(Path(tmpdir))
            result = subprocess.run(
                cli_cmd(
                    "stage-result",
                    "--ticket",
                    "DEMO-SCHEMA",
                    "--stage",
                    "implement",
                    "--result",
                    "continue",
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
                (root / "reports" / "loops" / "DEMO-SCHEMA" / "iteration_id_I1" / "stage.implement.result.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(payload.get("schema"), "aidd.stage_result.v1")
            self.assertNotIn("schema_version", payload)

    def test_review_missing_tests_soft_continues(self) -> None:
        with tempfile.TemporaryDirectory(prefix="stage-result-") as tmpdir:
            root = ensure_project_root(Path(tmpdir))
            ensure_gates_config(root, {"tests_required": "soft"})
            write_review_context_pack(root, "DEMO-1")

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
            self.assertEqual(payload.get("reason_code"), "no_tests_soft")

    def test_review_missing_tests_hard_blocks(self) -> None:
        with tempfile.TemporaryDirectory(prefix="stage-result-") as tmpdir:
            root = ensure_project_root(Path(tmpdir))
            ensure_gates_config(root, {"tests_required": "hard"})
            write_review_context_pack(root, "DEMO-2")

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
            self.assertEqual(payload.get("reason_code"), "no_tests_hard")

    def test_review_marker_not_required_disables_no_tests_soft(self) -> None:
        with tempfile.TemporaryDirectory(prefix="stage-result-") as tmpdir:
            root = ensure_project_root(Path(tmpdir))
            ensure_gates_config(
                root,
                {
                    "tests_required": "soft",
                    "reviewer": {
                        "enabled": True,
                        "tests_marker": "aidd/reports/reviewer/{ticket}/{scope_key}.tests.json",
                        "tests_field": "tests",
                        "required_values": ["required"],
                        "optional_values": ["optional", "skipped", "not-required"],
                    },
                },
            )
            write_review_context_pack(root, "DEMO-NR")
            write_file(
                root,
                "reports/reviewer/DEMO-NR/iteration_id_I1.tests.json",
                json.dumps({"tests": "not-required"}, indent=2) + "\n",
            )

            result = subprocess.run(
                cli_cmd(
                    "stage-result",
                    "--ticket",
                    "DEMO-NR",
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
                (root / "reports" / "loops" / "DEMO-NR" / "iteration_id_I1" / "stage.review.result.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(payload.get("result"), "done")
            self.assertNotEqual(payload.get("reason_code"), "no_tests_soft")

    def test_review_blocked_preserved_when_tests_missing_soft(self) -> None:
        with tempfile.TemporaryDirectory(prefix="stage-result-") as tmpdir:
            root = ensure_project_root(Path(tmpdir))
            ensure_gates_config(root, {"tests_required": "soft"})
            write_review_context_pack(root, "DEMO-2B")

            result = subprocess.run(
                cli_cmd(
                    "stage-result",
                    "--ticket",
                    "DEMO-2B",
                    "--stage",
                    "review",
                    "--result",
                    "blocked",
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
                (root / "reports" / "loops" / "DEMO-2B" / "iteration_id_I2" / "stage.review.result.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(payload.get("requested_result"), "blocked")
            self.assertEqual(payload.get("result"), "blocked")
            self.assertEqual(payload.get("verdict"), "BLOCKED")

    def test_review_context_pack_missing_blocks(self) -> None:
        with tempfile.TemporaryDirectory(prefix="stage-result-") as tmpdir:
            root = ensure_project_root(Path(tmpdir))
            ensure_gates_config(root, {"tests_required": "disabled"})

            result = subprocess.run(
                cli_cmd(
                    "stage-result",
                    "--ticket",
                    "DEMO-CTX",
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
                (root / "reports" / "loops" / "DEMO-CTX" / "iteration_id_I1" / "stage.review.result.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(payload.get("result"), "blocked")
            self.assertEqual(payload.get("reason_code"), "review_context_pack_missing")

    def test_review_context_pack_placeholder_warns(self) -> None:
        with tempfile.TemporaryDirectory(prefix="stage-result-") as tmpdir:
            root = ensure_project_root(Path(tmpdir))
            ensure_gates_config(root, {"tests_required": "disabled"})
            write_review_context_pack_with_placeholder(root, "DEMO-PLACE")

            result = subprocess.run(
                cli_cmd(
                    "stage-result",
                    "--ticket",
                    "DEMO-PLACE",
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
                (root / "reports" / "loops" / "DEMO-PLACE" / "iteration_id_I1" / "stage.review.result.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(payload.get("reason_code"), "review_context_pack_placeholder_warn")
            self.assertEqual(payload.get("result"), "continue")

    def test_review_blocking_findings_softens_to_revise(self) -> None:
        with tempfile.TemporaryDirectory(prefix="stage-result-") as tmpdir:
            root = ensure_project_root(Path(tmpdir))
            ensure_gates_config(root, {"tests_required": "disabled"})
            write_review_context_pack(root, "DEMO-BLOCKING-FINDINGS")

            result = subprocess.run(
                cli_cmd(
                    "stage-result",
                    "--ticket",
                    "DEMO-BLOCKING-FINDINGS",
                    "--stage",
                    "review",
                    "--result",
                    "blocked",
                    "--reason-code",
                    "blocking_findings",
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
                (
                    root / "reports" / "loops" / "DEMO-BLOCKING-FINDINGS" / "iteration_id_I1" / "stage.review.result.json"
                ).read_text(encoding="utf-8")
            )
            self.assertEqual(payload.get("reason_code"), "blocking_findings")
            self.assertEqual(payload.get("requested_result"), "blocked")
            self.assertEqual(payload.get("result"), "continue")
            self.assertEqual(payload.get("verdict"), "REVISE")

    def test_review_skipped_tests_capture_reason(self) -> None:
        with tempfile.TemporaryDirectory(prefix="stage-result-") as tmpdir:
            root = ensure_project_root(Path(tmpdir))
            ensure_gates_config(root, {"tests_required": "soft"})
            write_review_context_pack(root, "DEMO-3")
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
                        "reason_code": "manual_skip",
                        "reason": "tests skipped",
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
            self.assertEqual(payload.get("reason_code"), "no_tests_soft")

    def test_review_uses_latest_pass_when_review_skipped(self) -> None:
        with tempfile.TemporaryDirectory(prefix="stage-result-") as tmpdir:
            root = ensure_project_root(Path(tmpdir))
            ensure_gates_config(root, {"tests_required": "hard"})
            write_review_context_pack(root, "DEMO-4")
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

    def test_review_skipped_tests_block_on_hard(self) -> None:
        with tempfile.TemporaryDirectory(prefix="stage-result-") as tmpdir:
            root = ensure_project_root(Path(tmpdir))
            ensure_gates_config(root, {"tests_required": "hard"})
            write_review_context_pack(root, "DEMO-9")
            write_file(
                root,
                "reports/tests/DEMO-9/iteration_id_I9.jsonl",
                json.dumps(
                    {
                        "schema": "aidd.tests_log.v1",
                        "updated_at": "2024-01-02T00:00:00Z",
                        "ticket": "DEMO-9",
                        "stage": "review",
                        "scope_key": "iteration_id_I9",
                        "status": "skipped",
                        "reason_code": "manual_skip",
                        "reason": "tests skipped",
                    }
                )
                + "\n",
            )

            result = subprocess.run(
                cli_cmd(
                    "stage-result",
                    "--ticket",
                    "DEMO-9",
                    "--stage",
                    "review",
                    "--result",
                    "done",
                    "--work-item-key",
                    "iteration_id=I9",
                ),
                text=True,
                capture_output=True,
                cwd=root,
                env=cli_env(),
            )
            self.assertEqual(result.returncode, 0, msg=result.stdout + result.stderr)
            payload = json.loads(
                (root / "reports" / "loops" / "DEMO-9" / "iteration_id_I9" / "stage.review.result.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(payload.get("result"), "blocked")
            self.assertEqual(payload.get("reason_code"), "no_tests_hard")

    def test_review_stage_result_links_fix_plan(self) -> None:
        with tempfile.TemporaryDirectory(prefix="stage-result-") as tmpdir:
            root = ensure_project_root(Path(tmpdir))
            write_review_context_pack(root, "DEMO-10")
            write_file(
                root,
                "reports/loops/DEMO-10/iteration_id_I10/review.fix_plan.json",
                json.dumps(
                    {
                        "schema": "aidd.review_fix_plan.v1",
                        "updated_at": "2024-01-02T00:00:00Z",
                        "ticket": "DEMO-10",
                        "work_item_key": "iteration_id=I10",
                        "scope_key": "iteration_id_I10",
                        "fix_plan": {},
                    }
                )
                + "\n",
            )

            result = subprocess.run(
                cli_cmd(
                    "stage-result",
                    "--ticket",
                    "DEMO-10",
                    "--stage",
                    "review",
                    "--result",
                    "continue",
                    "--work-item-key",
                    "iteration_id=I10",
                ),
                text=True,
                capture_output=True,
                cwd=root,
                env=cli_env(),
            )
            self.assertEqual(result.returncode, 0, msg=result.stdout + result.stderr)
            payload = json.loads(
                (root / "reports" / "loops" / "DEMO-10" / "iteration_id_I10" / "stage.review.result.json").read_text(
                    encoding="utf-8"
                )
            )
            evidence_links = payload.get("evidence_links") or {}
            self.assertEqual(
                evidence_links.get("fix_plan_json"),
                "aidd/reports/loops/DEMO-10/iteration_id_I10/review.fix_plan.json",
            )

    def test_review_pack_verdict_overrides_stage_result(self) -> None:
        with tempfile.TemporaryDirectory(prefix="stage-result-") as tmpdir:
            root = ensure_project_root(Path(tmpdir))
            write_active_state(root, ticket="DEMO-PACK", work_item="iteration_id=I1")
            write_review_context_pack(root, "DEMO-PACK")
            write_file(
                root,
                "reports/loops/DEMO-PACK/iteration_id_I1/review.latest.pack.md",
                "---\n"
                "schema: aidd.review_pack.v2\n"
                "updated_at: 2024-01-02T00:00:00Z\n"
                "verdict: REVISE\n"
                "work_item_key: iteration_id=I1\n"
                "scope_key: iteration_id_I1\n"
                "---\n",
            )

            result = subprocess.run(
                cli_cmd(
                    "stage-result",
                    "--ticket",
                    "DEMO-PACK",
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
                (root / "reports" / "loops" / "DEMO-PACK" / "iteration_id_I1" / "stage.review.result.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(payload.get("verdict"), "REVISE")
            self.assertEqual(payload.get("result"), "continue")

    def test_qa_report_status_overrides_result(self) -> None:
        with tempfile.TemporaryDirectory(prefix="stage-result-") as tmpdir:
            root = ensure_project_root(Path(tmpdir))
            write_file(
                root,
                "reports/qa/DEMO-QA.json",
                json.dumps({"status": "WARN"}, indent=2),
            )
            write_file(
                root,
                "reports/tests/DEMO-QA/DEMO-QA.jsonl",
                json.dumps(
                    {
                        "schema": "aidd.tests_log.v1",
                        "updated_at": "2024-01-02T00:00:00Z",
                        "ticket": "DEMO-QA",
                        "stage": "qa",
                        "scope_key": "DEMO-QA",
                        "status": "pass",
                    }
                )
                + "\n",
            )

            result = subprocess.run(
                cli_cmd(
                    "stage-result",
                    "--ticket",
                    "DEMO-QA",
                    "--stage",
                    "qa",
                    "--result",
                    "blocked",
                ),
                text=True,
                capture_output=True,
                cwd=root,
                env=cli_env(),
            )
            self.assertEqual(result.returncode, 0, msg=result.stdout + result.stderr)
            payload = json.loads(
                (root / "reports" / "loops" / "DEMO-QA" / "DEMO-QA" / "stage.qa.result.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(payload.get("result"), "done")
            self.assertEqual(payload.get("reason_code"), "qa_warn")

    def test_qa_loop_mode_uses_iteration_scope_from_active_work_item(self) -> None:
        with tempfile.TemporaryDirectory(prefix="stage-result-") as tmpdir:
            root = ensure_project_root(Path(tmpdir))
            write_file(root, "docs/.active_mode", "loop\n")
            write_active_state(root, ticket="DEMO-QA-LOOP", stage="qa", work_item="iteration_id=I3")

            result = subprocess.run(
                cli_cmd(
                    "stage-result",
                    "--ticket",
                    "DEMO-QA-LOOP",
                    "--stage",
                    "qa",
                    "--result",
                    "done",
                ),
                text=True,
                capture_output=True,
                cwd=root,
                env=cli_env(),
            )
            self.assertEqual(result.returncode, 0, msg=result.stdout + result.stderr)
            payload = json.loads(
                (root / "reports" / "loops" / "DEMO-QA-LOOP" / "iteration_id_I3" / "stage.qa.result.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(payload.get("scope_key"), "iteration_id_I3")
            self.assertEqual(payload.get("work_item_key"), "iteration_id=I3")

    def test_qa_loop_mode_rejects_non_iteration_scope_shape(self) -> None:
        with tempfile.TemporaryDirectory(prefix="stage-result-") as tmpdir:
            root = ensure_project_root(Path(tmpdir))
            write_file(root, "docs/.active_mode", "loop\n")
            write_active_state(root, ticket="DEMO-QA-LOOP-BLOCK", stage="qa", work_item="iteration_id=I3")

            result = subprocess.run(
                cli_cmd(
                    "stage-result",
                    "--ticket",
                    "DEMO-QA-LOOP-BLOCK",
                    "--stage",
                    "qa",
                    "--result",
                    "done",
                    "--scope-key",
                    "DEMO-QA-LOOP-BLOCK",
                ),
                text=True,
                capture_output=True,
                cwd=root,
                env=cli_env(),
            )
            self.assertNotEqual(result.returncode, 0)
            result_path = (
                root / "reports" / "loops" / "DEMO-QA-LOOP-BLOCK" / "DEMO-QA-LOOP-BLOCK" / "stage.qa.result.json"
            )
            self.assertFalse(result_path.exists())

    def test_qa_report_blocked_overrides_result(self) -> None:
        with tempfile.TemporaryDirectory(prefix="stage-result-") as tmpdir:
            root = ensure_project_root(Path(tmpdir))
            write_file(
                root,
                "reports/qa/DEMO-QA-BLOCK.json",
                json.dumps({"status": "BLOCKED"}, indent=2),
            )
            write_file(
                root,
                "reports/tests/DEMO-QA-BLOCK/DEMO-QA-BLOCK.jsonl",
                json.dumps(
                    {
                        "schema": "aidd.tests_log.v1",
                        "updated_at": "2024-01-02T00:00:00Z",
                        "ticket": "DEMO-QA-BLOCK",
                        "stage": "qa",
                        "scope_key": "DEMO-QA-BLOCK",
                        "status": "pass",
                    }
                )
                + "\n",
            )

            result = subprocess.run(
                cli_cmd(
                    "stage-result",
                    "--ticket",
                    "DEMO-QA-BLOCK",
                    "--stage",
                    "qa",
                    "--result",
                    "done",
                ),
                text=True,
                capture_output=True,
                cwd=root,
                env=cli_env(),
            )
            self.assertEqual(result.returncode, 0, msg=result.stdout + result.stderr)
            payload = json.loads(
                (root / "reports" / "loops" / "DEMO-QA-BLOCK" / "DEMO-QA-BLOCK" / "stage.qa.result.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(payload.get("result"), "blocked")
            self.assertEqual(payload.get("reason_code"), "qa_blocked")

    def test_qa_tests_failed_blocks(self) -> None:
        with tempfile.TemporaryDirectory(prefix="stage-result-") as tmpdir:
            root = ensure_project_root(Path(tmpdir))
            write_file(
                root,
                "reports/tests/DEMO-QA-FAIL/DEMO-QA-FAIL.jsonl",
                json.dumps(
                    {
                        "schema": "aidd.tests_log.v1",
                        "updated_at": "2024-01-02T00:00:00Z",
                        "ticket": "DEMO-QA-FAIL",
                        "stage": "qa",
                        "scope_key": "DEMO-QA-FAIL",
                        "status": "fail",
                    }
                )
                + "\n",
            )

            result = subprocess.run(
                cli_cmd(
                    "stage-result",
                    "--ticket",
                    "DEMO-QA-FAIL",
                    "--stage",
                    "qa",
                    "--result",
                    "done",
                ),
                text=True,
                capture_output=True,
                cwd=root,
                env=cli_env(),
            )
            self.assertEqual(result.returncode, 0, msg=result.stdout + result.stderr)
            payload = json.loads(
                (root / "reports" / "loops" / "DEMO-QA-FAIL" / "DEMO-QA-FAIL" / "stage.qa.result.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(payload.get("result"), "blocked")
            self.assertEqual(payload.get("reason_code"), "qa_tests_failed")

    def test_rejects_composite_work_item_key(self) -> None:
        with tempfile.TemporaryDirectory(prefix="stage-result-") as tmpdir:
            root = ensure_project_root(Path(tmpdir))

            result = subprocess.run(
                cli_cmd(
                    "stage-result",
                    "--ticket",
                    "DEMO-COMPOSITE",
                    "--stage",
                    "review",
                    "--result",
                    "done",
                    "--work-item-key",
                    "iteration_id=I1,I2",
                ),
                text=True,
                capture_output=True,
                cwd=root,
                env=cli_env(),
            )
            self.assertNotEqual(result.returncode, 0)
            result_path = root / "reports" / "loops" / "DEMO-COMPOSITE" / "iteration_id_I1_I2" / "stage.review.result.json"
            self.assertFalse(result_path.exists())

    def test_stage_result_links_stream_logs(self) -> None:
        with tempfile.TemporaryDirectory(prefix="stage-result-") as tmpdir:
            root = ensure_project_root(Path(tmpdir))
            ensure_gates_config(root, {"tests_required": "disabled"})
            log_dir = root / "reports" / "loops" / "DEMO-STREAM"
            log_dir.mkdir(parents=True, exist_ok=True)
            stream_log = log_dir / "cli.loop-step.20240101-000000.stream.log"
            stream_jsonl = log_dir / "cli.loop-step.20240101-000000.stream.jsonl"
            stream_log.write_text("stream\n", encoding="utf-8")
            stream_jsonl.write_text("{\"type\":\"message_start\"}\n", encoding="utf-8")

            result = subprocess.run(
                cli_cmd(
                    "stage-result",
                    "--ticket",
                    "DEMO-STREAM",
                    "--stage",
                    "implement",
                    "--result",
                    "done",
                    "--work-item-key",
                    "iteration_id=I5",
                ),
                text=True,
                capture_output=True,
                cwd=root,
                env=cli_env(),
            )
            self.assertEqual(result.returncode, 0, msg=result.stdout + result.stderr)
            payload = json.loads(
                (root / "reports" / "loops" / "DEMO-STREAM" / "iteration_id_I5" / "stage.implement.result.json").read_text(
                    encoding="utf-8"
                )
            )
            links = payload.get("evidence_links") or {}
            self.assertEqual(
                links.get("cli_log"),
                "aidd/reports/loops/DEMO-STREAM/cli.loop-step.20240101-000000.stream.log",
            )
            self.assertEqual(
                links.get("cli_stream"),
                "aidd/reports/loops/DEMO-STREAM/cli.loop-step.20240101-000000.stream.jsonl",
            )


if __name__ == "__main__":
    unittest.main()
