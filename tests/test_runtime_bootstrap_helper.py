from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

from tests.helpers import REPO_ROOT

from aidd_runtime import _bootstrap


TOP_LEVEL_RUNTIME_ENTRYPOINTS = [
    REPO_ROOT / "aidd_runtime" / "init.py",
    REPO_ROOT / "aidd_runtime" / "tasks_new.py",
    REPO_ROOT / "aidd_runtime" / "analyst_check.py",
    REPO_ROOT / "aidd_runtime" / "analyst_guard.py",
    REPO_ROOT / "aidd_runtime" / "claude_stream_render.py",
    REPO_ROOT / "aidd_runtime" / "index_sync.py",
    REPO_ROOT / "aidd_runtime" / "research.py",
    REPO_ROOT / "aidd_runtime" / "research_check.py",
    REPO_ROOT / "aidd_runtime" / "research_guard.py",
    REPO_ROOT / "aidd_runtime" / "prd_check.py",
    REPO_ROOT / "aidd_runtime" / "prd_review.py",
    REPO_ROOT / "aidd_runtime" / "status.py",
    REPO_ROOT / "aidd_runtime" / "implement_run.py",
    REPO_ROOT / "aidd_runtime" / "review_run.py",
    REPO_ROOT / "aidd_runtime" / "qa_run.py",
    REPO_ROOT / "aidd_runtime" / "loop_run.py",
    REPO_ROOT / "aidd_runtime" / "loop_step.py",
    REPO_ROOT / "aidd_runtime" / "set_active_stage.py",
    REPO_ROOT / "aidd_runtime" / "set_active_feature.py",
    REPO_ROOT / "aidd_runtime" / "tools_inventory.py",
]


def test_ensure_repo_root_overrides_invalid_claude_plugin_root(monkeypatch):
    bogus_root = REPO_ROOT / "skills"
    start_file = REPO_ROOT / "skills" / "qa" / "runtime" / "qa_run.py"

    monkeypatch.setenv("CLAUDE_PLUGIN_ROOT", str(bogus_root))
    monkeypatch.delenv("AIDD_PLUGIN_DIR", raising=False)

    resolved = _bootstrap.ensure_repo_root(start_file)

    assert resolved == REPO_ROOT
    assert Path(os.environ["CLAUDE_PLUGIN_ROOT"]).resolve() == REPO_ROOT


def test_ensure_repo_root_accepts_aidd_plugin_dir_and_normalizes_env(monkeypatch):
    start_file = REPO_ROOT / "skills" / "review" / "runtime" / "review_run.py"

    monkeypatch.delenv("CLAUDE_PLUGIN_ROOT", raising=False)
    monkeypatch.setenv("AIDD_PLUGIN_DIR", str(REPO_ROOT))

    resolved = _bootstrap.ensure_repo_root(start_file)

    assert resolved == REPO_ROOT
    assert Path(os.environ["CLAUDE_PLUGIN_ROOT"]).resolve() == REPO_ROOT
    assert Path(os.environ["AIDD_PLUGIN_DIR"]).resolve() == REPO_ROOT


def test_runtime_entrypoint_help_recovers_from_invalid_plugin_root_env(tmp_path):
    entrypoint = REPO_ROOT / "skills" / "qa" / "runtime" / "qa_run.py"
    env = os.environ.copy()
    env["CLAUDE_PLUGIN_ROOT"] = str(REPO_ROOT / "skills")
    env.pop("AIDD_PLUGIN_DIR", None)
    env.pop("PYTHONPATH", None)
    env["PYTHONDONTWRITEBYTECODE"] = "1"

    result = subprocess.run(
        [sys.executable, str(entrypoint), "--help"],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "usage:" in ((result.stdout or "") + (result.stderr or "")).lower()


@pytest.mark.parametrize("entrypoint", TOP_LEVEL_RUNTIME_ENTRYPOINTS)
def test_top_level_runtime_entrypoint_help_recovers_from_invalid_plugin_root_env(tmp_path, entrypoint: Path):
    env = os.environ.copy()
    env["CLAUDE_PLUGIN_ROOT"] = str(REPO_ROOT / "skills")
    env.pop("AIDD_PLUGIN_DIR", None)
    env.pop("PYTHONPATH", None)
    env["PYTHONDONTWRITEBYTECODE"] = "1"

    result = subprocess.run(
        [sys.executable, str(entrypoint), "--help"],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, f"{entrypoint.name}: {result.stderr}"
    assert "usage:" in ((result.stdout or "") + (result.stderr or "")).lower()
