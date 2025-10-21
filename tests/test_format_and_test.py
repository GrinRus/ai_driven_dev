import json
import subprocess
from pathlib import Path
from typing import Optional

from .helpers import git_init

HOOK = Path(__file__).resolve().parents[1] / ".claude/hooks/format-and-test.sh"


def write_settings(tmp_path: Path, overrides: dict) -> Path:
    base = {
        "automation": {
            "format": {"commands": []},
            "tests": {
                "runner": "/bin/echo",
                "defaultTasks": ["default_task"],
                "fallbackTasks": [],
                "changedOnly": True,
                "strictDefault": 1,
                "moduleMatrix": [],
                "reviewerGate": {
                    "enabled": True,
                    "marker": "reports/reviewer/{slug}.json",
                    "field": "tests",
                    "requiredValues": ["required"],
                    "optionalValues": ["optional", "skipped", "not-required"],
                    "forceEnv": "FORCE_TESTS",
                    "skipEnv": "SKIP_TESTS",
                },
            },
        },
    }
    # shallow merge for tests
    for key, value in overrides.items():
        if isinstance(value, dict) and key in base:
            base[key].update(value)
        else:
            base[key] = value
    settings_path = tmp_path / "settings.json"
    settings_path.write_text(json.dumps(base, indent=2), encoding="utf-8")
    return settings_path


def run_hook(
    tmp_path: Path, settings_path: Path, env: Optional[dict] = None
) -> subprocess.CompletedProcess[str]:
    effective_env = {
        "CLAUDE_SETTINGS_PATH": str(settings_path),
        "SKIP_FORMAT": "1",
        **({} if env is None else env),
    }
    return subprocess.run(
        [str(HOOK)],
        cwd=tmp_path,
        text=True,
        capture_output=True,
        env=effective_env,
        check=True,
    )


def test_module_matrix_tasks_logged(tmp_path):
    git_init(tmp_path)
    settings = write_settings(tmp_path, {})
    (tmp_path / "src/main/kotlin/app").mkdir(parents=True, exist_ok=True)
    (tmp_path / "src/main/kotlin/app/App.kt").write_text("class App", encoding="utf-8")

    result = run_hook(tmp_path, settings, env={"TEST_SCOPE": "module-task"})

    assert "Выбранные задачи тестов: module-task" in result.stderr
    assert "Запуск тестов: /bin/echo module-task" in result.stderr


def test_common_change_forces_full_suite(tmp_path):
    git_init(tmp_path)
    settings = write_settings(tmp_path, {})
    (tmp_path / "config").mkdir(parents=True, exist_ok=True)
    (tmp_path / "config/app.yml").write_text("feature: true", encoding="utf-8")
    (tmp_path / "docs").mkdir(parents=True, exist_ok=True)
    (tmp_path / "docs/.active_feature").write_text("demo", encoding="utf-8")

    result = run_hook(tmp_path, settings)

    assert "Изменены только некодовые файлы" in result.stderr
    assert "Запуск тестов" not in result.stderr


def test_reviewer_marker_forces_full_suite(tmp_path):
    git_init(tmp_path)
    settings = write_settings(tmp_path, {})
    (tmp_path / "config").mkdir(parents=True, exist_ok=True)
    (tmp_path / "config/app.yml").write_text("feature: true", encoding="utf-8")
    (tmp_path / "docs").mkdir(parents=True, exist_ok=True)
    (tmp_path / "docs/.active_feature").write_text("demo", encoding="utf-8")
    marker = tmp_path / "reports" / "reviewer" / "demo.json"
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text('{"slug": "demo", "tests": "required"}', encoding="utf-8")

    result = run_hook(tmp_path, settings)

    assert "reviewer запросил тесты" in result.stderr
    assert "Выбранные задачи тестов: default_task" in result.stderr
    assert "Запуск тестов: /bin/echo default_task" in result.stderr


def test_skip_auto_tests_env(tmp_path):
    git_init(tmp_path)
    settings = write_settings(tmp_path, {})

    result = run_hook(tmp_path, settings, env={"SKIP_AUTO_TESTS": "1"})

    assert "SKIP_AUTO_TESTS=1" in result.stderr
    assert "Запуск тестов" not in result.stderr
