import sys
import tempfile
import unittest
import re
from pathlib import Path

from tests.helpers import REPO_ROOT

SRC_ROOT = REPO_ROOT
if str(SRC_ROOT) not in sys.path:  # pragma: no cover - test bootstrap
    sys.path.insert(0, str(SRC_ROOT))

from tests import helpers
from aidd_runtime import stage_lexicon, tasklist_check


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

    def test_tasklist_check_warns_on_missing_expected_reports_for_ready_tasklist(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            ticket = "DEMO-2A"
            tasklist = helpers.tasklist_ready_text(ticket).replace(
                f"Plan: aidd/docs/plan/{ticket}.md\n",
                f"Plan: aidd/docs/plan/{ticket}.md\n"
                "ExpectedReports:\n"
                f"  qa: aidd/reports/qa/{ticket}.json\n"
                f"  review_report: aidd/reports/reviewer/{ticket}/iteration_id_I1.json\n",
                1,
            )
            helpers.write_file(root, f"docs/tasklist/{ticket}.md", tasklist)
            helpers.write_plan_iterations(root, ticket)
            result = tasklist_check.check_tasklist(helpers._project_root(root), ticket)
            self.assertEqual(result.status, "warn", result.message)
            self.assertTrue(
                any("missing expected reports" in entry for entry in result.details or []),
                result.message,
            )
            self.assertTrue(
                any("tasklist is READY but expected downstream reports are still missing" in entry for entry in result.details or []),
                result.message,
            )
            self.assertTrue(
                any(issue.code == "missing_expected_report" and issue.category == "advisory_truth" for issue in result.issues or []),
                result.issues,
            )

    def test_tasklist_check_warns_on_active_stage_vs_plan_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            ticket = "DEMO-2B"
            helpers.write_active_stage(root, "implement")
            helpers.write_file(root, f"docs/tasklist/{ticket}.md", helpers.tasklist_ready_text(ticket))
            helpers.write_file(
                root,
                f"docs/plan/{ticket}.md",
                "# Plan\n\n"
                "## Plan Review\n"
                "Status: PENDING\n\n"
                "## AIDD:ITERATIONS\n"
                "- iteration_id: I1\n"
                "  - Goal: bootstrap\n"
                "- iteration_id: I2\n"
                "  - Goal: follow-up\n"
                "- iteration_id: I3\n"
                "  - Goal: follow-up\n",
            )

            result = tasklist_check.check_tasklist(helpers._project_root(root), ticket)
            self.assertEqual(result.status, "warn", result.message)
            self.assertTrue(
                any("active stage implement while plan status is PENDING" in entry for entry in result.details or []),
                result.message,
            )

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

    def test_tasklist_check_accepts_multiline_test_execution_tasks(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            ticket = "DEMO-3M"
            tasklist = helpers.tasklist_ready_text(ticket).replace(
                "- tasks: []\n",
                "- tasks:\n"
                "  - ./gradlew test --tests \"*GithubAnalysis*\"\n"
                "  - npm test -- --testPathPattern=\"MCP\"\n",
                1,
            )
            helpers.write_file(root, f"docs/tasklist/{ticket}.md", tasklist)
            write_plan(root, ticket)
            result = tasklist_check.check_tasklist(helpers._project_root(root), ticket)
            self.assertEqual(result.status, "ok", result.message)
            self.assertFalse(
                any("AIDD:TEST_EXECUTION missing tasks" in entry for entry in result.details or []),
                result.message,
            )

    def test_tasklist_check_fails_when_test_execution_tasks_key_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            ticket = "DEMO-3N"
            tasklist = helpers.tasklist_ready_text(ticket).replace("- tasks: []\n", "", 1)
            helpers.write_file(root, f"docs/tasklist/{ticket}.md", tasklist)
            write_plan(root, ticket)
            result = tasklist_check.check_tasklist(helpers._project_root(root), ticket)
            self.assertEqual(result.status, "error")
            self.assertTrue(
                any("AIDD:TEST_EXECUTION missing tasks" in entry for entry in result.details or []),
                result.message,
            )

    def test_tasklist_check_accepts_commands_alias_when_tasks_key_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            ticket = "DEMO-3C"
            tasklist = helpers.tasklist_ready_text(ticket).replace("- profile: none\n", "- profile: targeted\n", 1)
            tasklist = tasklist.replace(
                "- tasks: []\n",
                "- commands:\n  - echo tasklist-alias-ok\n",
                1,
            )
            helpers.write_file(root, f"docs/tasklist/{ticket}.md", tasklist)
            write_plan(root, ticket)
            result = tasklist_check.check_tasklist(helpers._project_root(root), ticket)
            self.assertEqual(result.status, "ok", result.message)
            self.assertFalse(
                any("AIDD:TEST_EXECUTION missing tasks" in entry for entry in result.details or []),
                result.message,
            )

    def test_tasklist_check_fails_on_shell_chain_single_task_entry(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            ticket = "DEMO-3B"
            tasklist = helpers.tasklist_ready_text(ticket).replace(
                "- tasks: []\n",
                '- tasks: ["echo smoke && echo next"]\n',
                1,
            )
            helpers.write_file(root, f"docs/tasklist/{ticket}.md", tasklist)
            write_plan(root, ticket)
            result = tasklist_check.check_tasklist(helpers._project_root(root), ticket)
            self.assertEqual(result.status, "error")
            self.assertTrue(
                any("single-entry shell chain" in entry for entry in result.details or []),
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

    def test_tasklist_check_warns_on_next3_unmet_deps(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            ticket = "DEMO-9B"
            tasklist = helpers.tasklist_ready_text(ticket)
            tasklist = tasklist.replace(
                "  - Steps:\n",
                "  - deps: I2\n  - Steps:\n",
                1,
            )
            helpers.write_file(root, f"docs/tasklist/{ticket}.md", tasklist)
            write_plan(root, ticket, iteration_ids=["I1", "I2"])
            result = tasklist_check.check_tasklist(helpers._project_root(root), ticket)
            self.assertEqual(result.status, "warn")
            self.assertTrue(
                any("unmet deps" in entry for entry in result.details or []),
                result.message,
            )

    def test_tasklist_check_warns_on_progress_log_without_checkbox(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            ticket = "DEMO-9C"
            tasklist = helpers.tasklist_ready_text(ticket)
            tasklist = tasklist.replace(
                "## AIDD:PROGRESS_LOG\n- (empty)\n",
                "## AIDD:PROGRESS_LOG\n- 2024-01-02 source=implement id=I1 kind=iteration hash=abc123 link=aidd/reports/tests/demo.jsonl msg=done\n",
            )
            helpers.write_file(root, f"docs/tasklist/{ticket}.md", tasklist)
            write_plan(root, ticket)
            result = tasklist_check.check_tasklist(helpers._project_root(root), ticket)
            self.assertEqual(result.status, "warn")
            self.assertTrue(
                any("PROGRESS_LOG entry for I1" in entry for entry in result.details or []),
                result.message,
            )

    def test_tasklist_check_accepts_iteration_dod_list_format(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            ticket = "DEMO-9D"
            tasklist = helpers.tasklist_ready_text(ticket).replace(
                "  - DoD: tasklist ready\n",
                "  - DoD:\n"
                "    - tasklist ready\n",
                1,
            )
            helpers.write_file(root, f"docs/tasklist/{ticket}.md", tasklist)
            write_plan(root, ticket)
            result = tasklist_check.check_tasklist(helpers._project_root(root), ticket)
            self.assertEqual(result.status, "ok", result.message)
            self.assertFalse(
                any("missing DoD" in entry for entry in result.details or []),
                result.message,
            )

    def test_tasklist_check_accepts_handoff_dod_list_format(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            ticket = "DEMO-9E"
            tasklist = helpers.tasklist_ready_text(ticket)
            tasklist = tasklist.replace(
                "## AIDD:NEXT_3\n"
                "- [ ] I1: Bootstrap (ref: iteration_id=I1)\n"
                "- [ ] I2: Follow-up (ref: iteration_id=I2)\n"
                "- [ ] I3: Follow-up (ref: iteration_id=I3)\n\n",
                "## AIDD:NEXT_3\n"
                "- [ ] Critical null check in webhook handler (ref: id=review:F6)\n"
                "- [ ] I1: Bootstrap (ref: iteration_id=I1)\n"
                "- [ ] I2: Follow-up (ref: iteration_id=I2)\n\n",
                1,
            )
            tasklist = tasklist.replace(
                "<!-- handoff:manual start -->\n"
                "<!-- handoff:manual end -->\n",
                "<!-- handoff:manual start -->\n"
                "- [ ] Critical null check in webhook handler (id: review:F6) (Priority: high) (Blocking: true)\n"
                "  - source: review\n"
                "  - Status: open\n"
                "  - scope: I1\n"
                "  - DoD:\n"
                "    - webhook rejects empty payload with 4xx\n"
                "    - regression test added\n"
                "  - Boundaries:\n"
                "    - must-touch: [\"src/webhooks/\", \"tests/webhooks/\"]\n"
                "  - Tests:\n"
                "    - profile: targeted\n"
                "    - tasks: [\"pytest tests/webhooks/test_handler.py\"]\n"
                "<!-- handoff:manual end -->\n",
                1,
            )
            helpers.write_file(root, f"docs/tasklist/{ticket}.md", tasklist)
            write_plan(root, ticket)
            result = tasklist_check.check_tasklist(helpers._project_root(root), ticket)
            self.assertEqual(result.status, "ok", result.message)
            self.assertFalse(
                any("handoff review:F6 missing DoD" in entry for entry in result.details or []),
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

    def test_tasklist_check_does_not_require_spec_for_ui_changes(self) -> None:
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
            self.assertNotEqual(result.status, "error", result.message)
            self.assertFalse(
                any("spec required" in entry.lower() for entry in result.details or []),
                result.message,
            )

    def test_tasklist_stage_treats_missing_plan_as_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            ticket = "DEMO-12"
            tasklist = helpers.tasklist_ready_text(ticket).replace("Stage: implement", "Stage: tasklist", 1)
            helpers.write_file(root, f"docs/tasklist/{ticket}.md", tasklist)
            result = tasklist_check.check_tasklist(helpers._project_root(root), ticket)
            self.assertEqual(result.status, "error")
            self.assertTrue(
                any("plan not found" in entry for entry in result.details or []),
                result.message,
            )
            self.assertTrue(
                any(issue.code == "plan_not_found" and issue.category == "upstream_blocker" for issue in result.issues or []),
                result.issues,
            )

    def test_tasklist_stage_treats_invalid_progress_log_as_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            ticket = "DEMO-13"
            tasklist = helpers.tasklist_ready_text(ticket).replace("Stage: implement", "Stage: tasklist", 1)
            tasklist = tasklist.replace(
                "## AIDD:PROGRESS_LOG\n- (empty)\n",
                "## AIDD:PROGRESS_LOG\n- totally invalid progress row\n",
            )
            helpers.write_file(root, f"docs/tasklist/{ticket}.md", tasklist)
            write_plan(root, ticket)
            result = tasklist_check.check_tasklist(helpers._project_root(root), ticket)
            self.assertEqual(result.status, "error")
            self.assertTrue(
                any("invalid PROGRESS_LOG format" in entry for entry in result.details or []),
                result.message,
            )

    def test_tasklist_template_is_valid(self) -> None:
        template_path = REPO_ROOT / "skills" / "tasks-new" / "templates" / "tasklist.template.md"
        template_text = template_path.read_text(encoding="utf-8")
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            result = tasklist_check.check_tasklist_text(root, "ABC-123", template_text)
            self.assertIn(result.status, {"ok", "warn"}, result.message)

    def test_tasklist_template_stage_placeholder_uses_supported_stages(self) -> None:
        template_path = REPO_ROOT / "skills" / "tasks-new" / "templates" / "tasklist.template.md"
        template_text = template_path.read_text(encoding="utf-8")
        match = re.search(r"^Stage:\s*<([^>]+)>", template_text, flags=re.MULTILINE)
        self.assertIsNotNone(match, "Stage placeholder is missing in tasklist template")
        stage_tokens = {item.strip() for item in match.group(1).split("|") if item.strip()}
        supported = set(stage_lexicon.supported_stage_values(include_aliases=True))
        unsupported = sorted(stage_tokens - supported)
        self.assertEqual(unsupported, [], f"unsupported stages in template: {unsupported}")
        self.assertNotIn("release", stage_tokens)

    def test_tasklist_template_does_not_ship_open_handoff_placeholders(self) -> None:
        template_path = REPO_ROOT / "skills" / "tasks-new" / "templates" / "tasklist.template.md"
        template_text = template_path.read_text(encoding="utf-8")
        next3_section = template_text.split("## AIDD:NEXT_3", 1)[1].split("##", 1)[0]
        handoff_section = template_text.split("## AIDD:HANDOFF_INBOX", 1)[1].split("##", 1)[0]

        self.assertNotIn("(ref: id=review:F6)", next3_section)
        self.assertNotRegex(handoff_section, r"(?m)^- \[ \].*\(id: review:F6\)")
        self.assertIn("<!-- handoff:manual start -->", handoff_section)
        self.assertIn("<!-- handoff:manual end -->", handoff_section)


if __name__ == "__main__":
    unittest.main()
