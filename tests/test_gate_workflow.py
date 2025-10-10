import pathlib
from textwrap import dedent

from .helpers import ensure_gates_config, run_hook, write_file

SRC_PAYLOAD = '{"tool_input":{"file_path":"src/main/kotlin/App.kt"}}'
DOC_PAYLOAD = '{"tool_input":{"file_path":"docs/prd/demo-checkout.prd.md"}}'


def test_no_active_feature_allows_changes(tmp_path):
    write_file(tmp_path, "src/main/kotlin/App.kt", "class App")
    result = run_hook(tmp_path, "gate-workflow.sh", SRC_PAYLOAD)
    assert result.returncode == 0, result.stderr


def test_missing_prd_blocks_when_feature_active(tmp_path):
    write_file(tmp_path, "src/main/kotlin/App.kt", "class App")
    write_file(tmp_path, "docs/.active_feature", "demo-checkout")

    result = run_hook(tmp_path, "gate-workflow.sh", SRC_PAYLOAD)
    assert result.returncode == 2
    assert "нет PRD" in result.stdout or "нет PRD" in result.stderr


def test_missing_plan_blocks(tmp_path):
    write_file(tmp_path, "src/main/kotlin/App.kt", "class App")
    write_file(tmp_path, "docs/.active_feature", "demo-checkout")
    write_file(tmp_path, "docs/prd/demo-checkout.prd.md", "# PRD")

    result = run_hook(tmp_path, "gate-workflow.sh", SRC_PAYLOAD)
    assert result.returncode == 2
    assert "нет плана" in result.stdout or "нет плана" in result.stderr


def test_missing_tasks_blocks(tmp_path):
    write_file(tmp_path, "src/main/kotlin/App.kt", "class App")
    write_file(tmp_path, "docs/.active_feature", "demo-checkout")
    write_file(tmp_path, "docs/prd/demo-checkout.prd.md", "# PRD")
    write_file(tmp_path, "docs/plan/demo-checkout.md", "# Plan")

    result = run_hook(tmp_path, "gate-workflow.sh", SRC_PAYLOAD)
    assert result.returncode == 2
    assert "нет задач" in result.stdout or "нет задач" in result.stderr


def test_tasks_with_slug_allow_changes(tmp_path):
    write_file(tmp_path, "src/main/kotlin/App.kt", "class App")
    write_file(tmp_path, "docs/.active_feature", "demo-checkout")
    write_file(tmp_path, "docs/prd/demo-checkout.prd.md", "# PRD")
    write_file(tmp_path, "docs/plan/demo-checkout.md", "# Plan")
    write_file(
        tmp_path,
        "tasklist.md",
        dedent(
            """\
            # demo tasklist
            - [ ] Demo Checkout :: подготовить PRD/план/tasklist
            """
        ),
    )

    result = run_hook(tmp_path, "gate-workflow.sh", SRC_PAYLOAD)
    assert result.returncode == 0, result.stderr


def test_documents_are_not_blocked(tmp_path):
    write_file(tmp_path, "docs/.active_feature", "demo-checkout")
    # PRD and plan intentionally absent

    result = run_hook(tmp_path, "gate-workflow.sh", DOC_PAYLOAD)
    assert result.returncode == 0, result.stderr
