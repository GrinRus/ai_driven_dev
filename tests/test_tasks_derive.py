import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from textwrap import dedent

from .helpers import cli_cmd, cli_env, ensure_project_root, write_active_feature, write_file, write_json


def _base_tasklist() -> str:
    return dedent(
        """\
        ---
        Feature: demo-checkout
        Status: draft
        PRD: docs/prd/demo-checkout.prd.md
        Plan: docs/plan/demo-checkout.md
        Research: docs/research/demo-checkout.md
        Updated: 2024-01-01
        ---

        ## AIDD:HANDOFF_INBOX

        ## 1. Аналитика и дизайн
        - [ ] research checklist

        ## 2. Реализация
        - [ ] impl checklist

        ## 3. QA / Проверки
        - [ ] qa checklist
        """
    )


def test_tasks_derive_from_qa_report(tmp_path):
    project_root = ensure_project_root(tmp_path)
    write_active_feature(project_root, "demo-checkout")
    write_file(project_root, "docs/tasklist/demo-checkout.md", _base_tasklist())
    write_json(
        project_root,
        "reports/qa/demo-checkout.json",
        {
            "status": "warn",
            "tests_summary": "pass",
            "tests_executed": [],
            "findings": [
                {"severity": "blocker", "scope": "api", "title": "Regression", "recommendation": "Fix failing flow"},
                {"severity": "minor", "scope": "ui", "title": "Spacing", "details": "Button offset"},
            ],
        },
    )

    result = subprocess.run(
        cli_cmd(
            "tasks-derive",
            "--source",
            "qa",
            "--ticket",
            "demo-checkout",
        ),
        cwd=project_root,
        text=True,
        capture_output=True,
        env=cli_env(),
    )

    assert result.returncode == 0, result.stderr
    content = (project_root / "docs/tasklist/demo-checkout.md").read_text(encoding="utf-8")
    assert "handoff:qa start" in content
    assert "QA [blocker]" in content
    assert "QA [minor]" in content
    assert "Report: aidd/reports/qa/demo-checkout.json" in content
    assert content.lower().find("aidd:handoff_inbox") < content.lower().find("handoff:qa"), "block should be under handoff inbox"


def test_tasks_derive_adds_placeholder_when_qa_empty(tmp_path):
    project_root = ensure_project_root(tmp_path)
    write_active_feature(project_root, "demo-checkout")
    write_file(project_root, "docs/tasklist/demo-checkout.md", _base_tasklist())
    write_json(
        project_root,
        "reports/qa/demo-checkout.json",
        {"tests_summary": "pass", "tests_executed": [], "findings": []},
    )

    result = subprocess.run(
        cli_cmd(
            "tasks-derive",
            "--source",
            "qa",
            "--ticket",
            "demo-checkout",
            "--append",
        ),
        cwd=project_root,
        text=True,
        capture_output=True,
        env=cli_env(),
    )

    assert result.returncode == 0, result.stderr
    content = (project_root / "docs/tasklist/demo-checkout.md").read_text(encoding="utf-8")
    assert "QA report:" in content
    assert "aidd/reports/qa/demo-checkout.json" in content


def test_tasks_derive_from_qa_pack(tmp_path):
    project_root = ensure_project_root(tmp_path)
    write_active_feature(project_root, "demo-checkout")
    write_file(project_root, "docs/tasklist/demo-checkout.md", _base_tasklist())
    pack_payload = {
        "schema": "aidd.report.pack.v1",
        "type": "qa",
        "kind": "report",
        "tests_summary": "fail",
        "tests_executed": {
            "cols": ["command", "status", "log", "exit_code"],
            "rows": [["pytest", "fail", "aidd/reports/qa/demo-tests.log", 1]],
        },
        "findings": {
            "cols": ["severity", "scope", "title", "details", "recommendation"],
            "rows": [["major", "api", "Timeout", "slow response", "Add caching"]],
        },
    }
    write_file(
        project_root,
        "reports/qa/demo-checkout.pack.yaml",
        json.dumps(pack_payload, indent=2),
    )

    result = subprocess.run(
        cli_cmd(
            "tasks-derive",
            "--source",
            "qa",
            "--ticket",
            "demo-checkout",
            "--report",
            "aidd/reports/qa/demo-checkout.pack.yaml",
        ),
        cwd=project_root,
        text=True,
        capture_output=True,
        env=cli_env(),
    )

    assert result.returncode == 0, result.stderr
    content = (project_root / "docs/tasklist/demo-checkout.md").read_text(encoding="utf-8")
    assert "QA [major]" in content
    assert "QA tests failed" in content


