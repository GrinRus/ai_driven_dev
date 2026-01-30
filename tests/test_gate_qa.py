import json
import tempfile
import unittest
from pathlib import Path

from tools import qa as qa_tools

from .helpers import HOOKS_DIR, ensure_gates_config, run_hook, write_active_feature, write_active_stage, write_file

SRC_PAYLOAD = '{"tool_input":{"file_path":"src/main/App.kt"}}'


def test_blocks_when_report_missing(tmp_path):
    ensure_gates_config(
        tmp_path,
        {
            "qa": {
                "enabled": True,
                "command": ["true"],
                "allow_missing_report": False,
                "report": "aidd/reports/qa/{ticket}.json",
            }
        },
    )
    write_active_feature(tmp_path, "qa-demo")
    write_active_stage(tmp_path, "qa")
    write_file(tmp_path, "src/main/App.kt", "class App")

    result = run_hook(
        tmp_path,
        "gate-qa.sh",
        SRC_PAYLOAD,
        extra_env={"CLAUDE_SKIP_TASKLIST_PROGRESS": "1"},
    )

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
                "report": "aidd/reports/qa/{ticket}.json",
            }
        },
    )
    write_active_feature(tmp_path, "qa-ok")
    write_active_stage(tmp_path, "qa")
    write_file(tmp_path, "src/main/App.kt", "class App")
    write_file(tmp_path, "reports/qa/qa-ok.json", "{}\n")

    result = run_hook(
        tmp_path,
        "gate-qa.sh",
        SRC_PAYLOAD,
        extra_env={"CLAUDE_SKIP_TASKLIST_PROGRESS": "1"},
    )

    assert result.returncode == 0, result.stderr


def test_allows_when_pack_present(tmp_path):
    ensure_gates_config(
        tmp_path,
        {
            "qa": {
                "enabled": True,
                "command": ["true"],
                "allow_missing_report": False,
                "report": "aidd/reports/qa/{ticket}.json",
            }
        },
    )
    write_active_feature(tmp_path, "qa-pack")
    write_active_stage(tmp_path, "qa")
    write_file(tmp_path, "src/main/App.kt", "class App")
    write_file(tmp_path, "reports/qa/qa-pack.pack.json", "{}\n")

    result = run_hook(
        tmp_path,
        "gate-qa.sh",
        SRC_PAYLOAD,
        extra_env={"CLAUDE_SKIP_TASKLIST_PROGRESS": "1"},
    )

    assert result.returncode == 0, result.stderr


def test_handoff_blocks_when_tasklist_missing(tmp_path):
    ensure_gates_config(
        tmp_path,
        {
            "qa": {
                "enabled": True,
                "command": ["true"],
                "allow_missing_report": False,
                "report": "aidd/reports/qa/{ticket}.json",
                "handoff": True,
                "handoff_mode": "block",
            }
        },
    )
    write_active_feature(tmp_path, "qa-handoff")
    write_active_stage(tmp_path, "qa")
    write_file(tmp_path, "src/main/App.kt", "class App")
    write_file(
        tmp_path,
        "reports/qa/qa-handoff.json",
        json.dumps({"tests_summary": "pass", "tests_executed": [], "findings": []}) + "\n",
    )

    result = run_hook(tmp_path, "gate-qa.sh", SRC_PAYLOAD)

    assert result.returncode == 2
    combined = (result.stdout + result.stderr).lower()
    assert "tasklist" in combined or "handoff" in combined


def test_handoff_warns_when_configured(tmp_path):
    ensure_gates_config(
        tmp_path,
        {
            "qa": {
                "enabled": True,
                "command": ["true"],
                "allow_missing_report": False,
                "report": "aidd/reports/qa/{ticket}.json",
                "handoff": True,
                "handoff_mode": "warn",
            }
        },
    )
    write_active_feature(tmp_path, "qa-warn")
    write_active_stage(tmp_path, "qa")
    write_file(tmp_path, "src/main/App.kt", "class App")
    write_file(
        tmp_path,
        "reports/qa/qa-warn.json",
        json.dumps({"tests_summary": "pass", "tests_executed": [], "findings": []}) + "\n",
    )

    result = run_hook(tmp_path, "gate-qa.sh", SRC_PAYLOAD)

    assert result.returncode == 0, result.stderr
    combined = (result.stdout + result.stderr).lower()
    assert "tasklist" in combined or "handoff" in combined


def test_skip_env_allows(tmp_path):
    ensure_gates_config(
        tmp_path,
        {
            "qa": {
                "enabled": True,
                "command": ["true"],
                "allow_missing_report": False,
                "report": "aidd/reports/qa/{ticket}.json",
            }
        },
    )
    write_active_feature(tmp_path, "qa-skip")
    write_active_stage(tmp_path, "qa")
    write_file(tmp_path, "src/main/App.kt", "class App")
    result = run_hook(
        tmp_path,
        "gate-qa.sh",
        SRC_PAYLOAD,
        extra_env={
            "CLAUDE_SKIP_QA": "1",
            "CLAUDE_SKIP_TASKLIST_PROGRESS": "1",
        },
    )

    assert result.returncode == 0, result.stderr


def test_discovery_respects_allowlist(tmp_path):
    ensure_gates_config(
        tmp_path,
        {
            "qa": {
                "tests": {
                    "source": "readme-ci",
                    "discover": {
                        "max_files": 10,
                        "max_bytes": 200000,
                        "allow_paths": ["README*"],
                    },
                }
            }
        },
    )
    write_file(tmp_path, "README.md", "run: pytest\n")
    write_file(tmp_path, ".github/workflows/ci.yml", "- run: npm test\n")

    commands, _ = qa_tools._load_qa_tests_config(tmp_path / "aidd")

    assert commands == [["pytest"]]


