import datetime as dt
import pathlib
from pathlib import Path
import subprocess
from textwrap import dedent

from .helpers import (
    ensure_gates_config,
    git_config_user,
    git_init,
    run_hook,
    write_active_feature,
    write_file,
    write_json,
)

SRC_PAYLOAD = '{"tool_input":{"file_path":"src/main/kotlin/App.kt"}}'
DOC_PAYLOAD = '{"tool_input":{"file_path":"docs/prd/demo-checkout.prd.md"}}'
PROMPT_PAYLOAD = '{"tool_input":{"file_path":".claude/agents/analyst.md"}}'
CMD_PAYLOAD = '{"tool_input":{"file_path":".claude/commands/plan-new.md"}}'
PROMPT_PAIRS = [
    ("analyst", "idea-new"),
    ("planner", "plan-new"),
    ("implementer", "implement"),
    ("reviewer", "review"),
    ("researcher", "researcher"),
    ("prd-reviewer", "review-prd"),
]
REVIEW_REPORT = '{"summary": "", "findings": []}'


def _timestamp() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def approved_prd(ticket: str = "demo-checkout") -> str:
    return (
        "# PRD\n\n"
        "## Диалог analyst\n"
        "Status: READY\n\n"
        f"Researcher: docs/research/{ticket}.md (Status: reviewed)\n\n"
        "Вопрос 1: Требуется ли отдельный сценарий оплаты?\n"
        "Ответ 1: Покрываем happy-path и отказ платежа.\n\n"
        "## PRD Review\n"
        "Status: approved\n"
    )


def write_research_doc(tmp_path: pathlib.Path, ticket: str = "demo-checkout", status: str = "reviewed") -> None:
    write_file(
        tmp_path,
        f"docs/research/{ticket}.md",
        f"# Research\n\nStatus: {status}\n",
    )


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
    write_file(tmp_path, "docs/prd/demo-checkout.prd.md", approved_prd())
    write_file(tmp_path, "reports/prd/demo-checkout.json", REVIEW_REPORT)
    write_research_doc(tmp_path)

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
        "Researcher: docs/research/demo-checkout.md (Status: pending)\n\n"
        "Вопрос 1: Требуется ли отдельный сценарий оплаты?\n"
        "Ответ 1: Нужен список кейсов, уточнение в процессе.\n\n"
        "## PRD Review\n"
        "Status: pending\n"
    )
    write_file(tmp_path, "docs/prd/demo-checkout.prd.md", blocked_prd)
    write_file(tmp_path, "reports/prd/demo-checkout.json", REVIEW_REPORT)
    write_research_doc(tmp_path)

    result = run_hook(tmp_path, "gate-workflow.sh", SRC_PAYLOAD)
    assert result.returncode == 2
    assert "Status" in result.stdout or "Status" in result.stderr


def test_missing_tasks_blocks(tmp_path):
    write_file(tmp_path, "src/main/kotlin/App.kt", "class App")
    write_active_feature(tmp_path, "demo-checkout")
    write_file(tmp_path, "docs/prd/demo-checkout.prd.md", approved_prd())
    write_file(tmp_path, "docs/plan/demo-checkout.md", "# Plan")
    write_file(tmp_path, "reports/prd/demo-checkout.json", REVIEW_REPORT)
    write_research_doc(tmp_path)

    result = run_hook(tmp_path, "gate-workflow.sh", SRC_PAYLOAD)
    assert result.returncode == 2
    assert "нет задач" in result.stdout or "нет задач" in result.stderr


def test_tasks_with_slug_allow_changes(tmp_path):
    write_file(tmp_path, "src/main/kotlin/App.kt", "class App")
    write_active_feature(tmp_path, "demo-checkout")
    write_file(tmp_path, "docs/prd/demo-checkout.prd.md", approved_prd())
    write_file(tmp_path, "docs/plan/demo-checkout.md", "# Plan")
    write_file(tmp_path, "reports/prd/demo-checkout.json", REVIEW_REPORT)
    write_research_doc(tmp_path)
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


def _ru_prompt(version: str, name: str = "analyst", skip: bool = False) -> str:
    text = dedent(
        f"""
        ---
        name: {name}
        description: test
        lang: ru
        prompt_version: {version}
        source_version: {version}
        tools: Read
        model: inherit
        ---

        ## Контекст
        text

        ## Входные артефакты
        - item

        ## Автоматизация
        text

        ## Пошаговый план
        1. step

        ## Fail-fast и вопросы
        text

        ## Формат ответа
        text
        """
    ).strip() + "\n"
    if skip:
        text = text.replace("model: inherit", "model: inherit\nLang-Parity: skip", 1)
    return text


