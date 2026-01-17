import json
import subprocess
from textwrap import dedent

from tests.helpers import (
    cli_cmd,
    cli_env,
    ensure_gates_config,
    ensure_project_root,
    git_config_user,
    git_init,
    write_active_feature,
    write_file,
)


def test_progress_detects_new_checkbox_without_modifying_tasklist(tmp_path):
    ticket = "demo-checkout"
    project_root = ensure_project_root(tmp_path)
    git_init(project_root)
    git_config_user(project_root)
    ensure_gates_config(project_root)
    write_active_feature(project_root, ticket)

    tasklist_path = write_file(
        project_root,
        f"docs/tasklist/{ticket}.md",
        dedent(
            """\
            ---
            Feature: demo-checkout
            Status: draft
            PRD: docs/prd/demo-checkout.prd.md
            Plan: docs/plan/demo-checkout.md
            Research: docs/research/demo-checkout.md
            Updated: 2024-01-01
            ---

            - [ ] Реализация :: подготовить сервис
            """
        ),
    )
    write_file(project_root, "src/main/App.kt", "class App { fun run() = \"ok\" }\n")

    subprocess.run(["git", "add", "."], cwd=project_root, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "feat: baseline"],
        cwd=project_root,
        check=True,
        capture_output=True,
    )

    write_file(project_root, "src/main/App.kt", "class App { fun run() = \"changed\" }\n")
    tasklist_path.write_text(
        dedent(
            """\
            ---
            Feature: demo-checkout
            Status: draft
            PRD: docs/prd/demo-checkout.prd.md
            Plan: docs/plan/demo-checkout.md
            Research: docs/research/demo-checkout.md
            Updated: 2024-01-02
            ---

            - [x] Реализация :: подготовить сервис — 2024-01-02 • итерация 1
            """
        ),
        encoding="utf-8",
    )

    before = tasklist_path.read_text(encoding="utf-8")
    result = subprocess.run(
        cli_cmd(
            "progress",
            "--target",
            ".",
            "--ticket",
            ticket,
            "--source",
            "implement",
            "--json",
        ),
        cwd=project_root,
        text=True,
        capture_output=True,
        env=cli_env(),
    )
    assert result.returncode == 0, result.stderr

    payload = json.loads(result.stdout)
    assert payload["status"] == "ok"
    assert any(item.startswith("- [x] Реализация ::") for item in payload["new_items"])

    after = tasklist_path.read_text(encoding="utf-8")
    assert after == before


def test_progress_blocks_without_new_checkbox_for_nested_root(tmp_path):
    ticket = "demo-nested"
    workspace_root = tmp_path
    project_root = ensure_project_root(tmp_path)
    git_init(workspace_root)
    git_config_user(workspace_root)
    ensure_gates_config(project_root)
    write_active_feature(project_root, ticket)

    write_file(
        project_root,
        f"docs/tasklist/{ticket}.md",
        dedent(
            """\
            ---
            Feature: demo-nested
            Status: draft
            Updated: 2024-01-01
            ---

            - [x] Baseline checkbox already checked
            """
        ),
    )
    write_file(workspace_root, "src/main/App.kt", "class App { fun run() = \"ok\" }\n")

    subprocess.run(["git", "add", "."], cwd=workspace_root, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "feat: baseline"],
        cwd=workspace_root,
        check=True,
        capture_output=True,
    )

    write_file(workspace_root, "src/main/App.kt", "class App { fun run() = \"changed\" }\n")

    result = subprocess.run(
        cli_cmd(
            "progress",
            "--target",
            str(project_root),
            "--ticket",
            ticket,
            "--source",
            "implement",
            "--json",
        ),
        cwd=workspace_root,
        text=True,
        capture_output=True,
        env=cli_env(),
    )

    assert result.returncode != 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["status"] == "error:no-checkbox"
