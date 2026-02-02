import sys
import tempfile
import unittest
from pathlib import Path

from tests.helpers import REPO_ROOT

SRC_ROOT = REPO_ROOT
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
            tasklist = helpers.tasklist_ready_text(ticket).replace(
                "- [ ] I1: Bootstrap (iteration_id: I1)",
                "- [ ] Bootstrap",
            )
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
            self.assertTrue(
                any("AIDD:TEST_EXECUTION missing profile" in entry for entry in result.details or []),
                result.message,
            )

    def test_tasklist_check_fails_when_next3_contains_checked_item(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            ticket = "DEMO-4"
            tasklist = helpers.tasklist_ready_text(ticket)
            tasklist = tasklist.replace("- [ ] I1:", "- [x] I1:", 1)
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
            self.assertTrue(
                any("missing iteration_id" in entry for entry in result.details or []),
                result.message,
            )

    def test_tasklist_check_fails_on_duplicate_sections(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            ticket = "DEMO-6"
            tasklist = helpers.tasklist_ready_text(ticket) + "\n## AIDD:PROGRESS_LOG\n- (empty)\n"
            helpers.write_file(root, f"docs/tasklist/{ticket}.md", tasklist)
            write_plan(root, ticket)
            result = tasklist_check.check_tasklist(helpers._project_root(root), ticket)
            self.assertEqual(result.status, "error")

    def test_tasklist_check_warns_on_implicit_iteration_id(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            ticket = "DEMO-7"
            tasklist = helpers.tasklist_ready_text(ticket).replace(
                "- [ ] I1: Bootstrap (iteration_id: I1)",
                "- [ ] I1: Bootstrap",
            )
            helpers.write_file(root, f"docs/tasklist/{ticket}.md", tasklist)
            write_plan(root, ticket)
            result = tasklist_check.check_tasklist(helpers._project_root(root), ticket)
            self.assertEqual(result.status, "warn")
            self.assertTrue(
                any("missing explicit iteration_id" in entry for entry in result.details or []),
                result.message,
            )

    def test_tasklist_check_warns_on_next3_missing_ref(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            ticket = "DEMO-8"
            tasklist = helpers.tasklist_ready_text(ticket).replace(
                "(ref: iteration_id=I1)",
                "(iteration_id=I1)",
                1,
            )
            helpers.write_file(root, f"docs/tasklist/{ticket}.md", tasklist)
            write_plan(root, ticket)
            result = tasklist_check.check_tasklist(helpers._project_root(root), ticket)
            self.assertEqual(result.status, "warn")
            self.assertTrue(
                any("missing ref" in entry for entry in result.details or []),
                result.message,
            )

    def test_tasklist_check_warns_on_next3_not_top_open_items(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            ticket = "DEMO-9"
            tasklist = helpers.tasklist_ready_text(ticket)
            tasklist = tasklist.replace(
                "- [ ] I1: Bootstrap (ref: iteration_id=I1)",
                "__SWAP__",
                1,
            )
            tasklist = tasklist.replace(
                "- [ ] I2: Follow-up (ref: iteration_id=I2)",
                "- [ ] I1: Bootstrap (ref: iteration_id=I1)",
                1,
            )
            tasklist = tasklist.replace(
                "__SWAP__",
                "- [ ] I2: Follow-up (ref: iteration_id=I2)",
                1,
            )
            helpers.write_file(root, f"docs/tasklist/{ticket}.md", tasklist)
            write_plan(root, ticket)
            result = tasklist_check.check_tasklist(helpers._project_root(root), ticket)
            self.assertEqual(result.status, "warn")
            self.assertTrue(
                any("top open items" in entry for entry in result.details or []),
                result.message,
            )

    def test_tasklist_check_fails_when_qa_not_met_but_ready(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            ticket = "DEMO-10"
            tasklist = helpers.tasklist_ready_text(ticket).replace("→ met →", "→ not met →", 1)
            helpers.write_file(root, f"docs/tasklist/{ticket}.md", tasklist)
            write_plan(root, ticket)
            result = tasklist_check.check_tasklist(helpers._project_root(root), ticket)
            self.assertEqual(result.status, "error")
            self.assertTrue(
                any("QA_TRACEABILITY NOT MET" in entry for entry in result.details or []),
                result.message,
            )

    def test_tasklist_check_requires_spec_for_ui_changes(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            ticket = "DEMO-11"
            helpers.write_file(root, f"docs/tasklist/{ticket}.md", helpers.tasklist_ready_text(ticket))
            helpers.write_file(
                root,
                f"docs/plan/{ticket}.md",
                "\n".join(
                    [
                        "Status: READY",
                        f"PRD: aidd/docs/prd/{ticket}.prd.md",
                        f"Research: aidd/docs/research/{ticket}.md",
                        "",
                        "## AIDD:FILES_TOUCHED",
                        "- frontend/components/Button.tsx",
                        "",
                        "## AIDD:ITERATIONS",
                        "- iteration_id: I1",
                        "  - Goal: Update UI",
                    ]
                )
                + "\n",
            )
            result = tasklist_check.check_tasklist(helpers._project_root(root), ticket)
            self.assertEqual(result.status, "error")
            self.assertTrue(
                any("spec required" in entry.lower() for entry in result.details or []),
                result.message,
            )

    def test_tasklist_template_is_valid(self) -> None:
        template_path = REPO_ROOT / "templates" / "aidd" / "docs" / "tasklist" / "template.md"
        template_text = template_path.read_text(encoding="utf-8")
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            result = tasklist_check.check_tasklist_text(root, "ABC-123", template_text)
            self.assertIn(result.status, {"ok", "warn"}, result.message)


if __name__ == "__main__":
    unittest.main()
