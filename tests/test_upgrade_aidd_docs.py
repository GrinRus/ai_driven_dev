import subprocess
import sys
from pathlib import Path

from .helpers import REPO_ROOT


def run_upgrade(root: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(REPO_ROOT / "tests" / "repo_tools" / "upgrade_aidd_docs.py"), "--root", str(root)],
        text=True,
        capture_output=True,
    )


def test_upgrade_inserts_missing_sections(tmp_path: Path) -> None:
    prd_dir = tmp_path / "aidd" / "docs" / "prd"
    prd_dir.mkdir(parents=True)
    prd_path = prd_dir / "ABC-1.prd.md"
    prd_path.write_text("# PRD\n\n## 1. Контекст\n- test\n", encoding="utf-8")

    result = run_upgrade(tmp_path)
    assert result.returncode == 0, result.stderr
    updated = prd_path.read_text(encoding="utf-8")
    assert "## AIDD:CONTEXT_PACK" in updated
    assert "## AIDD:GOALS" in updated


def test_upgrade_skips_existing_sections(tmp_path: Path) -> None:
    plan_dir = tmp_path / "aidd" / "docs" / "plan"
    plan_dir.mkdir(parents=True)
    plan_path = plan_dir / "ABC-1.md"
    plan_path.write_text(
        "# План\n\n## AIDD:CONTEXT_PACK\n- already\n\n## 1. Контекст\n- test\n",
        encoding="utf-8",
    )

    result = run_upgrade(tmp_path)
    assert result.returncode == 0, result.stderr
    updated = plan_path.read_text(encoding="utf-8")
    assert updated.count("## AIDD:CONTEXT_PACK") == 1
