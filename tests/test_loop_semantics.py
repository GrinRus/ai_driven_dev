import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from textwrap import dedent

from tests.helpers import cli_cmd, cli_env, ensure_project_root, write_active_feature, write_active_state, write_file


FIXTURES = Path(__file__).resolve().parent / "fixtures" / "loop_pack"
RUNNER_FIXTURES = Path(__file__).resolve().parent / "fixtures" / "loop_step"


def _write_plan(project_root: Path, ticket: str) -> None:
    write_file(
        project_root,
        f"docs/plan/{ticket}.md",
        dedent(
            f"""\
            Status: READY
            \n
            ## AIDD:ITERATIONS
            - iteration_id: I1
              - Goal: bootstrap
            - iteration_id: I2
              - Goal: follow-up
            - iteration_id: I3
              - Goal: follow-up
            """
        ),
    )


class LoopSemanticsTests(unittest.TestCase):
    def test_revise_reuses_scope_and_keeps_tasklist(self) -> None:
        with tempfile.TemporaryDirectory(prefix="loop-semantics-") as tmpdir:
            root = ensure_project_root(Path(tmpdir))
            ticket = "DEMO-1"
            tasklist = (FIXTURES / "tasklist.md").read_text(encoding="utf-8")
            write_file(root, f"docs/tasklist/{ticket}.md", tasklist)
            write_active_state(root, ticket=ticket, stage="review", work_item="iteration_id=I1")

            stage_review = {
                "schema": "aidd.stage_result.v1",
                "ticket": ticket,
                "stage": "review",
                "scope_key": "iteration_id_I1",
                "result": "continue",
                "updated_at": "2024-01-02T00:00:00Z",
            }
            write_file(
                root,
                f"reports/loops/{ticket}/iteration_id_I1/stage.review.result.json",
                json.dumps(stage_review),
            )
            stage_implement = {
                "schema": "aidd.stage_result.v1",
                "ticket": ticket,
                "stage": "implement",
                "scope_key": "iteration_id_I1",
                "result": "continue",
                "updated_at": "2024-01-02T00:00:00Z",
            }
            write_file(
                root,
                f"reports/loops/{ticket}/iteration_id_I1/stage.implement.result.json",
                json.dumps(stage_implement),
            )
            review_pack = (
                "---\n"
                "schema: aidd.review_pack.v2\n"
                "updated_at: 2024-01-02T00:00:00Z\n"
                "verdict: REVISE\n"
                "work_item_key: iteration_id=I1\n"
                "scope_key: iteration_id_I1\n"
                "---\n"
            )
            write_file(root, f"reports/loops/{ticket}/iteration_id_I1/review.latest.pack.md", review_pack)
            fix_plan = {
                "schema": "aidd.review_fix_plan.v1",
                "updated_at": "2024-01-02T00:00:00Z",
                "ticket": ticket,
                "work_item_key": "iteration_id=I1",
                "scope_key": "iteration_id_I1",
                "fix_plan": {
                    "steps": ["Fix review:F1"],
                    "commands": [],
                    "tests": ["see AIDD:TEST_EXECUTION"],
                    "expected_paths": ["src/**"],
                    "acceptance_check": "Blocking findings resolved: review:F1",
                    "links": [],
                    "fixes": ["review:F1"],
                },
            }
            write_file(
                root,
                f"reports/loops/{ticket}/iteration_id_I1/review.fix_plan.json",
                json.dumps(fix_plan),
            )

            before_tasklist = (root / f"docs/tasklist/{ticket}.md").read_text(encoding="utf-8")
            runner = RUNNER_FIXTURES / "runner.sh"
            log_path = root / "runner.log"
            env = cli_env({"AIDD_LOOP_RUNNER_LOG": str(log_path)})
            result = subprocess.run(
                cli_cmd(
                    "loop-step",
                    "--ticket",
                    ticket,
                    "--runner",
                    f"bash {runner}",
                    "--format",
                    "json",
                ),
                text=True,
                capture_output=True,
                cwd=root,
                env=env,
            )
            self.assertEqual(result.returncode, 10, msg=result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload.get("scope_key"), "iteration_id_I1")

            after_tasklist = (root / f"docs/tasklist/{ticket}.md").read_text(encoding="utf-8")
            self.assertEqual(before_tasklist, after_tasklist)
            active_payload = json.loads((root / "docs" / ".active.json").read_text(encoding="utf-8"))
            self.assertEqual(active_payload.get("work_item"), "iteration_id=I1")

    def test_ship_keeps_next3_shift_and_loop_run_ships(self) -> None:
        with tempfile.TemporaryDirectory(prefix="loop-semantics-") as tmpdir:
            root = ensure_project_root(Path(tmpdir))
            ticket = "demo-ship"
            write_active_feature(root, ticket)
            _write_plan(root, ticket)

            tasklist = dedent(
                f"""\
                ---
                Ticket: {ticket}
                Status: READY
                Updated: 2024-01-01
                Plan: aidd/docs/plan/{ticket}.md
                ---

                ## AIDD:CONTEXT_PACK
                Status: READY

                ## AIDD:SPEC_PACK
                - Goal: demo

                ## AIDD:TEST_STRATEGY
                - Unit: smoke

                ## AIDD:TEST_EXECUTION
                - profile: none
                - tasks: []
                - filters: []
                - when: manual
                - reason: docs-only

                ## AIDD:ITERATIONS_FULL
                - [x] I1: Bootstrap (iteration_id: I1)
                  - DoD: done
                  - Boundaries: docs/tasklist/{ticket}.md
                  - Tests:
                    - profile: none
                    - tasks: []
                    - filters: []
                - [ ] I2: Follow-up (iteration_id: I2)
                  - DoD: done
                  - Boundaries: docs/tasklist/{ticket}.md
                  - Tests:
                    - profile: none
                    - tasks: []
                    - filters: []
                - [ ] I3: Follow-up (iteration_id: I3)
                  - DoD: done
                  - Boundaries: docs/tasklist/{ticket}.md
                  - Tests:
                    - profile: none
                    - tasks: []
                    - filters: []

                ## AIDD:NEXT_3
                - [ ] I1: Bootstrap (ref: iteration_id=I1)
                - [ ] I2: Follow-up (ref: iteration_id=I2)
                - [ ] I3: Follow-up (ref: iteration_id=I3)

                ## AIDD:HANDOFF_INBOX
                <!-- handoff:manual start -->
                <!-- handoff:manual end -->

                ## AIDD:QA_TRACEABILITY
                - AC-1 → check → met → evidence

                ## AIDD:CHECKLIST
                ### AIDD:CHECKLIST_QA
                - [ ] QA: acceptance criteria verified

                ## AIDD:PROGRESS_LOG
                - (empty)

                ## AIDD:HOW_TO_UPDATE
                - update NEXT_3
                """
            )
            write_file(root, f"docs/tasklist/{ticket}.md", tasklist)

            result = subprocess.run(
                cli_cmd("tasklist-check", "--ticket", ticket, "--fix"),
                cwd=root,
                text=True,
                capture_output=True,
                env=cli_env(),
            )
            self.assertEqual(result.returncode, 0, msg=result.stderr)

            updated = (root / f"docs/tasklist/{ticket}.md").read_text(encoding="utf-8")
            next3_section = updated.split("## AIDD:NEXT_3", 1)[1].split("##", 1)[0]
            self.assertIn("- [ ] I2:", next3_section)
            self.assertNotIn("I1:", next3_section)

            write_active_state(root, stage="review")
            write_active_state(root, work_item="iteration_id=I1")
            stage_review = {
                "schema": "aidd.stage_result.v1",
                "ticket": ticket,
                "stage": "review",
                "scope_key": "iteration_id_I1",
                "result": "done",
                "updated_at": "2024-01-02T00:00:00Z",
            }
            write_file(
                root,
                f"reports/loops/{ticket}/iteration_id_I1/stage.review.result.json",
                json.dumps(stage_review),
            )
            review_pack = "---\nschema: aidd.review_pack.v2\nupdated_at: 2024-01-02T00:00:00Z\n---\n"
            write_file(root, f"reports/loops/{ticket}/iteration_id_I1/review.latest.pack.md", review_pack)

            result = subprocess.run(
                cli_cmd("loop-run", "--ticket", ticket, "--max-iterations", "1", "--format", "json"),
                text=True,
                capture_output=True,
                cwd=root,
                env=cli_env(),
            )
            self.assertEqual(result.returncode, 11, msg=result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload.get("status"), "max-iterations")
            active_payload = json.loads((root / "docs" / ".active.json").read_text(encoding="utf-8"))
            self.assertEqual(active_payload.get("work_item"), "iteration_id=I2")
            self.assertEqual(active_payload.get("stage"), "implement")
            log_path = root / "reports" / "loops" / ticket / "loop.run.log"
            self.assertIn("selected_next_work_item=iteration_id=I2", log_path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
