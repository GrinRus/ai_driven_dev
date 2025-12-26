import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Optional

from .helpers import PAYLOAD_ROOT, REPO_ROOT, cli_cmd, git_init, write_active_feature, write_file

HOOK = PAYLOAD_ROOT / "hooks" / "format-and-test.sh"


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
                    "marker": "reports/reviewer/{ticket}.json",
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
    project = tmp_path / "aidd"
    project.mkdir(parents=True, exist_ok=True)
    git_init(project)
    settings = write_settings(project, {})
    (project / "src/main/kotlin/app").mkdir(parents=True, exist_ok=True)
    (project / "src/main/kotlin/app/App.kt").write_text("class App", encoding="utf-8")

    result = run_hook(project, settings, env={"TEST_SCOPE": "module-task"})

    assert "Выбранные задачи тестов: module-task" in result.stderr
    assert "Запуск тестов: /bin/echo module-task" in result.stderr


def test_common_change_forces_full_suite(tmp_path):
    project = tmp_path / "aidd"
    project.mkdir(parents=True, exist_ok=True)
    git_init(project)
    settings = write_settings(project, {})
    (project / "config").mkdir(parents=True, exist_ok=True)
    (project / "config/app.yml").write_text("feature: true", encoding="utf-8")
    (project / "docs").mkdir(parents=True, exist_ok=True)
    write_active_feature(project, "demo")

    result = run_hook(project, settings)

    assert "Изменены только некодовые файлы" in result.stderr
    assert "Запуск тестов" not in result.stderr


def test_reviewer_marker_forces_full_suite(tmp_path):
    project = tmp_path / "aidd"
    project.mkdir(parents=True, exist_ok=True)
    git_init(project)
    settings = write_settings(project, {})
    (project / "config").mkdir(parents=True, exist_ok=True)
    (project / "config/app.yml").write_text("feature: true", encoding="utf-8")
    (project / "docs").mkdir(parents=True, exist_ok=True)
    write_active_feature(project, "demo")
    marker = project / "reports" / "reviewer" / "demo.json"
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text('{"ticket": "demo", "slug": "demo", "tests": "required"}', encoding="utf-8")

    result = run_hook(project, settings)

    assert "reviewer запросил тесты" in result.stderr
    assert "Выбранные задачи тестов: default_task" in result.stderr
    assert "Запуск тестов: /bin/echo default_task" in result.stderr


def test_skip_auto_tests_env(tmp_path):
    project = tmp_path / "aidd"
    project.mkdir(parents=True, exist_ok=True)
    git_init(project)
    settings = write_settings(project, {})

    result = run_hook(project, settings, env={"SKIP_AUTO_TESTS": "1"})

    assert "SKIP_AUTO_TESTS=1" in result.stderr
    assert "Запуск тестов" not in result.stderr


def test_snake_case_reviewer_gate_config(tmp_path):
    project = tmp_path / "aidd"
    project.mkdir(parents=True, exist_ok=True)
    git_init(project)
    settings = write_settings(project, {})
    payload = json.loads(settings.read_text(encoding="utf-8"))
    payload["automation"]["tests"]["reviewerGate"].update(
        {
            "enabled": True,
            "tests_marker": "reports/reviewer/{slug}.json",
            "tests_field": "state",
            "required_values": ["force"],
            "optional_values": ["idle"],
        }
    )
    settings.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    (project / "config").mkdir(parents=True, exist_ok=True)
    (project / "config/app.yml").write_text("feature: true", encoding="utf-8")
    (project / "docs").mkdir(parents=True, exist_ok=True)
    write_active_feature(project, "demo", slug_hint="checkout-lite")
    marker = project / "reports" / "reviewer" / "checkout-lite.json"
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text('{"ticket": "demo", "slug": "checkout-lite", "state": "force"}', encoding="utf-8")

    result = run_hook(project, settings)

    assert "reviewer запросил тесты" in result.stderr
    assert "default_task" in result.stderr


def test_reviewer_tests_cli_accepts_snake_case_status(tmp_path):
    settings = {
        "automation": {
            "tests": {
                "reviewerGate": {
                    "enabled": True,
                    "tests_marker": "reports/reviewer/{ticket}.json",
                    "tests_field": "state",
                    "required_values": ["force"],
                    "optional_values": ["idle"],
                }
            }
        }
    }
    project = tmp_path / "aidd"
    project.mkdir(parents=True, exist_ok=True)
    settings_path = tmp_path / ".claude" / "settings.json"
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    settings_path.write_text(json.dumps(settings, indent=2), encoding="utf-8")
    write_active_feature(project, "demo")
    env = os.environ.copy()
    python_path = str(REPO_ROOT / "src")
    existing = env.get("PYTHONPATH")
    env["PYTHONPATH"] = f"{python_path}:{existing}" if existing else python_path

    cmd = cli_cmd(
        "reviewer-tests",
        "--target",
        str(tmp_path),
        "--status",
        "force",
    )
    result = subprocess.run(cmd, cwd=tmp_path, text=True, capture_output=True, env=env, check=True)
    assert result.returncode == 0, result.stderr

    marker = project / "reports" / "reviewer" / "demo.json"
    payload = json.loads(marker.read_text(encoding="utf-8"))
    assert payload["state"] == "force"

    cmd_idle = cli_cmd(
        "reviewer-tests",
        "--target",
        str(tmp_path),
        "--status",
        "idle",
    )
    result_idle = subprocess.run(cmd_idle, cwd=tmp_path, text=True, capture_output=True, env=env, check=True)
    assert result_idle.returncode == 0, result_idle.stderr
    payload_idle = json.loads(marker.read_text(encoding="utf-8"))
    assert payload_idle["state"] == "idle"
