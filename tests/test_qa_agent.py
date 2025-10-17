import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from .helpers import REPO_ROOT, git_init, write_file

QA_AGENT = REPO_ROOT / "scripts" / "qa-agent.py"


class QaAgentTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(prefix="qa-agent-test-")
        self.root = Path(self._tmp.name)
        git_init(self.root)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def run_agent(self, *argv: str) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        env.setdefault("QA_AGENT_DIFF_BASE", "")
        return subprocess.run(
            ["python3", str(QA_AGENT), *argv],
            cwd=self.root,
            text=True,
            capture_output=True,
            env=env,
        )

    def test_fixme_causes_blocker(self):
        write_file(self.root, "src/main/App.kt", "class App { // FIXME: remove }\n")

        result = self.run_agent("--gate")

        self.assertEqual(result.returncode, 1, msg=result.stderr)
        self.assertIn("[qa-agent] BLOCKER", result.stderr)
        self.assertIn("FIXME", result.stderr)

    def test_tasklist_qa_item_report(self):
        write_file(self.root, "docs/.active_feature", "checkout")
        write_file(
            self.root,
            "docs/tasklist/checkout.md",
            "- [ ] QA: smoke checkout flow\n",
        )

        report_path = self.root / "reports" / "qa" / "checkout.json"
        result = self.run_agent(
            "--gate",
            "--dry-run",
            "--emit-json",
            "--report",
            str(report_path),
        )

        self.assertEqual(result.returncode, 0, msg=result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["status"], "fail")
        self.assertGreaterEqual(payload["counts"]["blocker"], 1)
        self.assertTrue(report_path.exists(), "QA report should be written")

    def test_missing_tests_flags_major_warning(self):
        write_file(self.root, "src/main/App.kt", "class App { fun run() = \"ok\" }\n")

        result = self.run_agent("--format", "json")

        self.assertEqual(result.returncode, 0, msg=result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["status"], "warn")
        self.assertGreaterEqual(payload["counts"].get("major", 0), 1)
        self.assertTrue(
            any(
                finding["severity"] == "major" and finding["scope"] == "tests"
                for finding in payload["findings"]
            )
        )
