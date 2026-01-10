import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Optional

from .helpers import (
    PAYLOAD_ROOT,
    REPO_ROOT,
    cli_cmd,
    git_config_user,
    git_init,
    write_active_feature,
    write_active_stage,
    write_file,
    write_json,
)

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
                    "marker": "aidd/reports/reviewer/{ticket}.json",
                    "field": "tests",
                    "requiredValues": ["required"],
                    "optionalValues": ["optional", "skipped", "not-required"],
                    "forceEnv": "FORCE_TESTS",
                    "skipEnv": "SKIP_TESTS",
                },
            },
        },
    }
    automation_override = overrides.get("automation")
    if isinstance(automation_override, dict):
        tests_override = automation_override.get("tests")
        if isinstance(tests_override, dict):
            base["automation"]["tests"].update(tests_override)
        format_override = automation_override.get("format")
        if isinstance(format_override, dict):
            base["automation"]["format"].update(format_override)
        for key, value in automation_override.items():
            if key in {"tests", "format"}:
                continue
            base["automation"][key] = value
    for key, value in overrides.items():
        if key == "automation":
            continue
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
    effective_env = os.environ.copy()
    effective_env.update(
        {
            "CLAUDE_SETTINGS_PATH": str(settings_path),
            "SKIP_FORMAT": "1",
            "CLAUDE_PROJECT_DIR": str(tmp_path),
            "CLAUDE_PLUGIN_ROOT": str(tmp_path),
        }
    )
    if env:
        effective_env.update(env)
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
    write_active_stage(project, "implement")
    (project / "src/main/kotlin/app").mkdir(parents=True, exist_ok=True)
    (project / "src/main/kotlin/app/App.kt").write_text("class App", encoding="utf-8")

    result = run_hook(project, settings, env={"TEST_SCOPE": "module-task"})

    assert "Выбранные задачи тестов (fast): module-task" in result.stderr
    assert "Запуск тестов: /bin/echo module-task" in result.stderr


def test_common_change_forces_full_suite(tmp_path):
    project = tmp_path / "aidd"
    project.mkdir(parents=True, exist_ok=True)
    git_init(project)
    settings = write_settings(
        project,
        {
            "automation": {
                "tests": {
                    "fastTasks": ["fast_task"],
                    "fullTasks": ["full_task"],
                }
            }
        },
    )
    write_active_stage(project, "implement")
    (project / "config").mkdir(parents=True, exist_ok=True)
    (project / "config/app.yml").write_text("feature: true", encoding="utf-8")
    (project / "docs").mkdir(parents=True, exist_ok=True)
    cache_dir = project / ".cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    (cache_dir / "test-policy.env").write_text("AIDD_TEST_PROFILE=fast\n", encoding="utf-8")
    write_active_feature(project, "demo")

    result = run_hook(project, settings)

    assert "Test policy detected" in result.stderr
    assert "Выбранные задачи тестов (full): full_task" in result.stderr
    assert "Запуск тестов: /bin/echo full_task" in result.stderr


def test_reviewer_marker_forces_full_suite(tmp_path):
    project = tmp_path / "aidd"
    project.mkdir(parents=True, exist_ok=True)
    git_init(project)
    settings = write_settings(project, {})
    write_active_stage(project, "implement")
    (project / "config").mkdir(parents=True, exist_ok=True)
    (project / "config/app.yml").write_text("feature: true", encoding="utf-8")
    (project / "docs").mkdir(parents=True, exist_ok=True)
    write_active_feature(project, "demo")
    marker = project / "reports" / "reviewer" / "demo.json"
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text('{"ticket": "demo", "slug": "demo", "tests": "required"}', encoding="utf-8")

    result = run_hook(project, settings)

    assert "reviewer запросил тесты" in result.stderr
    assert "Выбранные задачи тестов (full): default_task" in result.stderr
    assert "Запуск тестов: /bin/echo default_task" in result.stderr


def test_manual_cadence_skips_tests_without_override(tmp_path):
    project = tmp_path / "aidd"
    project.mkdir(parents=True, exist_ok=True)
    git_init(project)
    settings = write_settings(
        project,
        {
            "automation": {
                "tests": {
                    "cadence": "manual",
                }
            }
        },
    )
    write_active_stage(project, "implement")
    write_active_feature(project, "demo")

    result = run_hook(project, settings)

    assert "cadence=manual" in result.stderr
    assert "Запуск тестов" not in result.stderr