def _en_prompt(version: str, source: str, name: str = "analyst") -> str:
    return dedent(
        f"""
        ---
        name: {name}
        description: test en
        lang: en
        prompt_version: {version}
        source_version: {source}
        tools: Read
        model: inherit
        ---

        ## Context
        text

        ## Input Artifacts
        - item

        ## Automation
        text

        ## Step-by-step Plan
        1. step

        ## Fail-fast & Questions
        text

        ## Response Format
        text
        """
    ).strip() + "\n"


def test_prompt_locale_mismatch_blocks(tmp_path):
    _seed_prompt_pairs(tmp_path)
    result = run_hook(tmp_path, "gate-workflow.sh", PROMPT_PAYLOAD)
    assert result.returncode == 0, result.stderr

    write_file(tmp_path, ".claude/agents/analyst.md", _ru_prompt("1.0.1"))
    result = run_hook(tmp_path, "gate-workflow.sh", PROMPT_PAYLOAD)
    assert result.returncode == 2
    assert "Lang-Parity" in result.stderr or "Lang-Parity" in result.stdout

    _update_pair_versions(tmp_path, "analyst", "idea-new", "1.0.1")
    result = run_hook(tmp_path, "gate-workflow.sh", PROMPT_PAYLOAD)
    assert result.returncode == 0, result.stderr


def _ru_command(version: str, skip: bool = False, name: str = "plan-new") -> str:
    text = dedent(
        f"""
        ---
        description: "{name}"
        argument-hint: "<TICKET>"
        lang: ru
        prompt_version: {version}
        source_version: {version}
        allowed-tools: Read
        model: inherit
        ---

        ## Контекст
        text

        ## Входные артефакты
        - item

        ## Когда запускать
        text

        ## Автоматические хуки и переменные
        text

        ## Что редактируется
        text

        ## Пошаговый план
        1. step

        ## Fail-fast и вопросы
        text

        ## Ожидаемый вывод
        text

        ## Примеры CLI
        - `/cmd`
        """
    ).strip() + "\n"
    if skip:
        text = text.replace("model: inherit", "model: inherit\nLang-Parity: skip", 1)
    return text


def _en_command(version: str, source: str, name: str = "plan-new") -> str:
    return dedent(
        f"""
        ---
        description: "{name}"
        argument-hint: "<TICKET>"
        lang: en
        prompt_version: {version}
        source_version: {source}
        allowed-tools: Read
        model: inherit
        ---

        ## Context
        text

        ## Input Artifacts
        - item

        ## When to Run
        text

        ## Automation & Hooks
        text

        ## What is Edited
        text

        ## Step-by-step Plan
        1. step

        ## Fail-fast & Questions
        text

        ## Expected Output
        text

        ## CLI Examples
        - `/cmd`
        """
    ).strip() + "\n"


def test_command_locale_mismatch_blocks(tmp_path):
    _seed_prompt_pairs(tmp_path)
    result = run_hook(tmp_path, "gate-workflow.sh", CMD_PAYLOAD)
    assert result.returncode == 0, result.stderr

    write_file(tmp_path, ".claude/commands/plan-new.md", _ru_command("1.0.1"))
    result = run_hook(tmp_path, "gate-workflow.sh", CMD_PAYLOAD)
    assert result.returncode == 2
    assert "Lang-Parity" in result.stderr or "Lang-Parity" in result.stdout

    _apply_lang_parity_skip(tmp_path, "planner", "plan-new", "1.0.1")
    result = run_hook(tmp_path, "gate-workflow.sh", CMD_PAYLOAD)
    assert result.returncode == 0, result.stderr

    _update_pair_versions(tmp_path, "planner", "plan-new", "1.1.0")
    result = run_hook(tmp_path, "gate-workflow.sh", CMD_PAYLOAD)
    assert result.returncode == 0, result.stderr


def _seed_prompt_pairs(root: Path) -> None:
    for agent_name, command_name in PROMPT_PAIRS:
        _update_pair_versions(root, agent_name, command_name, "1.0.0")


def _update_pair_versions(root: Path, agent_name: str, command_name: str, version: str) -> None:
    write_file(root, f".claude/agents/{agent_name}.md", _ru_prompt(version, agent_name))
    write_file(root, f"prompts/en/agents/{agent_name}.md", _en_prompt(version, version, agent_name))
    write_file(root, f".claude/commands/{command_name}.md", _ru_command(version, name=command_name))
    write_file(root, f"prompts/en/commands/{command_name}.md", _en_command(version, version, command_name))


