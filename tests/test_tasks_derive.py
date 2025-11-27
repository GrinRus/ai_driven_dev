import json
import subprocess
from textwrap import dedent

from .helpers import cli_cmd, write_active_feature, write_file, write_json


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
    write_active_feature(tmp_path, "demo-checkout")
    write_file(tmp_path, "docs/tasklist/demo-checkout.md", _base_tasklist())
    write_json(
        tmp_path,
        "reports/qa/demo-checkout.json",
        {
            "status": "warn",
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
        cwd=tmp_path,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0, result.stderr
    content = (tmp_path / "docs/tasklist/demo-checkout.md").read_text(encoding="utf-8")
    assert "handoff:qa start" in content
    assert "QA [blocker]" in content
    assert "QA [minor]" in content
    assert content.lower().find("## 3. qa") < content.lower().find("handoff:qa"), "block should be under QA section"


def test_tasks_derive_research_appends_existing_block(tmp_path):
    write_active_feature(tmp_path, "demo-checkout")
    base = _base_tasklist() + "\n<!-- handoff:research start (source: reports/research/demo-checkout-context.json) -->\n- [ ] Research: existing item\n<!-- handoff:research end -->\n"
    write_file(tmp_path, "docs/tasklist/demo-checkout.md", base)
    context = {
        "profile": {"recommendations": ["Create baseline dirs"]},
        "manual_notes": ["Check logging"],
        "reuse_candidates": [{"path": "src/payments/Client.kt", "score": 3, "has_tests": True}],
    }
    write_file(
        tmp_path,
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
        cwd=tmp_path,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0, result.stderr
    content = (tmp_path / "docs/tasklist/demo-checkout.md").read_text(encoding="utf-8")
    assert content.count("handoff:research start") == 1
    assert "existing item" in content
    assert "Research: Create baseline dirs" in content
    assert "Reuse candidate: src/payments/Client.kt" in content


def test_tasks_derive_dry_run_does_not_modify(tmp_path):
    write_active_feature(tmp_path, "demo-checkout")
    original = _base_tasklist()
    write_file(tmp_path, "docs/tasklist/demo-checkout.md", original)
    write_json(
        tmp_path,
        "reports/qa/demo-checkout.json",
        {"findings": [{"severity": "blocker", "title": "Regression", "scope": "api"}]},
    )

    result = subprocess.run(
        cli_cmd("tasks-derive", "--source", "qa", "--ticket", "demo-checkout", "--dry-run"),
        cwd=tmp_path,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0, result.stderr
    assert (tmp_path / "docs/tasklist/demo-checkout.md").read_text(encoding="utf-8") == original
