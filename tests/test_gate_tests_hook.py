import json

from .helpers import PAYLOAD_ROOT
from .helpers import ensure_gates_config, run_hook, write_active_feature, write_file
from .helpers import write_json

SRC_PAYLOAD = '{"tool_input":{"file_path":"src/main/kotlin/service/RuleEngine.kt"}}'
DOC_PAYLOAD = '{"tool_input":{"file_path":"docs/readme.md"}}'


def test_allows_when_disabled(tmp_path):
    ensure_gates_config(tmp_path, {"tests_required": "disabled"})
    write_file(tmp_path, "src/main/kotlin/service/RuleEngine.kt", "class RuleEngine")

    result = run_hook(tmp_path, "gate-tests.sh", SRC_PAYLOAD)
    assert result.returncode == 0, result.stderr


def test_warns_but_allows_in_soft_mode(tmp_path):
    ensure_gates_config(tmp_path, {"tests_required": "soft"})
    write_file(tmp_path, "src/main/kotlin/service/RuleEngine.kt", "class RuleEngine")

    result = run_hook(tmp_path, "gate-tests.sh", SRC_PAYLOAD)
    assert result.returncode == 0
    assert "WARN" in (result.stderr or "")


def test_blocks_in_hard_mode_without_tests(tmp_path):
    ensure_gates_config(tmp_path, {"tests_required": "hard"})
    write_file(tmp_path, "src/main/kotlin/service/RuleEngine.kt", "class RuleEngine")

    result = run_hook(tmp_path, "gate-tests.sh", SRC_PAYLOAD)
    assert result.returncode == 2
    assert "нет теста" in (result.stderr or "")


def test_allows_in_hard_mode_with_matching_test(tmp_path):
    ensure_gates_config(tmp_path, {"tests_required": "hard"})
    write_file(tmp_path, "src/main/kotlin/service/RuleEngine.kt", "class RuleEngine")
    write_file(tmp_path, "src/test/kotlin/service/RuleEngineTest.kt", "class RuleEngineTest")

    result = run_hook(tmp_path, "gate-tests.sh", SRC_PAYLOAD)
    assert result.returncode == 0, result.stderr


def test_allows_with_plural_suffix(tmp_path):
    ensure_gates_config(tmp_path, {"tests_required": "hard"})
    write_file(tmp_path, "src/main/kotlin/service/RuleEngine.kt", "class RuleEngine")
    write_file(tmp_path, "src/test/kotlin/service/RuleEngineTests.kt", "class RuleEngineTests")

    result = run_hook(tmp_path, "gate-tests.sh", SRC_PAYLOAD)
    assert result.returncode == 0, result.stderr


def test_non_source_paths_not_checked(tmp_path):
    ensure_gates_config(tmp_path, {"tests_required": "hard"})
    write_file(tmp_path, "docs/readme.md", "docs")

    result = run_hook(tmp_path, "gate-tests.sh", DOC_PAYLOAD)
    assert result.returncode == 0, result.stderr


def test_warns_when_reviewer_requests_tests(tmp_path):
    ensure_gates_config(tmp_path, {"tests_required": "soft"})
    write_active_feature(tmp_path, "demo")
    write_json(
        tmp_path,
        "reports/reviewer/demo.json",
        {"ticket": "demo", "slug": "demo", "tests": "required", "requested_by": "ci"},
    )
    write_file(tmp_path, "src/main/kotlin/service/RuleEngine.kt", "class RuleEngine")

    result = run_hook(tmp_path, "gate-tests.sh", SRC_PAYLOAD)
    assert result.returncode == 0
    assert "reviewer запросил обязательный запуск тестов" in (result.stderr or "")


def test_plugin_hooks_include_tests_and_post_hooks():
    hooks = json.loads((PAYLOAD_ROOT / "hooks" / "hooks.json").read_text(encoding="utf-8"))
    pre_cmds = [
        hook.get("command", "")
        for entry in hooks.get("hooks", {}).get("PreToolUse", [])
        for hook in entry.get("hooks", [])
    ]
    post_cmds = [
        hook.get("command", "")
        for entry in hooks.get("hooks", {}).get("PostToolUse", [])
        for hook in entry.get("hooks", [])
    ]
    stop_cmds = [
        hook.get("command", "")
        for entry in hooks.get("hooks", {}).get("Stop", [])
        for hook in entry.get("hooks", [])
    ]
    post_cmds = [
        hook.get("command", "")
        for entry in hooks.get("hooks", {}).get("PostToolUse", [])
        for hook in entry.get("hooks", [])
    ]
    sub_stop_cmds = [
        hook.get("command", "")
        for entry in hooks.get("hooks", {}).get("SubagentStop", [])
        for hook in entry.get("hooks", [])
    ]
    assert any("gate-tests.sh" in cmd for cmd in pre_cmds), "gate-tests missing in PreToolUse hooks"
    assert any("format-and-test.sh" in cmd for cmd in post_cmds), "format-and-test missing in PostToolUse"
    assert any("lint-deps.sh" in cmd for cmd in post_cmds), "lint-deps missing in PostToolUse"
    assert any("format-and-test.sh" in cmd for cmd in stop_cmds + sub_stop_cmds), (
        "format-and-test missing in Stop/SubagentStop"
    )
    assert any("lint-deps.sh" in cmd for cmd in stop_cmds + sub_stop_cmds), (
        "lint-deps missing in Stop/SubagentStop"
    )
