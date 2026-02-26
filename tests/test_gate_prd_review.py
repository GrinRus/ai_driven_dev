import io
import os
from contextlib import redirect_stdout
from pathlib import Path
from textwrap import dedent

from aidd_runtime import prd_review_gate

from .helpers import ensure_gates_config, ensure_project_root, write_active_feature, write_file, write_json

SRC_PATH = "src/main/kotlin/App.kt"
PRD_PATH = "docs/prd/demo-checkout.prd.md"
DOC_PATH = "docs/plan/demo-checkout.md"


def make_prd(
    status: str,
    action_items: str = "",
    dialog_status: str = "READY",
    review_header: str = "## PRD Review",
) -> str:
    body = dedent(
        f"""\
        # PRD

        ## Диалог analyst
        Status: {dialog_status}

        Вопрос 1: Что уточнить?
        Ответ 1: Ответ получен.

        {review_header}
        Status: {status}
        {action_items}
        """
    )
    return body


def setup_base(tmp_path: Path) -> None:
    ensure_project_root(tmp_path)
    write_active_feature(tmp_path, "demo-checkout")
    ensure_gates_config(
        tmp_path,
        {
            "prd_review": {
                "enabled": True,
                "approved_statuses": ["ready"],
                "blocking_statuses": ["blocked"],
                "allow_missing_section": False,
                "require_action_items_closed": True,
                "allow_missing_report": False,
                "blocking_severities": ["critical"],
                "report_path": "aidd/reports/prd/{ticket}.json",
            }
        },
    )


def run_prd_gate(tmp_path: Path, file_path: str, *, skip_on_prd_edit: bool = True) -> tuple[int, str]:
    project_root = ensure_project_root(tmp_path)
    args = ["--ticket", "demo-checkout", "--file-path", file_path]
    if skip_on_prd_edit:
        args.append("--skip-on-prd-edit")
    parsed = prd_review_gate.parse_args(args)
    out = io.StringIO()
    prev_cwd = Path.cwd()
    try:
        os.chdir(project_root)
        with redirect_stdout(out):
            status = prd_review_gate.run_gate(parsed)
    finally:
        os.chdir(prev_cwd)
    return status, out.getvalue()


def test_blocks_when_section_missing(tmp_path):
    setup_base(tmp_path)
    write_file(tmp_path, "docs/prd/demo-checkout.prd.md", "# PRD")

    status, output = run_prd_gate(tmp_path, SRC_PATH)
    assert status == 1
    assert "PRD Review" in output


def test_skips_for_non_code_paths(tmp_path):
    setup_base(tmp_path)

    status, output = run_prd_gate(tmp_path, DOC_PATH)
    assert status == 0, output


def test_blocks_when_status_pending(tmp_path):
    setup_base(tmp_path)
    write_file(tmp_path, "docs/prd/demo-checkout.prd.md", make_prd("PENDING"))

    status, output = run_prd_gate(tmp_path, SRC_PATH)
    assert status == 1
    assert "не READY" in output


def test_blocks_when_dialog_status_draft(tmp_path):
    setup_base(tmp_path)
    write_file(
        tmp_path,
        "docs/prd/demo-checkout.prd.md",
        make_prd("READY", dialog_status="draft"),
    )

    status, output = run_prd_gate(tmp_path, SRC_PATH)
    assert status == 1
    assert "draft" in output.lower()


def test_blocks_when_action_items_open(tmp_path):
    setup_base(tmp_path)
    write_file(
        tmp_path,
        "docs/prd/demo-checkout.prd.md",
        make_prd("READY", "- [ ] sync metrics"),
    )

    status, output = run_prd_gate(tmp_path, SRC_PATH)
    assert status == 1
    assert "action items" in output


def test_allows_when_review_approved(tmp_path):
    setup_base(tmp_path)
    write_file(tmp_path, "docs/prd/demo-checkout.prd.md", make_prd("READY"))
    write_json(
        tmp_path,
        "reports/prd/demo-checkout.json",
        {"ticket": "demo-checkout", "status": "ready", "findings": []},
    )

    status, output = run_prd_gate(tmp_path, SRC_PATH)
    assert status == 0, output


