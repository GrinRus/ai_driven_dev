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
from typing import Iterable, List, Tuple

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR / "src") not in sys.path:
    sys.path.insert(0, str(ROOT_DIR / "src"))

from claude_workflow_cli.feature_ids import resolve_identifiers  # type: ignore

LOG_PREFIX = "[format-and-test]"
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

DEFAULT_CODE_PATHS = (
    "src",
    "app",
    "apps",
    "modules",
    "packages",
    "service",
    "services",
    "backend",
    "frontend",
    "lib",
    "libs",
    "server",
    "client",
    "core",
    "domain",
    "shared",
    "python",
    "java",
    "kotlin",
)

DEFAULT_CODE_EXTENSIONS = (
    ".kt",
    ".kts",
    ".java",
    ".groovy",
    ".gradle",
    ".gradle.kts",
    ".scala",
    ".swift",
    ".c",
    ".cc",
    ".cpp",
    ".cxx",
    ".h",
    ".hpp",
    ".cs",
    ".go",
    ".rb",
    ".rs",
    ".py",
    ".pyi",
    ".pyx",
    ".js",
    ".jsx",
    ".ts",
    ".tsx",
    ".m",
    ".mm",
    ".php",
    ".dart",
    ".mjs",
    ".cjs",
    ".fs",
    ".fsx",
    ".fsharp",
    ".hs",
    ".erl",
    ".ex",
    ".exs",
    ".cls",
)

DEFAULT_CODE_FILES = (
    "build.gradle",
    "build.gradle.kts",
    "settings.gradle",
    "settings.gradle.kts",
    "pom.xml",
)

DEFAULT_REVIEWER_MARKER = "reports/reviewer/{ticket}.json"
DEFAULT_REVIEWER_FIELD = "tests"
DEFAULT_REVIEWER_REQUIRED = ("required",)
DEFAULT_REVIEWER_OPTIONAL = ("optional", "skipped", "not-required")


def dedupe_preserve(items: Iterable[str]) -> Tuple[str, ...]:
    seen: set[str] = set()
    result: List[str] = []
    for item in items:
        if not item or item in seen:
            continue
        seen.add(item)
        result.append(item)
    return tuple(result)


def normalize_code_paths(values: Iterable[str] | None) -> Tuple[str, ...]:
    if values is None:
        values = DEFAULT_CODE_PATHS
    normalized: List[str] = []
    for raw in values:
        text = str(raw).strip()
        if not text:
            continue
        text = text.lstrip("./")
        if not text:
            continue
        text = text.rstrip("/")
        if not text:
            continue
        normalized.append(text.lower())
    return dedupe_preserve(normalized)


def normalize_code_extensions(values: Iterable[str] | None) -> Tuple[str, ...]:
    if values is None:
        values = DEFAULT_CODE_EXTENSIONS
    normalized: List[str] = []
    for raw in values:
        text = str(raw).strip()
        if not text:
            continue
        text = text.lstrip("*")
        if not text:
            continue
        if not text.startswith("."):
            text = f".{text}"
        normalized.append(text.lower())
    return dedupe_preserve(normalized)


def normalize_code_files(values: Iterable[str] | None) -> Tuple[str, ...]:
    if values is None:
        values = DEFAULT_CODE_FILES
    normalized: List[str] = []
    for raw in values:
        text = str(raw).strip()
        if not text:
            continue
        text = text.lstrip("./")
        if not text:
            continue
        normalized.append(text.lower())
    return dedupe_preserve(normalized)


def is_code_related(path: str, prefixes: Tuple[str, ...], suffixes: Tuple[str, ...], exact: Tuple[str, ...]) -> bool:
    if not path:
        return False
    normalized = path.lstrip("./")
    lowered = normalized.lower()
    if lowered in exact:
        return True
    for prefix in prefixes:
        if not prefix:
            continue
        if lowered == prefix or lowered.startswith(prefix + "/"):
            return True
    for suffix in suffixes:
        if not suffix:
            continue
        if lowered.endswith(suffix):
            return True
    return False


