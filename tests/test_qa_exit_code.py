import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from aidd_runtime import qa
from tests.helpers import ensure_project_root


class QaExitCodeTests(unittest.TestCase):
    def test_blocked_report_returns_exit_2(self) -> None:
        with tempfile.TemporaryDirectory(prefix="qa-exit-") as tmpdir:
            root = ensure_project_root(Path(tmpdir))
            ticket = "DEMO-QA"
            report_path = root / "reports" / "qa" / f"{ticket}.json"

            def fake_qa_agent_main(_args: list[str]) -> int:
                report_path.parent.mkdir(parents=True, exist_ok=True)
                report_path.write_text(
                    json.dumps({"status": "BLOCKED", "summary": "blocker found", "findings": []}) + "\n",
                    encoding="utf-8",
                )
                return 0

            stderr = io.StringIO()
            with patch("aidd_runtime.qa.runtime.require_workflow_root", return_value=(root.parent, root)), patch(
                "aidd_runtime.qa.runtime.load_gates_config",
                return_value={"tests_required": "soft"},
            ), patch(
                "aidd_runtime.qa.runtime.resolve_feature_context",
                return_value=SimpleNamespace(resolved_ticket=ticket, slug_hint=ticket.lower()),
            ), patch(
                "aidd_runtime.qa.runtime.detect_branch",
                return_value="feature/demo",
            ), patch(
                "aidd_runtime.qa.runtime.maybe_sync_index",
                return_value=None,
            ), patch(
                "aidd_runtime.qa._load_qa_tests_config",
                return_value=([], True),
            ), patch(
                "aidd_runtime.qa._qa_agent.main",
                side_effect=fake_qa_agent_main,
            ), redirect_stderr(stderr):
                exit_code = qa.main(["--ticket", ticket, "--skip-tests", "--allow-no-tests"])

            self.assertEqual(exit_code, 2)
            self.assertIn("BLOCK: QA report status is BLOCKED", stderr.getvalue())

    def test_blocked_overall_status_returns_exit_2(self) -> None:
        with tempfile.TemporaryDirectory(prefix="qa-exit-overall-") as tmpdir:
            root = ensure_project_root(Path(tmpdir))
            ticket = "DEMO-QA-OVERALL"
            report_path = root / "reports" / "qa" / f"{ticket}.json"

            def fake_qa_agent_main(_args: list[str]) -> int:
                report_path.parent.mkdir(parents=True, exist_ok=True)
                report_path.write_text(
                    json.dumps({"overall_status": "BLOCKED", "summary": "blocker found", "findings": []}) + "\n",
                    encoding="utf-8",
                )
                return 0

            stderr = io.StringIO()
            stage_result_calls: list[list[str]] = []
            event_statuses: list[str] = []

            def fake_stage_result_main(argv: list[str]) -> int:
                stage_result_calls.append(list(argv))
                return 0

            def fake_append_event(*_args, **kwargs) -> None:
                event_statuses.append(str(kwargs.get("status") or ""))

            with patch("aidd_runtime.qa.runtime.require_workflow_root", return_value=(root.parent, root)), patch(
                "aidd_runtime.qa.runtime.load_gates_config",
                return_value={"tests_required": "soft"},
            ), patch(
                "aidd_runtime.qa.runtime.resolve_feature_context",
                return_value=SimpleNamespace(resolved_ticket=ticket, slug_hint=ticket.lower()),
            ), patch(
                "aidd_runtime.qa.runtime.detect_branch",
                return_value="feature/demo",
            ), patch(
                "aidd_runtime.qa.runtime.maybe_sync_index",
                return_value=None,
            ), patch(
                "aidd_runtime.qa._load_qa_tests_config",
                return_value=([], True),
            ), patch(
                "aidd_runtime.qa._qa_agent.main",
                side_effect=fake_qa_agent_main,
            ), patch(
                "aidd_runtime.stage_result.main",
                side_effect=fake_stage_result_main,
            ), patch(
                "aidd_runtime.reports.events.append_event",
                side_effect=fake_append_event,
            ), redirect_stderr(stderr):
                exit_code = qa.main(["--ticket", ticket, "--skip-tests", "--allow-no-tests"])

            self.assertEqual(exit_code, 2)
            self.assertIn("BLOCK: QA report status is BLOCKED", stderr.getvalue())
            self.assertTrue(stage_result_calls)
            self.assertIn("--result", stage_result_calls[-1])
            result_index = stage_result_calls[-1].index("--result") + 1
            self.assertEqual(stage_result_calls[-1][result_index], "blocked")
            self.assertIn("BLOCKED", event_statuses)

    def test_overall_status_blocked_overrides_non_blocking_status(self) -> None:
        with tempfile.TemporaryDirectory(prefix="qa-exit-overall-override-") as tmpdir:
            root = ensure_project_root(Path(tmpdir))
            ticket = "DEMO-QA-OVERALL-OVERRIDE"
            report_path = root / "reports" / "qa" / f"{ticket}.json"

            def fake_qa_agent_main(_args: list[str]) -> int:
                report_path.parent.mkdir(parents=True, exist_ok=True)
                report_path.write_text(
                    json.dumps(
                        {
                            "status": "READY",
                            "overall_status": "BLOCKED",
                            "summary": "legacy status conflict",
                            "findings": [],
                        }
                    )
                    + "\n",
                    encoding="utf-8",
                )
                return 0

            stderr = io.StringIO()
            stage_result_calls: list[list[str]] = []

            def fake_stage_result_main(argv: list[str]) -> int:
                stage_result_calls.append(list(argv))
                return 0

            with patch("aidd_runtime.qa.runtime.require_workflow_root", return_value=(root.parent, root)), patch(
                "aidd_runtime.qa.runtime.load_gates_config",
                return_value={"tests_required": "soft"},
            ), patch(
                "aidd_runtime.qa.runtime.resolve_feature_context",
                return_value=SimpleNamespace(resolved_ticket=ticket, slug_hint=ticket.lower()),
            ), patch(
                "aidd_runtime.qa.runtime.detect_branch",
                return_value="feature/demo",
            ), patch(
                "aidd_runtime.qa.runtime.maybe_sync_index",
                return_value=None,
            ), patch(
                "aidd_runtime.qa._load_qa_tests_config",
                return_value=([], True),
            ), patch(
                "aidd_runtime.qa._qa_agent.main",
                side_effect=fake_qa_agent_main,
            ), patch(
                "aidd_runtime.stage_result.main",
                side_effect=fake_stage_result_main,
            ), redirect_stderr(stderr):
                exit_code = qa.main(["--ticket", ticket, "--skip-tests", "--allow-no-tests"])

            self.assertEqual(exit_code, 2)
            self.assertIn("BLOCK: QA report status is BLOCKED", stderr.getvalue())
            self.assertTrue(stage_result_calls)
            self.assertIn("--result", stage_result_calls[-1])
            result_index = stage_result_calls[-1].index("--result") + 1
            self.assertEqual(stage_result_calls[-1][result_index], "blocked")


if __name__ == "__main__":
    unittest.main()
