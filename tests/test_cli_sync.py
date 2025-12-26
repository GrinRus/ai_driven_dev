from __future__ import annotations

from types import SimpleNamespace
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1] / "src"))

from claude_workflow_cli import cli


PAYLOAD_ROOT = Path(__file__).resolve().parents[1] / "src" / "claude_workflow_cli" / "data" / "payload"


def _clean_payload_pycache() -> None:
    if not PAYLOAD_ROOT.exists():
        return
    for pycache in PAYLOAD_ROOT.rglob("__pycache__"):
        if pycache.is_dir():
            for child in pycache.iterdir():
                child.unlink()
            pycache.rmdir()


def test_sync_materialises_claude(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    project_root = workspace / "aidd"

    _clean_payload_pycache()
    args = SimpleNamespace(target=str(workspace), include=None, force=False, dry_run=False, release=None, cache_dir=None)
    cli._sync_command(args)

    settings = workspace / ".claude" / "settings.json"
    version = workspace / ".claude" / ".template_version"

    assert settings.exists(), "sync should copy .claude/settings.json"
    assert version.exists(), "sync should record template version when .claude included"
    assert version.read_text(encoding="utf-8").strip() == cli.VERSION


def test_sync_dry_run_does_not_touch_files(tmp_path, capsys):
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    _clean_payload_pycache()
    args = SimpleNamespace(target=str(workspace), include=None, force=False, dry_run=True, release=None, cache_dir=None)
    cli._sync_command(args)

    assert not any(workspace.iterdir()), "dry-run must not create new files"
    out = capsys.readouterr().out
    assert "sync dry-run" in out


def test_sync_custom_include(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    project_root = workspace / "aidd"

    _clean_payload_pycache()
    args = SimpleNamespace(
        target=str(workspace),
        include=["claude-presets"],
        force=False,
        dry_run=False,
        release=None,
        cache_dir=None,
    )
    cli._sync_command(args)

    preset = project_root / "claude-presets" / "feature-prd.yaml"
    assert preset.exists(), "sync should copy requested payload fragments"
    template_version = workspace / ".claude" / ".template_version"
    assert not template_version.exists(), "template version should not update when .claude not synced"


def test_sync_supports_claude_include(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    project_root = workspace / "aidd"

    _clean_payload_pycache()
    args = SimpleNamespace(
        target=str(workspace),
        include=["CLAUDE.md"],
        force=False,
        dry_run=False,
        release=None,
        cache_dir=None,
    )
    cli._sync_command(args)

    claude_doc = project_root / "CLAUDE.md"
    assert claude_doc.exists(), "sync should copy CLAUDE.md when explicitly requested"
