import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Optional, Dict

from .helpers import (
    REPO_ROOT,
    cli_cmd,
    ensure_gates_config,
    ensure_project_root,
    git_config_user,
    git_init,
    write_active_feature,
    write_file,
)

APPROVED_PRD = "# PRD\n\n## PRD Review\nStatus: READY\n"


class QaAgentTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(prefix="qa-agent-test-")
        self.root = Path(self._tmp.name)
        self.project_root = ensure_project_root(self.root)
        (self.project_root / "docs").mkdir(parents=True, exist_ok=True)
        git_init(self.project_root)
        git_config_user(self.project_root)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def run_agent(self, *argv: str, env: Optional[Dict] = None) -> subprocess.CompletedProcess[str]:
        run_env = os.environ.copy()
        run_env.setdefault("QA_AGENT_DIFF_BASE", "")
        if env:
            run_env.update(env)
        pythonpath = os.pathsep.join(filter(None, [str(REPO_ROOT / "src"), run_env.get("PYTHONPATH")]))
        run_env["PYTHONPATH"] = pythonpath
        return subprocess.run(
            [sys.executable, "-m", "claude_workflow_cli.tools.qa_agent", *argv],
            cwd=self.project_root,
            text=True,
            capture_output=True,
            env=run_env,
        )

    def test_fixme_causes_blocker(self):
        write_file(self.project_root, "src/main/App.kt", "class App { // FIXME: remove }\n")

        result = self.run_agent("--gate")

        self.assertEqual(result.returncode, 1, msg=result.stderr)
        self.assertIn("[qa-agent] BLOCKER", result.stderr)
        self.assertIn("FIXME", result.stderr)

    def test_tasklist_qa_item_report(self):
        write_active_feature(self.project_root, "checkout")
        write_file(
            self.project_root,
            "docs/tasklist/checkout.md",
            "- [ ] QA: smoke checkout flow\n",
        )

        report_path = self.project_root / "reports" / "qa" / "checkout.json"
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
        write_file(self.project_root, "src/main/App.kt", "class App { fun run() = \"ok\" }\n")

        result = self.run_agent("--format", "json")

        self.assertEqual(result.returncode, 0, msg=result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["status"], "fail")
        self.assertGreaterEqual(payload["counts"].get("blocker", 0), 1)
        self.assertTrue(
            any(
                finding["severity"] == "blocker" and finding["scope"] == "tests"
                for finding in payload["findings"]
            )
        )

    def test_tests_not_run_blocks_when_not_allowed(self):
        result = self.run_agent(
            "--gate",
            "--emit-json",
            env={
                "QA_TESTS_SUMMARY": "not-run",
                "QA_ALLOW_NO_TESTS": "0",
            },
        )

        self.assertEqual(result.returncode, 1, msg=result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["tests_summary"], "not-run")
        self.assertTrue(any(f["title"] == "Тесты не запускались" for f in payload["findings"]))

    def test_tests_metadata_included(self):
        report_env = {
            "QA_TESTS_SUMMARY": "fail",
            "QA_TESTS_EXECUTED": json.dumps(
                [
                    {"command": "bash scripts/ci-lint.sh", "status": "fail", "log": "reports/qa/demo-tests.log"}
                ]
            ),
            "QA_ALLOW_NO_TESTS": "1",
        }
        result = self.run_agent("--format", "json", env=report_env)

        self.assertEqual(result.returncode, 0, msg=result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["tests_summary"], "fail")
        self.assertEqual(len(payload["tests_executed"]), 1)
        self.assertEqual(payload["tests_executed"][0]["status"], "fail")

    def test_progress_cli_requires_tasklist_update(self):
        slug = "demo-checkout"
        ensure_gates_config(
            self.project_root,
            {
                "prd_review": {"enabled": False},
                "researcher": {"enabled": False},
                "analyst": {"enabled": False},
                "tasklist_progress": {"enabled": True},
                "reviewer": {"enabled": False},
            },
        )
        write_active_feature(self.project_root, slug)
        write_file(
            self.project_root,
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
        write_file(self.project_root, f"docs/prd/{slug}.prd.md", APPROVED_PRD)
        write_file(self.project_root, f"docs/plan/{slug}.md", "# Plan\n\n## Plan Review\nStatus: READY\n")
        write_file(self.project_root, "src/main/App.kt", "class App { fun run() = \"ok\" }\n")

        subprocess.run(["git", "add", "."], cwd=self.project_root, check=True, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "feat: baseline"],
            cwd=self.project_root,
            check=True,
            capture_output=True,
        )

        write_file(self.project_root, "src/main/App.kt", "class App { fun run() = \"updated\" }\n")

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
            cwd=self.project_root,
            text=True,
            capture_output=True,
        )
        output = result.stdout + result.stderr
        self.assertEqual(result.returncode, 1, msg=output)
        self.assertIn("`- [x]`", output)

        write_file(
            self.project_root,
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
            cwd=self.project_root,
            text=True,
            capture_output=True,
        )
        self.assertEqual(result_ok.returncode, 0, msg=result_ok.stderr)
        self.assertIn("Прогресс tasklist", result_ok.stdout)

    def test_cli_qa_report_resolves_target_root(self):
        (self.project_root / "docs").mkdir(parents=True, exist_ok=True)
        workdir = self.root / "outside"
        workdir.mkdir(parents=True, exist_ok=True)
        report_rel = "reports/qa/demo.json"

        result = subprocess.run(
            cli_cmd(
                "qa",
                "--target",
                str(self.root),
                "--ticket",
                "DEMO-1",
                "--skip-tests",
                "--report",
                report_rel,
                "--format",
                "json",
            ),
            cwd=workdir,
            text=True,
            capture_output=True,
        )

        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertTrue((self.project_root / report_rel).is_file())
        self.assertFalse((workdir / report_rel).exists())
