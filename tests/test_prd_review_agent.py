from __future__ import annotations

import os
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from textwrap import dedent

from tests.helpers import REPO_ROOT
SRC_ROOT = REPO_ROOT
if str(SRC_ROOT) not in sys.path:  # pragma: no cover - test bootstrap
    sys.path.insert(0, str(SRC_ROOT))

from tools import prd_review as prd_review_agent  # noqa: E402


class PRDReviewAgentTests(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self._tmpdir.name)
        self.workspace = self.tmp_path / "workspace"
        self.project_root = self.workspace / "aidd"
        self.project_root.mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        self._tmpdir.cleanup()

    def write_prd(self, body: str) -> Path:
        path = self.project_root / "docs" / "prd" / "demo-feature.prd.md"
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
        self.assertTrue(all(f.id for f in report.findings))
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
        self.assertTrue(all(f.id for f in report.findings))

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

        report_path = self.project_root / "reports" / "prd" / "demo-feature.json"
        report_path.parent.mkdir(parents=True, exist_ok=True)

        env = os.environ.copy()
        env["CLAUDE_PLUGIN_ROOT"] = str(REPO_ROOT)
        subprocess.run(
            [
                str(REPO_ROOT / "tools" / "prd-review.sh"),
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
            cwd=self.workspace,
            env=env,
        )

        payload = json.loads(report_path.read_text(encoding="utf-8"))
        self.assertEqual(payload["ticket"], "demo-feature")
        self.assertEqual(payload["status"], "ready")
        self.assertEqual(payload["recommended_status"], "ready")

    def test_cli_emit_patch_and_pack_only(self):
        prd = self.write_prd(
            dedent(
                """\
                # Demo

                ## PRD Review
                Status: READY
                """
            ),
        )

        report_path = self.project_root / "reports" / "prd" / "demo-feature.json"
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps({"status": "pending"}), encoding="utf-8")

        env = os.environ.copy()
        env["CLAUDE_PLUGIN_ROOT"] = str(REPO_ROOT)
        subprocess.run(
            [
                str(REPO_ROOT / "tools" / "prd-review.sh"),
                "--ticket",
                "demo-feature",
                "--slug",
                "demo-feature",
                "--prd",
                str(prd),
                "--report",
                str(report_path),
                "--emit-patch",
                "--pack-only",
            ],
            check=True,
            cwd=self.workspace,
            env=env,
        )

        patch_path = report_path.with_suffix(".patch.json")
        pack_path = report_path.with_suffix(".pack.yaml")
        self.assertTrue(patch_path.exists(), "PRD patch should be written")
        self.assertTrue(pack_path.exists(), "PRD pack should be written")
        self.assertFalse(report_path.exists(), "JSON report should be removed in pack-only mode")

    def test_cli_default_report_path_under_plugin_root(self):
        workspace = self.workspace
        project_root = self.project_root
        prd = project_root / "docs" / "prd" / "demo-feature.prd.md"
        prd.parent.mkdir(parents=True, exist_ok=True)
        prd.write_text(
            "# Demo\n\n## PRD Review\nStatus: READY\n",
            encoding="utf-8",
        )
        (project_root / "reports" / "prd").mkdir(parents=True, exist_ok=True)

        env = os.environ.copy()
        env["CLAUDE_PLUGIN_ROOT"] = str(REPO_ROOT)

        result = subprocess.run(
            [
                str(REPO_ROOT / "tools" / "prd-review.sh"),
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
        self.assertIn("[prd-review] report saved to aidd/reports/prd/demo-feature.json", result.stderr)


if __name__ == "__main__":
    unittest.main()
