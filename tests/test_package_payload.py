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
    payload_prefix = "claude_workflow_cli/data/payload"
    plugin_prefix = f"{payload_prefix}/aidd"
    with zipfile.ZipFile(wheel) as z:
        names = set(z.namelist())
        for expected in [
            f"{payload_prefix}/.claude/settings.json",
            f"{payload_prefix}/.claude/cache/.gitkeep",
            f"{payload_prefix}/.claude-plugin/marketplace.json",
            f"{payload_prefix}/smoke-workflow.sh",
            f"{plugin_prefix}/AGENTS.md",
            f"{plugin_prefix}/conventions.md",
            f"{plugin_prefix}/config/conventions.json",
            f"{plugin_prefix}/config/gates.json",
            f"{plugin_prefix}/config/allowed-deps.txt",
            f"{plugin_prefix}/config/context_gc.json",
            f"{plugin_prefix}/hooks/lib.sh",
            f"{plugin_prefix}/docs/plan/.gitkeep",
            f"{plugin_prefix}/docs/adr/.gitkeep",
            f"{plugin_prefix}/docs/prd/.gitkeep",
            f"{plugin_prefix}/docs/prd/template.md",
            f"{plugin_prefix}/docs/tasklist/template.md",
            f"{plugin_prefix}/docs/research/template.md",
            f"{payload_prefix}/manifest.json",
        ]:
            assert expected in names, f"missing {expected} in {wheel.name}"
        for dev_only in [
            "claude_workflow_cli/data/payload/doc/dev/backlog.md",
            "doc/dev/cli-migration.md",
            "doc/dev/reports-format.md",
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
