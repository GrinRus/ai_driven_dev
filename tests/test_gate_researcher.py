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
        f"reports/research/{ticket}-rlm-targets.json",
        {
            "ticket": ticket,
            "files": ["src/main/kotlin/App.kt"],
            "paths": ["src/main/kotlin"],
            "paths_discovered": [],
            "generated_at": _utc_now(),
        },
    )
    write_json(
        tmp_path,
        f"reports/research/{ticket}-rlm-manifest.json",
        {
            "ticket": ticket,
            "files": [
                {
                    "file_id": "file-app",
                    "path": "src/main/kotlin/App.kt",
                    "rev_sha": "rev-app",
                    "lang": "kt",
                    "size": 10,
                    "prompt_version": "v1",
                }
            ],
        },
    )
    write_json(
        tmp_path,
        f"reports/research/{ticket}-rlm.worklist.pack.json",
        {"schema": "aidd.report.pack.v1", "type": "rlm-worklist", "status": "pending"},
    )


def test_researcher_blocks_pending_baseline_in_downstream_stage(tmp_path):
    ticket = "demo-checkout"
    _setup_common_artifacts(tmp_path, ticket)
    write_file(
        tmp_path,
        f"docs/research/{ticket}.md",
        "# Research\n\nStatus: pending\n\nКонтекст пуст, требуется baseline\n",
    )

    result = run_hook(tmp_path, "gate-workflow.sh", SRC_PAYLOAD)
    assert result.returncode == 2
    combined = (result.stdout + result.stderr).lower()
    assert "reason_code=rlm_status_pending" in combined


def test_researcher_blocks_pending_baseline_without_extra_flags(tmp_path):
    ticket = "demo-checkout"
    _setup_common_artifacts(tmp_path, ticket)
    write_file(
        tmp_path,
        f"docs/research/{ticket}.md",
        "# Research\n\nStatus: pending\n\nКонтекст пуст, требуется baseline\n",
    )

    result = run_hook(tmp_path, "gate-workflow.sh", SRC_PAYLOAD)
    assert result.returncode == 2
    combined = (result.stdout + result.stderr).lower()
    assert "reason_code=rlm_status_pending" in combined


def test_researcher_blocks_pending_without_baseline_marker(tmp_path):
    ticket = "demo-checkout"
    _setup_common_artifacts(tmp_path, ticket)
    write_file(
        tmp_path,
        f"docs/research/{ticket}.md",
        "# Research\n\nStatus: pending\n\n(no baseline note)\n",
    )

    result = run_hook(tmp_path, "gate-workflow.sh", SRC_PAYLOAD)
    assert result.returncode == 2
    combined = (result.stdout + result.stderr).lower()
    assert "pending" in combined or "baseline" in combined


def test_researcher_blocks_missing_report(tmp_path):
    ticket = "demo-checkout"
    _setup_common_artifacts(tmp_path, ticket)
    # Researcher report intentionally missing

    result = run_hook(tmp_path, "gate-workflow.sh", SRC_PAYLOAD)
    assert result.returncode == 2
    combined = (result.stdout + result.stderr).lower()
    assert "reason_code=rlm_status_pending" in combined or "reason_code=research_report_missing" in combined
