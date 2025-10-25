import pathlib
import subprocess
from textwrap import dedent

from .helpers import (
    ensure_gates_config,
    git_config_user,
    git_init,
    run_hook,
    write_active_feature,
    write_file,
)

SRC_PAYLOAD = '{"tool_input":{"file_path":"src/main/kotlin/App.kt"}}'
DOC_PAYLOAD = '{"tool_input":{"file_path":"docs/prd/demo-checkout.prd.md"}}'
APPROVED_PRD = (
    "# PRD\n\n"
    "## Диалог analyst\n"
    "Status: READY\n\n"
    "Вопрос 1: Требуется ли отдельный сценарий оплаты?\n"
    "Ответ 1: Покрываем happy-path и отказ платежа.\n\n"
    "## PRD Review\n"
    "Status: approved\n"
)
REVIEW_REPORT = '{"summary": "", "findings": []}'


def test_no_active_feature_allows_changes(tmp_path):
    write_file(tmp_path, "src/main/kotlin/App.kt", "class App")
    result = run_hook(tmp_path, "gate-workflow.sh", SRC_PAYLOAD)
    assert result.returncode == 0, result.stderr


def test_missing_prd_blocks_when_feature_active(tmp_path):
    write_file(tmp_path, "src/main/kotlin/App.kt", "class App")
    write_active_feature(tmp_path, "demo-checkout")

    result = run_hook(tmp_path, "gate-workflow.sh", SRC_PAYLOAD)
    assert result.returncode == 2
    assert "нет PRD" in result.stdout or "нет PRD" in result.stderr


def test_missing_plan_blocks(tmp_path):
    write_file(tmp_path, "src/main/kotlin/App.kt", "class App")
    write_active_feature(tmp_path, "demo-checkout")
    write_file(tmp_path, "docs/prd/demo-checkout.prd.md", APPROVED_PRD)
    write_file(tmp_path, "reports/prd/demo-checkout.json", REVIEW_REPORT)

    result = run_hook(tmp_path, "gate-workflow.sh", SRC_PAYLOAD)
    assert result.returncode == 2
    assert "нет плана" in result.stdout or "нет плана" in result.stderr


def test_blocked_status_blocks(tmp_path):
    write_file(tmp_path, "src/main/kotlin/App.kt", "class App")
    write_active_feature(tmp_path, "demo-checkout")
    blocked_prd = (
        "# PRD\n\n"
        "## Диалог analyst\n"
        "Status: BLOCKED\n\n"
        "Вопрос 1: Требуется ли отдельный сценарий оплаты?\n"
        "Ответ 1: Нужен список кейсов, уточнение в процессе.\n\n"
        "## PRD Review\n"
        "Status: pending\n"
    )
    write_file(tmp_path, "docs/prd/demo-checkout.prd.md", blocked_prd)
    write_file(tmp_path, "reports/prd/demo-checkout.json", REVIEW_REPORT)

    result = run_hook(tmp_path, "gate-workflow.sh", SRC_PAYLOAD)
    assert result.returncode == 2
    assert "Status" in result.stdout or "Status" in result.stderr


def test_missing_tasks_blocks(tmp_path):
    write_file(tmp_path, "src/main/kotlin/App.kt", "class App")
    write_active_feature(tmp_path, "demo-checkout")
    write_file(tmp_path, "docs/prd/demo-checkout.prd.md", APPROVED_PRD)
    write_file(tmp_path, "docs/plan/demo-checkout.md", "# Plan")
    write_file(tmp_path, "reports/prd/demo-checkout.json", REVIEW_REPORT)

    result = run_hook(tmp_path, "gate-workflow.sh", SRC_PAYLOAD)
    assert result.returncode == 2
    assert "нет задач" in result.stdout or "нет задач" in result.stderr


def test_tasks_with_slug_allow_changes(tmp_path):
    write_file(tmp_path, "src/main/kotlin/App.kt", "class App")
    write_active_feature(tmp_path, "demo-checkout")
    write_file(tmp_path, "docs/prd/demo-checkout.prd.md", APPROVED_PRD)
    write_file(tmp_path, "docs/plan/demo-checkout.md", "# Plan")
    write_file(tmp_path, "reports/prd/demo-checkout.json", REVIEW_REPORT)
    write_file(
        tmp_path,
        "docs/tasklist/demo-checkout.md",
        dedent(
            """\
            ---
            Feature: demo-checkout
            Status: draft
            PRD: docs/prd/demo-checkout.prd.md
            Plan: docs/plan/demo-checkout.md
            Research: docs/research/demo-checkout.md
            Updated: 2024-01-01
            ---

            - [ ] QA :: подготовить smoke сценарии
            """
        ),
    )

    result = run_hook(tmp_path, "gate-workflow.sh", SRC_PAYLOAD)
    assert result.returncode == 0, result.stderr


def test_progress_blocks_without_checkbox(tmp_path):
    slug = "demo-checkout"
    git_init(tmp_path)
    git_config_user(tmp_path)
    ensure_gates_config(
        tmp_path,
        {
            "prd_review": {"enabled": False},
            "researcher": {"enabled": False},
            "analyst": {"enabled": False},
            "reviewer": {"enabled": False},
        },
    )

    write_active_feature(tmp_path, slug)
    write_file(tmp_path, f"docs/prd/{slug}.prd.md", APPROVED_PRD)
    write_file(tmp_path, f"docs/plan/{slug}.md", "# Plan")
    write_file(tmp_path, f"reports/prd/{slug}.json", REVIEW_REPORT)
    write_file(
        tmp_path,
        f"docs/tasklist/{slug}.md",
        dedent(
            """\
            ---
            Feature: demo-checkout
            Status: draft
            PRD: docs/prd/demo-checkout.prd.md
            Plan: docs/plan/demo-checkout.md
            Research: docs/research/demo-checkout.md
            Updated: 2024-01-01
            ---

            - [ ] Реализация :: подготовить сервис
            """
        ),
    )
    write_file(
        tmp_path,
        "src/main/kotlin/App.kt",
        "class App {\n    fun call() = \"ok\"\n}\n",
    )

    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "feat: baseline"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )

    write_file(
        tmp_path,
        "src/main/kotlin/App.kt",
        "class App {\n    fun call() = \"updated\"\n}\n",
    )

    result = run_hook(tmp_path, "gate-workflow.sh", SRC_PAYLOAD)
    assert result.returncode == 2
    assert "новых `- [x]`" in result.stdout or "новых `- [x]`" in result.stderr

    write_file(
        tmp_path,
        f"docs/tasklist/{slug}.md",
        dedent(
            """\
            ---
            Feature: demo-checkout
            Status: draft
            PRD: docs/prd/demo-checkout.prd.md
            Plan: docs/plan/demo-checkout.md
            Research: docs/research/demo-checkout.md
            Updated: 2024-01-01
            ---

            - [x] Реализация :: подготовить сервис — 2024-05-01 • итерация 1
            - [ ] QA :: подготовить smoke сценарии
            """
        ),
    )

    result_ok = run_hook(tmp_path, "gate-workflow.sh", SRC_PAYLOAD)
    assert result_ok.returncode == 0, result_ok.stderr


def test_documents_are_not_blocked(tmp_path):
    write_active_feature(tmp_path, "demo-checkout")
    # PRD and plan intentionally absent

    result = run_hook(tmp_path, "gate-workflow.sh", DOC_PAYLOAD)
    assert result.returncode == 0, result.stderr
