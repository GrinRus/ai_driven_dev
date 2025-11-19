import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from .helpers import REPO_ROOT, cli_cmd, ensure_gates_config, git_config_user, git_init, write_active_feature, write_file

QA_AGENT = REPO_ROOT / "scripts" / "qa-agent.py"

APPROVED_PRD = "# PRD\n\n## PRD Review\nStatus: approved\n"


class QaAgentTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(prefix="qa-agent-test-")
        self.root = Path(self._tmp.name)
        git_init(self.root)
        git_config_user(self.root)

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
        write_active_feature(self.root, "checkout")
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

    def test_progress_cli_requires_tasklist_update(self):
        slug = "demo-checkout"
        ensure_gates_config(
            self.root,
            {
                "prd_review": {"enabled": False},
                "researcher": {"enabled": False},
                "analyst": {"enabled": False},
            },
        )
        write_active_feature(self.root, slug)
        write_file(
            self.root,
            f"docs/tasklist/{slug}.md",
            """---
Feature: demo-checkout
Status: draft
PRD: docs/prd/demo-checkout.prd.md
Plan: docs/plan/demo-checkout.md
Research: docs/research/demo-checkout.md
Updated: 2024-01-01

- [ ] Реализация :: подготовить сервис
""",
        )
        write_file(self.root, f"docs/prd/{slug}.prd.md", APPROVED_PRD)
        write_file(self.root, f"docs/plan/{slug}.md", "# Plan")
        write_file(self.root, "src/main/App.kt", "class App { fun run() = \"ok\" }\n")

        subprocess.run(["git", "add", "."], cwd=self.root, check=True, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "feat: baseline"],
            cwd=self.root,
            check=True,
            capture_output=True,
        )

        write_file(self.root, "src/main/App.kt", "class App { fun run() = \"updated\" }\n")

        result = subprocess.run(
            cli_cmd(
                "progress",
                "--target",
                ".",
                "--ticket",
                slug,
                "--source",
                "qa",
            ),
            cwd=self.root,
            text=True,
            capture_output=True,
        )
        output = result.stdout + result.stderr
        self.assertEqual(result.returncode, 1, msg=output)
        self.assertIn("`- [x]`", output)

        write_file(
            self.root,
            f"docs/tasklist/{slug}.md",
            """---
Feature: demo-checkout
Status: draft
PRD: docs/prd/demo-checkout.prd.md
Plan: docs/plan/demo-checkout.md
Research: docs/research/demo-checkout.md
Updated: 2024-01-02

- [x] Реализация :: подготовить сервис — 2024-01-02 • итерация 1
""",
        )

        result_ok = subprocess.run(
            cli_cmd(
                "progress",
                "--target",
                ".",
                "--ticket",
                slug,
                "--source",
                "qa",
            ),
            cwd=self.root,
            text=True,
            capture_output=True,
        )
        self.assertEqual(result_ok.returncode, 0, msg=result_ok.stderr)
        self.assertIn("Прогресс tasklist", result_ok.stdout)