def test_checkpoint_cadence_runs_with_checkpoint(tmp_path):
    project = tmp_path / "aidd"
    project.mkdir(parents=True, exist_ok=True)
    git_init(project)
    settings = write_settings(
        project,
        {
            "automation": {
                "tests": {
                    "cadence": "checkpoint",
                    "checkpointTrigger": "progress",
                }
            }
        },
    )
    write_active_stage(project, "implement")
    write_active_feature(project, "demo")
    write_json(
        project,
        ".cache/test-checkpoint.json",
        {"ticket": "demo", "trigger": "progress"},
    )

    result = run_hook(project, settings)

    assert "checkpoint trigger активен" in result.stderr
    assert "Запуск тестов" in result.stderr


def test_skip_auto_tests_env(tmp_path):
    project = tmp_path / "aidd"
    project.mkdir(parents=True, exist_ok=True)
    git_init(project)
    settings = write_settings(project, {})
    write_active_stage(project, "implement")

    result = run_hook(project, settings, env={"SKIP_AUTO_TESTS": "1"})

    assert "SKIP_AUTO_TESTS=1" in result.stderr
    assert "Запуск тестов" not in result.stderr


def test_snake_case_reviewer_gate_config(tmp_path):
    project = tmp_path / "aidd"
    project.mkdir(parents=True, exist_ok=True)
    git_init(project)
    settings = write_settings(project, {})
    write_active_stage(project, "implement")
    payload = json.loads(settings.read_text(encoding="utf-8"))
    payload["automation"]["tests"]["reviewerGate"].update(
        {
            "enabled": True,
            "tests_marker": "aidd/reports/reviewer/{slug}.json",
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
                    "tests_marker": "aidd/reports/reviewer/{ticket}.json",
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


def test_profile_none_skips_tests(tmp_path):
    project = tmp_path / "aidd"
    project.mkdir(parents=True, exist_ok=True)
    git_init(project)
    settings = write_settings(project, {})
    write_active_stage(project, "implement")
    (project / "src").mkdir(parents=True, exist_ok=True)
    (project / "src" / "main.py").write_text("print('ok')", encoding="utf-8")

    result = run_hook(project, settings, env={"AIDD_TEST_PROFILE": "none"})

    assert "AIDD_TEST_PROFILE=none" in result.stderr
    assert "Запуск тестов" not in result.stderr


def test_profile_full_uses_full_tasks(tmp_path):
    project = tmp_path / "aidd"
    project.mkdir(parents=True, exist_ok=True)
    git_init(project)
    settings = write_settings(
        project,
        {
            "automation": {
                "tests": {
                    "fastTasks": ["fast_task"],
                    "fullTasks": ["full_task"],
                }
            }
        },
    )
    write_active_stage(project, "implement")
    (project / "src").mkdir(parents=True, exist_ok=True)
    (project / "src" / "main.py").write_text("print('ok')", encoding="utf-8")

    result = run_hook(project, settings, env={"AIDD_TEST_PROFILE": "full"})

    assert "Выбранные задачи тестов (full): full_task" in result.stderr
    assert "Запуск тестов: /bin/echo full_task" in result.stderr


def test_policy_file_tasks_and_filters(tmp_path):
    project = tmp_path / "aidd"
    project.mkdir(parents=True, exist_ok=True)
    git_init(project)
    settings = write_settings(
        project,
        {"automation": {"tests": {"targetedTask": "fallback_target"}}},
    )
    write_active_stage(project, "implement")
    cache_dir = project / ".cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    (cache_dir / "test-policy.env").write_text(
        "\n".join(
            [
                "AIDD_TEST_PROFILE=targeted",
                "AIDD_TEST_TASKS=policy_task",
                "AIDD_TEST_FILTERS=FilterOne,FilterTwo",
            ]
        ),
        encoding="utf-8",
    )
    (project / "src").mkdir(parents=True, exist_ok=True)
    (project / "src" / "main.py").write_text("print('ok')", encoding="utf-8")

    result = run_hook(project, settings)

    assert "Test policy detected" in result.stderr
    assert "policy_task" in result.stderr
    assert "--tests FilterOne" in result.stderr
    assert "--tests FilterTwo" in result.stderr


def test_dedupe_skips_repeat_run_and_force_overrides(tmp_path):
    project = tmp_path / "aidd"
    project.mkdir(parents=True, exist_ok=True)
    git_init(project)
    settings = write_settings(project, {})
    write_active_stage(project, "implement")
    cache_dir = project / ".cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    (cache_dir / "test-policy.env").write_text("AIDD_TEST_PROFILE=fast\n", encoding="utf-8")
    (project / "src").mkdir(parents=True, exist_ok=True)
    (project / "src" / "main.py").write_text("print('ok')", encoding="utf-8")

    first = run_hook(project, settings)
    assert "Запуск тестов" in first.stderr

    second = run_hook(project, settings)
    assert "Dedupe: тесты уже запускались" in second.stderr
    assert "Запуск тестов" not in second.stderr

    forced = run_hook(project, settings, env={"AIDD_TEST_FORCE": "1"})
    assert "AIDD_TEST_FORCE=1" in forced.stderr
    assert "Запуск тестов" in forced.stderr


def test_dedupe_includes_staged_diff(tmp_path):
    project = tmp_path / "aidd"
    project.mkdir(parents=True, exist_ok=True)
    git_init(project)
    git_config_user(project)
    settings = write_settings(project, {})
    write_active_stage(project, "implement")
    cache_dir = project / ".cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    (cache_dir / "test-policy.env").write_text("AIDD_TEST_PROFILE=fast\n", encoding="utf-8")
    (project / "src").mkdir(parents=True, exist_ok=True)
    source = project / "src" / "main.py"
    source.write_text("print('v1')", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=project, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=project, check=True, capture_output=True)

    source.write_text("print('v2')", encoding="utf-8")
    subprocess.run(["git", "add", "src/main.py"], cwd=project, check=True, capture_output=True)
    first = run_hook(project, settings)
    assert "Запуск тестов" in first.stderr

    source.write_text("print('v3')", encoding="utf-8")
    subprocess.run(["git", "add", "src/main.py"], cwd=project, check=True, capture_output=True)
    second = run_hook(project, settings)
    assert "Dedupe: тесты уже запускались" not in second.stderr
    assert "Запуск тестов" in second.stderr


def test_default_profile_env_applies_when_no_policy(tmp_path):
    project = tmp_path / "aidd"
    project.mkdir(parents=True, exist_ok=True)
    git_init(project)
    settings = write_settings(
        project,
        {
            "automation": {
                "tests": {
                    "fastTasks": ["fast_task"],
                    "targetedTask": "target_task",
                    "reviewerGate": {"enabled": False},
                }
            }
        },
    )
    write_active_stage(project, "implement")
    (project / "src").mkdir(parents=True, exist_ok=True)
    (project / "src" / "main.py").write_text("print('ok')", encoding="utf-8")

    result = run_hook(project, settings, env={"AIDD_TEST_PROFILE_DEFAULT": "targeted"})

    assert "Test profile: targeted (source: default-env)." in result.stderr
    assert "Выбранные задачи тестов (targeted): target_task" in result.stderr


def test_summary_log_written(tmp_path):
    project = tmp_path / "aidd"
    project.mkdir(parents=True, exist_ok=True)
    git_init(project)
    settings = write_settings(
        project,
        {
            "automation": {
                "tests": {
                    "reviewerGate": {"enabled": False},
                }
            }
        },
    )
    write_active_stage(project, "implement")
    (project / "src").mkdir(parents=True, exist_ok=True)
    (project / "src" / "main.py").write_text("print('ok')", encoding="utf-8")

    run_hook(project, settings, env={"AIDD_TEST_LOG": "summary"})

    log_dir = project / ".cache" / "logs"
    logs = sorted(log_dir.glob("format-and-test.*.log"))
    assert logs, "expected summary log file to be created"
    assert "default_task" in logs[-1].read_text(encoding="utf-8")


class FormatAndTestEventTests(unittest.TestCase):
    def test_format_and_test_appends_event(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            project = Path(tmpdir) / "aidd"
            project.mkdir(parents=True, exist_ok=True)
            git_init(project)
            settings = write_settings(project, {})
            write_active_feature(project, "fmt-1")
            write_active_stage(project, "implement")
            (project / "src/main/kotlin/app").mkdir(parents=True, exist_ok=True)
            (project / "src/main/kotlin/app/App.kt").write_text("class App", encoding="utf-8")

            run_hook(project, settings)

            events_path = project / "reports" / "events" / "fmt-1.jsonl"
            self.assertTrue(events_path.exists())
            last_event = json.loads(events_path.read_text(encoding="utf-8").splitlines()[-1])
            self.assertEqual(last_event.get("type"), "format-and-test")
            self.assertIn(last_event.get("status"), {"pass", "skipped"})

    def test_format_and_test_appends_tests_log(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            project = Path(tmpdir) / "aidd"
            project.mkdir(parents=True, exist_ok=True)
            git_init(project)
            settings = write_settings(project, {})
            write_active_feature(project, "fmt-2")
            write_active_stage(project, "implement")
            (project / "src/main/kotlin/app").mkdir(parents=True, exist_ok=True)
            (project / "src/main/kotlin/app/App.kt").write_text("class App", encoding="utf-8")

            run_hook(project, settings)

            log_path = project / "reports" / "tests" / "fmt-2.jsonl"
            self.assertTrue(log_path.exists())
            last_entry = json.loads(log_path.read_text(encoding="utf-8").splitlines()[-1])
            self.assertEqual(last_entry.get("type"), "tests")
            self.assertIn(last_entry.get("status"), {"pass", "fail", "skipped"})
