from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURES = REPO_ROOT / "tests" / "fixtures" / "audit_tst001"
FIXTURES_20260310 = REPO_ROOT / "tests" / "fixtures" / "audit_tst001_20260310"
FIXTURES_20260311 = REPO_ROOT / "tests" / "fixtures" / "audit_tst001_20260311"
FIXTURES_20260317 = REPO_ROOT / "tests" / "fixtures" / "audit_tst001_20260317"
RUNNER_PATH = REPO_ROOT / "tests" / "repo_tools" / "aidd_audit_runner.py"


def _load_runner_module():
    spec = importlib.util.spec_from_file_location("aidd_audit_runner", RUNNER_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"unable to load runner module from {RUNNER_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class AiddAuditRunnerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.runner = _load_runner_module()

    def test_06_implement_classified_as_env_misconfig_no_space(self) -> None:
        payload = self.runner.analyze_run(
            summary_path=FIXTURES / "06_implement_run1.summary.txt",
            run_log_path=FIXTURES / "06_implement_run1.log",
        )
        self.assertEqual(payload.get("classification"), "ENV_MISCONFIG")
        self.assertEqual(payload.get("classification_subtype"), "no_space_left_on_device")
        self.assertEqual(payload.get("classification_source"), "summary")

    def test_06_review_classified_as_watchdog_terminated(self) -> None:
        payload = self.runner.analyze_run(
            summary_path=FIXTURES / "06_review_run1.summary.txt",
            run_log_path=FIXTURES / "06_review_run1.log",
            termination_path=FIXTURES / "06_review_termination_attribution.txt",
        )
        self.assertEqual(payload.get("classification"), "PROMPT_EXEC_ISSUE")
        self.assertEqual(payload.get("classification_subtype"), "watchdog_terminated")
        self.assertIn("NOT_VERIFIED(killed)", str(payload.get("effective_classification") or ""))

    def test_07_loop_run_first_attempt_classified_as_env_missing(self) -> None:
        payload = self.runner.analyze_run(
            summary_path=FIXTURES / "07_loop_run_run1.summary.txt",
            run_log_path=FIXTURES / "07_loop_run_run1.log",
        )
        self.assertEqual(payload.get("classification"), "ENV_MISCONFIG")
        self.assertEqual(payload.get("classification_subtype"), "loop_runner_env_missing")

    def test_07_loop_run_second_attempt_keeps_blocked_top_level_with_recoverable_path(self) -> None:
        payload = self.runner.analyze_run(
            summary_path=FIXTURES / "07_loop_run_run2.summary.txt",
            run_log_path=FIXTURES / "07_loop_run_run2.log",
            aux_log_paths=[FIXTURES / "07_loop_run_loop.run.log"],
        )
        self.assertEqual(payload.get("top_level_result_present"), 1)
        self.assertEqual(payload.get("top_level_status"), "blocked")
        self.assertEqual(payload.get("result_count_interpretation"), "telemetry_only_top_level_present")
        self.assertEqual(payload.get("effective_terminal_status"), "BLOCKED(recoverable ralph path observed)")
        self.assertEqual(payload.get("recoverable_ralph_observed"), 1)

    def test_08_qa_classified_as_watchdog_terminated(self) -> None:
        payload = self.runner.analyze_run(
            summary_path=FIXTURES / "08_qa_run1.summary.txt",
            run_log_path=FIXTURES / "08_qa_run1.log",
            termination_path=FIXTURES / "08_qa_termination_attribution.txt",
        )
        self.assertEqual(payload.get("classification"), "PROMPT_EXEC_ISSUE")
        self.assertEqual(payload.get("classification_subtype"), "watchdog_terminated")
        self.assertIn("NOT_VERIFIED(killed)", str(payload.get("effective_classification") or ""))

    def test_preflight_disk_low_source_has_priority(self) -> None:
        payload = self.runner.analyze_run(
            summary_path=FIXTURES / "06_implement_run1.summary.txt",
            run_log_path=FIXTURES / "06_implement_run1.log",
            preflight={"disk_low": 1},
        )
        self.assertEqual(payload.get("classification"), "ENV_MISCONFIG")
        self.assertEqual(payload.get("classification_source"), "runner_preflight")

    def test_launcher_enospc_reason_marker_classified_as_env_misconfig(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            summary_path = Path(tmp) / "marker.summary.txt"
            summary_path.write_text(
                "\n".join(
                    [
                        "status=failed",
                        "exit_code=70",
                        "reason_code=launcher_io_enospc",
                    ]
                ),
                encoding="utf-8",
            )
            payload = self.runner.analyze_run(summary_path=summary_path)
        self.assertEqual(payload.get("classification"), "ENV_MISCONFIG")
        self.assertEqual(payload.get("classification_subtype"), "no_space_left_on_device")
        self.assertEqual(payload.get("classification_source"), "summary")

    def test_tasks_new_partial_success_without_top_level_result_is_warn(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            summary_path = Path(tmp) / "05_tasks_new_run1.summary.txt"
            log_path = Path(tmp) / "05_tasks_new_run1.log"
            summary_path.write_text(
                "\n".join(
                    [
                        "step=05_tasks_new",
                        "result_count=0",
                        "exit_code=0",
                    ]
                ),
                encoding="utf-8",
            )
            log_path.write_text(
                "\n".join(
                    [
                        "$ python3 /tmp/plugin/skills/tasks-new/runtime/tasks_new.py --ticket TST-001",
                        "[tasks-new] tasklist-check: warn",
                    ]
                ),
                encoding="utf-8",
            )
            payload = self.runner.analyze_run(summary_path=summary_path, run_log_path=log_path)
        self.assertEqual(payload.get("classification"), "TELEMETRY_ONLY")
        self.assertEqual(payload.get("classification_subtype"), "partial_success_no_top_level_result")
        self.assertEqual(payload.get("effective_classification"), "WARN(partial_success_no_top_level_result)")
        self.assertEqual(payload.get("partial_success_no_top_level_result"), 1)

    def test_invalid_fallback_runtime_path_is_classified_as_prompt_exec_issue(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            summary_path = Path(tmp) / "05_tasks_new_fallback.summary.txt"
            log_path = Path(tmp) / "05_tasks_new_fallback.log"
            summary_path.write_text(
                "\n".join(
                    [
                        "step=05_tasks_new",
                        "result_count=0",
                        "exit_code=1",
                    ]
                ),
                encoding="utf-8",
            )
            log_path.write_text(
                "\n".join(
                    [
                        "$ python3 /skills/tasks-new/runtime/tasks_new.py --ticket TST-001",
                        "can't open file '/skills/tasks-new/runtime/tasks_new.py': [Errno 2] No such file or directory",
                    ]
                ),
                encoding="utf-8",
            )
            payload = self.runner.analyze_run(summary_path=summary_path, run_log_path=log_path)
        self.assertEqual(payload.get("classification"), "PROMPT_EXEC_ISSUE")
        self.assertEqual(payload.get("classification_subtype"), "fallback_path_assembly_bug")
        self.assertEqual(payload.get("invalid_fallback_path_count"), 1)

    def test_precondition_readiness_gate_failure_is_classified_as_prompt_exec_issue(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            summary_path = Path(tmp) / "05_plan_new_run1.summary.txt"
            precondition_path = Path(tmp) / "05_precondition_block.txt"
            summary_path.write_text(
                "\n".join(
                    [
                        "step=05_plan_new",
                        "result_count=0",
                        "exit_code=0",
                    ]
                ),
                encoding="utf-8",
            )
            precondition_path.write_text(
                "\n".join(
                    [
                        "readiness_gate=FAIL",
                        "reason_code=prd_not_ready",
                    ]
                ),
                encoding="utf-8",
            )
            payload = self.runner.analyze_run(
                summary_path=summary_path,
                precondition_path=precondition_path,
            )
        self.assertEqual(payload.get("classification"), "PROMPT_EXEC_ISSUE")
        self.assertEqual(payload.get("classification_subtype"), "readiness_gate_failed")
        self.assertEqual(payload.get("readiness_gate_failed"), 1)
        self.assertEqual(payload.get("readiness_reason"), "prd_not_ready")

    def test_readiness_signal_does_not_override_env_blocker(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            summary_path = Path(tmp) / "05_plan_new_run1.summary.txt"
            precondition_path = Path(tmp) / "05_precondition_block.txt"
            summary_path.write_text(
                "\n".join(
                    [
                        "step=05_plan_new",
                        "result_count=0",
                        "exit_code=1",
                        "unknown_skill_hit=1",
                    ]
                ),
                encoding="utf-8",
            )
            precondition_path.write_text(
                "\n".join(
                    [
                        "readiness_gate=FAIL",
                        "reason_code=prd_not_ready",
                    ]
                ),
                encoding="utf-8",
            )
            payload = self.runner.analyze_run(
                summary_path=summary_path,
                precondition_path=precondition_path,
            )
        self.assertEqual(payload.get("classification"), "ENV_BLOCKER")
        self.assertEqual(payload.get("classification_subtype"), "plugin_not_loaded")
        self.assertEqual(payload.get("readiness_gate_failed"), 1)
        self.assertEqual(payload.get("readiness_reason"), "prd_not_ready")

    def test_no_stream_emitted_with_top_level_result_is_telemetry_info(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            summary_path = Path(tmp) / "07_loop_run_run1.summary.txt"
            log_path = Path(tmp) / "07_loop_run_run1.log"
            liveness_path = Path(tmp) / "07_loop_run_stream_liveness_check.txt"
            summary_path.write_text(
                "\n".join(
                    [
                        "exit_code=0",
                        "result_count=0",
                    ]
                ),
                encoding="utf-8",
            )
            log_path.write_text("[loop-run] status=blocked iterations=1 log=aidd/reports/loops/TST-001/loop.run.log\n", encoding="utf-8")
            liveness_path.write_text(
                "\n".join(
                    [
                        "run_start_epoch=100",
                        "main_log_bytes=1",
                        "main_log_mtime=100",
                        "valid_stream_count=0",
                        "active_source=none",
                        "stagnation_seconds=0",
                        "classification=no_stream_emitted",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            payload = self.runner.analyze_run(summary_path=summary_path, run_log_path=log_path, liveness_path=liveness_path)
        self.assertEqual(payload.get("classification"), "TELEMETRY_ONLY")
        self.assertEqual(payload.get("classification_subtype"), "stream_path_not_emitted_by_cli")
        self.assertEqual(payload.get("effective_classification"), "INFO(stream_path_not_emitted_by_cli)")

    def test_silent_stall_from_liveness_promotes_prompt_exec_issue(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            summary_path = Path(tmp) / "08_qa_run1.summary.txt"
            log_path = Path(tmp) / "08_qa_run1.log"
            liveness_path = Path(tmp) / "08_qa_stream_liveness_check.txt"
            summary_path.write_text(
                "\n".join(
                    [
                        "exit_code=0",
                        "result_count=0",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            log_path.write_text("no top level result present\n", encoding="utf-8")
            liveness_path.write_text(
                "\n".join(
                    [
                        "run_start_epoch=100",
                        "main_log_bytes=1",
                        "main_log_mtime=100",
                        "valid_stream_count=1",
                        "stream_0_path=/tmp/stream.log",
                        "stream_0_bytes=1",
                        "stream_0_mtime=100",
                        "active_source=none",
                        "stagnation_seconds=2000",
                        "classification=silent_stall",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            payload = self.runner.analyze_run(summary_path=summary_path, run_log_path=log_path, liveness_path=liveness_path)
        self.assertEqual(payload.get("classification"), "PROMPT_EXEC_ISSUE")
        self.assertEqual(payload.get("classification_subtype"), "silent_stall")

    def test_infer_liveness_path_prefers_run_specific_then_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            summary = root / "07_loop_run_run2.summary.txt"
            summary.write_text("exit_code=0\n", encoding="utf-8")
            generic = root / "07_loop_run_stream_liveness_check.txt"
            run_specific = root / "07_loop_run_stream_liveness_check_run2.txt"
            generic.write_text("classification=no_stream_emitted\n", encoding="utf-8")
            run_specific.write_text("classification=active_stream\n", encoding="utf-8")

            inferred = self.runner.infer_liveness_path(summary)
            self.assertEqual(inferred, run_specific)

    def test_fixture_pack_20260310_replays_review_watchdog_classification(self) -> None:
        payload = self.runner.analyze_run(
            summary_path=FIXTURES_20260310 / "06_review_run1.summary.txt",
            run_log_path=FIXTURES_20260310 / "06_review_run1.log",
            termination_path=FIXTURES_20260310 / "06_review_termination_attribution.txt",
        )
        self.assertEqual(payload.get("classification"), "PROMPT_EXEC_ISSUE")
        self.assertEqual(payload.get("classification_subtype"), "watchdog_terminated")

    def test_fixture_pack_20260311_replays_qa_watchdog_classification(self) -> None:
        payload = self.runner.analyze_run(
            summary_path=FIXTURES_20260311 / "08_qa_run1.summary.txt",
            run_log_path=FIXTURES_20260311 / "08_qa_run1.log",
            termination_path=FIXTURES_20260311 / "08_qa_termination_attribution.txt",
        )
        self.assertEqual(payload.get("classification"), "PROMPT_EXEC_ISSUE")
        self.assertEqual(payload.get("classification_subtype"), "watchdog_terminated")

    def test_fixture_pack_20260317_replays_qa_runtime_cli_contract_mismatch(self) -> None:
        payload = self.runner.analyze_run(
            summary_path=FIXTURES_20260317 / "08_qa_run1.summary.txt",
            run_log_path=FIXTURES_20260317 / "08_qa_run1.log",
        )
        self.assertEqual(payload.get("classification"), "PROMPT_EXEC_ISSUE")
        self.assertEqual(payload.get("classification_subtype"), "runtime_cli_contract_mismatch")

    def test_fixture_pack_20260317_replays_review_spec_mismatch_as_telemetry_with_valid_report_payload(self) -> None:
        payload = self.runner.analyze_run(
            summary_path=FIXTURES_20260317 / "05_review_spec_run2.summary.txt",
            run_log_path=FIXTURES_20260317 / "05_review_spec_run2.log",
            aux_log_paths=[FIXTURES_20260317 / "05_review_spec_report_check_run2.txt"],
        )
        self.assertEqual(payload.get("classification"), "TELEMETRY_ONLY")
        self.assertEqual(payload.get("classification_subtype"), "top_level_success")
        self.assertEqual(payload.get("review_spec_report_mismatch"), 1)
        self.assertEqual(payload.get("review_spec_payload_valid"), 1)
        self.assertEqual(payload.get("review_spec_recovery_source"), "report_payload")

    def test_fixture_pack_20260317_replays_loop_terminal_marker_with_scope_mismatch(self) -> None:
        payload = self.runner.analyze_run(
            summary_path=FIXTURES_20260317 / "07_loop_run_run2.summary.txt",
            run_log_path=FIXTURES_20260317 / "07_loop_run_run2.log",
        )
        self.assertEqual(payload.get("classification"), "TELEMETRY_ONLY")
        self.assertEqual(payload.get("classification_subtype"), "terminal_marker_present")
        self.assertEqual(payload.get("result_count_interpretation"), "terminal_marker_present")
        self.assertEqual(payload.get("terminal_marker_present"), 1)

    def test_fixture_pack_20260317_replays_workspace_layout_preexisting_info(self) -> None:
        payload = self.runner.analyze_run(
            summary_path=FIXTURES_20260317 / "99_post_run_run1.summary.txt",
            run_log_path=FIXTURES_20260317 / "99_post_run_run1.log",
            aux_log_paths=[FIXTURES_20260317 / "99_workspace_layout_check.txt"],
        )
        self.assertEqual(payload.get("classification"), "TELEMETRY_ONLY")
        self.assertEqual(payload.get("classification_subtype"), "preexisting_noncanonical_root")
        self.assertEqual(payload.get("workspace_layout_noncanonical_detected"), 1)
        self.assertEqual(payload.get("workspace_layout_preexisting_only"), 1)

    def test_review_spec_report_mismatch_with_valid_report_payload_stays_telemetry(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            summary_path = root / "05_review_spec_run1.summary.txt"
            log_path = root / "05_review_spec_run1.log"
            report_check_path = root / "05_review_spec_report_check_run1.txt"
            summary_path.write_text("exit_code=0\nresult_count=1\n", encoding="utf-8")
            log_path.write_text('{"type":"result","status":"success"}\n', encoding="utf-8")
            report_check_path.write_text(
                "\n".join(
                    [
                        "report_path=aidd/reports/prd/TST-001.json",
                        "recommended_status=ready",
                        "findings_count=3",
                        "open_questions_count=0",
                        "spec_exists=1",
                        "prd_findings_sync_needed=0",
                        "plan_findings_sync_needed=0",
                        "narrative_vs_report_mismatch=1",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            payload = self.runner.analyze_run(
                summary_path=summary_path,
                run_log_path=log_path,
                aux_log_paths=[report_check_path],
            )
        self.assertEqual(payload.get("classification"), "TELEMETRY_ONLY")
        self.assertEqual(payload.get("classification_subtype"), "top_level_success")
        self.assertEqual(payload.get("review_spec_report_mismatch"), 1)
        self.assertEqual(payload.get("review_spec_payload_valid"), 1)
        self.assertEqual(payload.get("review_spec_report_path"), "aidd/reports/prd/TST-001.json")
        self.assertEqual(payload.get("review_spec_recommended_status"), "ready")
        self.assertEqual(payload.get("review_spec_recovery_source"), "report_payload")

    def test_review_spec_report_check_without_mismatch_keeps_top_level_classification(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            summary_path = root / "05_review_spec_run1.summary.txt"
            log_path = root / "05_review_spec_run1.log"
            report_check_path = root / "05_review_spec_report_check_run1.txt"
            summary_path.write_text("exit_code=0\nresult_count=1\n", encoding="utf-8")
            log_path.write_text('{"type":"result","status":"success"}\n', encoding="utf-8")
            report_check_path.write_text(
                "\n".join(
                    [
                        "report_path=aidd/reports/prd/TST-001.json",
                        "recommended_status=ready",
                        "narrative_vs_report_mismatch=0",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            payload = self.runner.analyze_run(
                summary_path=summary_path,
                run_log_path=log_path,
                aux_log_paths=[report_check_path],
            )
        self.assertEqual(payload.get("classification"), "TELEMETRY_ONLY")
        self.assertEqual(payload.get("classification_subtype"), "top_level_success")
        self.assertEqual(payload.get("review_spec_report_mismatch"), 0)
        self.assertEqual(payload.get("review_spec_payload_valid"), 1)
        self.assertEqual(payload.get("review_spec_recovery_source"), "report_payload")

    def test_review_spec_report_check_prefers_inferred_run_file_over_aux(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            summary_path = root / "05_review_spec_run1.summary.txt"
            log_path = root / "05_review_spec_run1.log"
            inferred_path = root / "05_review_spec_report_check_run1.txt"
            aux_path = root / "manual_review_spec_report_check.txt"

            summary_path.write_text("exit_code=0\nresult_count=1\n", encoding="utf-8")
            log_path.write_text('{"type":"result","status":"success"}\n', encoding="utf-8")
            inferred_path.write_text(
                "report_path=aidd/reports/prd/TST-001.json\n"
                "recommended_status=ready\n"
                "narrative_vs_report_mismatch=0\n",
                encoding="utf-8",
            )
            aux_path.write_text(
                "report_path=aidd/reports/prd/TST-001-stale.json\n"
                "recommended_status=pending\n"
                "narrative_vs_report_mismatch=1\n",
                encoding="utf-8",
            )

            payload = self.runner.analyze_run(
                summary_path=summary_path,
                run_log_path=log_path,
                aux_log_paths=[aux_path],
            )

        self.assertEqual(payload.get("classification"), "TELEMETRY_ONLY")
        self.assertEqual(payload.get("classification_subtype"), "top_level_success")
        self.assertEqual(payload.get("review_spec_report_mismatch"), 0)
        self.assertEqual(payload.get("review_spec_report_path"), "aidd/reports/prd/TST-001.json")
        self.assertIn("05_review_spec_report_check_run1.txt", str(payload.get("review_spec_report_check_path")))

    def test_review_spec_report_mismatch_without_structured_report_payload_promotes_prompt_exec_issue(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            summary_path = root / "05_review_spec_run1.summary.txt"
            log_path = root / "05_review_spec_run1.log"
            report_check_path = root / "05_review_spec_report_check_run1.txt"
            summary_path.write_text("exit_code=0\nresult_count=1\n", encoding="utf-8")
            log_path.write_text('{"type":"result","status":"success"}\n', encoding="utf-8")
            report_check_path.write_text(
                "narrative_vs_report_mismatch=1\n",
                encoding="utf-8",
            )
            payload = self.runner.analyze_run(
                summary_path=summary_path,
                run_log_path=log_path,
                aux_log_paths=[report_check_path],
            )
        self.assertEqual(payload.get("classification"), "PROMPT_EXEC_ISSUE")
        self.assertEqual(payload.get("classification_subtype"), "review_spec_report_mismatch")
        self.assertEqual(payload.get("review_spec_report_mismatch"), 1)
        self.assertEqual(payload.get("review_spec_payload_valid"), 0)
        self.assertEqual(payload.get("review_spec_recovery_source"), "")

    def test_no_top_level_result_is_prompt_exec_issue_when_terminal_marker_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            summary_path = root / "07_loop_run_run1.summary.txt"
            summary_path.write_text("exit_code=0\nresult_count=0\n", encoding="utf-8")
            payload = self.runner.analyze_run(summary_path=summary_path)
        self.assertEqual(payload.get("classification"), "PROMPT_EXEC_ISSUE")
        self.assertEqual(payload.get("classification_subtype"), "no_top_level_result")
        self.assertEqual(payload.get("terminal_marker_present"), 0)

    def test_terminal_marker_allows_telemetry_classification_without_top_level_status(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            summary_path = root / "07_loop_run_run1.summary.txt"
            log_path = root / "07_loop_run_run1.log"
            summary_path.write_text("exit_code=0\nresult_count=0\n", encoding="utf-8")
            log_path.write_text('{"terminal_marker":1,"reason_code":"watchdog_terminated"}\n', encoding="utf-8")
            payload = self.runner.analyze_run(summary_path=summary_path, run_log_path=log_path)
        self.assertEqual(payload.get("classification"), "TELEMETRY_ONLY")
        self.assertEqual(payload.get("classification_subtype"), "terminal_marker_present")
        self.assertEqual(payload.get("result_count_interpretation"), "terminal_marker_present")
        self.assertEqual(payload.get("terminal_marker_present"), 1)

    def test_workspace_layout_preexisting_paths_report_info_not_warn(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            summary_path = root / "99_post_run_run1.summary.txt"
            log_path = root / "99_post_run_run1.log"
            workspace_layout_path = root / "99_workspace_layout_check.txt"
            summary_path.write_text("exit_code=0\nresult_count=1\n", encoding="utf-8")
            log_path.write_text('{"type":"result","status":"success"}\n', encoding="utf-8")
            workspace_layout_path.write_text(
                "\n".join(
                    [
                        "workspace_layout_non_canonical_root_detected=1",
                        "workspace_layout_delta_detected=0",
                        "preexisting_noncanonical_root=1",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            payload = self.runner.analyze_run(
                summary_path=summary_path,
                run_log_path=log_path,
                aux_log_paths=[workspace_layout_path],
            )
        self.assertEqual(payload.get("classification"), "TELEMETRY_ONLY")
        self.assertEqual(payload.get("classification_subtype"), "preexisting_noncanonical_root")
        self.assertEqual(payload.get("workspace_layout_noncanonical_detected"), 1)
        self.assertEqual(payload.get("workspace_layout_preexisting_only"), 1)

    def test_workspace_layout_delta_reports_warn(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            summary_path = root / "99_post_run_run1.summary.txt"
            log_path = root / "99_post_run_run1.log"
            workspace_layout_path = root / "99_workspace_layout_check.txt"
            summary_path.write_text("exit_code=0\nresult_count=1\n", encoding="utf-8")
            log_path.write_text('{"type":"result","status":"success"}\n', encoding="utf-8")
            workspace_layout_path.write_text(
                "\n".join(
                    [
                        "workspace_layout_non_canonical_root_detected=1",
                        "workspace_layout_delta_detected=1",
                        "workspace_layout_delta_count=2",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            payload = self.runner.analyze_run(
                summary_path=summary_path,
                run_log_path=log_path,
                aux_log_paths=[workspace_layout_path],
            )
        self.assertEqual(payload.get("classification"), "TELEMETRY_ONLY")
        self.assertEqual(payload.get("classification_subtype"), "workspace_layout_non_canonical_root_detected")
        self.assertEqual(payload.get("effective_classification"), "WARN(workspace_layout_non_canonical_root_detected)")
        self.assertEqual(payload.get("workspace_layout_noncanonical_detected"), 1)
        self.assertEqual(payload.get("workspace_layout_preexisting_only"), 0)

    def test_workspace_layout_zero_flags_do_not_trigger_detection(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            summary_path = root / "99_post_run_run1.summary.txt"
            log_path = root / "99_post_run_run1.log"
            workspace_layout_path = root / "99_workspace_layout_check.txt"
            summary_path.write_text("exit_code=0\nresult_count=1\n", encoding="utf-8")
            log_path.write_text('{"type":"result","status":"success"}\n', encoding="utf-8")
            workspace_layout_path.write_text(
                "\n".join(
                    [
                        "workspace_layout_non_canonical_root_detected=0",
                        "workspace_layout_delta_detected=0",
                        "preexisting_noncanonical_root=0",
                        "workspace_layout_delta_count=0",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            payload = self.runner.analyze_run(
                summary_path=summary_path,
                run_log_path=log_path,
                aux_log_paths=[workspace_layout_path],
            )
        self.assertEqual(payload.get("classification"), "TELEMETRY_ONLY")
        self.assertEqual(payload.get("classification_subtype"), "top_level_success")
        self.assertEqual(payload.get("workspace_layout_noncanonical_detected"), 0)
        self.assertEqual(payload.get("workspace_layout_preexisting_only"), 0)


if __name__ == "__main__":
    unittest.main()
