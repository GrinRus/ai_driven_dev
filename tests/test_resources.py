from pathlib import Path
import sys

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from claude_workflow_cli import cli
from claude_workflow_cli.resources import DEFAULT_PROJECT_SUBDIR, resolve_project_root


def test_resolve_project_root_treats_target_as_workspace(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    workspace_root, project_root = resolve_project_root(workspace)

    assert workspace_root == workspace.resolve()
    assert project_root == workspace.resolve() / DEFAULT_PROJECT_SUBDIR


def test_resolve_project_root_when_target_is_project_dir(tmp_path):
    project_dir = tmp_path / "workspace" / DEFAULT_PROJECT_SUBDIR
    project_dir.mkdir(parents=True)

    workspace_root, project_root = resolve_project_root(project_dir)

    assert workspace_root == project_dir.parent.resolve()
    assert project_root == project_dir.resolve()


def test_require_workflow_root_errors_when_missing_payload(tmp_path):
    workspace = tmp_path / "ws"
    workspace.mkdir()
    # project exists but not initialised
    project_root = workspace / DEFAULT_PROJECT_SUBDIR
    project_root.mkdir()

    with pytest.raises(FileNotFoundError) as excinfo:
        cli._require_workflow_root(workspace)

    message = str(excinfo.value)
    assert f"{project_root}/.claude" in message
    assert "claude-workflow init --target" in message


def test_resolve_roots_creates_project_on_demand(tmp_path):
    workspace = tmp_path / "ws"
    workspace.mkdir()

    workspace_root, project_root = cli._resolve_roots(workspace, create=True)

    assert workspace_root == workspace.resolve()
    assert project_root == workspace.resolve() / DEFAULT_PROJECT_SUBDIR
    assert project_root.is_dir()


def test_resolve_roots_errors_when_project_missing(tmp_path):
    workspace = tmp_path / "ws"
    workspace.mkdir()

    with pytest.raises(FileNotFoundError) as excinfo:
        cli._resolve_roots(workspace, create=False)

    message = str(excinfo.value)
    assert "workflow not found at" in message
    assert f"claude-workflow init --target {workspace.resolve()}" in message
