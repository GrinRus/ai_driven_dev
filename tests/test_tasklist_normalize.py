import subprocess
from pathlib import Path
from textwrap import dedent

from tests.helpers import cli_cmd, cli_env, ensure_project_root, write_active_feature, write_file


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


def test_tasklist_normalize_rebuilds_next3_and_dedupes(tmp_path):
    project_root = ensure_project_root(tmp_path)
    ticket = "demo-checkout"
    write_active_feature(project_root, ticket)
    _write_plan(project_root, ticket)

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
        - [ ] I1: Bootstrap (iteration_id: I1)
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
        - [x] I1: Bootstrap (ref: iteration_id=I1)

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

        ## AIDD:PROGRESS_LOG
        - (empty)

        ## AIDD:HOW_TO_UPDATE
        - update NEXT_3
        """
    )
    write_file(project_root, f"docs/tasklist/{ticket}.md", tasklist)

    result = subprocess.run(
        cli_cmd("tasklist-check", "--ticket", ticket, "--fix"),
        cwd=project_root,
        text=True,
        capture_output=True,
        env=cli_env(),
    )
    assert result.returncode == 0, result.stderr

    updated = (project_root / f"docs/tasklist/{ticket}.md").read_text(encoding="utf-8")
    assert updated.count("## AIDD:PROGRESS_LOG") == 1
    assert "- [x] I1:" not in updated
    assert "(ref: iteration_id=I1)" in updated
    backups = project_root / "reports" / "tasklist_backups" / ticket
    assert backups.exists()
    assert list(backups.iterdir())


def test_tasklist_normalize_inserts_next3_when_missing(tmp_path):
    project_root = ensure_project_root(tmp_path)
    ticket = "demo-missing-next3"
    write_active_feature(project_root, ticket)
    _write_plan(project_root, ticket)

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
        - [ ] I1: Bootstrap (iteration_id: I1)
          - DoD: done
          - Boundaries: docs/tasklist/{ticket}.md
          - Tests:
            - profile: none
            - tasks: []
            - filters: []

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
    write_file(project_root, f"docs/tasklist/{ticket}.md", tasklist)

    result = subprocess.run(
        cli_cmd("tasklist-check", "--ticket", ticket, "--fix"),
        cwd=project_root,
        text=True,
        capture_output=True,
        env=cli_env(),
    )
    assert result.returncode == 0, result.stderr

    updated = (project_root / f"docs/tasklist/{ticket}.md").read_text(encoding="utf-8")
    assert "## AIDD:NEXT_3" in updated
    assert "(ref: iteration_id=I1)" in updated


def test_tasklist_normalize_migrates_legacy_handoff(tmp_path):
    project_root = ensure_project_root(tmp_path)
    ticket = "demo-legacy"
    write_active_feature(project_root, ticket)
    _write_plan(project_root, ticket)

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
        - [ ] I1: Bootstrap (iteration_id: I1)
          - DoD: done
          - Boundaries: docs/tasklist/{ticket}.md
          - Tests:
            - profile: none
            - tasks: []
            - filters: []

        ## AIDD:NEXT_3
        - [ ] I1: Bootstrap (ref: iteration_id=I1)

        ## AIDD:HANDOFF_INBOX
        <!-- handoff:qa start -->
        - [ ] QA: legacy issue (id: qa:legacy-1)
        <!-- handoff:qa end -->

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
    write_file(project_root, f"docs/tasklist/{ticket}.md", tasklist)

    result = subprocess.run(
        cli_cmd("tasklist-check", "--ticket", ticket, "--fix"),
        cwd=project_root,
        text=True,
        capture_output=True,
        env=cli_env(),
    )
    assert result.returncode == 0, result.stderr

    updated = (project_root / f"docs/tasklist/{ticket}.md").read_text(encoding="utf-8")
    assert "Report: legacy" in updated
    assert "source: qa" in updated


def test_tasklist_normalize_dry_run_does_not_write_archive(tmp_path):
    project_root = ensure_project_root(tmp_path)
    ticket = "demo-progress-archive"
    write_active_feature(project_root, ticket)
    _write_plan(project_root, ticket)

    progress_entries = "\n".join(
        [
            f"- 2026-01-0{idx} source=implement id=I1 kind=iteration hash=abc{idx} link=aidd/reports/tests/demo.log msg=note-{idx}"
            for idx in range(1, 26)
        ]
    )

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
        - [ ] I1: Bootstrap (iteration_id: I1)
          - DoD: done
          - Boundaries: docs/tasklist/{ticket}.md
          - Tests:
            - profile: none
            - tasks: []
            - filters: []

        ## AIDD:NEXT_3
        - [ ] I1: Bootstrap (ref: iteration_id=I1)

        ## AIDD:HANDOFF_INBOX
        <!-- handoff:manual start -->
        <!-- handoff:manual end -->

        ## AIDD:QA_TRACEABILITY
        - AC-1 → check → met → evidence

        ## AIDD:CHECKLIST
        ### AIDD:CHECKLIST_QA
        - [ ] QA: acceptance criteria verified

        ## AIDD:PROGRESS_LOG
        {progress_entries}
        """
    )
    write_file(project_root, f"docs/tasklist/{ticket}.md", tasklist)

    result = subprocess.run(
        cli_cmd("tasklist-check", "--ticket", ticket, "--fix", "--dry-run"),
        cwd=project_root,
        text=True,
        capture_output=True,
        env=cli_env(),
    )
    assert result.returncode == 0, result.stderr
    archive_path = project_root / "reports" / "progress" / f"{ticket}.log"
    assert not archive_path.exists()
