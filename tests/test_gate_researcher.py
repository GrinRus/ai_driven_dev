import datetime as dt
import json
from pathlib import Path

from .helpers import (
    DEFAULT_GATES_CONFIG,
    REPO_ROOT,
    ensure_gates_config,
    run_hook,
    write_active_feature,
    write_file,
    write_json,
    write_tasklist_ready,
)


SRC_PAYLOAD = '{"tool_input":{"file_path":"src/main/kotlin/App.kt"}}'


def _utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _setup_common_artifacts(tmp_path: Path, ticket: str = "demo-checkout") -> None:
    researcher_cfg = DEFAULT_GATES_CONFIG["researcher"].copy()
    researcher_cfg["require_for_branches"] = ["feature/*", "release/*", "hotfix/*"]
    ensure_gates_config(
        tmp_path,
        {
            "reviewer": {"enabled": False},
            "researcher": researcher_cfg,
        },
    )
    write_active_feature(tmp_path, ticket)
    write_file(tmp_path, "src/main/kotlin/App.kt", "class App")
    prd_body = (
        "# PRD\n\n"
        "## Диалог analyst\n"
        "Status: READY\n\n"
        "Вопрос 1: Какие этапы покрываем?\n"
        "Ответ 1: Happy-path и отказ оплаты.\n\n"
        f"Researcher: docs/research/{ticket}.md (Status: pending)\n\n"
        "## PRD Review\n"
        "Status: READY\n"
    )
    write_file(tmp_path, f"docs/prd/{ticket}.prd.md", prd_body)
    write_json(tmp_path, f"reports/prd/{ticket}.json", {"status": "ready", "findings": []})
    write_file(
        tmp_path,
        f"docs/plan/{ticket}.md",
        "# Plan\n\n## Architecture & Patterns\n- service layer\n\n## Plan Review\nStatus: READY\n",
    )
    write_tasklist_ready(tmp_path, ticket)
    write_json(
        tmp_path,
        f"reports/research/{ticket}-targets.json",
        {"ticket": ticket, "paths": ["src"], "docs": ["docs"], "generated_at": _utc_now()},
    )
    write_json(
        tmp_path,
        f"reports/research/{ticket}-ast-grep.pack.yaml",
        {"type": "ast-grep", "status": "ok"},
    )


def _write_context(
    tmp_path: Path,
    ticket: str,
    *,
    is_new: bool,
    auto_mode: bool,
    call_graph_engine: str = "auto",
) -> None:
    write_json(
        tmp_path,
        f"reports/research/{ticket}-context.json",
        {
            "ticket": ticket,
            "generated_at": _utc_now(),
            "profile": {"is_new_project": is_new},
            "auto_mode": auto_mode,
            "import_graph": [],
            "call_graph_engine": call_graph_engine,
            "call_graph_supported_languages": [],
            "call_graph_filter": "",
            "call_graph_limit": 300,
            "call_graph_warning": "",
        },
    )


def test_researcher_allows_pending_baseline_with_auto_and_new_project(tmp_path):
    ticket = "demo-checkout"
    _setup_common_artifacts(tmp_path, ticket)
    write_file(
        tmp_path,
        f"docs/research/{ticket}.md",
        "# Research\n\nStatus: pending\n\nКонтекст пуст, требуется baseline\n",
    )
    _write_context(tmp_path, ticket, is_new=True, auto_mode=True)

    result = run_hook(tmp_path, "gate-workflow.sh", SRC_PAYLOAD)
    assert result.returncode == 0, result.stderr


def test_researcher_allows_graph_engine_none_for_baseline(tmp_path):
    ticket = "demo-checkout"
    _setup_common_artifacts(tmp_path, ticket)
    write_file(
        tmp_path,
        f"docs/research/{ticket}.md",
        "# Research\n\nStatus: pending\n\nКонтекст пуст, требуется baseline\n",
    )
    _write_context(tmp_path, ticket, is_new=True, auto_mode=True, call_graph_engine="none")

    result = run_hook(tmp_path, "gate-workflow.sh", SRC_PAYLOAD)
    assert result.returncode == 0, result.stderr


def test_researcher_blocks_pending_without_baseline_marker(tmp_path):
    ticket = "demo-checkout"
    _setup_common_artifacts(tmp_path, ticket)
    write_file(
        tmp_path,
        f"docs/research/{ticket}.md",
        "# Research\n\nStatus: pending\n\n(no baseline note)\n",
    )
    _write_context(tmp_path, ticket, is_new=True, auto_mode=True)

    result = run_hook(tmp_path, "gate-workflow.sh", SRC_PAYLOAD)
    assert result.returncode == 2
    combined = (result.stdout + result.stderr).lower()
    assert "pending" in combined or "baseline" in combined


def test_researcher_blocks_missing_report(tmp_path):
    ticket = "demo-checkout"
    _setup_common_artifacts(tmp_path, ticket)
    # Researcher report intentionally missing
    _write_context(tmp_path, ticket, is_new=False, auto_mode=False)

    result = run_hook(tmp_path, "gate-workflow.sh", SRC_PAYLOAD)
    assert result.returncode == 2
    combined = (result.stdout + result.stderr).lower()
    assert "researcher" in combined or "отчёт" in combined or "report" in combined
