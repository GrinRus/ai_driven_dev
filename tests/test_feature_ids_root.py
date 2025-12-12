import os
from pathlib import Path
import tempfile

import pytest

from claude_workflow_cli.feature_ids import resolve_project_root


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    """Ensure path resolution tests are not polluted by caller env."""
    monkeypatch.delenv("CLAUDE_PLUGIN_ROOT", raising=False)
    monkeypatch.delenv("CLAUDE_PROJECT_DIR", raising=False)


def test_prefers_plugin_root(monkeypatch):
    with tempfile.TemporaryDirectory(prefix="feature-ids-") as tmp:
        base = Path(tmp)
        plugin = base / "aidd"
        (plugin / "docs").mkdir(parents=True)
        monkeypatch.setenv("CLAUDE_PLUGIN_ROOT", str(plugin))

        resolved = resolve_project_root(base)

        assert resolved == plugin.resolve()


def test_prefers_aidd_subdir_when_present(monkeypatch):
    with tempfile.TemporaryDirectory(prefix="feature-ids-") as tmp:
        base = Path(tmp)
        aidd = base / "aidd"
        (aidd / "docs").mkdir(parents=True)

        resolved = resolve_project_root(base)

        assert resolved == aidd.resolve()


def test_falls_back_to_cwd_docs(monkeypatch):
    with tempfile.TemporaryDirectory(prefix="feature-ids-") as tmp:
        base = Path(tmp)
        (base / "docs").mkdir(parents=True)

        resolved = resolve_project_root(base)

        assert resolved == base.resolve()


def test_uses_project_dir_as_last_resort(monkeypatch):
    with tempfile.TemporaryDirectory(prefix="feature-ids-") as tmp:
        base = Path(tmp)
        project = base / "project-root"
        (project / "docs").mkdir(parents=True)
        monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(project))

        resolved = resolve_project_root(base)

        assert resolved == project.resolve()
