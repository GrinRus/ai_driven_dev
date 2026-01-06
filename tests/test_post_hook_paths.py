import json
import os
import shutil
import subprocess

from tests.helpers import PAYLOAD_ROOT, write_active_feature, write_file


def _copy_hook(src_name: str, dst_dir):
    src = PAYLOAD_ROOT / "hooks" / src_name
    dst = dst_dir / src_name
    dst_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    return dst


def test_post_hooks_use_project_aidd_root_when_plugin_root_empty(tmp_path):
    slug = "demo"
    legacy_root = tmp_path
    write_file(legacy_root, "docs/prd/legacy.prd.md", "# Legacy")

    project_root = legacy_root / "aidd"
    project_root.mkdir(exist_ok=True)
    write_active_feature(project_root, slug)
    write_file(project_root, f"docs/prd/{slug}.prd.md", "# PRD\n\n## PRD Review\nStatus: READY\n")
    write_file(project_root, f"docs/plan/{slug}.md", "# Plan\n\n## Plan Review\nStatus: READY\n")
    write_file(project_root, f"docs/tasklist/{slug}.md", "- [ ] impl\n")
    write_file(project_root, f"docs/research/{slug}.md", "# Research\nStatus: reviewed\n")
    write_file(project_root, "src/main/kotlin/App.kt", "class App")

    hooks_dir = project_root / "hooks"
    fmt_path = _copy_hook("format-and-test.sh", hooks_dir)
    lint_path = _copy_hook("lint-deps.sh", hooks_dir)
    _copy_hook("lib.sh", hooks_dir)
    settings_src = PAYLOAD_ROOT.parent / ".claude" / "settings.json"
    settings_dst = legacy_root / ".claude" / "settings.json"
    settings_dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(settings_src, settings_dst)
    # minimal config for lint-deps allowlist off
    write_file(project_root, "config/gates.json", json.dumps({"deps_allowlist": False}))

    # allowlist file only under aidd/; legacy root lacks it
    write_file(project_root, "config/allowed-deps.txt", "com.acme:ok-lib\n")

    common_env = os.environ.copy()
    common_env.update(
        {
            "CLAUDE_PLUGIN_ROOT": "",
            "CLAUDE_PROJECT_DIR": str(legacy_root),
            "PYTHONPATH": f"{PAYLOAD_ROOT.parents[4] / 'src'}:{common_env.get('PYTHONPATH','')}",
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
    assert "legacy" not in combined
    # no files touched under legacy docs/
    legacy_docs = list((legacy_root / "docs").rglob("*"))
    assert all(item.name == "legacy.prd.md" for item in legacy_docs if item.is_file())