def test_tasks_derive_research_appends_existing_block(tmp_path):
    project_root = ensure_project_root(tmp_path)
    write_active_feature(project_root, "demo-checkout")
    base = _base_tasklist() + "\n<!-- handoff:research start (source: aidd/reports/research/demo-checkout-context.json) -->\n- [ ] Research: existing item\n<!-- handoff:research end -->\n"
    write_file(project_root, "docs/tasklist/demo-checkout.md", base)
    context = {
        "profile": {"recommendations": ["Create baseline dirs"]},
        "manual_notes": ["Check logging"],
        "reuse_candidates": [{"path": "src/payments/Client.kt", "score": 3, "has_tests": True}],
    }
    write_file(
        project_root,
        "reports/research/demo-checkout-context.json",
        json.dumps(context, indent=2),
    )

    result = subprocess.run(
        cli_cmd(
            "tasks-derive",
            "--source",
            "research",
            "--ticket",
            "demo-checkout",
            "--append",
        ),
        cwd=project_root,
        text=True,
        capture_output=True,
        env=cli_env(),
    )

    assert result.returncode == 0, result.stderr
    content = (project_root / "docs/tasklist/demo-checkout.md").read_text(encoding="utf-8")
    assert content.count("handoff:research start") == 1
    assert "existing item" not in content
    assert "Research: Create baseline dirs" in content
    assert "Reuse candidate: src/payments/Client.kt" in content


def test_tasks_derive_dry_run_does_not_modify(tmp_path):
    project_root = ensure_project_root(tmp_path)
    write_active_feature(project_root, "demo-checkout")
    original = _base_tasklist()
    write_file(project_root, "docs/tasklist/demo-checkout.md", original)
    write_json(
        project_root,
        "reports/qa/demo-checkout.json",
        {
            "tests_summary": "fail",
            "tests_executed": [{"command": "bash tests/repo_tools/ci-lint.sh", "status": "fail", "log": "aidd/reports/qa/demo-tests.log"}],
            "findings": [{"severity": "blocker", "title": "Regression", "scope": "api"}],
        },
    )

    result = subprocess.run(
        cli_cmd("tasks-derive", "--source", "qa", "--ticket", "demo-checkout", "--dry-run"),
        cwd=project_root,
        text=True,
        capture_output=True,
        env=cli_env(),
    )

    assert result.returncode == 0, result.stderr
    assert (project_root / "docs/tasklist/demo-checkout.md").read_text(encoding="utf-8") == original
    assert "QA tests:" in result.stdout


def test_tasks_derive_prefers_pack_for_research(tmp_path):
    project_root = ensure_project_root(tmp_path)
    write_active_feature(project_root, "demo-checkout")
    write_file(project_root, "docs/tasklist/demo-checkout.md", _base_tasklist())
    write_json(
        project_root,
        "reports/research/demo-checkout-context.json",
        {
            "profile": {"recommendations": ["from json"]},
            "manual_notes": [],
            "reuse_candidates": [],
        },
    )
    pack_payload = {
        "schema": "aidd.report.pack.v1",
        "type": "research",
        "kind": "context",
        "profile": {"recommendations": ["from pack"]},
        "manual_notes": [],
        "reuse_candidates": [],
    }
    write_file(
        project_root,
        "reports/research/demo-checkout-context.pack.yaml",
        json.dumps(pack_payload, indent=2),
    )

    env = cli_env()
    env["AIDD_PACK_FIRST"] = "1"
    result = subprocess.run(
        cli_cmd(
            "tasks-derive",
            "--source",
            "research",
            "--ticket",
            "demo-checkout",
        ),
        cwd=project_root,
        text=True,
        capture_output=True,
            env=env,
        )

    assert result.returncode == 0, result.stderr
    content = (project_root / "docs/tasklist/demo-checkout.md").read_text(encoding="utf-8")
    assert "Research: from pack" in content
    assert "Research: from json" not in content


def test_tasks_derive_from_review_report(tmp_path):
    project_root = ensure_project_root(tmp_path)
    write_active_feature(project_root, "demo-checkout")
    write_file(project_root, "docs/tasklist/demo-checkout.md", _base_tasklist())
    write_json(
        project_root,
        "reports/reviewer/demo-checkout.json",
        {
            "kind": "review",
            "status": "warn",
            "findings": [
                {"severity": "major", "scope": "api", "title": "Null guard", "recommendation": "Add guard"},
            ],
        },
    )

    result = subprocess.run(
        cli_cmd(
            "tasks-derive",
            "--source",
            "review",
            "--ticket",
            "demo-checkout",
            "--append",
        ),
        cwd=project_root,
        text=True,
        capture_output=True,
        env=cli_env(),
    )

    assert result.returncode == 0, result.stderr
    content = (project_root / "docs/tasklist/demo-checkout.md").read_text(encoding="utf-8")
    assert "handoff:review start" in content
    assert "Review [major]" in content
    assert "aidd/reports/reviewer/demo-checkout.json" in content


