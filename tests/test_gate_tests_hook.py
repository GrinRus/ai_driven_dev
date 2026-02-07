import json
import tempfile
import unittest
from pathlib import Path

from .helpers import HOOKS_DIR, ensure_gates_config, run_hook, write_active_feature, write_active_stage, write_file
from .helpers import write_json

SRC_PAYLOAD = '{"tool_input":{"file_path":"src/main/kotlin/service/RuleEngine.kt"}}'
DOC_PAYLOAD = '{"tool_input":{"file_path":"docs/readme.md"}}'


def test_allows_when_disabled(tmp_path):
    ensure_gates_config(tmp_path, {"tests_required": "disabled"})
    write_active_stage(tmp_path, "review")
    write_file(tmp_path, "src/main/kotlin/service/RuleEngine.kt", "class RuleEngine")

    result = run_hook(tmp_path, "gate-tests.sh", SRC_PAYLOAD)
    assert result.returncode == 0, result.stderr


def test_warns_but_allows_in_soft_mode(tmp_path):
    ensure_gates_config(tmp_path, {"tests_required": "soft"})
    write_active_stage(tmp_path, "review")
    write_file(tmp_path, "src/main/kotlin/service/RuleEngine.kt", "class RuleEngine")

    result = run_hook(tmp_path, "gate-tests.sh", SRC_PAYLOAD)
    assert result.returncode == 0
    assert "WARN" in (result.stdout or "")


def test_blocks_in_hard_mode_without_tests(tmp_path):
    ensure_gates_config(tmp_path, {"tests_required": "hard"})
    write_active_stage(tmp_path, "review")
    write_file(tmp_path, "src/main/kotlin/service/RuleEngine.kt", "class RuleEngine")

    result = run_hook(tmp_path, "gate-tests.sh", SRC_PAYLOAD)
    assert result.returncode == 2
    assert "нет теста" in (result.stderr or "")


def test_allows_in_hard_mode_with_matching_test(tmp_path):
    ensure_gates_config(tmp_path, {"tests_required": "hard"})
    write_active_stage(tmp_path, "review")
    write_file(tmp_path, "src/main/kotlin/service/RuleEngine.kt", "class RuleEngine")
    write_file(tmp_path, "src/test/kotlin/service/RuleEngineTest.kt", "class RuleEngineTest")

    result = run_hook(tmp_path, "gate-tests.sh", SRC_PAYLOAD)
    assert result.returncode == 0, result.stderr


def test_allows_with_plural_suffix(tmp_path):
    ensure_gates_config(tmp_path, {"tests_required": "hard"})
    write_active_stage(tmp_path, "review")
    write_file(tmp_path, "src/main/kotlin/service/RuleEngine.kt", "class RuleEngine")
    write_file(tmp_path, "src/test/kotlin/service/RuleEngineTests.kt", "class RuleEngineTests")

    result = run_hook(tmp_path, "gate-tests.sh", SRC_PAYLOAD)
    assert result.returncode == 0, result.stderr


def test_non_source_paths_not_checked(tmp_path):
    ensure_gates_config(tmp_path, {"tests_required": "hard"})
    write_active_stage(tmp_path, "review")
    write_file(tmp_path, "docs/readme.md", "docs")

    result = run_hook(tmp_path, "gate-tests.sh", DOC_PAYLOAD)
    assert result.returncode == 0, result.stderr


def test_skips_test_directories(tmp_path):
    ensure_gates_config(tmp_path, {"tests_required": "hard"})
    write_active_stage(tmp_path, "implement")
    write_file(tmp_path, "src/test/kotlin/service/RuleEngineTest.kt", "class RuleEngineTest")

    payload = '{"tool_input":{"file_path":"src/test/kotlin/service/RuleEngineTest.kt"}}'
    result = run_hook(tmp_path, "gate-tests.sh", payload)
    assert result.returncode == 0, result.stderr


def test_warns_when_reviewer_requests_tests(tmp_path):
    ensure_gates_config(tmp_path, {"tests_required": "soft"})
    write_active_feature(tmp_path, "demo")
    write_active_stage(tmp_path, "review")
    write_json(
        tmp_path,
        "reports/reviewer/demo/demo.tests.json",
        {"ticket": "demo", "slug": "demo", "tests": "required", "requested_by": "ci"},
    )
    write_file(tmp_path, "src/main/kotlin/service/RuleEngine.kt", "class RuleEngine")

    result = run_hook(tmp_path, "gate-tests.sh", SRC_PAYLOAD)
    assert result.returncode == 0
    assert "reviewer запросил обязательный запуск тестов" in (result.stdout or "")


def test_gate_tests_requires_plugin_root(tmp_path):
    ensure_gates_config(tmp_path, {"tests_required": "hard"})
    project_root = tmp_path / "aidd"
    project_root.mkdir(exist_ok=True)
    write_active_feature(project_root, "demo")
    write_active_stage(project_root, "implement")
    write_file(project_root, "src/main/kotlin/service/RuleEngine.kt", "class RuleEngine")
    write_file(project_root, "src/test/kotlin/service/RuleEngineTest.kt", "class RuleEngineTest")

    env = {"CLAUDE_PLUGIN_ROOT": ""}
    result = run_hook(tmp_path, "gate-tests.sh", SRC_PAYLOAD, extra_env=env)
    assert result.returncode == 2
    assert "CLAUDE_PLUGIN_ROOT is required" in result.stderr

def test_plugin_hooks_include_tests_and_post_hooks():
    hooks = json.loads((HOOKS_DIR / "hooks.json").read_text(encoding="utf-8"))
    stop_cmds = [
        hook.get("command", "")
        for entry in hooks.get("hooks", {}).get("Stop", [])
        for hook in entry.get("hooks", [])
    ]
    sub_stop_cmds = [
        hook.get("command", "")
        for entry in hooks.get("hooks", {}).get("SubagentStop", [])
        for hook in entry.get("hooks", [])
    ]
    assert any("gate-tests.sh" in cmd for cmd in stop_cmds + sub_stop_cmds), (
        "gate-tests missing in Stop/SubagentStop"
    )
    assert any("format-and-test.sh" in cmd for cmd in stop_cmds + sub_stop_cmds), (
        "format-and-test missing in Stop/SubagentStop"
    )
    assert any("lint-deps.sh" in cmd for cmd in stop_cmds + sub_stop_cmds), (
        "lint-deps missing in Stop/SubagentStop"
    )


class GateTestsEventTests(unittest.TestCase):
    def test_gate_tests_appends_event(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            ensure_gates_config(tmp_path, {"tests_required": "soft"})
            write_active_feature(tmp_path, "gate-soft")
            write_active_stage(tmp_path, "review")
            write_file(tmp_path, "src/main/kotlin/service/RuleEngine.kt", "class RuleEngine")

            result = run_hook(tmp_path, "gate-tests.sh", SRC_PAYLOAD)

            self.assertEqual(result.returncode, 0, result.stderr)
            events_path = tmp_path / "aidd" / "reports" / "events" / "gate-soft.jsonl"
            self.assertTrue(events_path.exists())
            last_event = json.loads(events_path.read_text(encoding="utf-8").splitlines()[-1])
            self.assertEqual(last_event.get("type"), "gate-tests")
            self.assertEqual(last_event.get("status"), "warn")
