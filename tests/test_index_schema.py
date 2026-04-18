import json
import sys
import tempfile
import unittest
from pathlib import Path
from textwrap import dedent

from tests.helpers import REPO_ROOT

SRC_ROOT = REPO_ROOT
if str(SRC_ROOT) not in sys.path:  # pragma: no cover - test bootstrap
    sys.path.insert(0, str(SRC_ROOT))

from aidd_runtime import index_sync

from .helpers import ensure_project_root, write_active_feature, write_active_stage, write_file


def test_index_sync_generates_required_fields(tmp_path):
    project_root = ensure_project_root(tmp_path)
    write_active_feature(project_root, "DEMO-1")
    write_active_stage(project_root, "tasklist")

    write_file(
        project_root,
        "docs/tasklist/DEMO-1.md",
        dedent(
            """
            # Tasklist

            ## AIDD:CONTEXT_PACK
            - Context line

            ## AIDD:NEXT_3
            - [ ] First

            ## AIDD:OPEN_QUESTIONS
            - Question

            ## AIDD:RISKS
            - Risk
            """
        ).strip()
        + "\n",
    )
    write_file(
        project_root,
        "docs/prd/DEMO-1.prd.md",
        "# Demo PRD\n\n## AIDD:OPEN_QUESTIONS\n- Q\n",
    )

    index_path = index_sync.write_index(project_root, "DEMO-1", "DEMO-1")
    payload = json.loads(index_path.read_text(encoding="utf-8"))

    for field in index_sync.REQUIRED_FIELDS:
        assert field in payload, f"missing {field}"
    assert payload["ticket"] == "DEMO-1"
    assert payload["schema"] == index_sync.SCHEMA
    assert payload.get("open_questions_source") in {"tasklist", "prd:aidd_open_questions", "none"}


def test_index_sync_includes_pack_variants(tmp_path):
    project_root = ensure_project_root(tmp_path)
    write_active_feature(project_root, "DEMO-2")
    write_active_stage(project_root, "qa")
    write_file(
        project_root,
        "docs/tasklist/DEMO-2.md",
        "## AIDD:CONTEXT_PACK\n- Demo\n",
    )
    write_file(project_root, "docs/prd/DEMO-2.prd.md", "# Demo PRD\n")
    write_file(
        project_root,
        "reports/qa/DEMO-2.pack.json",
        json.dumps({"status": "WARN"}, indent=2),
    )
    write_file(
        project_root,
        "reports/research/DEMO-2-rlm.pack.json",
        json.dumps({"status": "ok"}, indent=2),
    )

    index_path = index_sync.write_index(project_root, "DEMO-2", "DEMO-2")
    payload = json.loads(index_path.read_text(encoding="utf-8"))

    reports = payload.get("reports") or []
    assert "aidd/reports/qa/DEMO-2.pack.json" in reports
    assert "aidd/reports/research/DEMO-2-rlm.pack.json" in reports
    checks = payload.get("checks") or []
    qa_check = next((item for item in checks if item.get("name") == "qa"), None)
    assert qa_check is not None
    assert qa_check.get("status") == "WARN"


def test_index_sync_ignores_template_none_and_guidance_in_open_questions(tmp_path):
    project_root = ensure_project_root(tmp_path)
    write_active_feature(project_root, "DEMO-2A")
    write_active_stage(project_root, "idea")
    write_file(project_root, "docs/tasklist/DEMO-2A.md", "## AIDD:CONTEXT_PACK\n- Demo\n")
    write_file(
        project_root,
        "docs/prd/DEMO-2A.prd.md",
        dedent(
            """
            # Demo PRD

            ## AIDD:OPEN_QUESTIONS
            - `none`
            > Номера `Q` синхронизируй с `Вопрос N` из «Диалог analyst».
            > Если ответ зафиксирован, перенеси пункт в `AIDD:DECISIONS`.
            """
        ).strip()
        + "\n",
    )

    index_path = index_sync.write_index(project_root, "DEMO-2A", "DEMO-2A")
    payload = json.loads(index_path.read_text(encoding="utf-8"))

    assert payload["open_questions"] == []
    assert payload["open_questions_source"] == "none"


