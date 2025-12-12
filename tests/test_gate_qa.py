import json
import os

from .helpers import PAYLOAD_ROOT, ensure_gates_config, run_hook, write_active_feature, write_file

SRC_PAYLOAD = '{"tool_input":{"file_path":"src/main/App.kt"}}'


def test_blocks_when_report_missing(tmp_path):
    ensure_gates_config(
        tmp_path,
        {
            "qa": {
                "enabled": True,
                "command": ["true"],
                "allow_missing_report": False,
                "report": "reports/qa/{ticket}.json",
            }
        },
    )
    write_active_feature(tmp_path, "qa-demo")
    write_file(tmp_path, "src/main/App.kt", "class App")

    os.environ["CLAUDE_SKIP_TASKLIST_PROGRESS"] = "1"
    os.environ["CLAUDE_PROJECT_DIR"] = str(tmp_path)
    try:
        result = run_hook(tmp_path, "gate-qa.sh", SRC_PAYLOAD)
    finally:
        os.environ.pop("CLAUDE_SKIP_TASKLIST_PROGRESS", None)
        os.environ.pop("CLAUDE_PROJECT_DIR", None)

    assert result.returncode != 0
    assert "отчёт QA не создан" in (result.stderr or "")


def test_allows_when_report_present(tmp_path):
    ensure_gates_config(
        tmp_path,
        {
            "qa": {
                "enabled": True,
                "command": ["true"],
                "allow_missing_report": False,
                "report": "reports/qa/{ticket}.json",
            }
        },
    )
    write_active_feature(tmp_path, "qa-ok")
    write_file(tmp_path, "src/main/App.kt", "class App")
    write_file(tmp_path, "reports/qa/qa-ok.json", "{}\n")

    os.environ["CLAUDE_SKIP_TASKLIST_PROGRESS"] = "1"
    os.environ["CLAUDE_PROJECT_DIR"] = str(tmp_path)
    try:
        result = run_hook(tmp_path, "gate-qa.sh", SRC_PAYLOAD)
    finally:
        os.environ.pop("CLAUDE_SKIP_TASKLIST_PROGRESS", None)
        os.environ.pop("CLAUDE_PROJECT_DIR", None)

    assert result.returncode == 0, result.stderr


def test_skip_env_allows(tmp_path):
    ensure_gates_config(
        tmp_path,
        {
            "qa": {
                "enabled": True,
                "command": ["true"],
                "allow_missing_report": False,
                "report": "reports/qa/{ticket}.json",
            }
        },
    )
    write_active_feature(tmp_path, "qa-skip")
    write_file(tmp_path, "src/main/App.kt", "class App")
    os.environ["CLAUDE_SKIP_QA"] = "1"
    os.environ["CLAUDE_SKIP_TASKLIST_PROGRESS"] = "1"
    os.environ["CLAUDE_PROJECT_DIR"] = str(tmp_path)
    try:
        result = run_hook(tmp_path, "gate-qa.sh", SRC_PAYLOAD)
    finally:
        os.environ.pop("CLAUDE_SKIP_QA", None)
        os.environ.pop("CLAUDE_SKIP_TASKLIST_PROGRESS", None)
        os.environ.pop("CLAUDE_PROJECT_DIR", None)

    assert result.returncode == 0, result.stderr


def test_plugin_hooks_include_qa_gate():
    hooks = json.loads((PAYLOAD_ROOT / "hooks" / "hooks.json").read_text(encoding="utf-8"))
    pre_hooks = hooks.get("hooks", {}).get("PreToolUse", [])
    commands = [hook for entry in pre_hooks for hook in entry.get("hooks", [])]
    qa_hook = next((hook for hook in commands if "gate-qa.sh" in hook.get("command", "")), None)
    assert qa_hook is not None, "gate-qa hook not registered in PreToolUse"
    assert qa_hook.get("timeout") == 60, "gate-qa expected timeout=60s"


def test_gate_qa_resolves_aidd_root_when_plugin_root_missing(tmp_path):
    ensure_gates_config(tmp_path)
    project_root = tmp_path / "aidd"
    project_root.mkdir(exist_ok=True)
    write_active_feature(project_root, "demo")
    write_file(project_root, "src/main/App.kt", "class App")
    write_file(project_root, "docs/tasklist/demo.md", "- [ ] QA")
    write_file(project_root, "docs/prd/demo.prd.md", "# PRD\n\n## PRD Review\nStatus: approved\n")
    write_file(project_root, "docs/plan/demo.md", "# Plan")
    write_file(project_root, "docs/research/demo.md", "# Research\nStatus: reviewed\n")
    write_file(project_root, "reports/qa/demo.json", '{"status": "ready"}\n')

    env = {"CLAUDE_PLUGIN_ROOT": "", "CLAUDE_PROJECT_DIR": str(tmp_path)}
    result = run_hook(tmp_path, "gate-qa.sh", SRC_PAYLOAD, extra_env=env)
    assert result.returncode in (0, 2)
    combined = result.stdout + result.stderr
    assert "/aidd" in combined
