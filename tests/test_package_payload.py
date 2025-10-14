from __future__ import annotations

import shutil
import subprocess
import zipfile
from pathlib import Path


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
    with zipfile.ZipFile(wheel) as z:
        names = set(z.namelist())
        for expected in [
            "claude_workflow_cli/data/payload/CLAUDE.md",
            "claude_workflow_cli/data/payload/conventions.md",
            "claude_workflow_cli/data/payload/workflow.md",
            "claude_workflow_cli/data/payload/config/conventions.json",
            "claude_workflow_cli/data/payload/config/gates.json",
            "claude_workflow_cli/data/payload/config/allowed-deps.txt",
            "claude_workflow_cli/data/payload/.claude/settings.json",
            "claude_workflow_cli/data/payload/.claude/hooks/lib.sh",
            "claude_workflow_cli/data/payload/.claude/cache/.gitkeep",
            "claude_workflow_cli/data/payload/.github/workflows/gradle.yml",
            "claude_workflow_cli/data/payload/docs/plan/.gitkeep",
            "claude_workflow_cli/data/payload/docs/adr/.gitkeep",
            "claude_workflow_cli/data/payload/docs/prd/.gitkeep",
        ]:
            assert expected in names, f"missing {expected} in {wheel.name}"

    shutil.rmtree(dist_dir)
