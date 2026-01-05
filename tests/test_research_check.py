from __future__ import annotations

import datetime as dt
from types import SimpleNamespace
from pathlib import Path

import sys

import pytest

sys.path.append(str(Path(__file__).resolve().parents[1] / "src"))

from claude_workflow_cli import cli  # noqa: E402

from .helpers import ensure_gates_config, ensure_project_root, write_active_feature, write_file, write_json


def _setup_workspace(tmp_path: Path) -> tuple[Path, Path]:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    project_root = ensure_project_root(workspace)
    ensure_gates_config(project_root)
    return workspace, project_root


def _timestamp() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def test_research_check_blocks_missing_report(tmp_path):
    workspace, project_root = _setup_workspace(tmp_path)
    ticket = "demo-check"
    write_active_feature(project_root, ticket)

    args = SimpleNamespace(
        target=str(workspace),
        ticket=ticket,
        slug_hint=None,
        branch=None,
    )

    with pytest.raises(RuntimeError) as excinfo:
        cli._research_check_command(args)

    assert "нет отчёта Researcher" in str(excinfo.value)


def test_research_check_passes_with_reviewed_report(tmp_path):
    workspace, project_root = _setup_workspace(tmp_path)
    ticket = "demo-check"
    write_active_feature(project_root, ticket)
    write_file(project_root, f"docs/research/{ticket}.md", "# Research\n\nStatus: reviewed\n")
    write_json(
        project_root,
        f"reports/research/{ticket}-targets.json",
        {"paths": ["src/main"], "docs": [f"docs/research/{ticket}.md"]},
    )
    write_json(
        project_root,
        f"reports/research/{ticket}-context.json",
        {"ticket": ticket, "generated_at": _timestamp(), "profile": {}, "auto_mode": False},
    )

    args = SimpleNamespace(
        target=str(workspace),
        ticket=ticket,
        slug_hint=None,
        branch=None,
    )

    cli._research_check_command(args)
