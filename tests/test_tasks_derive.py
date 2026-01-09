import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from textwrap import dedent

from .helpers import cli_cmd, ensure_project_root, write_active_feature, write_file, write_json


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
            "--target",
            ".",
        ),
        cwd=project_root,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0, result.stderr
    content = (project_root / "docs/tasklist/demo-checkout.md").read_text(encoding="utf-8")
    assert "handoff:qa start" in content
    assert "QA [blocker]" in content
    assert "QA [minor]" in content
    assert content.lower().find("## 3. qa") < content.lower().find("handoff:qa"), "block should be under QA section"


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
            "rows": [["pytest", "fail", "reports/qa/demo-tests.log", 1]],
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
            "--target",
            ".",
            "--report",
            "reports/qa/demo-checkout.pack.yaml",
        ),
        cwd=project_root,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0, result.stderr
    content = (project_root / "docs/tasklist/demo-checkout.md").read_text(encoding="utf-8")
    assert "QA [major]" in content
    assert "QA tests: fail" in content

def test_tasks_derive_research_appends_existing_block(tmp_path):
    project_root = ensure_project_root(tmp_path)
    write_active_feature(project_root, "demo-checkout")
    base = _base_tasklist() + "\n<!-- handoff:research start (source: reports/research/demo-checkout-context.json) -->\n- [ ] Research: existing item\n<!-- handoff:research end -->\n"
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
            "--target",
            ".",
            "--append",
        ),
        cwd=project_root,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0, result.stderr
    content = (project_root / "docs/tasklist/demo-checkout.md").read_text(encoding="utf-8")
    assert content.count("handoff:research start") == 1
    assert "existing item" in content
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
            "tests_executed": [{"command": "bash scripts/ci-lint.sh", "status": "fail", "log": "reports/qa/demo-tests.log"}],
            "findings": [{"severity": "blocker", "title": "Regression", "scope": "api"}],
        },
    )

    result = subprocess.run(
        cli_cmd("tasks-derive", "--source", "qa", "--ticket", "demo-checkout", "--dry-run"),
        cwd=project_root,
        text=True,
        capture_output=True,
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

    env = os.environ.copy()
    env["AIDD_PACK_FIRST"] = "1"
    result = subprocess.run(
        cli_cmd(
            "tasks-derive",
            "--source",
            "research",
            "--ticket",
            "demo-checkout",
            "--target",
            ".",
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


class TasksDeriveArgsTests(unittest.TestCase):
    def test_tasks_derive_rejects_review_source(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = ensure_project_root(Path(tmpdir))
            write_active_feature(project_root, "demo-checkout")

            result = subprocess.run(
                cli_cmd("tasks-derive", "--source", "review", "--ticket", "demo-checkout"),
                cwd=project_root,
                text=True,
                capture_output=True,
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("invalid choice", (result.stderr or ""))


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

            env = os.environ.copy()
            env.pop("AIDD_INDEX_AUTO", None)
            result = subprocess.run(
                cli_cmd(
                    "tasks-derive",
                    "--source",
                    "qa",
                    "--ticket",
                    "demo-checkout",
                    "--target",
                    ".",
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

            env = os.environ.copy()
            env["AIDD_INDEX_AUTO"] = "0"
            result = subprocess.run(
                cli_cmd(
                    "tasks-derive",
                    "--source",
                    "qa",
                    "--ticket",
                    "demo-checkout",
                    "--target",
                    ".",
                ),
                cwd=project_root,
                text=True,
                capture_output=True,
                env=env,
            )

            self.assertEqual(result.returncode, 0, msg=result.stderr)
            self.assertFalse(index_path.exists())
