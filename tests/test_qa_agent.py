import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from typing import Optional, Dict

from .helpers import (
    REPO_ROOT,
    cli_cmd,
    cli_env,
    ensure_gates_config,
    ensure_project_root,
    git_config_user,
    git_init,
    tasklist_ready_text,
    write_active_feature,
    write_file,
    write_json,
)

APPROVED_PRD = "# PRD\n\n## PRD Review\nStatus: READY\n"


class QaAgentTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(prefix="qa-agent-test-")
        self.root = Path(self._tmp.name)
        self.project_root = ensure_project_root(self.root)
        git_init(self.project_root)
        git_config_user(self.project_root)
        ensure_gates_config(self.project_root)
        write_file(self.project_root, "README.md", "## QA\n\n```sh\npython3 -m unittest\n```\n")
        write_file(
            self.project_root,
            "test_dummy.py",
            "import unittest\n\n\nclass DummyTest(unittest.TestCase):\n    def test_ok(self):\n        self.assertTrue(True)\n",
        )
        write_active_feature(self.project_root, "demo-ticket")

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def run_agent(self, *argv: str, env: Optional[Dict] = None) -> subprocess.CompletedProcess[str]:
        run_env = os.environ.copy()
        run_env.setdefault("QA_AGENT_DIFF_BASE", "")
        run_env.setdefault("CLAUDE_PLUGIN_ROOT", str(REPO_ROOT))
        if env:
            run_env.update(env)
        return subprocess.run(
            cli_cmd("qa", *argv),
            cwd=self.project_root,
            text=True,
            capture_output=True,
            env=run_env,
        )

    def test_fixme_causes_blocker(self):
        write_file(self.project_root, "src/main/App.kt", "class App { // FIXME: remove }\n")

        result = self.run_agent("--gate")

        self.assertEqual(result.returncode, 2, msg=result.stderr)
        self.assertIn("[qa-agent] BLOCKER", result.stderr)
        self.assertIn("FIXME", result.stderr)

    def test_tasklist_qa_item_report(self):
        write_active_feature(self.project_root, "checkout")
        write_file(
            self.project_root,
            "docs/tasklist/checkout.md",
            "### AIDD:CHECKLIST_QA\n- [ ] QA: smoke checkout flow\n",
        )

        report_path = self.project_root / "reports" / "qa" / "checkout.json"
        result = self.run_agent(
            "--gate",
            "--dry-run",
            "--emit-json",
            "--report",
            str(report_path),
        )

        self.assertEqual(result.returncode, 2, msg=result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["status"], "BLOCKED")
        self.assertGreaterEqual(payload["counts"]["blocker"], 1)
        self.assertTrue(all(finding.get("id") for finding in payload["findings"]))
        self.assertTrue(all("blocking" in finding for finding in payload["findings"]))
        self.assertTrue(report_path.exists(), "QA report should be written")

    def test_non_blocking_handoff_warns_and_matches_report(self):
        write_active_feature(self.project_root, "handoff-demo")
        write_file(
            self.project_root,
            "docs/tasklist/handoff-demo.md",
            "\n".join(
                [
                    "# Tasklist",
                    "",
                    "## AIDD:HANDOFF_INBOX",
                    "<!-- handoff:qa start -->",
                    "- [ ] QA non-blocking item (id: qa:demo) (Priority: low) (Blocking: false)",
                    "  - source: qa",
                    "  - scope: iteration_id=I1",
                    "<!-- handoff:qa end -->",
                    "",
                ]
            ),
        )

        report_path = self.project_root / "reports" / "qa" / "handoff-demo.json"
        result = self.run_agent("--emit-json", "--report", str(report_path))

        self.assertEqual(result.returncode, 0, msg=result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["status"], "WARN")
        report_payload = json.loads(report_path.read_text(encoding="utf-8"))
        self.assertEqual(report_payload["status"], "WARN")

    def test_emit_patch_writes_patch_file(self):
        write_file(self.project_root, "src/main/App.kt", "class App { fun run() = \"ok\" }\n")

        report_path = self.project_root / "reports" / "qa" / "demo.json"
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps({"status": "READY"}), encoding="utf-8")

        result = self.run_agent(
            "--emit-json",
            "--emit-patch",
            "--report",
            str(report_path),
        )

        self.assertEqual(result.returncode, 0, msg=result.stderr)
        patch_path = report_path.with_suffix(".patch.json")
        self.assertTrue(patch_path.exists(), "QA patch should be written")
        patch_ops = json.loads(patch_path.read_text(encoding="utf-8"))
        self.assertIsInstance(patch_ops, list)

    def test_pack_only_removes_json_report(self):
        write_file(self.project_root, "src/main/App.kt", "class App { fun run() = \"ok\" }\n")

        report_path = self.project_root / "reports" / "qa" / "demo.json"
        report_path.parent.mkdir(parents=True, exist_ok=True)

        result = self.run_agent(
            "--emit-json",
            "--pack-only",
            "--report",
            str(report_path),
        )

        self.assertEqual(result.returncode, 0, msg=result.stderr)
        pack_path = report_path.with_suffix(".pack.json")
        self.assertTrue(pack_path.exists(), "QA pack should be written")
        self.assertFalse(report_path.exists(), "JSON report should be absent in pack-only mode")

    def test_missing_tests_flags_major_warning(self):
        write_file(self.project_root, "src/main/App.kt", "class App { fun run() = \"ok\" }\n")

        result = self.run_agent("--format", "json")

        self.assertEqual(result.returncode, 0, msg=result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["status"], "WARN")
        self.assertGreaterEqual(payload["counts"].get("major", 0), 1)
        self.assertTrue(
            any(
                finding["severity"] == "major" and finding["scope"] == "tests"
                for finding in payload["findings"]
            )
        )

    def test_tests_not_run_blocks_when_not_allowed(self):
        write_json(
            self.project_root,
            "config/gates.json",
            {
                "tests_required": "hard",
                "qa": {"tests": {"commands": ["echo smoke-test-ok"], "allow_skip": False}},
            },
        )
        result = self.run_agent("--gate", "--emit-json", "--skip-tests")

        self.assertEqual(result.returncode, 2, msg=result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["tests_summary"], "skipped")
        self.assertEqual(payload["status"], "BLOCKED")
        self.assertTrue(any(f["title"] == "Тесты не запускались" for f in payload["findings"]))

    def test_tests_not_run_warns_when_allowed(self):
        write_json(
            self.project_root,
            "config/gates.json",
            {
                "tests_required": "soft",
                "qa": {"tests": {"commands": ["echo smoke-test-ok"], "allow_skip": True}},
            },
        )
        result = self.run_agent("--emit-json", "--skip-tests")

        self.assertEqual(result.returncode, 0, msg=result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["tests_summary"], "skipped")
        self.assertEqual(payload["status"], "WARN")

    def test_tests_metadata_included(self):
        write_json(
            self.project_root,
            "config/gates.json",
            {"qa": {"tests": {"commands": ["false"]}}},
        )
        result = self.run_agent("--format", "json")

        self.assertEqual(result.returncode, 2, msg=result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["tests_summary"], "fail")
        self.assertEqual(len(payload["tests_executed"]), 1)
        self.assertEqual(payload["tests_executed"][0]["status"], "fail")

    def test_tasklist_test_execution_overrides_config(self):
        ticket = "tasklist-tests"
        write_active_feature(self.project_root, ticket)
        tasklist = tasklist_ready_text(ticket)
        tasklist = tasklist.replace("- profile: none\n", "- profile: targeted\n", 1)
        tasklist = tasklist.replace("- tasks: []\n", "- tasks: echo qa-ok\n", 1)
        write_file(self.project_root, f"docs/tasklist/{ticket}.md", tasklist)
        write_json(
            self.project_root,
            "config/gates.json",
            {"qa": {"tests": {"commands": ["false"]}}},
        )
        result = self.run_agent("--format", "json")

        self.assertEqual(result.returncode, 2, msg=result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["tests_summary"], "pass")
        self.assertTrue(payload["tests_executed"], "expected tests from tasklist to run")
        self.assertEqual(payload["tests_executed"][0]["command"], "echo qa-ok")

    def test_tasklist_profile_none_skips_tests_and_writes_stage_result(self):
        ticket = "tasklist-none"
        write_active_feature(self.project_root, ticket)
        tasklist = tasklist_ready_text(ticket)
        write_file(self.project_root, f"docs/tasklist/{ticket}.md", tasklist)
        result = self.run_agent("--format", "json")

        self.assertEqual(result.returncode, 2, msg=result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["tests_summary"], "skipped")
        stage_result = (
            self.project_root
            / "reports"
            / "loops"
            / ticket
            / ticket
            / "stage.qa.result.json"
        )
        self.assertTrue(stage_result.exists(), "QA stage_result should be written")
        stage_payload = json.loads(stage_result.read_text(encoding="utf-8"))
        links = stage_payload.get("evidence_links") or {}
        self.assertEqual(links.get("qa_report"), f"aidd/reports/qa/{ticket}.json")

    def test_qa_skipped_tests_logged_as_skipped(self):
        write_json(
            self.project_root,
            "config/gates.json",
            {
                "tests_required": "soft",
                "qa": {
                    "tests": {
                        "commands": [
                            [
                                "bash",
                                "-lc",
                                "echo \"[format-and-test] Активная стадия 'qa' — форматирование/тесты пропущены.\"",
                            ]
                        ],
                        "allow_skip": True,
                    }
                },
            },
        )
        result = self.run_agent("--format", "json")

        self.assertEqual(result.returncode, 0, msg=result.stderr)
        ticket = "demo-ticket"
        log_path = self.project_root / "reports" / "tests" / ticket / f"{ticket}.jsonl"
        self.assertTrue(log_path.exists(), "QA tests log should be written")
        lines = [line for line in log_path.read_text(encoding="utf-8").splitlines() if line.strip()]
        self.assertTrue(lines, "QA tests log should have entries")
        payload = json.loads(lines[-1])
        self.assertEqual(payload.get("status"), "skipped")

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
                "--ticket",
                slug,
                "--source",
                "qa",
            ),
            cwd=self.project_root,
            text=True,
            capture_output=True,
            env=cli_env(),
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
                "--ticket",
                slug,
                "--source",
                "qa",
            ),
            cwd=self.project_root,
            text=True,
            capture_output=True,
            env=cli_env(),
        )
        self.assertEqual(result_ok.returncode, 0, msg=result_ok.stderr)
        self.assertIn("Прогресс tasklist", result_ok.stdout)

    def test_cli_qa_report_resolves_target_root(self):
        (self.project_root / "docs").mkdir(parents=True, exist_ok=True)
        workdir = self.root
        report_rel = "aidd/reports/qa/demo.json"

        result = subprocess.run(
            cli_cmd(
                "qa",
                "--ticket",
                "DEMO-1",
                "--skip-tests",
                "--allow-no-tests",
                "--report",
                report_rel,
                "--format",
                "json",
            ),
            cwd=workdir,
            text=True,
            capture_output=True,
            env=cli_env(),
        )

        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertTrue((self.project_root / "reports/qa/demo.json").is_file())

    def test_manual_qa_items_set_warn(self):
        write_active_feature(self.project_root, "manual-qa")
        write_file(
            self.project_root,
            "docs/tasklist/manual-qa.md",
            "### AIDD:CHECKLIST_QA\n- [ ] QA: manual regression checklist\n",
        )

        result = self.run_agent("--format", "json")

        self.assertEqual(result.returncode, 0, msg=result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["status"], "WARN")
        self.assertTrue(payload.get("manual_required"))
        self.assertIn("manual", payload["manual_required"][0].lower())

    def test_manual_and_blocker_items_not_deduped(self):
        write_active_feature(self.project_root, "mixed-qa")
        write_file(
            self.project_root,
            "docs/tasklist/mixed-qa.md",
            "### AIDD:CHECKLIST_QA\n- [ ] QA: manual regression checklist\n- [ ] QA: smoke checkout flow\n",
        )

        result = self.run_agent("--format", "json", env={"QA_ALLOW_NO_TESTS": "1"})

        self.assertEqual(result.returncode, 2, msg=result.stderr)
        payload = json.loads(result.stdout)
        checklist = [f for f in payload["findings"] if f.get("scope") == "checklist"]
        severities = {f.get("severity") for f in checklist}
        self.assertIn("major", severities)
        self.assertIn("blocker", severities)
        self.assertEqual(len(checklist), 2)

    def test_dedupes_findings_by_id(self):
        write_active_feature(self.project_root, "dup-qa")
        write_file(
            self.project_root,
            "docs/tasklist/dup-qa.md",
            "### AIDD:CHECKLIST_QA\n- [ ] QA: smoke checkout flow\n- [ ] QA: smoke checkout flow\n",
        )

        result = self.run_agent("--format", "json")

        self.assertEqual(result.returncode, 2, msg=result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(len(payload["findings"]), 1)

    def test_qa_handoff_non_blocking_does_not_block(self):
        write_active_feature(self.project_root, "handoff-qa")
        write_file(
            self.project_root,
            "docs/tasklist/handoff-qa.md",
            """<!-- handoff:qa start -->
- [ ] QA [major] Resolve TODO items (id: qa:todo-001) (Priority: medium) (Blocking: false)
<!-- handoff:qa end -->
""",
        )

        result = self.run_agent("--format", "json")

        self.assertEqual(result.returncode, 0, msg=result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["status"], "WARN")
        self.assertTrue(any(f["severity"] == "major" for f in payload["findings"]))
        self.assertFalse(any(f["severity"] == "blocker" for f in payload["findings"]))
