import sys
import tempfile
import unittest
from pathlib import Path

SRC_ROOT = Path(__file__).resolve().parents[2]
if str(SRC_ROOT) not in sys.path:  # pragma: no cover - test bootstrap
    sys.path.insert(0, str(SRC_ROOT))

from tests import helpers
from tools import tasklist_check


def write_plan(root: Path, ticket: str, iteration_ids: list[str] | None = None) -> None:
    if iteration_ids is None:
        iteration_ids = ["I1", "I2", "I3"]
    lines = [
        "Status: READY",
        f"PRD: aidd/docs/prd/{ticket}.prd.md",
        f"Research: aidd/docs/research/{ticket}.md",
        "",
        "## AIDD:ITERATIONS",
    ]
    for iteration_id in iteration_ids:
        lines.extend(
            [
                f"- iteration_id: {iteration_id}",
                f"  - Goal: milestone for {iteration_id}",
            ]
        )
    helpers.write_file(root, f"docs/plan/{ticket}.md", "\n".join(lines) + "\n")


class TasklistCheckTests(unittest.TestCase):
    def test_tasklist_check_passes_with_iteration_ids(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            ticket = "DEMO-1"
            helpers.write_file(root, f"docs/tasklist/{ticket}.md", helpers.tasklist_ready_text(ticket))
            write_plan(root, ticket)
            result = tasklist_check.check_tasklist(helpers._project_root(root), ticket)
            self.assertEqual(result.status, "ok", result.message)

    def test_tasklist_check_fails_without_iteration_id(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            ticket = "DEMO-2"
            tasklist = helpers.tasklist_ready_text(ticket).replace("iteration_id: I1\n", "")
            helpers.write_file(root, f"docs/tasklist/{ticket}.md", tasklist)
            write_plan(root, ticket)
            result = tasklist_check.check_tasklist(helpers._project_root(root), ticket)
            self.assertEqual(result.status, "error")

    def test_tasklist_check_fails_without_test_execution_profile(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            ticket = "DEMO-3"
            tasklist = helpers.tasklist_ready_text(ticket).replace("- profile: none\n", "", 1)
            helpers.write_file(root, f"docs/tasklist/{ticket}.md", tasklist)
            write_plan(root, ticket)
            result = tasklist_check.check_tasklist(helpers._project_root(root), ticket)
            self.assertEqual(result.status, "error")
            self.assertIn("AIDD:TEST_EXECUTION missing profile", result.message)

    def test_tasklist_check_fails_without_next3_steps(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            ticket = "DEMO-4"
            tasklist = helpers.tasklist_ready_text(ticket)
            missing_steps_block = (
                "## AIDD:NEXT_3\n"
                "- [ ] Task 1\n"
                "  - iteration_id: I1\n"
                "  - Goal: setup baseline\n"
                "  - DoD: done\n"
                f"  - Boundaries: docs/tasklist/{ticket}.md\n"
                "  - Steps:\n"
                "    - update tasklist\n"
                "    - verify gate\n"
                "    - record progress\n"
            )
            replacement = (
                "## AIDD:NEXT_3\n"
                "- [ ] Task 1\n"
                "  - iteration_id: I1\n"
                "  - Goal: setup baseline\n"
                "  - DoD: done\n"
                f"  - Boundaries: docs/tasklist/{ticket}.md\n"
            )
            tasklist = tasklist.replace(missing_steps_block, replacement, 1)
            helpers.write_file(root, f"docs/tasklist/{ticket}.md", tasklist)
            write_plan(root, ticket)
            result = tasklist_check.check_tasklist(helpers._project_root(root), ticket)
            self.assertEqual(result.status, "error")

    def test_tasklist_check_fails_when_plan_has_extra_iteration(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            ticket = "DEMO-5"
            helpers.write_file(root, f"docs/tasklist/{ticket}.md", helpers.tasklist_ready_text(ticket))
            write_plan(root, ticket, iteration_ids=["I1", "I2", "I3", "I4"])
            result = tasklist_check.check_tasklist(helpers._project_root(root), ticket)
            self.assertEqual(result.status, "error")
            self.assertIn("missing iteration_id", result.message)


if __name__ == "__main__":
    unittest.main()
