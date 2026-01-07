from __future__ import annotations

import os
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from textwrap import dedent

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:  # pragma: no cover - test bootstrap
    sys.path.insert(0, str(SRC_ROOT))

from claude_workflow_cli.tools import prd_review as prd_review_agent  # noqa: E402


class PRDReviewAgentTests(unittest.TestCase):
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
                Status: READY
                - [ ] sync metrics with ops
                """
            ),
        )

        report = prd_review_agent.analyse_prd("demo-feature", prd)

        self.assertEqual(report.status, "ready")
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

        report = prd_review_agent.analyse_prd("demo-feature", prd)

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

        report = prd_review_agent.analyse_prd("demo-feature", prd)

        self.assertEqual(report.status, "blocked")
        self.assertEqual(report.recommended_status, "blocked")
        self.assertTrue(any(f.severity == "critical" for f in report.findings))

    def test_cli_writes_json_report(self):
        prd = self.write_prd(
            dedent(
                """\
                # Demo

                ## PRD Review
                Status: READY
                """
            ),
        )

        report_path = self.tmp_path / "reports" / "prd" / "demo-feature.json"
        report_path.parent.mkdir(parents=True, exist_ok=True)

        env = os.environ.copy()
        pythonpath = os.pathsep.join(filter(None, [str(SRC_ROOT), env.get("PYTHONPATH")]))
        env["PYTHONPATH"] = pythonpath
        subprocess.run(
            [
                sys.executable,
                "-m",
                "claude_workflow_cli.tools.prd_review",
                "--ticket",
                "demo-feature",
                "--slug",
                "demo-feature",
                "--prd",
                str(prd),
                "--report",
                str(report_path),
            ],
            check=True,
            cwd=self.tmp_path,
            env=env,
        )

        payload = json.loads(report_path.read_text(encoding="utf-8"))
        self.assertEqual(payload["ticket"], "demo-feature")
        self.assertEqual(payload["status"], "ready")
        self.assertEqual(payload["recommended_status"], "ready")

    def test_cli_default_report_path_under_plugin_root(self):
        workspace = self.tmp_path / "workspace"
        project_root = workspace / "aidd"
        prd = project_root / "docs" / "prd" / "demo-feature.prd.md"
        prd.parent.mkdir(parents=True, exist_ok=True)
        prd.write_text(
            "# Demo\n\n## PRD Review\nStatus: READY\n",
            encoding="utf-8",
        )
        (project_root / "reports" / "prd").mkdir(parents=True, exist_ok=True)

        env = os.environ.copy()
        env["CLAUDE_PLUGIN_ROOT"] = str(project_root)
        pythonpath = os.pathsep.join(filter(None, [str(SRC_ROOT), env.get("PYTHONPATH")]))
        env["PYTHONPATH"] = pythonpath

        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "claude_workflow_cli.tools.prd_review",
                "--ticket",
                "demo-feature",
                "--prd",
                str(prd),
                "--stdout-format",
                "json",
            ],
            check=True,
            cwd=workspace,
            env=env,
            capture_output=True,
            text=True,
        )

        report_path = project_root / "reports" / "prd" / "demo-feature.json"
        self.assertTrue(report_path.exists(), "default report path should be under plugin root")
        payload = json.loads(report_path.read_text(encoding="utf-8"))
        self.assertEqual(payload["ticket"], "demo-feature")
        self.assertEqual(payload["status"], "ready")
        self.assertIn("[prd-review] report saved to reports/prd/demo-feature.json", result.stderr)


if __name__ == "__main__":
    unittest.main()
