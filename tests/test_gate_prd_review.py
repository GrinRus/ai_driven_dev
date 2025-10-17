from textwrap import dedent

from .helpers import ensure_gates_config, run_hook, write_file

SRC_PAYLOAD = '{"tool_input":{"file_path":"src/main/kotlin/App.kt"}}'
PRD_PAYLOAD = '{"tool_input":{"file_path":"docs/prd/demo-checkout.prd.md"}}'


def make_prd(status: str, action_items: str = "") -> str:
    body = dedent(
        f"""\
        # PRD

        ## PRD Review
        Status: {status}
        {action_items}
        """
    )
    return body


def setup_base(tmp_path) -> None:
    write_file(tmp_path, "docs/.active_feature", "demo-checkout")
    ensure_gates_config(
        tmp_path,
        {
            "prd_review": {
                "enabled": True,
                "approved_statuses": ["approved"],
                "blocking_statuses": ["blocked"],
                "allow_missing_section": False,
                "require_action_items_closed": True,
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

    result = run_hook(tmp_path, "gate-prd-review.sh", SRC_PAYLOAD)
    assert result.returncode == 0, result.stderr


def test_skips_for_direct_prd_edit(tmp_path):
    setup_base(tmp_path)
    write_file(tmp_path, "docs/prd/demo-checkout.prd.md", make_prd("pending"))

    result = run_hook(tmp_path, "gate-prd-review.sh", PRD_PAYLOAD)
    assert result.returncode == 0, result.stderr
