import argparse
import os
import sys
import tempfile
import unittest
from pathlib import Path

from tests.helpers import REPO_ROOT

SRC_ROOT = REPO_ROOT
if str(SRC_ROOT) not in sys.path:  # pragma: no cover - test bootstrap
    sys.path.insert(0, str(SRC_ROOT))

from tools import plan_review_gate


def write_plan(root: Path, ticket: str, review_body: str) -> Path:
    plan_path = root / "docs" / "plan" / f"{ticket}.md"
    plan_path.parent.mkdir(parents=True, exist_ok=True)
    content = f"# Plan\n\n## Plan Review\n{review_body}\n\n## AIDD:ITERATIONS\n- iteration_id: I1\n"
    plan_path.write_text(content, encoding="utf-8")
    return plan_path


def run_gate(root: Path, ticket: str, review_body: str) -> int:
    write_plan(root, ticket, review_body)
    args = argparse.Namespace(
        ticket=ticket,
        file_path="src/main/kotlin/App.kt",
        branch="",
        config="config/gates.json",
        skip_on_plan_edit=False,
    )
    old_cwd = Path.cwd()
    os.chdir(root)
    try:
        return plan_review_gate.run_gate(args)
    finally:
        os.chdir(old_cwd)


class PlanReviewGateTests(unittest.TestCase):
    def test_action_items_only_section_is_enforced(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            ticket = "DEMO-PLAN-1"
            body = (
                "Status: READY (ok)\n"
                "### Summary\n"
                "- [ ] not an action item\n"
                "### Action items\n"
                "- [x] done\n"
            )
            self.assertEqual(run_gate(root, ticket, body), 0)

    def test_open_action_item_blocks(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            ticket = "DEMO-PLAN-2"
            body = "Status: READY\n### Action items\n- [ ] pending\n"
            self.assertEqual(run_gate(root, ticket, body), 1)

    def test_fenced_code_block_ignored(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            ticket = "DEMO-PLAN-3"
            body = (
                "Status: READY\n"
                "### Action items\n"
                "```\n"
                "- [ ] example in code block\n"
                "```\n"
                "- [x] done\n"
            )
            self.assertEqual(run_gate(root, ticket, body), 0)

    def test_open_checkbox_blocks_without_action_items_heading(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            ticket = "DEMO-PLAN-4"
            body = "Status: READY\n- [ ] legacy open item\n"
            self.assertEqual(run_gate(root, ticket, body), 1)


if __name__ == "__main__":
    unittest.main()
