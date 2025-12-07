from __future__ import annotations

import shutil
import subprocess
import zipfile
from pathlib import Path
import os


def test_payload_includes_dotfiles(tmp_path):
    project_root = Path(__file__).resolve().parents[1]
    dist_dir = project_root / "dist"
    if dist_dir.exists():
        shutil.rmtree(dist_dir)

    subprocess.run(
        ["python3", "-m", "build", "--wheel"],
        check=True,
        cwd=project_root,
    )

    wheels = sorted(dist_dir.glob("claude_workflow_cli-*.whl"))
    assert wheels, "wheel build should produce at least one wheel"
    wheel = wheels[-1]
    prefix = "claude_workflow_cli/data/payload/aidd"
    with zipfile.ZipFile(wheel) as z:
        names = set(z.namelist())
        for expected in [
            f"{prefix}/CLAUDE.md",
            f"{prefix}/conventions.md",
            f"{prefix}/workflow.md",
            f"{prefix}/config/conventions.json",
            f"{prefix}/config/gates.json",
            f"{prefix}/config/allowed-deps.txt",
            f"{prefix}/.claude/settings.json",
            f"{prefix}/.claude/hooks/lib.sh",
            f"{prefix}/.claude/hooks/_vendor/claude_workflow_cli/__init__.py",
            f"{prefix}/.claude/hooks/_vendor/claude_workflow_cli/feature_ids.py",
            f"{prefix}/.claude/hooks/_vendor/claude_workflow_cli/progress.py",
            f"{prefix}/.claude/hooks/_vendor/claude_workflow_cli/tools/__init__.py",
            f"{prefix}/.claude/hooks/_vendor/claude_workflow_cli/tools/analyst_guard.py",
            f"{prefix}/.claude/cache/.gitkeep",
            f"{prefix}/docs/plan/.gitkeep",
            f"{prefix}/docs/adr/.gitkeep",
            f"{prefix}/docs/prd/.gitkeep",
            "claude_workflow_cli/data/payload/manifest.json",
        ]:
            assert expected in names, f"missing {expected} in {wheel.name}"
        for dev_only in [
            "claude_workflow_cli/data/payload/doc/backlog.md",
        ]:
            assert dev_only not in names, f"dev-only file should not be packaged: {dev_only}"

    shutil.rmtree(dist_dir)


def test_package_payload_archive_script(tmp_path):
    project_root = Path(__file__).resolve().parents[1]
    dist_dir = project_root / "dist"
    if dist_dir.exists():
        shutil.rmtree(dist_dir)

    env = os.environ.copy()
    env["PAYLOAD_ARCHIVE_VERSION"] = "test"
    subprocess.run(
        ["python3", "scripts/package_payload_archive.py"],
        check=True,
        cwd=project_root,
        env=env,
    )

    archive = dist_dir / "claude-workflow-payload-test.zip"
    manifest_copy = dist_dir / "claude-workflow-manifest-test.json"
    assert archive.exists(), "payload archive should be created"
    assert archive.with_suffix(archive.suffix + ".sha256").exists(), "archive checksum should exist"
    assert manifest_copy.exists(), "manifest copy should be created"
    assert manifest_copy.with_suffix(manifest_copy.suffix + ".sha256").exists(), "manifest checksum should exist"

    shutil.rmtree(dist_dir)