class IndexSyncEventTests(unittest.TestCase):
    def test_index_sync_includes_events(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = ensure_project_root(Path(tmpdir))
            write_active_feature(project_root, "DEMO-3")
            write_active_stage(project_root, "implement")
            write_file(
                project_root,
                "docs/tasklist/DEMO-3.md",
                "## AIDD:CONTEXT_PACK\n- Demo\n",
            )
            write_file(project_root, "docs/prd/DEMO-3.prd.md", "# Demo PRD\n")
            write_file(
                project_root,
                "reports/events/DEMO-3.jsonl",
                "\n".join(
                    [
                        json.dumps({"ts": "2024-01-01T00:00:00Z", "ticket": "DEMO-3", "type": "qa", "status": "pass"}),
                        json.dumps({"ts": "2024-01-02T00:00:00Z", "ticket": "DEMO-3", "type": "progress"}),
                    ]
                )
                + "\n",
            )

            index_path = index_sync.write_index(project_root, "DEMO-3", "DEMO-3")
            payload = json.loads(index_path.read_text(encoding="utf-8"))

            events = payload.get("events") or []
            self.assertEqual(len(events), 2)
            self.assertEqual(events[0].get("type"), "qa")


def test_index_sync_includes_tests_log(tmp_path):
    project_root = ensure_project_root(tmp_path)
    write_active_feature(project_root, "DEMO-4")
    write_active_stage(project_root, "implement")
    write_file(project_root, "docs/tasklist/DEMO-4.md", "## AIDD:CONTEXT_PACK\n- Demo\n")
    write_file(project_root, "docs/prd/DEMO-4.prd.md", "# Demo PRD\n")
    write_file(
        project_root,
        "reports/tests/DEMO-4/DEMO-4.jsonl",
        json.dumps({"ts": "2024-01-03T00:00:00Z", "ticket": "DEMO-4", "type": "tests", "status": "pass"})
        + "\n",
    )

    index_path = index_sync.write_index(project_root, "DEMO-4", "DEMO-4")
    payload = json.loads(index_path.read_text(encoding="utf-8"))

    reports = payload.get("reports") or []
    assert "aidd/reports/tests/DEMO-4/DEMO-4.jsonl" in reports


def test_index_sync_separates_expected_and_actual_reports_with_truth_checks(tmp_path):
    project_root = ensure_project_root(tmp_path)
    ticket = "DEMO-5"
    write_active_feature(project_root, ticket)
    write_active_stage(project_root, "implement")
    write_file(
        project_root,
        f"docs/tasklist/{ticket}.md",
        dedent(
            f"""
            ---
            Ticket: {ticket}
            Status: READY
            Plan: aidd/docs/plan/{ticket}.md
            Reports:
              qa: aidd/reports/qa/{ticket}.json
              review_report: aidd/reports/reviewer/{ticket}/iteration_id_I1.json
            ---

            ## AIDD:CONTEXT_PACK
            Updated: 2024-01-01
            Ticket: {ticket}
            Stage: implement
            Status: READY

            ## AIDD:TEST_EXECUTION
            - profile: none
            - tasks: []
            - filters: []
            - when: manual
            - reason: docs-only

            ## AIDD:NEXT_3
            - [ ] I1: Bootstrap (ref: iteration_id=I1)
            """
        ).strip()
        + "\n",
    )
    write_file(
        project_root,
        f"docs/plan/{ticket}.md",
        "# Plan\n\n"
        "## Plan Review\n"
        "Status: PENDING\n\n"
        "## AIDD:ITERATIONS\n"
        "- iteration_id: I1\n"
        "  - Goal: bootstrap\n",
    )
    write_file(project_root, f"docs/prd/{ticket}.prd.md", "# Demo PRD\n\nStatus: READY\n")
    write_file(project_root, f"reports/qa/{ticket}.json", json.dumps({"status": "WARN"}, indent=2))

    index_path = index_sync.write_index(project_root, ticket, ticket)
    payload = json.loads(index_path.read_text(encoding="utf-8"))

    assert payload["reports"] == [f"aidd/reports/qa/{ticket}.json"]
    assert payload["expected_reports"] == [
        f"aidd/reports/qa/{ticket}.json",
        f"aidd/reports/reviewer/{ticket}/iteration_id_I1.json",
    ]
    assert payload["missing_expected_reports"] == [f"aidd/reports/reviewer/{ticket}/iteration_id_I1.json"]
    assert payload["doc_statuses"]["plan"] == "PENDING"
    assert "spec" not in payload["doc_statuses"]
    assert all("docs/spec/" not in path for path in payload["artifacts"])
    codes = {item["code"] for item in payload.get("truth_checks") or []}
    assert "missing_expected_report" in codes
    assert "active_stage_vs_plan_mismatch" in codes


def test_index_sync_collapses_repeated_gate_tests_events(tmp_path):
    project_root = ensure_project_root(tmp_path)
    ticket = "DEMO-6"
    write_active_feature(project_root, ticket)
    write_active_stage(project_root, "implement")
    write_file(project_root, f"docs/tasklist/{ticket}.md", "## AIDD:CONTEXT_PACK\n- Demo\n")
    write_file(project_root, f"docs/prd/{ticket}.prd.md", "# Demo PRD\n\nStatus: READY\n")
    write_file(
        project_root,
        f"reports/events/{ticket}.jsonl",
        "\n".join(
            [
                json.dumps(
                    {
                        "ts": "2024-01-01T00:00:00Z",
                        "ticket": ticket,
                        "type": "gate-tests",
                        "status": "warn",
                        "source": "hook gate-tests",
                        "details": {"summary": "docs-only skip"},
                    }
                ),
                json.dumps(
                    {
                        "ts": "2024-01-01T00:01:00Z",
                        "ticket": ticket,
                        "type": "gate-tests",
                        "status": "warn",
                        "source": "hook gate-tests",
                        "details": {"summary": "docs-only skip"},
                    }
                ),
                json.dumps(
                    {
                        "ts": "2024-01-01T00:02:00Z",
                        "ticket": ticket,
                        "type": "progress",
                        "status": "ok",
                    }
                ),
            ]
        )
        + "\n",
    )

    payload = json.loads(index_sync.write_index(project_root, ticket, ticket).read_text(encoding="utf-8"))
    events = payload.get("events") or []

    assert len(events) == 2
    assert events[0]["type"] == "gate-tests"
    assert events[0]["repeat_count"] == 2
    assert events[0]["first_seen"] == "2024-01-01T00:00:00Z"
    assert events[0]["last_seen"] == "2024-01-01T00:01:00Z"
