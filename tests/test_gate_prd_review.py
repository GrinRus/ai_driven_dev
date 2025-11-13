from textwrap import dedent

from .helpers import ensure_gates_config, run_hook, write_active_feature, write_file, write_json

SRC_PAYLOAD = '{"tool_input":{"file_path":"src/main/kotlin/App.kt"}}'
PRD_PAYLOAD = '{"tool_input":{"file_path":"docs/prd/demo-checkout.prd.md"}}'


def make_prd(status: str, action_items: str = "", dialog_status: str = "READY") -> str:
    body = dedent(
        f"""\
        # PRD

        ## Диалог analyst
        Status: {dialog_status}

        Вопрос 1: Что уточнить?
        Ответ 1: Ответ получен.

        ## PRD Review
        Status: {status}
        {action_items}
        """
    )
    return body


def setup_base(tmp_path) -> None:
    write_active_feature(tmp_path, "demo-checkout")
    ensure_gates_config(
        tmp_path,
        {
            "prd_review": {
                "enabled": True,
                "approved_statuses": ["approved"],
                "blocking_statuses": ["blocked"],
                "allow_missing_section": False,
                "require_action_items_closed": True,
                "allow_missing_report": False,
                "blocking_severities": ["critical"],
                "report_path": "reports/prd/{ticket}.json",
            }
        },
    )


def test_blocks_when_section_missing(tmp_path):
    setup_base(tmp_path)
    write_file(tmp_path, "docs/prd/demo-checkout.prd.md", "# PRD")

    result = run_hook(tmp_path, "gate-prd-review.sh", SRC_PAYLOAD)
    assert result.returncode == 2
    assert "PRD Review" in (result.stdout + result.stderr)


def test_blocks_when_status_pending(tmp_path):
    setup_base(tmp_path)
    write_file(tmp_path, "docs/prd/demo-checkout.prd.md", make_prd("pending"))

    result = run_hook(tmp_path, "gate-prd-review.sh", SRC_PAYLOAD)
    assert result.returncode == 2
    assert "не утверждён" in (result.stdout + result.stderr)


def test_blocks_when_dialog_status_draft(tmp_path):
    setup_base(tmp_path)
    write_file(
        tmp_path,
        "docs/prd/demo-checkout.prd.md",
        make_prd("approved", dialog_status="draft"),
    )

    result = run_hook(tmp_path, "gate-prd-review.sh", SRC_PAYLOAD)
    assert result.returncode == 2
    assert "draft" in (result.stdout + result.stderr).lower()


def test_blocks_when_action_items_open(tmp_path):
    setup_base(tmp_path)
    write_file(
        tmp_path,
        "docs/prd/demo-checkout.prd.md",
        make_prd("approved", "- [ ] sync metrics"),
    )

    result = run_hook(tmp_path, "gate-prd-review.sh", SRC_PAYLOAD)
    assert result.returncode == 2
    assert "action items" in (result.stdout + result.stderr)


def test_allows_when_review_approved(tmp_path):
    setup_base(tmp_path)
    write_file(tmp_path, "docs/prd/demo-checkout.prd.md", make_prd("approved"))
    write_json(
        tmp_path,
        "reports/prd/demo-checkout.json",
        {"ticket": "demo-checkout", "findings": []},
    )

    result = run_hook(tmp_path, "gate-prd-review.sh", SRC_PAYLOAD)
    assert result.returncode == 0, result.stderr


def test_skips_for_direct_prd_edit(tmp_path):
    setup_base(tmp_path)
    write_file(tmp_path, "docs/prd/demo-checkout.prd.md", make_prd("pending"))

    result = run_hook(tmp_path, "gate-prd-review.sh", PRD_PAYLOAD)
    assert result.returncode == 0, result.stderr


def test_blocks_when_report_missing(tmp_path):
    setup_base(tmp_path)
    write_file(tmp_path, "docs/prd/demo-checkout.prd.md", make_prd("approved"))

    result = run_hook(tmp_path, "gate-prd-review.sh", SRC_PAYLOAD)
    assert result.returncode == 2
    assert "отчёт" in (result.stdout + result.stderr)


def test_blocks_on_blocking_severity(tmp_path):
    setup_base(tmp_path)
    write_file(tmp_path, "docs/prd/demo-checkout.prd.md", make_prd("approved"))
    write_json(
        tmp_path,
        "reports/prd/demo-checkout.json",
        {
            "ticket": "demo-checkout",
            "findings": [{"severity": "critical", "title": "issue", "details": "..."}],
        },
    )

    result = run_hook(tmp_path, "gate-prd-review.sh", SRC_PAYLOAD)
    assert result.returncode == 2
    assert "critical" in (result.stdout + result.stderr).lower()


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
    write_file(tmp_path, "docs/prd/demo-checkout.prd.md", make_prd("approved"))

    result = run_hook(tmp_path, "gate-prd-review.sh", SRC_PAYLOAD)
    assert result.returncode == 0, result.stderr