def _apply_lang_parity_skip(root: Path, agent_name: str, command_name: str, version: str) -> None:
    write_file(root, f".claude/agents/{agent_name}.md", _ru_prompt(version, agent_name, skip=True))
    write_file(root, f".claude/commands/{command_name}.md", _ru_command(version, skip=True, name=command_name))
    for path in (
        root / "prompts/en/agents" / f"{agent_name}.md",
        root / "prompts/en/commands" / f"{command_name}.md",
    ):
        if path.exists():
            path.unlink()


def test_allows_pending_research_baseline(tmp_path):
    ensure_gates_config(tmp_path)
    ticket = "demo-checkout"
    write_file(tmp_path, "src/main/kotlin/App.kt", "class App")
    write_active_feature(tmp_path, ticket)
    write_file(tmp_path, f"docs/prd/{ticket}.prd.md", approved_prd(ticket))
    write_file(tmp_path, f"docs/plan/{ticket}.md", "# Plan")
    write_file(tmp_path, f"reports/prd/{ticket}.json", REVIEW_REPORT)
    write_file(
        tmp_path,
        f"docs/tasklist/{ticket}.md",
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
    baseline_doc = (
        "# Research\n\nStatus: pending\n\n## Отсутствие паттернов\n- Контекст пуст, требуется baseline\n"
    )
    write_file(tmp_path, f"docs/research/{ticket}.md", baseline_doc)
    write_json(
        tmp_path,
        f"reports/research/{ticket}-targets.json",
        {
            "ticket": ticket,
            "paths": ["src/main/kotlin"],
            "docs": [f"docs/research/{ticket}.md"],
        },
    )
    now = _timestamp()
    write_json(
        tmp_path,
        f"reports/research/{ticket}-context.json",
        {
            "ticket": ticket,
            "slug": ticket,
            "generated_at": now,
            "matches": [],
            "profile": {"is_new_project": True},
            "auto_mode": True,
        },
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
    write_file(tmp_path, f"docs/prd/{slug}.prd.md", approved_prd(slug))
    write_file(tmp_path, f"docs/plan/{slug}.md", "# Plan")
    write_file(tmp_path, f"reports/prd/{slug}.json", REVIEW_REPORT)
    write_research_doc(tmp_path, slug)
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


def test_reviewer_marker_with_slug_hint(tmp_path):
    ticket = "FEAT-123"
    slug_hint = "checkout-lite"
    write_file(tmp_path, "src/main/kotlin/App.kt", "class App")
    ensure_gates_config(
        tmp_path,
        {
            "prd_review": {"enabled": False},
            "researcher": {"enabled": False},
            "analyst": {"enabled": False},
            "reviewer": {
                "enabled": True,
                "tests_marker": "reports/reviewer/{slug}.json",
                "tests_field": "tests",
                "required_values": ["required"],
                "warn_on_missing": True,
            },
        },
    )
    write_active_feature(tmp_path, ticket, slug_hint=slug_hint)
    write_file(tmp_path, f"docs/prd/{ticket}.prd.md", approved_prd(ticket))
    write_research_doc(tmp_path, ticket)
    write_file(tmp_path, f"docs/plan/{ticket}.md", "# Plan")
    write_file(tmp_path, f"reports/prd/{ticket}.json", REVIEW_REPORT)
    write_file(
        tmp_path,
        f"docs/tasklist/{ticket}.md",
        dedent(
            """\
            ---
            Ticket: FEAT-123
            Slug hint: checkout-lite
            Status: draft
            PRD: docs/prd/FEAT-123.prd.md
            Plan: docs/plan/FEAT-123.md
            Research: docs/research/FEAT-123.md
            Updated: 2024-06-01
            ---

            - [ ] Реализация :: подготовить сервис
            """
        ),
    )
    reviewer_marker = {
        "ticket": ticket,
        "slug": slug_hint,
        "tests": "required",
    }
    write_json(tmp_path, f"reports/reviewer/{slug_hint}.json", reviewer_marker)

    result = run_hook(tmp_path, "gate-workflow.sh", SRC_PAYLOAD)
    assert result.returncode == 0, result.stderr
    combined_output = (result.stdout + result.stderr).lower()
    assert "checkout-lite" in combined_output
    assert "reviewer запросил тесты" in combined_output


def test_documents_are_not_blocked(tmp_path):
    write_active_feature(tmp_path, "demo-checkout")
    # PRD and plan intentionally absent

    result = run_hook(tmp_path, "gate-workflow.sh", DOC_PAYLOAD)
    assert result.returncode == 0, result.stderr
