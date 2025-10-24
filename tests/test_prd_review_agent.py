from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from textwrap import dedent


MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "prd-review-agent.py"


def _load_prd_review_agent():
    spec = importlib.util.spec_from_file_location("prd_review_agent", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class PRDReviewAgentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.prd_review_agent = _load_prd_review_agent()

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self._tmpdir.name)

    def tearDown(self):
        self._tmpdir.cleanup()

    def write_prd(self, body: str) -> Path:
        path = self.tmp_path / "docs" / "prd" / "demo-feature.prd.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body, encoding="utf-8")
        return path

    def test_analyse_prd_marks_pending_when_action_items(self):
        prd = self.write_prd(
            dedent(
                """\
                # Demo

                ## PRD Review
                Status: approved
                - [ ] sync metrics with ops
                """
            ),
        )

        report = self.prd_review_agent.analyse_prd("demo-feature", prd)

        self.assertEqual(report.status, "approved")
        self.assertEqual(report.recommended_status, "pending")
        self.assertEqual(report.action_items, ["- [ ] sync metrics with ops"])
        self.assertFalse(any(f.severity == "critical" for f in report.findings))

    def test_analyse_prd_detects_placeholders(self):
        prd = self.write_prd(
            dedent(
                """\
                # Demo

                TBD: заполнить раздел

                ## PRD Review
                Status: pending
                """
            ),
        )

        report = self.prd_review_agent.analyse_prd("demo-feature", prd)

        self.assertEqual(report.status, "pending")
        self.assertTrue(any(f.severity == "major" for f in report.findings))
        self.assertEqual(report.recommended_status, "pending")

    def test_analyse_prd_blocks_on_blocked_status(self):
        prd = self.write_prd(
            dedent(
                """\
                # Demo

                ## PRD Review
                Status: blocked
                """
            ),
        )

        report = self.prd_review_agent.analyse_prd("demo-feature", prd)

        self.assertEqual(report.status, "blocked")
        self.assertEqual(report.recommended_status, "blocked")
        self.assertTrue(any(f.severity == "critical" for f in report.findings))

    def test_cli_writes_json_report(self):
        prd = self.write_prd(
            dedent(
                """\
                # Demo

                ## PRD Review
                Status: approved
                """
            ),
        )

        report_path = self.tmp_path / "reports" / "prd" / "demo-feature.json"
        report_path.parent.mkdir(parents=True, exist_ok=True)

        subprocess.run(
            [
                sys.executable,
                str(MODULE_PATH),
                "--slug",
                "demo-feature",
                "--prd",
                str(prd),
                "--report",
                str(report_path),
            ],
            check=True,
            cwd=self.tmp_path,
        )

        payload = json.loads(report_path.read_text(encoding="utf-8"))
        self.assertEqual(payload["ticket"], "demo-feature")
        self.assertEqual(payload["status"], "approved")
        self.assertEqual(payload["recommended_status"], "approved")


if __name__ == "__main__":
    unittest.main()
