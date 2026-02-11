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


if __name__ == "__main__":
    unittest.main()
