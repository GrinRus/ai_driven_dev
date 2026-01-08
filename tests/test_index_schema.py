import json
import sys
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