def test_discovery_preserves_python_pytest_prefix(tmp_path):
    ensure_gates_config(
        tmp_path,
        {
            "qa": {
                "tests": {
                    "source": "readme-ci",
                    "discover": {
                        "max_files": 10,
                        "max_bytes": 200000,
                        "allow_paths": ["README*"],
                    },
                }
            }
        },
    )
    write_file(tmp_path, "README.md", "python -m pytest -q\n")

    commands, _ = qa_tools._load_qa_tests_config(tmp_path / "aidd")

    assert commands == [["python", "-m", "pytest", "-q"]]


def test_discovery_respects_max_files(tmp_path):
    ensure_gates_config(
        tmp_path,
        {
            "qa": {
                "tests": {
                    "source": "readme-ci",
                    "discover": {
                        "max_files": 1,
                        "max_bytes": 200000,
                        "allow_paths": ["README*"],
                    },
                }
            }
        },
    )
    write_file(tmp_path, "README-1.md", "pytest\n")
    write_file(tmp_path, "README-2.md", "npm test\n")

    commands, _ = qa_tools._load_qa_tests_config(tmp_path / "aidd")

    assert commands == [["pytest"]]


def test_debounce_stamp_written_only_on_success(tmp_path):
    ensure_gates_config(
        tmp_path,
        {
            "qa": {
                "enabled": True,
                "command": ["false"],
                "allow_missing_report": False,
                "report": "aidd/reports/qa/{ticket}.json",
                "debounce_minutes": 10,
            }
        },
    )
    write_active_feature(tmp_path, "qa-fail")
    write_active_stage(tmp_path, "qa")
    write_file(tmp_path, "src/main/App.kt", "class App")

    result = run_hook(
        tmp_path,
        "gate-qa.sh",
        SRC_PAYLOAD,
        extra_env={"CLAUDE_SKIP_TASKLIST_PROGRESS": "1"},
    )

    assert result.returncode != 0
    stamp_path = tmp_path / "aidd" / "reports" / "qa" / ".gate-qa.qa-fail.stamp"
    assert not stamp_path.exists()


def test_plugin_hooks_include_qa_gate():
    hooks = json.loads((HOOKS_DIR / "hooks.json").read_text(encoding="utf-8"))
    stop_hooks = hooks.get("hooks", {}).get("Stop", [])
    sub_stop_hooks = hooks.get("hooks", {}).get("SubagentStop", [])
    commands = [
        hook
        for entry in stop_hooks + sub_stop_hooks
        for hook in entry.get("hooks", [])
    ]
    qa_hook = next((hook for hook in commands if "gate-qa.sh" in hook.get("command", "")), None)
    assert qa_hook is not None, "gate-qa hook not registered in Stop/SubagentStop"
    assert qa_hook.get("timeout") == 60, "gate-qa expected timeout=60s"


def test_gate_qa_requires_plugin_root(tmp_path):
    ensure_gates_config(tmp_path)
    project_root = tmp_path / "aidd"
    project_root.mkdir(exist_ok=True)
    write_active_feature(project_root, "demo")
    write_active_stage(project_root, "qa")
    write_file(project_root, "src/main/App.kt", "class App")
    write_file(project_root, "docs/tasklist/demo.md", "- [ ] QA")
    write_file(project_root, "docs/prd/demo.prd.md", "# PRD\n\n## PRD Review\nStatus: READY\n")
    write_file(project_root, "docs/plan/demo.md", "# Plan\n\n## Plan Review\nStatus: READY\n")
    write_file(project_root, "docs/research/demo.md", "# Research\nStatus: reviewed\n")
    write_file(project_root, "reports/qa/demo.json", '{"status": "READY"}\n')

    env = {"CLAUDE_PLUGIN_ROOT": ""}
    result = run_hook(tmp_path, "gate-qa.sh", SRC_PAYLOAD, extra_env=env)
    assert result.returncode == 2
    assert "CLAUDE_PLUGIN_ROOT is required" in result.stderr


class GateQaEventTests(unittest.TestCase):
    def test_gate_qa_appends_event(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            ensure_gates_config(
                tmp_path,
                {
                    "qa": {
                        "enabled": True,
                        "command": ["true"],
                        "allow_missing_report": False,
                "report": "aidd/reports/qa/{ticket}.json",
                    }
                },
            )
            write_active_feature(tmp_path, "qa-ok")
            write_active_stage(tmp_path, "qa")
            write_file(tmp_path, "src/main/App.kt", "class App")
            write_file(tmp_path, "reports/qa/qa-ok.json", "{}\n")

            env = {"CLAUDE_SKIP_TASKLIST_PROGRESS": "1"}
            result = run_hook(tmp_path, "gate-qa.sh", SRC_PAYLOAD, extra_env=env)

            self.assertEqual(result.returncode, 0, result.stderr)
            events_path = tmp_path / "aidd" / "reports" / "events" / "qa-ok.jsonl"
            self.assertTrue(events_path.exists())
            last_event = json.loads(events_path.read_text(encoding="utf-8").splitlines()[-1])
            self.assertEqual(last_event.get("type"), "gate-qa")
            self.assertEqual(last_event.get("status"), "pass")
