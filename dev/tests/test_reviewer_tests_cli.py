from __future__ import annotations

import json
from pathlib import Path

import sys

sys.path.append(str(Path(__file__).resolve().parents[2]))

from tools import reviewer_tests  # noqa: E402

from .helpers import ensure_project_root, write_active_feature


def prepare_workspace(tmp_path: Path) -> Path:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    project_root = ensure_project_root(workspace)
    # seed active feature and reviewer folder
    write_active_feature(project_root, "demo")
    return workspace


def test_reviewer_tests_command_updates_marker(tmp_path, monkeypatch):
    workspace = prepare_workspace(tmp_path)
    monkeypatch.setenv("USER", "ci-tester")

    reviewer_tests.main(
        [
            "--target",
            str(workspace),
            "--ticket",
            "demo",
            "--status",
            "required",
        ]
    )

    marker = workspace / "aidd" / "reports" / "reviewer" / "demo.json"
    assert marker.exists(), "marker should be created for required tests"
    data = json.loads(marker.read_text(encoding="utf-8"))
    assert data["tests"] == "required"
    assert data["ticket"] == "demo"
    assert data["requested_by"] == "ci-tester"
    assert "updated_at" in data

    reviewer_tests.main(
        [
            "--target",
            str(workspace),
            "--ticket",
            "demo",
            "--status",
            "optional",
            "--note",
            "smoke passed",
        ]
    )

    data = json.loads(marker.read_text(encoding="utf-8"))
    assert data["tests"] == "optional"
    assert data["note"] == "smoke passed"

    reviewer_tests.main(
        [
            "--target",
            str(workspace),
            "--ticket",
            "demo",
            "--status",
            "optional",
            "--clear",
        ]
    )
    assert not marker.exists(), "marker should be removed on --clear"


def test_reviewer_tests_rejects_unknown_status(tmp_path, monkeypatch):
    workspace = prepare_workspace(tmp_path)
    monkeypatch.setenv("USER", "ci-tester")

    try:
        reviewer_tests.main(
            [
                "--target",
                str(workspace),
                "--ticket",
                "demo",
                "--status",
                "unexpected",
            ]
        )
    except ValueError as exc:
        assert "status must be one of" in str(exc)
    else:
        raise AssertionError("command should reject unsupported status")