def test_tasks_derive_idempotent_by_id(tmp_path):
    project_root = ensure_project_root(tmp_path)
    write_active_feature(project_root, "demo-checkout")
    write_file(project_root, "docs/tasklist/demo-checkout.md", _base_tasklist())
    write_json(
        project_root,
        "reports/qa/demo-checkout.json",
        {
            "status": "warn",
            "tests_summary": "pass",
            "tests_executed": [],
            "findings": [
                {
                    "id": "qa-1",
                    "severity": "minor",
                    "scope": "ui",
                    "title": "Spacing",
                    "recommendation": "Fix spacing v1",
                },
            ],
        },
    )

    result = subprocess.run(
        cli_cmd(
            "tasks-derive",
            "--source",
            "qa",
            "--ticket",
            "demo-checkout",
            "--append",
        ),
        cwd=project_root,
        text=True,
        capture_output=True,
        env=cli_env(),
    )
    assert result.returncode == 0, result.stderr

    write_json(
        project_root,
        "reports/qa/demo-checkout.json",
        {
            "status": "warn",
            "tests_summary": "pass",
            "tests_executed": [],
            "findings": [
                {
                    "id": "qa-1",
                    "severity": "minor",
                    "scope": "ui",
                    "title": "Spacing",
                    "recommendation": "Fix spacing v2",
                },
            ],
        },
    )
    result = subprocess.run(
        cli_cmd(
            "tasks-derive",
            "--source",
            "qa",
            "--ticket",
            "demo-checkout",
            "--append",
        ),
        cwd=project_root,
        text=True,
        capture_output=True,
        env=cli_env(),
    )
    assert result.returncode == 0, result.stderr

    content = (project_root / "docs/tasklist/demo-checkout.md").read_text(encoding="utf-8")
    assert content.count("id: qa:qa-1") == 1
    assert "Fix spacing v2" in content
    assert "Fix spacing v1" not in content


def test_tasks_derive_replaces_legacy_without_id(tmp_path):
    project_root = ensure_project_root(tmp_path)
    write_active_feature(project_root, "demo-checkout")
    base = _base_tasklist() + "\n<!-- handoff:qa start (source: aidd/reports/qa/demo-checkout.json) -->\n- [ ] QA [minor] Spacing (source: aidd/reports/qa/demo-checkout.json)\n<!-- handoff:qa end -->\n"
    write_file(project_root, "docs/tasklist/demo-checkout.md", base)
    write_json(
        project_root,
        "reports/qa/demo-checkout.json",
        {
            "status": "warn",
            "tests_summary": "pass",
            "tests_executed": [],
            "findings": [
                {
                    "severity": "minor",
                    "scope": "",
                    "title": "Spacing",
                    "recommendation": "Fix spacing v2",
                },
            ],
        },
    )

    result = subprocess.run(
        cli_cmd(
            "tasks-derive",
            "--source",
            "qa",
            "--ticket",
            "demo-checkout",
            "--append",
        ),
        cwd=project_root,
        text=True,
        capture_output=True,
        env=cli_env(),
    )
    assert result.returncode == 0, result.stderr

    content = (project_root / "docs/tasklist/demo-checkout.md").read_text(encoding="utf-8")
    assert content.count("QA [minor] Spacing") == 1
    assert "id: qa:" in content


