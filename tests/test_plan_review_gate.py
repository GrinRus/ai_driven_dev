import argparse
import io
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from tests.helpers import REPO_ROOT, ensure_project_root

SRC_ROOT = REPO_ROOT
if str(SRC_ROOT) not in sys.path:  # pragma: no cover - test bootstrap
    sys.path.insert(0, str(SRC_ROOT))

from aidd_runtime import plan_review_gate


def write_plan(root: Path, ticket: str, review_body: str) -> Path:
    plan_path = root / "docs" / "plan" / f"{ticket}.md"
    plan_path.parent.mkdir(parents=True, exist_ok=True)
    content = f"# Plan\n\n## Plan Review\n{review_body}\n\n## AIDD:ITERATIONS\n- iteration_id: I1\n"
    plan_path.write_text(content, encoding="utf-8")
    return plan_path


def _make_args(ticket: str, *, docs_only: bool) -> argparse.Namespace:
    return argparse.Namespace(
        ticket=ticket,
        file_path="src/main/kotlin/App.kt",
        branch="",
        config="config/gates.json",
        skip_on_plan_edit=False,
        docs_only=docs_only,
    )


def run_gate(root: Path, ticket: str, review_body: str, *, docs_only: bool = False) -> int:
    write_plan(root, ticket, review_body)
    args = _make_args(ticket, docs_only=docs_only)
    old_cwd = Path.cwd()
    os.chdir(root)
    try:
        return plan_review_gate.run_gate(args)
    finally:
        os.chdir(old_cwd)


def run_gate_with_output(root: Path, ticket: str, review_body: str, *, docs_only: bool = False) -> tuple[int, str]:
    write_plan(root, ticket, review_body)
    args = _make_args(ticket, docs_only=docs_only)
    old_cwd = Path.cwd()
    os.chdir(root)
    try:
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            code = plan_review_gate.run_gate(args)
    finally:
        os.chdir(old_cwd)
    return code, buffer.getvalue()


class PlanReviewGateTests(unittest.TestCase):
    def test_parse_args_accepts_plan_path_alias(self) -> None:
        args = plan_review_gate.parse_args(
            [
                "--ticket",
                "DEMO-PLAN-ALIAS",
                "--plan-path",
                "docs/plan/DEMO-PLAN-ALIAS.md",
            ]
        )
        self.assertEqual(args.file_path, "docs/plan/DEMO-PLAN-ALIAS.md")

    def test_action_items_only_section_is_enforced(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = ensure_project_root(Path(tmpdir))
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
            root = ensure_project_root(Path(tmpdir))
            ticket = "DEMO-PLAN-2"
            body = "Status: READY\n### Action items\n- [ ] pending\n"
            self.assertEqual(run_gate(root, ticket, body), 1)

    def test_fenced_code_block_ignored(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = ensure_project_root(Path(tmpdir))
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
            root = ensure_project_root(Path(tmpdir))
            ticket = "DEMO-PLAN-4"
            body = "Status: READY\n- [ ] open item\n"
            self.assertEqual(run_gate(root, ticket, body), 1)

    def test_docs_only_softens_non_ready_plan_review(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = ensure_project_root(Path(tmpdir))
            ticket = "DEMO-PLAN-5"
            body = "Status: PENDING\n### Action items\n- [ ] pending\n"
            code, output = run_gate_with_output(root, ticket, body, docs_only=True)
            self.assertEqual(code, 0)
            self.assertIn("WARN:", output)
            self.assertIn("docs_only_mode=1", output)
            self.assertIn("reinvoke_allowed=1", output)

    def test_manual_reinvoke_allowed_after_blocked_run(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = ensure_project_root(Path(tmpdir))
            ticket = "DEMO-PLAN-6"
            body = "Status: PENDING\n### Action items\n- [ ] pending\n"
            blocked_code, _ = run_gate_with_output(root, ticket, body, docs_only=False)
            softened_code, softened_output = run_gate_with_output(root, ticket, body, docs_only=True)
            self.assertEqual(blocked_code, 1)
            self.assertEqual(softened_code, 0)
            self.assertIn("reinvoke_allowed=1", softened_output)


if __name__ == "__main__":
    unittest.main()
