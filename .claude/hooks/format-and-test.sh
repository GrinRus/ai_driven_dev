#!/usr/bin/env python3
"""Unified formatter and test runner hook.

Reads automation settings from .claude/settings.json (or CLAUDE_SETTINGS_PATH),
runs configured formatting commands, then executes the appropriate test tasks
depending on the change scope and configuration flags.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Iterable, List

LOG_PREFIX = "[format-and-test]"
ROOT_DIR = Path(__file__).resolve().parents[2]
SETTINGS_PATH = Path(
    os.environ.get("CLAUDE_SETTINGS_PATH", ROOT_DIR / ".claude" / "settings.json")
)
COMMON_PATTERNS = (
    "config/",
    "gradle/libs.versions.toml",
    "settings.gradle",
    "settings.gradle.kts",
    "build.gradle",
    "build.gradle.kts",
    "buildSrc/",
)


def log(message: str) -> None:
    print(f"{LOG_PREFIX} {message}", file=sys.stderr)


def fail(message: str, code: int = 1) -> int:
    log(message)
    return code


def load_config() -> dict | None:
    if not SETTINGS_PATH.exists():
        log(f"Конфигурация {SETTINGS_PATH} не найдена — шаги пропущены.")
        return None
    try:
        return json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SystemExit(fail(f"Не удалось разобрать {SETTINGS_PATH}: {exc}", 1))


def run_subprocess(cmd: List[str], strict: bool = True) -> bool:
    log(f"→ {' '.join(cmd)}")
    result = subprocess.run(cmd, text=True)
    if result.returncode == 0:
        return True
    if strict:
        log(f"Команда завершилась с ошибкой (exit={result.returncode}).")
    return False


def env_flag(name: str) -> bool | None:
    value = os.environ.get(name)
    if value is None or value == "":
        return None
    return value not in {"0", "false", "False"}


def collect_changed_files() -> List[str]:
    files: set[str] = set()

    def git_lines(args: Iterable[str]) -> List[str]:
        proc = subprocess.run(args, text=True, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        if proc.returncode != 0:
            return []
        return [line.strip() for line in proc.stdout.splitlines() if line.strip()]

    # tracked changes
    proc = subprocess.run([
        "git",
        "rev-parse",
        "--verify",
        "HEAD",
    ], text=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if proc.returncode == 0:
        files.update(git_lines(["git", "diff", "--name-only", "HEAD"]))

    # untracked
    files.update(git_lines(["git", "ls-files", "--others", "--exclude-standard"]))
    return sorted(files)


def append_unique(container: List[str], value: str) -> None:
    if value and value not in container:
        container.append(value)


def parse_scope(value: str) -> List[str]:
    items: List[str] = []
    for chunk in value.replace(",", " ").split():
        chunk = chunk.strip()
        if chunk:
            append_unique(items, chunk)
    return items


def determine_project_dir() -> Path:
    if "CLAUDE_PROJECT_DIR" in os.environ:
        return Path(os.environ["CLAUDE_PROJECT_DIR"]).resolve()
    settings_parent = SETTINGS_PATH.parent
    if settings_parent.name == ".claude":
        return settings_parent.parent.resolve()
    return settings_parent.resolve()


def main() -> int:
    os.chdir(determine_project_dir())

    if env_flag("SKIP_AUTO_TESTS"):
        log("SKIP_AUTO_TESTS=1 — автоматический запуск форматирования и выборочных тестов пропущен.")
        return 0

    config = load_config()
    if config is None:
        return 0

    automation = config.get("automation", {})
    format_cfg = automation.get("format", {})
    format_commands = [
        [str(part) for part in cmd]
        for cmd in format_cfg.get("commands", [])
        if isinstance(cmd, list)
    ]

    tests_cfg = automation.get("tests", {})
    runner_cfg = tests_cfg.get("runner", "./gradlew")
    if isinstance(runner_cfg, list):
        test_runner = [str(part) for part in runner_cfg]
    else:
        test_runner = [str(runner_cfg)]

    default_tasks = [str(task) for task in tests_cfg.get("defaultTasks", [":test"])]
    fallback_tasks = [str(task) for task in tests_cfg.get("fallbackTasks", [])]
    module_matrix = [
        {
            "match": str(item.get("match", "")),
            "tasks": [str(t) for t in item.get("tasks", [])],
        }
        for item in tests_cfg.get("moduleMatrix", [])
        if isinstance(item, dict)
    ]
    changed_only_default = bool(tests_cfg.get("changedOnly", True))
    strict_default = bool(tests_cfg.get("strictDefault", 1))

    skip_format = os.environ.get("SKIP_FORMAT", "0") == "1"
    if skip_format:
        log("SKIP_FORMAT=1 — форматирование пропущено.")
    else:
        if not format_commands:
            log("Команды форматирования не настроены (automation.format.commands).")
        else:
            for cmd in format_commands:
                if not run_subprocess(cmd):
                    return 1

    if os.environ.get("FORMAT_ONLY", "0") == "1":
        log("FORMAT_ONLY=1 — стадия тестов пропущена.")
        return 0

    strict_flag = env_flag("STRICT_TESTS")
    if strict_flag is None:
        strict_flag = strict_default

    changed_only_flag = env_flag("TEST_CHANGED_ONLY")
    if changed_only_flag is None:
        changed_only_flag = changed_only_default

    test_tasks: List[str] = []
    test_scope_env = os.environ.get("TEST_SCOPE")
    if test_scope_env:
        for item in parse_scope(test_scope_env):
            append_unique(test_tasks, item)
        changed_only_flag = False

    changed_files = collect_changed_files()
    active_slug = Path("docs/.active_feature").read_text(encoding="utf-8").strip() if Path("docs/.active_feature").exists() else ""

    if active_slug and changed_files:
        common_hits = [
            path
            for path in changed_files
            if any(path == pattern or path.startswith(pattern) for pattern in COMMON_PATTERNS)
        ]
        if common_hits:
            changed_only_flag = False
            log(
                f"Активная фича '{active_slug}', изменены общие файлы: {' '.join(common_hits)} — полный прогон тестов."
            )

    if changed_only_flag and changed_files and module_matrix:
        matrix_tasks: List[str] = []
        for item in module_matrix:
            match = item.get("match", "")
            if not match:
                continue
            if any(path.startswith(match) for path in changed_files):
                for task in item.get("tasks", []):
                    append_unique(matrix_tasks, task)
        for task in matrix_tasks:
            append_unique(test_tasks, task)

    if not test_tasks:
        for task in default_tasks:
            append_unique(test_tasks, task)

    if not test_tasks:
        for task in fallback_tasks:
            append_unique(test_tasks, task)

    if not test_tasks:
        log("Нет задач для запуска тестов — проверка пропущена.")
        return 0

    log(f"Выбранные задачи тестов: {' '.join(test_tasks)}")

    if not test_runner or not test_runner[0]:
        log("Не указан runner для тестов — стадия пропущена.")
        return 0

    command = test_runner + test_tasks
    log(f"Запуск тестов: {' '.join(command)}")
    result = subprocess.run(command, text=True)
    if result.returncode == 0:
        log("Тесты завершились успешно.")
        return 0

    if strict_flag:
        return fail("Тесты завершились с ошибкой (STRICT_TESTS=1).", result.returncode)

    log("Тесты завершились с ошибкой, но STRICT_TESTS != 1 — продолжаем.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
