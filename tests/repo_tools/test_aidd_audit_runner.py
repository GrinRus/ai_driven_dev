from __future__ import annotations

import importlib.util
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


if __name__ == "__main__":
    unittest.main()
