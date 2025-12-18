from __future__ import annotations

import importlib.util
import os
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from textwrap import dedent

from .helpers import PAYLOAD_ROOT

MODULE_PATH = PAYLOAD_ROOT / "scripts" / "prd-review-agent.py"


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

        env = os.environ.copy()
        pythonpath = os.pathsep.join(filter(None, [str(PAYLOAD_ROOT.parents[5] / "src"), env.get("PYTHONPATH")]))
        env["PYTHONPATH"] = pythonpath
        subprocess.run(
            [
                sys.executable,
                str(MODULE_PATH),
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
        self.assertEqual(payload["status"], "approved")
        self.assertEqual(payload["recommended_status"], "approved")

    def test_cli_default_report_path_under_plugin_root(self):
        workspace = self.tmp_path / "workspace"
        project_root = workspace / "aidd"
        prd = project_root / "docs" / "prd" / "demo-feature.prd.md"
        prd.parent.mkdir(parents=True, exist_ok=True)
        prd.write_text(
            "# Demo\n\n## PRD Review\nStatus: approved\n",
            encoding="utf-8",
        )

        env = os.environ.copy()
        env["CLAUDE_PLUGIN_ROOT"] = str(project_root)
        pythonpath = os.pathsep.join(filter(None, [str(PAYLOAD_ROOT.parents[5] / "src"), env.get("PYTHONPATH")]))
        env["PYTHONPATH"] = pythonpath

        result = subprocess.run(
            [
                sys.executable,
                str(MODULE_PATH),
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
        self.assertEqual(payload["status"], "approved")
        self.assertIn("[prd-review] report saved to reports/prd/demo-feature.json", result.stderr)


if __name__ == "__main__":
    unittest.main()