def test_allows_numbered_prd_review_header(tmp_path):
    setup_base(tmp_path)
    write_file(
        tmp_path,
        "docs/prd/demo-checkout.prd.md",
        make_prd("READY", review_header="## 11. PRD Review"),
    )
    write_json(
        tmp_path,
        "reports/prd/demo-checkout.json",
        {"ticket": "demo-checkout", "status": "ready", "findings": []},
    )

    status, output = run_prd_gate(tmp_path, SRC_PATH)
    assert status == 0, output


def test_allows_ready_for_implementation_alias(tmp_path):
    setup_base(tmp_path)
    write_file(tmp_path, "docs/prd/demo-checkout.prd.md", make_prd("READY_FOR_IMPLEMENTATION"))
    write_json(
        tmp_path,
        "reports/prd/demo-checkout.json",
        {"ticket": "demo-checkout", "status": "ready_for_implementation", "findings": []},
    )

    status, output = run_prd_gate(tmp_path, SRC_PATH)
    assert status == 0, output


def test_allows_when_pack_report_present(tmp_path):
    setup_base(tmp_path)
    write_file(tmp_path, "docs/prd/demo-checkout.prd.md", make_prd("READY"))
    write_json(
        tmp_path,
        "reports/prd/demo-checkout.pack.json",
        {
            "schema": "aidd.report.pack.v1",
            "findings": {
                "cols": ["severity", "title", "details"],
                "rows": [["minor", "note", "ok"]],
            },
            "status": "ready",
        },
    )

    status, output = run_prd_gate(tmp_path, SRC_PATH)
    assert status == 0, output


def test_skips_for_direct_prd_edit(tmp_path):
    setup_base(tmp_path)
    write_file(tmp_path, "docs/prd/demo-checkout.prd.md", make_prd("PENDING"))

    status, output = run_prd_gate(tmp_path, PRD_PATH)
    assert status == 0, output


def test_blocks_when_report_missing(tmp_path):
    setup_base(tmp_path)
    write_file(tmp_path, "docs/prd/demo-checkout.prd.md", make_prd("READY"))

    status, output = run_prd_gate(tmp_path, SRC_PATH)
    assert status == 1
    assert "отчёт" in output


def test_blocks_on_blocking_severity(tmp_path):
    setup_base(tmp_path)
    write_file(tmp_path, "docs/prd/demo-checkout.prd.md", make_prd("READY"))
    write_json(
        tmp_path,
        "reports/prd/demo-checkout.json",
        {
            "ticket": "demo-checkout",
            "status": "ready",
            "findings": [{"severity": "critical", "title": "issue", "details": "..."}],
        },
    )

    status, output = run_prd_gate(tmp_path, SRC_PATH)
    assert status == 1
    assert "critical" in output.lower()


def test_blocks_on_report_status_mismatch(tmp_path):
    setup_base(tmp_path)
    write_file(tmp_path, "docs/prd/demo-checkout.prd.md", make_prd("READY"))
    write_json(
        tmp_path,
        "reports/prd/demo-checkout.json",
        {"ticket": "demo-checkout", "status": "pending", "findings": []},
    )

    status, output = run_prd_gate(tmp_path, SRC_PATH)
    assert status == 1
    assert "не совпадает" in output


def test_blocks_on_recommended_status_mismatch(tmp_path):
    setup_base(tmp_path)
    write_file(tmp_path, "docs/prd/demo-checkout.prd.md", make_prd("READY"))
    write_json(
        tmp_path,
        "reports/prd/demo-checkout.json",
        {
            "ticket": "demo-checkout",
            "status": "ready",
            "recommended_status": "pending",
            "findings": [],
        },
    )

    status, output = run_prd_gate(tmp_path, SRC_PATH)
    assert status == 1
    assert "не совпадает" in output


def test_allows_when_report_missing_but_allowed(tmp_path):
    setup_base(tmp_path)
    ensure_gates_config(
        tmp_path,
        {
            "prd_review": {
                "allow_missing_report": True,
            }
        },
    )
    write_file(tmp_path, "docs/prd/demo-checkout.prd.md", make_prd("READY"))

    status, output = run_prd_gate(tmp_path, SRC_PATH)
    assert status == 0, output