def test_tasks_derive_preserves_multiline_task_details(tmp_path):
    project_root = ensure_project_root(tmp_path)
    write_active_feature(project_root, "demo-checkout")
    base = _base_tasklist() + dedent(
        """
        <!-- handoff:qa start (source: aidd/reports/qa/demo-checkout.json) -->
        - [ ] QA [minor] Spacing — Fix spacing v1 (source: aidd/reports/qa/demo-checkout.json, id: qa:qa-1)
          - scope: ui
          - DoD: spacing matches design
          - Boundaries:
            - must-touch: ["src/ui/"]
            - must-not-touch: []
          - Tests:
            - profile: fast
            - tasks: []
            - filters: []
          - Notes: existing
        <!-- handoff:qa end -->
        """
    )
    write_file(project_root, "docs/tasklist/demo-checkout.md", base)
    write_json(
        project_root,
        "reports/qa/demo-checkout.json",
        {
            "status": "warn",
            "tests_summary": "pass",
            "tests_executed": [],
            "findings": [
                {
                    "id": "qa-1",
                    "severity": "minor",
                    "scope": "ui",
                    "title": "Spacing",
                    "recommendation": "Fix spacing v2",
                },
            ],
        },
    )

    result = subprocess.run(
        cli_cmd(
            "tasks-derive",
            "--source",
            "qa",
            "--ticket",
            "demo-checkout",
            "--append",
        ),
        cwd=project_root,
        text=True,
        capture_output=True,
        env=cli_env(),
    )
    assert result.returncode == 0, result.stderr

    content = (project_root / "docs/tasklist/demo-checkout.md").read_text(encoding="utf-8")
    assert content.count("id: qa:qa-1") == 1
    assert "Fix spacing v2" in content
    assert "Fix spacing v1" not in content
    assert "DoD: spacing matches design" in content
    assert "DoD: Fix spacing v2" not in content
    assert 'must-touch: ["src/ui/"]' in content
    assert "profile: fast" in content
    assert "Notes: existing" in content


class TasksDeriveArgsTests(unittest.TestCase):
    def test_tasks_derive_allows_review_source(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = ensure_project_root(Path(tmpdir))
            write_active_feature(project_root, "demo-checkout")
            write_file(project_root, "docs/tasklist/demo-checkout.md", _base_tasklist())
            write_json(
                project_root,
                "reports/reviewer/demo-checkout.json",
                {"kind": "review", "findings": [{"severity": "minor", "title": "Lint", "id": "review-1"}]},
            )

            result = subprocess.run(
                cli_cmd("tasks-derive", "--source", "review", "--ticket", "demo-checkout"),
                cwd=project_root,
                text=True,
                capture_output=True,
                env=cli_env(),
            )

            self.assertEqual(result.returncode, 0, msg=result.stderr)


class TasksDeriveIndexAutoSyncTests(unittest.TestCase):
    def test_tasks_derive_updates_index(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = ensure_project_root(Path(tmpdir))
            write_active_feature(project_root, "demo-checkout")
            write_file(project_root, "docs/tasklist/demo-checkout.md", _base_tasklist())
            write_json(
                project_root,
                "reports/qa/demo-checkout.json",
                {
                    "status": "warn",
                    "tests_summary": "pass",
                    "tests_executed": [],
                    "findings": [
                        {"severity": "minor", "scope": "ui", "title": "Spacing", "details": "Button offset"},
                    ],
                },
            )

            index_path = project_root / "docs" / "index" / "demo-checkout.yaml"
            self.assertFalse(index_path.exists())

            env = cli_env()
            env.pop("AIDD_INDEX_AUTO", None)
            result = subprocess.run(
                cli_cmd(
                    "tasks-derive",
                    "--source",
                    "qa",
                    "--ticket",
                    "demo-checkout",
                ),
                cwd=project_root,
                text=True,
                capture_output=True,
                env=env,
            )

            self.assertEqual(result.returncode, 0, msg=result.stderr)
            self.assertTrue(index_path.exists())
            payload = json.loads(index_path.read_text(encoding="utf-8"))
            self.assertEqual(payload.get("ticket"), "demo-checkout")

    def test_tasks_derive_skips_index_when_disabled(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = ensure_project_root(Path(tmpdir))
            write_active_feature(project_root, "demo-checkout")
            write_file(project_root, "docs/tasklist/demo-checkout.md", _base_tasklist())
            write_json(
                project_root,
                "reports/qa/demo-checkout.json",
                {
                    "status": "warn",
                    "tests_summary": "pass",
                    "tests_executed": [],
                    "findings": [
                        {"severity": "minor", "scope": "ui", "title": "Spacing", "details": "Button offset"},
                    ],
                },
            )

            index_path = project_root / "docs" / "index" / "demo-checkout.yaml"
            self.assertFalse(index_path.exists())

            env = cli_env()
            env["AIDD_INDEX_AUTO"] = "0"
            result = subprocess.run(
                cli_cmd(
                    "tasks-derive",
                    "--source",
                    "qa",
                    "--ticket",
                    "demo-checkout",
                ),
                cwd=project_root,
                text=True,
                capture_output=True,
                env=env,
            )

            self.assertEqual(result.returncode, 0, msg=result.stderr)
            self.assertFalse(index_path.exists())
