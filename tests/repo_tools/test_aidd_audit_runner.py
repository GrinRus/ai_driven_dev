from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURES = REPO_ROOT / "tests" / "fixtures" / "audit_tst001"
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

    def test_collect_preflight_marks_topology_invariant_failure(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".claude-plugin").mkdir(parents=True, exist_ok=True)
            (root / "skills").mkdir(parents=True, exist_ok=True)
            payload = self.runner.collect_preflight(project_dir=root, plugin_dir=root)
        self.assertEqual(payload.get("topology_invariant_ok"), 0)
        self.assertEqual(payload.get("topology_reason"), "project_dir_equals_plugin_dir")
        self.assertEqual(payload.get("topology_reason_code"), "cwd_wrong")
        self.assertEqual(payload.get("topology_classification"), "ENV_MISCONFIG(cwd_wrong)")

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

    def test_seed_watchdog_fixture_uses_primary_termination_attribution(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            summary_path = Path(tmp) / "06_seed_watchdog_run1.summary.txt"
            log_path = Path(tmp) / "06_seed_watchdog_run1.log"
            summary_path.write_text((FIXTURES / "06_seed_watchdog_run1.summary.txt").read_text(encoding="utf-8"), encoding="utf-8")
            log_path.write_text((FIXTURES / "06_seed_watchdog_run1.log").read_text(encoding="utf-8"), encoding="utf-8")
            # Use canonical sibling name so infer_termination_path resolves it automatically.
            (Path(tmp) / "06_seed_watchdog_termination_attribution.txt").write_text(
                (FIXTURES / "06_seed_watchdog_termination_attribution.txt").read_text(encoding="utf-8"),
                encoding="utf-8",
            )
            payload = self.runner.analyze_run(
                summary_path=summary_path,
                run_log_path=log_path,
            )
        self.assertEqual(payload.get("classification"), "PROMPT_EXEC_ISSUE")
        self.assertEqual(payload.get("classification_subtype"), "watchdog_terminated")

    def test_07_loop_run_first_attempt_classified_as_env_missing(self) -> None:
        payload = self.runner.analyze_run(
            summary_path=FIXTURES / "07_loop_run_run1.summary.txt",
            run_log_path=FIXTURES / "07_loop_run_run1.log",
        )
        self.assertEqual(payload.get("classification"), "ENV_MISCONFIG")
        self.assertEqual(payload.get("classification_subtype"), "loop_runner_env_missing")

    def test_nested_tool_result_marker_does_not_trigger_loop_runner_env_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            summary_path = Path(tmp) / "05_plan_new_run2.summary.txt"
            log_path = Path(tmp) / "05_plan_new_run2.log"
            summary_path.write_text(
                "\n".join(
                    [
                        "step=05_plan_new",
                        "exit_code=0",
                        "result_count=1",
                        "top_level_result=1",
                        "top_level_status=pending",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            log_path.write_text(
                "\n".join(
                    [
                        '{"type":"user","message":{"content":[{"type":"tool_result","content":"claude_plugin_root (or aidd_plugin_dir) is required"}]}}',
                        '{"type":"result","subtype":"success","result":"**Status: PENDING** validator gaps remain"}',
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            payload = self.runner.analyze_run(summary_path=summary_path, run_log_path=log_path)
        self.assertNotEqual(payload.get("classification_subtype"), "loop_runner_env_missing")
        self.assertEqual(payload.get("classification"), "TELEMETRY_ONLY")
        self.assertEqual(payload.get("classification_subtype"), "top_level_pending")

    def test_exit_zero_completed_termination_does_not_map_to_parent_terminated(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            summary_path = Path(tmp) / "05_plan_new_run2.summary.txt"
            log_path = Path(tmp) / "05_plan_new_run2.log"
            termination_path = Path(tmp) / "05_plan_new_termination_attribution.txt"
            summary_path.write_text(
                "\n".join(
                    [
                        "step=05_plan_new",
                        "exit_code=0",
                        "effective_exit_code=0",
                        "result_count=1",
                        "top_level_result=1",
                        "top_level_status=pending",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            log_path.write_text('{"type":"result","subtype":"success","result":"**Status: PENDING** validator gaps remain"}\n', encoding="utf-8")
            termination_path.write_text(
                "\n".join(
                    [
                        "exit_code=0",
                        "killed_flag=0",
                        "watchdog_marker=0",
                        "classification=completed",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            payload = self.runner.analyze_run(
                summary_path=summary_path,
                run_log_path=log_path,
                termination_path=termination_path,
            )
        self.assertNotEqual(payload.get("classification_subtype"), "parent_terminated_or_external_terminate")
        self.assertEqual(payload.get("classification"), "TELEMETRY_ONLY")
        self.assertEqual(payload.get("classification_subtype"), "top_level_pending")

    def test_loop_runner_env_missing_from_summary_reason_code_remains_env_misconfig(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            summary_path = Path(tmp) / "07_loop_run_run1.summary.txt"
            summary_path.write_text(
                "\n".join(
                    [
                        "step=07_loop_run",
                        "exit_code=2",
                        "reason=claude_plugin_root (or aidd_plugin_dir) is required",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            payload = self.runner.analyze_run(summary_path=summary_path)
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

    def test_cwd_wrong_with_exit_143_is_classified_as_env_misconfig_cwd_wrong(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            summary_path = Path(tmp) / "05_tasks_new_run1.summary.txt"
            log_path = Path(tmp) / "05_tasks_new_run1.log"
            termination_path = Path(tmp) / "05_tasks_new_termination_attribution.txt"
            summary_path.write_text(
                "\n".join(
                    [
                        "step=05_tasks_new",
                        "exit_code=143",
                        "result_count=0",
                        "reason_code=cwd_wrong",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            log_path.write_text(
                "[aidd] ERROR: refusing to use plugin repository as workspace root for runtime artifacts; run commands from the project workspace root.\n",
                encoding="utf-8",
            )
            termination_path.write_text(
                "\n".join(
                    [
                        "exit_code=143",
                        "signal=SIGTERM",
                        "killed_flag=0",
                        "watchdog_marker=0",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            payload = self.runner.analyze_run(
                summary_path=summary_path,
                run_log_path=log_path,
                termination_path=termination_path,
            )
        self.assertEqual(payload.get("classification"), "ENV_MISCONFIG")
        self.assertEqual(payload.get("classification_subtype"), "cwd_wrong")
        self.assertEqual(payload.get("result_count_interpretation"), "no_top_level_result_confirmed")
        self.assertEqual(payload.get("termination_secondary_telemetry"), 1)
        self.assertEqual(payload.get("downstream_skip_hint"), "NOT VERIFIED (upstream_tasks_new_failed)")
        self.assertIn("no_top_level_result", payload.get("secondary_telemetry") or [])
        self.assertNotIn("no_top_level_result", payload.get("secondary_symptoms") or [])

    def test_topology_preflight_violation_overrides_unclassified_run(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            summary_path = Path(tmp) / "05_tasks_new_run1.summary.txt"
            summary_path.write_text(
                "\n".join(
                    [
                        "step=05_tasks_new",
                        "exit_code=0",
                        "result_count=1",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            payload = self.runner.analyze_run(
                summary_path=summary_path,
                preflight={"topology_invariant_ok": 0},
            )
        self.assertEqual(payload.get("classification"), "ENV_MISCONFIG")
        self.assertEqual(payload.get("classification_subtype"), "cwd_wrong")
        self.assertEqual(payload.get("classification_source"), "runner_preflight")

    def test_topology_cwd_wrong_is_not_overridden_by_tasks_new_partial_success(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            summary_path = Path(tmp) / "05_tasks_new_run1.summary.txt"
            log_path = Path(tmp) / "05_tasks_new_run1.log"
            summary_path.write_text(
                "\n".join(
                    [
                        "step=05_tasks_new",
                        "result_count=0",
                        "exit_code=143",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            log_path.write_text(
                "\n".join(
                    [
                        "$ python3 /tmp/plugin/skills/tasks-new/runtime/tasks_new.py --ticket TST-001",
                        "[tasks-new] tasklist-check: warn",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            payload = self.runner.analyze_run(
                summary_path=summary_path,
                run_log_path=log_path,
                preflight={"topology_invariant_ok": 0},
            )
        self.assertEqual(payload.get("classification"), "ENV_MISCONFIG")
        self.assertEqual(payload.get("classification_subtype"), "cwd_wrong")

    def test_cwd_wrong_primary_demotes_write_safety_layout_signals_to_secondary_telemetry(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            summary_path = Path(tmp) / "99_post_run_run1.summary.txt"
            summary_path.write_text(
                "\n".join(
                    [
                        "step=99_post_run",
                        "exit_code=143",
                        "result_count=0",
                        "reason_code=cwd_wrong",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            write_safety_path = Path(tmp) / "99_write_safety_classification.txt"
            write_safety_path.write_text(
                "\n".join(
                    [
                        "classification=WARN(plugin_write_safety_inconclusive)",
                        "layout_warn=WARN(workspace_layout_non_canonical_root_detected)",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            payload = self.runner.analyze_run(
                summary_path=summary_path,
                aux_log_paths=[write_safety_path],
            )
        self.assertEqual(payload.get("classification"), "ENV_MISCONFIG")
        self.assertEqual(payload.get("classification_subtype"), "cwd_wrong")
        self.assertIn("plugin_write_safety_inconclusive", payload.get("secondary_telemetry") or [])
        self.assertIn("workspace_layout_non_canonical_root_detected", payload.get("secondary_telemetry") or [])
        self.assertNotIn("plugin_write_safety_inconclusive", payload.get("secondary_symptoms") or [])
        self.assertNotIn("workspace_layout_non_canonical_root_detected", payload.get("secondary_symptoms") or [])

    def test_write_safety_warn_does_not_override_flow_bug_primary_classification(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            summary_path = Path(tmp) / "99_post_run_run1.summary.txt"
            summary_path.write_text(
                "\n".join(
                    [
                        "step=99_post_run",
                        "exit_code=0",
                        "result_count=0",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            write_safety_path = Path(tmp) / "99_write_safety_classification.txt"
            write_safety_path.write_text(
                "\n".join(
                    [
                        "classification=WARN(plugin_write_safety_inconclusive)",
                        "layout_warn=WARN(workspace_layout_non_canonical_root_detected)",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            payload = self.runner.analyze_run(
                summary_path=summary_path,
                aux_log_paths=[write_safety_path],
            )
        self.assertEqual(payload.get("classification"), "FLOW_BUG")
        self.assertEqual(payload.get("classification_subtype"), "unclassified_terminal_state")
        self.assertIn("plugin_write_safety_inconclusive", payload.get("secondary_symptoms") or [])
        self.assertIn("workspace_layout_non_canonical_root_detected", payload.get("secondary_symptoms") or [])

    def test_result_count_zero_with_type_result_event_is_not_no_top_level_result(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            summary_path = Path(tmp) / "05_review_spec_run1.summary.txt"
            log_path = Path(tmp) / "05_review_spec_run1.log"
            summary_path.write_text("exit_code=0\nresult_count=0\n", encoding="utf-8")
            log_path.write_text('{"type":"result","subtype":"success","result":"ok"}\n', encoding="utf-8")
            payload = self.runner.analyze_run(summary_path=summary_path, run_log_path=log_path)
        self.assertEqual(payload.get("top_level_result_present"), 1)
        self.assertEqual(payload.get("result_count_interpretation"), "telemetry_only_top_level_present")

    def test_pending_question_closure_is_promoted_to_primary_rollup_outcome(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            summary_path = Path(tmp) / "05_idea_new_run2.summary.txt"
            log_path = Path(tmp) / "05_idea_new_run2.log"
            summary_path.write_text(
                "\n".join(
                    [
                        "step=05_idea_new",
                        "exit_code=0",
                        "result_count=1",
                        "top_level_status=pending",
                        "question_cycle_required=1",
                        "pending_question_count=1",
                        "pending_question_ids=Q4",
                        "retry_attempted=1",
                        "answered_question_ids=",
                        "unanswered_question_ids=Q4",
                        "question_retry_incomplete=1",
                        "question_trigger_required=1",
                        "question_trigger_source=result_text_questions",
                        "question_trigger_confidence=high",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            log_path.write_text(
                '{"type":"result","subtype":"success","result":"**PENDING** — остался один обязательный вопрос."}\n',
                encoding="utf-8",
            )
            payload = self.runner.analyze_run(summary_path=summary_path, run_log_path=log_path)
        self.assertEqual(payload.get("classification"), "TELEMETRY_ONLY")
        self.assertEqual(payload.get("classification_subtype"), "pending_question_closure")
        self.assertEqual(payload.get("effective_classification"), "PENDING(question_retry_incomplete)")
        self.assertEqual(payload.get("effective_terminal_status"), "PENDING(question_retry_incomplete)")
        self.assertEqual(payload.get("rollup_outcome"), "pending_question_closure")
        self.assertEqual(payload.get("question_cycle_required"), 1)
        self.assertEqual(payload.get("retry_attempted"), 1)
        self.assertEqual(payload.get("pending_question_ids"), ["Q4"])
        self.assertEqual(payload.get("question_trigger_source"), "result_text_questions")
        self.assertIn("question_retry_incomplete", payload.get("secondary_symptoms") or [])

    def test_persisted_template_questions_with_answers_do_not_trigger_pending_question_closure(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            summary_path = Path(tmp) / "05_plan_new_run2.summary.txt"
            log_path = Path(tmp) / "05_plan_new_run2.log"
            summary_path.write_text(
                "\n".join(
                    [
                        "step=05_plan_new",
                        "exit_code=0",
                        "result_count=1",
                        "top_level_result=1",
                        "top_level_status=pending",
                        "question_cycle_required=1",
                        "pending_question_count=3",
                        "pending_question_ids=Q1,Q2,Q3",
                        "retry_attempted=1",
                        "answered_question_ids=Q1,Q2,Q3",
                        "unanswered_question_ids=",
                        "question_retry_incomplete=0",
                        "question_source=persisted_doc",
                        "question_trigger_required=0",
                        "question_trigger_source=none",
                        "question_trigger_confidence=none",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            log_path.write_text(
                '{"type":"result","subtype":"success","result":"## Stage Result: `plan`\\n\\n**Status: PENDING**\\n\\nValidator gaps found."}\n',
                encoding="utf-8",
            )
            payload = self.runner.analyze_run(summary_path=summary_path, run_log_path=log_path)
        self.assertNotEqual(payload.get("rollup_outcome"), "pending_question_closure")
        self.assertNotEqual(payload.get("effective_terminal_status"), "PENDING(question_closure_required)")
        self.assertEqual(payload.get("has_unresolved_questions"), 0)

    def test_tst001_regression_path_does_not_cascade_to_upstream_plan_qna_unresolved(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            idea_summary = root / "05_idea_new_run2.summary.txt"
            idea_log = root / "05_idea_new_run2.log"
            research_summary = root / "05_researcher_run2.summary.txt"
            research_log = root / "05_researcher_run2.log"
            plan_summary = root / "05_plan_new_run2.summary.txt"
            plan_log = root / "05_plan_new_run2.log"
            precondition_path = root / "05_precondition_block.txt"

            idea_summary.write_text(
                "\n".join(
                    [
                        "step=05_idea_new",
                        "run=2",
                        "exit_code=0",
                        "result_count=1",
                        "top_level_result=1",
                        "top_level_status=",
                        "question_cycle_required=0",
                        "pending_question_count=0",
                        "pending_question_ids=",
                        "retry_attempted=1",
                        "answered_question_ids=Q1,Q2,Q3",
                        "unanswered_question_ids=",
                        "question_retry_incomplete=0",
                        "question_source=none",
                        "question_trigger_required=0",
                        "question_trigger_source=none",
                        "question_trigger_confidence=none",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            idea_log.write_text('{"type":"result","subtype":"success","result":"**TST-001 idea stage: READY**"}\n', encoding="utf-8")

            research_summary.write_text(
                "\n".join(
                    [
                        "step=05_researcher",
                        "run=2",
                        "exit_code=0",
                        "result_count=1",
                        "top_level_result=1",
                        "top_level_status=",
                        "question_cycle_required=0",
                        "pending_question_count=0",
                        "pending_question_ids=",
                        "retry_attempted=1",
                        "answered_question_ids=Q1,Q2,Q3",
                        "unanswered_question_ids=",
                        "question_retry_incomplete=0",
                        "question_source=none",
                        "question_trigger_required=0",
                        "question_trigger_source=none",
                        "question_trigger_confidence=none",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            research_log.write_text(
                '{"type":"result","subtype":"success","result":"Research pipeline for TST-001 completed successfully. RLM Status: ready"}\n',
                encoding="utf-8",
            )

            plan_summary.write_text(
                "\n".join(
                    [
                        "step=05_plan_new",
                        "run=2",
                        "exit_code=0",
                        "result_count=1",
                        "top_level_result=1",
                        "top_level_status=pending",
                        "question_cycle_required=1",
                        "pending_question_count=3",
                        "pending_question_ids=Q1,Q2,Q3",
                        "retry_attempted=1",
                        "answered_question_ids=Q1,Q2,Q3",
                        "unanswered_question_ids=",
                        "question_retry_incomplete=0",
                        "question_source=persisted_doc",
                        "question_trigger_required=0",
                        "question_trigger_source=none",
                        "question_trigger_confidence=none",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            plan_log.write_text(
                '{"type":"result","subtype":"success","result":"## Stage Result: `plan`\\n\\n**Status: PENDING**\\n\\nValidator gaps found."}\n',
                encoding="utf-8",
            )
            precondition_path.write_text(
                "\n".join(
                    [
                        "prd_status=READY",
                        "open_questions_count=0",
                        "answers_format=compact_q_values",
                        "research_status=reviewed",
                        "research_warn_scope=none",
                        "readiness_gate=PASS",
                        "reason_code=-",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            idea_payload = self.runner.analyze_run(
                summary_path=idea_summary,
                run_log_path=idea_log,
                precondition_path=precondition_path,
            )
            research_payload = self.runner.analyze_run(
                summary_path=research_summary,
                run_log_path=research_log,
                precondition_path=precondition_path,
            )
            plan_payload = self.runner.analyze_run(
                summary_path=plan_summary,
                run_log_path=plan_log,
                precondition_path=precondition_path,
            )
            rolled = self.runner.rollup_latest_runs([idea_payload, research_payload, plan_payload])

        steps = rolled.get("steps") or {}
        self.assertNotEqual((steps.get("05_idea_new") or {}).get("rollup_outcome"), "pending_question_closure")
        self.assertNotEqual((steps.get("05_researcher") or {}).get("rollup_outcome"), "pending_question_closure")
        self.assertNotEqual((steps.get("05_plan_new") or {}).get("rollup_outcome"), "pending_question_closure")
        self.assertNotIn("upstream_plan_qna_unresolved", json.dumps(rolled, ensure_ascii=False))

    def test_project_contract_reason_overrides_exit_143_external_terminate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            summary_path = Path(tmp) / "06_review_run1.summary.txt"
            termination_path = Path(tmp) / "06_review_termination_attribution.txt"
            summary_path.write_text(
                "\n".join(
                    [
                        "exit_code=143",
                        "reason_code=project_contract_missing",
                        "result_count=0",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            termination_path.write_text(
                "\n".join(
                    [
                        "exit_code=143",
                        "killed_flag=0",
                        "watchdog_marker=0",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            payload = self.runner.analyze_run(
                summary_path=summary_path,
                termination_path=termination_path,
            )
        self.assertEqual(payload.get("classification"), "PROMPT_EXEC_ISSUE")
        self.assertEqual(payload.get("classification_subtype"), "project_contract_missing")

    def test_review_spec_report_mismatch_ready_is_non_blocking_info(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            summary_path = Path(tmp) / "05_review_spec_run1.summary.txt"
            log_path = Path(tmp) / "05_review_spec_run1.log"
            report_check_path = Path(tmp) / "05_review_spec_report_check_run1.txt"
            summary_path.write_text("step=05_review_spec\nexit_code=0\nresult_count=1\n", encoding="utf-8")
            log_path.write_text("[review-spec] done\n", encoding="utf-8")
            report_check_path.write_text(
                "\n".join(
                    [
                        "recommended_status=ready",
                        "findings_count=0",
                        "open_questions_count=0",
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
        self.assertEqual(payload.get("classification_subtype"), "review_spec_report_mismatch_non_blocking")
        self.assertEqual(payload.get("effective_classification"), "INFO(review_spec_report_mismatch_non_blocking)")
        self.assertEqual(payload.get("review_spec_report_mismatch_detected"), 1)
        self.assertEqual(payload.get("review_spec_report_mismatch_non_blocking"), 1)

    def test_review_spec_mismatch_non_blocking_does_not_override_primary_blocker(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            summary_path = Path(tmp) / "05_review_spec_run1.summary.txt"
            report_check_path = Path(tmp) / "05_review_spec_report_check_run1.txt"
            summary_path.write_text(
                "\n".join(
                    [
                        "step=05_review_spec",
                        "exit_code=2",
                        "result_count=0",
                        "reason_code=project_contract_missing",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            report_check_path.write_text(
                "\n".join(
                    [
                        "recommended_status=ready",
                        "findings_count=0",
                        "open_questions_count=0",
                        "narrative_vs_report_mismatch=1",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            payload = self.runner.analyze_run(
                summary_path=summary_path,
                aux_log_paths=[report_check_path],
            )
        self.assertEqual(payload.get("classification"), "PROMPT_EXEC_ISSUE")
        self.assertEqual(payload.get("classification_subtype"), "project_contract_missing")
        self.assertEqual(payload.get("review_spec_report_mismatch_detected"), 1)
        self.assertEqual(payload.get("review_spec_report_mismatch_non_blocking"), 1)

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

    def test_readiness_prd_not_ready_with_ready_prd_and_pending_report_is_report_driven(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            summary_path = Path(tmp) / "05_plan_new_run1.summary.txt"
            precondition_path = Path(tmp) / "05_precondition_block.txt"
            report_check_path = Path(tmp) / "05_review_spec_report_check_run1.txt"
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
                        "prd_status=READY",
                        "readiness_gate=FAIL",
                        "reason_code=prd_not_ready",
                        "review_spec_recommended_status=pending",
                    ]
                ),
                encoding="utf-8",
            )
            report_check_path.write_text(
                "\n".join(
                    [
                        "recommended_status=pending",
                        "findings_count=1",
                        "open_questions_count=0",
                    ]
                ),
                encoding="utf-8",
            )
            payload = self.runner.analyze_run(
                summary_path=summary_path,
                precondition_path=precondition_path,
                aux_log_paths=[report_check_path],
            )
        self.assertEqual(payload.get("classification"), "PROMPT_EXEC_ISSUE")
        self.assertEqual(payload.get("classification_subtype"), "readiness_gate_failed")
        self.assertEqual(payload.get("readiness_reason"), "prd_not_ready")
        self.assertEqual(payload.get("readiness_failure_mode"), "report_recommended_status_not_ready")

    def test_repeated_command_failure_reason_is_softened_for_06_implement_in_soft_default(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            summary_path = Path(tmp) / "06_implement_run1.summary.txt"
            summary_path.write_text(
                "\n".join(
                    [
                        "step=06_implement",
                        "exit_code=20",
                        "reason_code=repeated_command_failure_no_new_evidence",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            payload = self.runner.analyze_run(summary_path=summary_path)
        self.assertEqual(payload.get("classification"), "TELEMETRY_ONLY")
        self.assertEqual(payload.get("classification_subtype"), "soft_default_repeated_command_failure_no_new_evidence")
        self.assertEqual(payload.get("strict_shadow_classification_type"), "PROMPT_EXEC_ISSUE")
        self.assertEqual(payload.get("strict_shadow_classification_subtype"), "repeated_command_failure_no_new_evidence")
        self.assertEqual(payload.get("softened"), 1)

    def test_repeated_command_failure_reason_remains_strict_when_profile_is_strict(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            summary_path = Path(tmp) / "06_implement_run1.summary.txt"
            summary_path.write_text(
                "\n".join(
                    [
                        "step=06_implement",
                        "exit_code=20",
                        "reason_code=repeated_command_failure_no_new_evidence",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            payload = self.runner.analyze_run(summary_path=summary_path, classification_profile="strict")
        self.assertEqual(payload.get("classification"), "PROMPT_EXEC_ISSUE")
        self.assertEqual(payload.get("classification_subtype"), "repeated_command_failure_no_new_evidence")
        self.assertEqual(payload.get("strict_shadow_classification_type"), "PROMPT_EXEC_ISSUE")
        self.assertEqual(payload.get("softened"), 0)

    def test_project_contract_missing_is_primary_even_with_no_top_level_result(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            summary_path = Path(tmp) / "06_implement_run1.summary.txt"
            summary_path.write_text(
                "\n".join(
                    [
                        "step=06_implement",
                        "exit_code=2",
                        "result_count=0",
                        "reason_code=project_contract_missing",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            payload = self.runner.analyze_run(summary_path=summary_path)
        self.assertEqual(payload.get("classification"), "PROMPT_EXEC_ISSUE")
        self.assertEqual(payload.get("classification_subtype"), "project_contract_missing")
        self.assertEqual(payload.get("classification_source"), "summary")
        self.assertEqual(payload.get("result_count_interpretation"), "no_top_level_result_confirmed")

    def test_tests_cwd_mismatch_is_primary_even_with_no_top_level_result(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            summary_path = Path(tmp) / "06_review_run1.summary.txt"
            summary_path.write_text(
                "\n".join(
                    [
                        "step=06_review",
                        "exit_code=2",
                        "result_count=0",
                        "reason_code=tests_cwd_mismatch",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            payload = self.runner.analyze_run(summary_path=summary_path)
        self.assertEqual(payload.get("classification"), "PROMPT_EXEC_ISSUE")
        self.assertEqual(payload.get("classification_subtype"), "tests_cwd_mismatch")
        self.assertEqual(payload.get("classification_source"), "summary")
        self.assertEqual(payload.get("result_count_interpretation"), "no_top_level_result_confirmed")

    def test_stage_result_scope_drift_marker_is_not_contract_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            summary_path = Path(tmp) / "07_loop_run_run1.summary.txt"
            log_path = Path(tmp) / "07_loop_run_run1.log"
            summary_path.write_text(
                "\n".join(
                    [
                        "step=07_loop_run",
                        "exit_code=20",
                        "reason_code=stage_result_missing_or_invalid",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            log_path.write_text(
                "stage_result_missing_or_invalid diagnostics=scope_shape_invalid=iteration_id_I1\n",
                encoding="utf-8",
            )
            payload = self.runner.analyze_run(summary_path=summary_path, run_log_path=log_path)
        self.assertEqual(payload.get("classification"), "PROMPT_EXEC_ISSUE")
        self.assertEqual(payload.get("classification_subtype"), "scope_drift_recoverable")

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

    def test_rollup_latest_wins_marks_superseded_runs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            summary_run1 = root / "05_tasks_new_run1.summary.txt"
            summary_run2 = root / "05_tasks_new_run2.summary.txt"
            log_run2 = root / "05_tasks_new_run2.log"

            summary_run1.write_text(
                "\n".join(
                    [
                        "step=05_tasks_new",
                        "exit_code=2",
                        "result_count=0",
                        "reason_code=project_contract_missing",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            summary_run2.write_text(
                "\n".join(
                    [
                        "step=05_tasks_new",
                        "exit_code=0",
                        "result_count=0",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            log_run2.write_text('{"type":"result","status":"success"}\n', encoding="utf-8")

            payload1 = self.runner.analyze_run(summary_path=summary_run1)
            payload2 = self.runner.analyze_run(summary_path=summary_run2, run_log_path=log_run2)
            rolled = self.runner.rollup_latest_runs([payload1, payload2])

        self.assertEqual(rolled.get("steps_total"), 1)
        step_payload = (rolled.get("steps") or {}).get("05_tasks_new")
        self.assertIsNotNone(step_payload)
        self.assertEqual(step_payload.get("run_index"), 2)
        superseded = step_payload.get("superseded_runs") or []
        self.assertTrue(any(str(summary_run1) in item for item in superseded))

    def test_rollup_keeps_soft_profile_and_strict_shadow_fields(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            summary_path = Path(tmp) / "06_implement_run1.summary.txt"
            summary_path.write_text(
                "\n".join(
                    [
                        "step=06_implement",
                        "exit_code=2",
                        "result_count=1",
                        "reason_code=seed_scope_cascade_detected",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            payload = self.runner.analyze_run(summary_path=summary_path)
            rolled = self.runner.rollup_latest_runs([payload])
        step_payload = (rolled.get("steps") or {}).get("06_implement")
        self.assertIsNotNone(step_payload)
        self.assertEqual(step_payload.get("classification_profile"), "soft_default")
        self.assertEqual(step_payload.get("classification"), "TELEMETRY_ONLY")
        self.assertEqual(step_payload.get("classification_subtype"), "soft_default_seed_scope_cascade_detected")
        self.assertEqual(step_payload.get("strict_shadow_classification_subtype"), "seed_scope_cascade_detected")
        self.assertEqual(step_payload.get("primary_root_cause"), "PROMPT_EXEC_ISSUE:seed_scope_cascade_detected")
        self.assertEqual(step_payload.get("softened"), 1)

    def test_analyze_run_infers_sibling_termination_attribution_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            summary_path = Path(tmp) / "06_implement_run1.summary.txt"
            summary_path.write_text(
                "\n".join(
                    [
                        "step=06_implement",
                        "exit_code=143",
                        "result_count=0",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            termination_path = Path(tmp) / "06_implement_termination_attribution.txt"
            termination_path.write_text(
                "\n".join(
                    [
                        "exit_code=143",
                        "signal=SIGTERM",
                        "killed_flag=1",
                        "watchdog_marker=1",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            payload = self.runner.analyze_run(summary_path=summary_path)
        self.assertEqual(payload.get("classification"), "TELEMETRY_ONLY")
        self.assertEqual(payload.get("classification_subtype"), "soft_default_watchdog_terminated")
        self.assertEqual(payload.get("strict_shadow_classification_type"), "PROMPT_EXEC_ISSUE")
        self.assertEqual(payload.get("strict_shadow_classification_subtype"), "watchdog_terminated")
        self.assertEqual(payload.get("softened"), 1)
        self.assertEqual(payload.get("classification_profile"), "soft_default")
        self.assertEqual(Path(str(payload.get("termination_path") or "")).name, "06_implement_termination_attribution.txt")

    def test_seed_scope_cascade_reason_is_softened_in_soft_default_profile(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            summary_path = Path(tmp) / "06_implement_run1.summary.txt"
            summary_path.write_text(
                "\n".join(
                    [
                        "step=06_implement",
                        "exit_code=2",
                        "result_count=1",
                        "reason_code=seed_scope_cascade_detected",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            payload = self.runner.analyze_run(summary_path=summary_path)
        self.assertEqual(payload.get("classification"), "TELEMETRY_ONLY")
        self.assertEqual(payload.get("classification_subtype"), "soft_default_seed_scope_cascade_detected")
        self.assertEqual(payload.get("strict_shadow_classification_type"), "PROMPT_EXEC_ISSUE")
        self.assertEqual(payload.get("strict_shadow_classification_subtype"), "seed_scope_cascade_detected")
        self.assertEqual(payload.get("softened"), 1)

    def test_seed_scope_cascade_reason_keeps_strict_shadow_profile(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            summary_path = Path(tmp) / "06_implement_run1.summary.txt"
            summary_path.write_text(
                "\n".join(
                    [
                        "step=06_implement",
                        "exit_code=2",
                        "result_count=1",
                        "reason_code=seed_scope_cascade_detected",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            payload = self.runner.analyze_run(summary_path=summary_path, classification_profile="strict")
        self.assertEqual(payload.get("classification"), "PROMPT_EXEC_ISSUE")
        self.assertEqual(payload.get("classification_subtype"), "seed_scope_cascade_detected")
        self.assertEqual(payload.get("strict_shadow_classification_type"), "PROMPT_EXEC_ISSUE")
        self.assertEqual(payload.get("softened"), 0)

    def test_tests_env_dependency_missing_reason_is_softened_in_soft_default_profile(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            summary_path = Path(tmp) / "06_implement_run1.summary.txt"
            summary_path.write_text(
                "\n".join(
                    [
                        "step=06_implement",
                        "exit_code=2",
                        "result_count=1",
                        "reason_code=tests_env_dependency_missing",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            payload = self.runner.analyze_run(summary_path=summary_path)
        self.assertEqual(payload.get("classification"), "TELEMETRY_ONLY")
        self.assertEqual(payload.get("classification_subtype"), "soft_default_tests_env_dependency_missing")
        self.assertEqual(payload.get("strict_shadow_classification_type"), "PROMPT_EXEC_ISSUE")
        self.assertEqual(payload.get("strict_shadow_classification_subtype"), "tests_env_dependency_missing")
        self.assertEqual(payload.get("softened"), 1)

    def test_fixture_i1_done_i2_drift_soft_and_strict_profiles_keep_root_cause(self) -> None:
        summary_path = FIXTURES / "06_implement_i1_done_i2_drift_run1.summary.txt"
        log_path = FIXTURES / "06_implement_i1_done_i2_drift_run1.log"

        soft_payload = self.runner.analyze_run(summary_path=summary_path, run_log_path=log_path)
        self.assertEqual(soft_payload.get("classification_profile"), "soft_default")
        self.assertEqual(soft_payload.get("classification"), "TELEMETRY_ONLY")
        self.assertEqual(soft_payload.get("classification_subtype"), "soft_default_seed_scope_cascade_detected")
        self.assertEqual(soft_payload.get("strict_shadow_classification_type"), "PROMPT_EXEC_ISSUE")
        self.assertEqual(soft_payload.get("strict_shadow_classification_subtype"), "seed_scope_cascade_detected")
        self.assertEqual(soft_payload.get("primary_root_cause"), "PROMPT_EXEC_ISSUE:seed_scope_cascade_detected")
        self.assertEqual(soft_payload.get("softened"), 1)

        strict_payload = self.runner.analyze_run(
            summary_path=summary_path,
            run_log_path=log_path,
            classification_profile="strict",
        )
        self.assertEqual(strict_payload.get("classification_profile"), "strict")
        self.assertEqual(strict_payload.get("classification"), "PROMPT_EXEC_ISSUE")
        self.assertEqual(strict_payload.get("classification_subtype"), "seed_scope_cascade_detected")
        self.assertEqual(strict_payload.get("primary_root_cause"), "PROMPT_EXEC_ISSUE:seed_scope_cascade_detected")
        self.assertEqual(strict_payload.get("softened"), 0)


if __name__ == "__main__":
    unittest.main()
