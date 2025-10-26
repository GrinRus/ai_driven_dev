import json
import subprocess
from pathlib import Path

from .helpers import REPO_ROOT, write_file

SCRIPT = REPO_ROOT / "tools" / "migrate_ticket.py"


def run_migration(tmp_path: Path, *extra_args: str, dry_run: bool = False) -> subprocess.CompletedProcess[str]:
    args = ["python3", str(SCRIPT), "--target", str(tmp_path), *extra_args]
    if dry_run:
        args.append("--dry-run")
    return subprocess.run(
        args,
        text=True,
        capture_output=True,
        check=True,
    )


def test_creates_active_ticket_and_updates_tasklist(tmp_path: Path) -> None:
    write_file(tmp_path, "docs/.active_feature", "demo-feature\n")
    write_file(
        tmp_path,
        "docs/tasklist/demo-feature.md",
        """---
Feature: demo-feature
Status: draft
PRD: docs/prd/demo-feature.prd.md
Updated: 2024-01-01
---

# Tasklist — Demo
""",
    )

    result = run_migration(tmp_path)
    assert result.returncode == 0, result.stderr

    ticket_path = tmp_path / "docs" / ".active_ticket"
    assert ticket_path.read_text(encoding="utf-8").strip() == "demo-feature"

    tasklist_text = (tmp_path / "docs/tasklist/demo-feature.md").read_text(encoding="utf-8")
    assert "Ticket: demo-feature" in tasklist_text
    assert "Slug hint: demo-feature" in tasklist_text
    assert "Feature: demo-feature" in tasklist_text


def test_dry_run_does_not_touch_files(tmp_path: Path) -> None:
    write_file(tmp_path, "docs/.active_feature", "checkout\n")
    tasklist = """---
Feature: checkout
Status: draft
---
"""
    write_file(tmp_path, "docs/tasklist/checkout.md", tasklist)

    result = run_migration(tmp_path, dry_run=True)
    assert result.returncode == 0, result.stderr

    ticket_path = tmp_path / "docs" / ".active_ticket"
    assert not ticket_path.exists()
    assert (tmp_path / "docs/tasklist/checkout.md").read_text(encoding="utf-8") == tasklist


def test_blank_active_ticket_is_rewritten(tmp_path: Path) -> None:
    write_file(tmp_path, "docs/.active_feature", "demo\n")
    write_file(tmp_path, "docs/.active_ticket", "   \n")

    result = run_migration(tmp_path)
    assert result.returncode == 0, result.stderr

    ticket_path = tmp_path / "docs" / ".active_ticket"
    assert ticket_path.read_text(encoding="utf-8").strip() == "demo"
