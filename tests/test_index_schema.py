import json
import sys
import tempfile
import unittest
from pathlib import Path
from textwrap import dedent

SRC_ROOT = Path(__file__).resolve().parents[1] / "src"
if str(SRC_ROOT) not in sys.path:  # pragma: no cover - test bootstrap
    sys.path.insert(0, str(SRC_ROOT))

from claude_workflow_cli.tools import index_sync

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

            ## AIDD:RISKS_TOP5
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
        "reports/qa/DEMO-2.pack.yaml",
        json.dumps({"status": "warn"}, indent=2),
    )
    write_file(
        project_root,
        "reports/research/DEMO-2-context.pack.toon",
        json.dumps({"status": "ok"}, indent=2),
    )

    index_path = index_sync.write_index(project_root, "DEMO-2", "DEMO-2")
    payload = json.loads(index_path.read_text(encoding="utf-8"))

    reports = payload.get("reports") or []
    assert "reports/qa/DEMO-2.pack.yaml" in reports
    assert "reports/research/DEMO-2-context.pack.toon" in reports
    checks = payload.get("checks") or []
    qa_check = next((item for item in checks if item.get("name") == "qa"), None)
    assert qa_check is not None
    assert qa_check.get("status") == "warn"


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
        "reports/tests/DEMO-4.jsonl",
        json.dumps({"ts": "2024-01-03T00:00:00Z", "ticket": "DEMO-4", "type": "tests", "status": "pass"})
        + "\n",
    )

    index_path = index_sync.write_index(project_root, "DEMO-4", "DEMO-4")
    payload = json.loads(index_path.read_text(encoding="utf-8"))

    reports = payload.get("reports") or []
    assert "reports/tests/DEMO-4.jsonl" in reports
