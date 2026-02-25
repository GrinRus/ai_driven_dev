import json
import os
import subprocess

from tests.helpers import HOOKS_DIR, REPO_ROOT, write_active_feature, write_file


def test_post_hooks_use_project_aidd_root_when_plugin_root_empty(tmp_path):
    slug = "demo"
    workspace_root = tmp_path
    root_prd = "docs/prd/root.prd.md"
    write_file(workspace_root, root_prd, "# Root")

    project_root = workspace_root / "aidd"
    project_root.mkdir(exist_ok=True)
    write_active_feature(project_root, slug)
    write_file(project_root, f"docs/prd/{slug}.prd.md", "# PRD\n\n## PRD Review\nStatus: READY\n")
    write_file(project_root, f"docs/plan/{slug}.md", "# Plan\n\n## Plan Review\nStatus: READY\n")
    write_file(project_root, f"docs/tasklist/{slug}.md", "- [ ] impl\n")
    write_file(project_root, f"docs/research/{slug}.md", "# Research\nStatus: reviewed\n")
    write_file(project_root, "src/main/kotlin/App.kt", "class App")

    fmt_path = HOOKS_DIR / "format_and_test.py"
    lint_path = HOOKS_DIR / "lint_deps.py"
    # minimal config for lint-deps allowlist off
    write_file(project_root, "config/gates.json", json.dumps({"deps_allowlist": False}))

    # allowlist file only under aidd/; root docs do not include it
    write_file(project_root, "config/allowed-deps.txt", "com.acme:ok-lib\n")

    common_env = os.environ.copy()
    common_env.update(
        {
            "CLAUDE_PLUGIN_ROOT": str(REPO_ROOT),
            "SKIP_AUTO_TESTS": "1",
            "SKIP_FORMAT": "1",
        }
    )

    fmt_result = subprocess.run(
        [str(fmt_path)],
        cwd=project_root,
        env=common_env,
        text=True,
        capture_output=True,
    )
    lint_result = subprocess.run(
        [str(lint_path)],
        cwd=project_root,
        env=common_env,
        text=True,
        capture_output=True,
    )

    assert fmt_result.returncode == 0, fmt_result.stderr
    assert lint_result.returncode == 0, lint_result.stderr
    combined = (fmt_result.stdout + fmt_result.stderr + lint_result.stdout + lint_result.stderr).lower()
    assert root_prd not in combined
    # no files touched under root docs/
    root_docs = list((workspace_root / "docs").rglob("*"))
    assert all(item.name == "root.prd.md" for item in root_docs if item.is_file())