def has_code_changes(files: Iterable[str], prefixes: Tuple[str, ...], suffixes: Tuple[str, ...], exact: Tuple[str, ...]) -> bool:
    for path in files:
        if is_code_related(path, prefixes, suffixes, exact):
            return True
    return False


def reviewer_marker_path(template: str, ticket: str, slug_hint: str | None) -> Path:
    resolved = template.replace("{ticket}", ticket)
    if "{slug}" in template:
        resolved = resolved.replace("{slug}", slug_hint or ticket)
    return Path(resolved)


def reviewer_tests_required(ticket: str, slug_hint: str | None, config: dict) -> tuple[bool, str]:
    marker_template = str(
        config.get("tests_marker")
        or config.get("marker")
        or DEFAULT_REVIEWER_MARKER
    )
    field = str(
        config.get("tests_field")
        or config.get("field")
        or DEFAULT_REVIEWER_FIELD
    )

    required_source = config.get("required_values")
    if required_source is None:
        required_source = config.get("requiredValues")
    if required_source is None:
        required_source = DEFAULT_REVIEWER_REQUIRED
    elif not isinstance(required_source, list):
        required_source = [required_source]
    required_values = [
        str(value).strip().lower() for value in required_source
    ]
    if not required_values:
        required_values = list(DEFAULT_REVIEWER_REQUIRED)

    optional_source = config.get("optional_values")
    if optional_source is None:
        optional_source = config.get("optionalValues")
    if optional_source is None:
        optional_source = DEFAULT_REVIEWER_OPTIONAL
    elif not isinstance(optional_source, list):
        optional_source = [optional_source]
    optional_values = [
        str(value).strip().lower() for value in optional_source
    ]
    if not optional_values:
        optional_values = list(DEFAULT_REVIEWER_OPTIONAL)

    fallback_raw = config.get("default_value")
    if fallback_raw is None:
        fallback_raw = config.get("defaultValue", "")
    fallback_value = str(fallback_raw).strip().lower()
    marker = reviewer_marker_path(marker_template, ticket, slug_hint)
    if not marker.exists():
        return False, marker.as_posix()
    try:
        data = json.loads(marker.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        log(f"Не удалось прочитать маркер reviewer {marker}: {exc}; запускаем тесты по умолчанию.")
        return True, marker.as_posix()
    value_raw = data.get(field, "")
    value = str(value_raw).strip().lower()
    if value in required_values:
        return True, marker.as_posix()
    if value in optional_values:
        return False, marker.as_posix()
    if fallback_value and fallback_value in required_values:
        return True, marker.as_posix()
    return False, marker.as_posix()


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


def feature_label(ticket: str, slug_hint: str | None) -> str:
    if not ticket:
        return ""
    hint = (slug_hint or "").strip()
    if hint and hint != ticket:
        return f"{ticket} (slug hint: {hint})"
    return ticket


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

    code_paths_raw = tests_cfg.get("codePaths")
    if isinstance(code_paths_raw, list):
        code_prefixes = normalize_code_paths(code_paths_raw)
    elif code_paths_raw is None:
        code_prefixes = normalize_code_paths(None)
    else:
        code_prefixes = normalize_code_paths([code_paths_raw])

    code_ext_raw = tests_cfg.get("codeExtensions")
    if isinstance(code_ext_raw, list):
        code_suffixes = normalize_code_extensions(code_ext_raw)
    elif code_ext_raw is None:
        code_suffixes = normalize_code_extensions(None)
    else:
        code_suffixes = normalize_code_extensions([code_ext_raw])

    code_files_raw = tests_cfg.get("codeFiles")
    if isinstance(code_files_raw, list):
        code_exact = normalize_code_files(code_files_raw)
    elif code_files_raw is None:
        code_exact = normalize_code_files(None)
    else:
        code_exact = normalize_code_files([code_files_raw])

    changed_files = collect_changed_files()
    identifiers = resolve_identifiers(Path.cwd())
    active_ticket = identifiers.resolved_ticket or ""
    slug_hint = identifiers.slug_hint

    reviewer_cfg = tests_cfg.get("reviewerGate") or {}
    reviewer_enabled = bool(reviewer_cfg.get("enabled", False))
    force_env_name = str(reviewer_cfg.get("forceEnv", "FORCE_TESTS") or "")
    skip_env_name = str(reviewer_cfg.get("skipEnv", "SKIP_TESTS") or "")

    force_tests_flag = env_flag(force_env_name) if force_env_name else None
    skip_tests_flag = env_flag(skip_env_name) if skip_env_name else None

    force_tests = bool(force_tests_flag) if force_env_name else False
    skip_tests = bool(skip_tests_flag) if skip_env_name else False

    manual_scope_requested = bool(test_scope_env)
    if manual_scope_requested:
        force_tests = True
    if force_tests:
        skip_tests = False

    reviewer_required = False
    reviewer_marker_source = ""
    if reviewer_enabled and not force_tests and not skip_tests:
        if active_ticket:
            reviewer_required, reviewer_marker_source = reviewer_tests_required(active_ticket, slug_hint, reviewer_cfg)
        else:
            log("reviewerGate.enabled=1, но docs/.active_ticket не найден — тесты будут ожидать запроса reviewer.")

    tests_should_run = True
    skip_reason = ""
    if skip_tests:
        tests_should_run = False
        skip_reason = f"{skip_env_name}=1 — стадия тестов пропущена."
    elif force_tests or manual_scope_requested:
        tests_should_run = True
        if manual_scope_requested:
            log("TEST_SCOPE задан — выполняем указанные задачи тестов.")
        elif force_env_name and force_tests:
            log(f"{force_env_name}=1 — тесты будут запущены независимо от маркера reviewer.")
    elif reviewer_enabled:
        if reviewer_required:
            tests_should_run = True
            if reviewer_marker_source:
                log(f"reviewer запросил тесты ({reviewer_marker_source}).")
            else:
                log("reviewer запросил тесты — выполняем стадия тестов.")
        else:
            tests_should_run = False
            if reviewer_marker_source:
                skip_reason = (
                    f"reviewer не запросил тесты (маркер {reviewer_marker_source}) — стадия тестов пропущена."
                )
            else:
                skip_reason = "reviewer не запросил тесты — стадия тестов пропущена."
    else:
        tests_should_run = True

    skip_format_flag = os.environ.get("SKIP_FORMAT", "0") == "1"
    format_only_flag = os.environ.get("FORMAT_ONLY", "0") == "1"

    if changed_only_flag and not force_tests and not reviewer_required:
        if not changed_files:
            log("Изменения не обнаружены — форматирование и тесты пропущены.")
            if not format_only_flag:
                return 0
        elif not has_code_changes(changed_files, code_prefixes, code_suffixes, code_exact):
            preview = " ".join(changed_files[:8])
            if len(changed_files) > 8:
                preview = f"{preview} ..."
            if format_only_flag:
                log(f"Изменены только некодовые файлы ({preview}) — FORMAT_ONLY=1, выполняем только форматирование.")
            else:
                log(f"Изменены только некодовые файлы ({preview}) — форматирование и тесты пропущены.")
                return 0

    if skip_format_flag:
        log("SKIP_FORMAT=1 — форматирование пропущено.")
    else:
        if not format_commands:
            log("Команды форматирования не настроены (automation.format.commands).")
        else:
            for cmd in format_commands:
                if not run_subprocess(cmd):
                    return 1

    if format_only_flag:
        log("FORMAT_ONLY=1 — стадия тестов пропущена.")
        return 0

    if not tests_should_run:
        if skip_reason:
            log(skip_reason)
        else:
            log("Стадия тестов пропущена (reviewerGate).")
        return 0

    if active_ticket and changed_files:
        common_hits = [
            path
            for path in changed_files
            if any(path == pattern or path.startswith(pattern) for pattern in COMMON_PATTERNS)
        ]
        if common_hits:
            changed_only_flag = False
            log(
                f"Активная фича '{feature_label(active_ticket, slug_hint)}', изменены общие файлы: {' '.join(common_hits)} — полный прогон тестов."
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
