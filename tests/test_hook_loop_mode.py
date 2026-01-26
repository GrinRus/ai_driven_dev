import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from typing import Optional

from tests.helpers import (
    HOOKS_DIR,
    REPO_ROOT,
    git_config_user,
    git_init,
    write_active_feature,
    write_active_stage,
    write_file,
)

HOOK = HOOKS_DIR / "format-and-test.sh"


def write_settings(tmp_path: Path, overrides: dict) -> Path:
    base = {
        "automation": {
            "format": {"commands": []},
            "tests": {
                "runner": "/bin/echo",
                "defaultTasks": ["default_task"],
                "fallbackTasks": [],
                "changedOnly": True,
                "reviewerGate": {"enabled": False},
            },
        },
    }
    automation_override = overrides.get("automation")
    if isinstance(automation_override, dict):
        tests_override = automation_override.get("tests")
        if isinstance(tests_override, dict):
            base["automation"]["tests"].update(tests_override)
    settings_path = tmp_path / "settings.json"
    settings_path.write_text(json.dumps(base, indent=2), encoding="utf-8")
    return settings_path


def run_hook(tmp_path: Path, settings_path: Path, env: Optional[dict] = None) -> subprocess.CompletedProcess[str]:
    effective_env = {
        "CLAUDE_SETTINGS_PATH": str(settings_path),
        "SKIP_FORMAT": "1",
        "CLAUDE_PLUGIN_ROOT": str(REPO_ROOT),
    }
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


def seed_repo_with_file(project: Path, rel: str, content: str) -> None:
    write_file(project, rel, content)
    subprocess.run(["git", "add", rel], cwd=project, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=project, check=True, capture_output=True)
    write_file(project, rel, content + "changed\n")


class LoopModeHookTests(unittest.TestCase):
    def test_loop_mode_skips_tests_by_default(self) -> None:
        with tempfile.TemporaryDirectory(prefix="loop-hook-") as tmpdir:
            project = Path(tmpdir) / "aidd"
            project.mkdir(parents=True, exist_ok=True)
            git_init(project)
            git_config_user(project)
            settings = write_settings(project, {})
            write_active_stage(project, "implement")
            write_active_feature(project, "loop-1")
            write_file(project, "docs/.active_mode", "loop\n")
            seed_repo_with_file(project, "src/main.py", "print('ok')\n")

            result = run_hook(project, settings)
            self.assertNotIn("Запуск тестов", result.stderr)
            self.assertIn("loop-mode", result.stderr)

    def test_loop_mode_override_runs_tests(self) -> None:
        with tempfile.TemporaryDirectory(prefix="loop-hook-") as tmpdir:
            project = Path(tmpdir) / "aidd"
            project.mkdir(parents=True, exist_ok=True)
            git_init(project)
            git_config_user(project)
            settings = write_settings(project, {})
            write_active_stage(project, "implement")
            write_active_feature(project, "loop-2")
            write_file(project, "docs/.active_mode", "loop\n")
            seed_repo_with_file(project, "src/app.py", "print('ok')\n")

            result = run_hook(project, settings, env={"AIDD_LOOP_TESTS": "1"})
            self.assertIn("Запуск тестов", result.stderr)

    def test_loop_mode_review_skips_tests(self) -> None:
        with tempfile.TemporaryDirectory(prefix="loop-hook-") as tmpdir:
            project = Path(tmpdir) / "aidd"
            project.mkdir(parents=True, exist_ok=True)
            git_init(project)
            git_config_user(project)
            settings = write_settings(project, {})
            write_active_stage(project, "review")
            write_active_feature(project, "loop-3")
            write_file(project, "docs/.active_mode", "loop\n")
            seed_repo_with_file(project, "src/review.py", "print('ok')\n")

            result = run_hook(project, settings, env={"AIDD_LOOP_TESTS": "1"})
            self.assertNotIn("Запуск тестов", result.stderr)
            self.assertIn("loop-mode", result.stderr)

    def test_service_only_blocks_override(self) -> None:
        with tempfile.TemporaryDirectory(prefix="loop-hook-") as tmpdir:
            project = Path(tmpdir) / "aidd"
            project.mkdir(parents=True, exist_ok=True)
            git_init(project)
            git_config_user(project)
            settings = write_settings(project, {"automation": {"tests": {"changedOnly": False}}})
            write_active_stage(project, "implement")
            write_active_feature(project, "loop-4")
            write_file(project, "docs/.active_mode", "loop\n")
            seed_repo_with_file(project, "docs/note.md", "note\n")

            result = run_hook(project, settings, env={"AIDD_LOOP_TESTS": "1"})
            self.assertNotIn("Запуск тестов", result.stderr)
            self.assertIn("Diff пустой/только service", result.stderr)


if __name__ == "__main__":
    unittest.main()
