from __future__ import annotations

from types import SimpleNamespace
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1] / "src"))

from claude_workflow_cli import cli


def test_sync_materialises_claude(tmp_path):
    target = tmp_path / "workspace"
    target.mkdir()

    args = SimpleNamespace(target=str(target), include=None, force=False, dry_run=False)
    cli._sync_command(args)

    settings = target / ".claude" / "settings.json"
    version = target / ".claude" / ".template_version"

    assert settings.exists(), "sync should copy .claude/settings.json"
    assert version.exists(), "sync should record template version when .claude included"
    assert version.read_text(encoding="utf-8").strip() == cli.VERSION


def test_sync_dry_run_does_not_touch_files(tmp_path, capsys):
    target = tmp_path / "workspace"
    target.mkdir()

    args = SimpleNamespace(target=str(target), include=None, force=False, dry_run=True)
    cli._sync_command(args)

    assert not any(target.iterdir()), "dry-run must not create new files"
    out = capsys.readouterr().out
    assert "sync dry-run" in out


def test_sync_custom_include(tmp_path):
    target = tmp_path / "workspace"
    target.mkdir()

    args = SimpleNamespace(
        target=str(target),
        include=["claude-presets"],
        force=False,
        dry_run=False,
    )
    cli._sync_command(args)

    preset = target / "claude-presets" / "feature-prd.yaml"
    assert preset.exists(), "sync should copy requested payload fragments"
    template_version = target / ".claude" / ".template_version"
    assert not template_version.exists(), "template version should not update when .claude not synced"
