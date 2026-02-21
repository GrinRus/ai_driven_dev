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


if __name__ == "__main__":
    unittest.main()
