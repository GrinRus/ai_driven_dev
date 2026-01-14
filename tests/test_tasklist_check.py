import tempfile
import unittest
from pathlib import Path

from tests import helpers
from claude_workflow_cli.tools import tasklist_check


def write_plan(root: Path, ticket: str) -> None:
    content = (
        "Status: READY\n"
        f"PRD: aidd/docs/prd/{ticket}.prd.md\n"
        f"Research: aidd/docs/research/{ticket}.md\n\n"
        "## AIDD:ITERATIONS\n"
        "- iteration_id: I1\n"
        "  - Goal: bootstrap\n"
        "- iteration_id: I2\n"
        "  - Goal: follow-up\n"
        "- iteration_id: I3\n"
        "  - Goal: follow-up\n"
    )
    helpers.write_file(root, f"docs/plan/{ticket}.md", content)


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


if __name__ == "__main__":
    unittest.main()
