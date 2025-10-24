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
