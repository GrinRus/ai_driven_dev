import os

from .helpers import ensure_gates_config, run_hook, write_active_feature, write_file

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
