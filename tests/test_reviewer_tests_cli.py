from __future__ import annotations

import json
from types import SimpleNamespace
from pathlib import Path

import sys

sys.path.append(str(Path(__file__).resolve().parents[1] / "src"))

from claude_workflow_cli import cli  # noqa: E402

from .helpers import REPO_ROOT


def prepare_workspace(tmp_path: Path) -> Path:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    settings_src = REPO_ROOT / ".claude" / "settings.json"
    settings_dst = workspace / ".claude" / "settings.json"
    settings_dst.parent.mkdir(parents=True, exist_ok=True)
    settings_dst.write_text(settings_src.read_text(encoding="utf-8"), encoding="utf-8")
    return workspace


def test_reviewer_tests_command_updates_marker(tmp_path, monkeypatch):
    workspace = prepare_workspace(tmp_path)
    monkeypatch.setenv("USER", "ci-tester")

    args = SimpleNamespace(
        target=str(workspace),
        ticket="demo",
        status="required",
        note=None,
        requested_by=None,
        clear=False,
    )

    cli._reviewer_tests_command(args)

    marker = workspace / "reports" / "reviewer" / "demo.json"
    assert marker.exists(), "marker should be created for required tests"
    data = json.loads(marker.read_text(encoding="utf-8"))
    assert data["tests"] == "required"
    assert data["ticket"] == "demo"
    assert data["requested_by"] == "ci-tester"
    assert "updated_at" in data

    args.status = "optional"
    args.note = "smoke passed"
    cli._reviewer_tests_command(args)

    data = json.loads(marker.read_text(encoding="utf-8"))
    assert data["tests"] == "optional"
    assert data["note"] == "smoke passed"

    args.clear = True
    cli._reviewer_tests_command(args)
    assert not marker.exists(), "marker should be removed on --clear"


def test_reviewer_tests_rejects_unknown_status(tmp_path, monkeypatch):
    workspace = prepare_workspace(tmp_path)
    monkeypatch.setenv("USER", "ci-tester")

    args = SimpleNamespace(
        target=str(workspace),
        ticket="demo",
        status="unexpected",
        note=None,
        requested_by=None,
        clear=False,
    )

    try:
        cli._reviewer_tests_command(args)
    except ValueError as exc:
        assert "status must be one of" in str(exc)
    else:
        raise AssertionError("command should reject unsupported status")
