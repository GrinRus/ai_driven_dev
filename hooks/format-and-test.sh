#!/usr/bin/env python3
"""Unified formatter and test runner hook.

Reads automation settings from .claude/settings.json (or CLAUDE_SETTINGS_PATH),
runs configured formatting commands, then executes the appropriate test tasks
depending on the change scope and configuration flags.
"""

from __future__ import annotations

import datetime as dt
import fnmatch
import hashlib
import json
import os
import subprocess
import sys
import time
from collections import deque
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

def _require_plugin_root() -> Path:
    raw = os.environ.get("CLAUDE_PLUGIN_ROOT")
    if not raw:
        print("[format-and-test] CLAUDE_PLUGIN_ROOT is required to run hooks.", file=sys.stderr)
        raise SystemExit(2)
    return Path(raw).expanduser().resolve()


PLUGIN_ROOT = _require_plugin_root()
if str(PLUGIN_ROOT) not in sys.path:
    sys.path.insert(0, str(PLUGIN_ROOT))
HOOKS_DIR = Path(__file__).resolve().parent
VENDOR_DIR = HOOKS_DIR / "_vendor"
if VENDOR_DIR.exists():
    sys.path.insert(0, str(VENDOR_DIR))

from tools.feature_ids import FeatureIdentifiers, resolve_aidd_root, resolve_identifiers
from tools.test_settings_defaults import (
    DEFAULT_COMMON_PATTERNS,
    DEFAULT_CODE_EXTENSIONS,
    DEFAULT_CODE_FILES,
    DEFAULT_CODE_PATHS,
)


def append_event(
    root: Path,
    identifiers: FeatureIdentifiers,
    status: str,
    details: Dict[str, object] | None = None,
) -> None:
    ticket = identifiers.resolved_ticket
    if not ticket:
        return
    payload: Dict[str, object] = {
        "ts": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "ticket": ticket,
        "slug_hint": identifiers.slug_hint or ticket,
        "type": "format-and-test",
        "status": status,
        "source": "hook format-and-test",
    }
    if details:
        payload["details"] = details
    path = root / "reports" / "events" / f"{ticket}.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False) + "\n")
    except OSError:
        return

LOG_PREFIX = "[format-and-test]"


def resolve_settings_path(workspace_root: Path) -> Path:
    env_path = os.environ.get("CLAUDE_SETTINGS_PATH")
    if env_path:
        return Path(env_path).expanduser().resolve()
    return (workspace_root / ".claude" / "settings.json").resolve()
DEFAULT_REVIEWER_MARKER = "aidd/reports/reviewer/{ticket}/{scope_key}.json"
DEFAULT_REVIEWER_FIELD = "tests"
DEFAULT_REVIEWER_REQUIRED = ("required",)
DEFAULT_REVIEWER_OPTIONAL = ("optional", "skipped", "not-required")
CHECKPOINT_PATH = Path(".cache") / "test-checkpoint.json"


def dedupe_preserve(items: Iterable[str]) -> Tuple[str, ...]:
    seen: set[str] = set()
    result: List[str] = []
    for item in items:
        if not item or item in seen:
            continue
        seen.add(item)
        result.append(item)
    return tuple(result)


def normalize_common_patterns(values: Iterable[str] | None) -> Tuple[str, ...]:
    if values is None:
        values = DEFAULT_COMMON_PATTERNS
    normalized: List[str] = []
    for raw in values:
        text = str(raw).strip()
        if not text:
            continue
        text = text.replace("\\", "/").lstrip("./")
        if not text:
            continue
        normalized.append(text.lower())
    return dedupe_preserve(normalized)


def match_common_pattern(path: str, pattern: str) -> bool:
    if not path or not pattern:
        return False
    normalized = path.lstrip("./").lower()
    pattern = pattern.strip().lower()
    if not pattern:
        return False
    if any(char in pattern for char in "*?["):
        if fnmatch.fnmatch(normalized, pattern):
            return True
        if pattern.startswith("**/") and fnmatch.fnmatch(normalized, pattern[3:]):
            return True
        return False
    if normalized == pattern:
        return True
    if pattern.endswith("/"):
        return normalized.startswith(pattern)
    return normalized.startswith(pattern + "/")


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


def reviewer_marker_path(
    template: str,
    ticket: str,
    slug_hint: str | None,
    project_root: Path,
    *,
    scope_key: str | None = None,
) -> Path:
    resolved = template.replace("{ticket}", ticket)
    if "{slug}" in template:
        resolved = resolved.replace("{slug}", slug_hint or ticket)
    if "{scope_key}" in template:
        resolved_scope = ""
        try:
            from tools import runtime as _runtime

            resolved_scope = _runtime.resolve_scope_key(scope_key, ticket)
        except Exception:
            raw = (scope_key or ticket or "").strip()
            cleaned = "".join(ch if ch.isalnum() or ch in "._-" else "_" for ch in raw)
            resolved_scope = cleaned.strip("._-")
        resolved = resolved.replace("{scope_key}", resolved_scope or "ticket")
    path = Path(resolved)
    if not path.is_absolute():
        parts = path.parts
        if parts and parts[0] == "aidd" and project_root.name == "aidd":
            path = Path(*parts[1:])
        path = project_root / path
    return path


def reviewer_tests_required(ticket: str, slug_hint: str | None, config: dict, project_root: Path) -> tuple[bool, str]:
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
    work_item_key = read_active_work_item(project_root)
    marker = reviewer_marker_path(
        marker_template,
        ticket,
        slug_hint,
        project_root,
        scope_key=work_item_key,
    )
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


def resolve_hook_verbosity() -> str:
    mode = (os.environ.get("AIDD_HOOK_VERBOSITY") or "summary").strip().lower()
    if mode not in {"summary", "full"}:
        return "summary"
    return mode


def resolve_test_log_mode() -> str:
    raw = os.environ.get("AIDD_TEST_LOG")
    if raw:
        mode = raw.strip().lower()
        if mode in {"summary", "full"}:
            return mode
    mode = resolve_hook_verbosity()
    if mode not in {"summary", "full"}:
        return "summary"
    return mode


def resolve_test_log_tail_lines() -> int:
    raw = os.environ.get("AIDD_TEST_LOG_TAIL_LINES", "")
    try:
        value = int(raw)
    except (TypeError, ValueError):
        value = 120
    return max(0, value)


def ensure_test_log_path(project_root: Path, ticket: str) -> Path:
    log_dir = project_root / "reports" / "tests"
    log_dir.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    label = ticket or "unknown"
    return log_dir / f"{label}.{stamp}.log"


def tail_file_lines(path: Path, max_lines: int) -> str:
    if max_lines <= 0:
        return ""
    try:
        with path.open("r", encoding="utf-8", errors="replace") as handle:
            lines = deque(handle, maxlen=max_lines)
        return "".join(lines)
    except OSError:
        return ""


def run_tests_with_tee(command: List[str], log_path: Path) -> subprocess.CompletedProcess[str]:
    with log_path.open("w", encoding="utf-8") as handle:
        proc = subprocess.Popen(
            command,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        if proc.stdout:
            for line in proc.stdout:
                sys.stdout.write(line)
                handle.write(line)
        returncode = proc.wait()
    return subprocess.CompletedProcess(command, returncode)


def fail(message: str, code: int = 1) -> int:
    log(message)
    return code


def load_config(settings_path: Path) -> dict | None:
    if not settings_path.exists():
        log(f"Конфигурация {settings_path} не найдена — шаги пропущены.")
        return None
    try:
        return json.loads(settings_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SystemExit(fail(f"Не удалось разобрать {settings_path}: {exc}", 1))


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


def parse_bool_value(value: str | None) -> bool | None:
    if value is None:
        return None
    text = value.strip().lower()
    if text == "":
        return None
    return text not in {"0", "false", "no"}


def parse_env_file(path: Path) -> Dict[str, str]:
    if not path.exists():
        return {}
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        log(f"Не удалось прочитать {path}: {exc}")
        return {}
    data: Dict[str, str] = {}
    for raw in lines:
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if not key:
            continue
        clean = value.strip().strip('"').strip("'")
        data[key] = clean
    return data


def git_has_head() -> bool:
    proc = subprocess.run(
        ["git", "rev-parse", "--verify", "HEAD"],
        text=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return proc.returncode == 0


def git_output(args: Iterable[str]) -> str:
    proc = subprocess.run(args, text=True, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    if proc.returncode != 0:
        return ""
    return proc.stdout or ""


def list_untracked_files() -> List[str]:
    output = git_output(["git", "ls-files", "--others", "--exclude-standard"])
    return [line.strip() for line in output.splitlines() if line.strip()]


def hash_file_content(path: Path, hasher: "hashlib._Hash") -> None:
    try:
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(65536), b""):
                hasher.update(chunk)
    except OSError:
        return


def strip_event_diffs(diff_text: str) -> str:
    if not diff_text:
        return ""
    lines = diff_text.splitlines()
    filtered: List[str] = []
    skip = False
    for line in lines:
        if line.startswith("diff --git "):
            skip = False
            if "reports/events/" in line or "aidd/reports/events/" in line:
                skip = True
        if skip:
            continue
        filtered.append(line)
    return "\n".join(filtered)


def load_dedupe_state(path: Path) -> Dict[str, str]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if isinstance(payload, dict):
        return {str(k): str(v) for k, v in payload.items()}
    return {}


def write_dedupe_state(path: Path, payload: Dict[str, object]) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    except OSError as exc:
        log(f"Не удалось записать dedupe cache {path}: {exc}")


def compute_tests_fingerprint(
    metadata: Dict[str, object], diff_text: str, untracked_files: List[str]
) -> str:
    hasher = hashlib.sha256()
    encoded = json.dumps(metadata, sort_keys=True, ensure_ascii=True).encode("utf-8")
    hasher.update(encoded)
    if diff_text:
        hasher.update(diff_text.encode("utf-8"))
    for rel in untracked_files:
        hasher.update(rel.encode("utf-8"))
        hash_file_content(Path(rel), hasher)
    return hasher.hexdigest()


def resolve_git_root(base: Path) -> Path:
    try:
        proc = subprocess.run(
            ["git", "-C", str(base), "rev-parse", "--show-toplevel"],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )
    except OSError:
        return base
    if proc.returncode != 0:
        return base
    root = proc.stdout.strip()
    if not root:
        return base
    return Path(root).resolve()


def collect_changed_files(base: Path) -> List[str]:
    files: set[str] = set()
    git_root = resolve_git_root(base)

    def git_lines(args: Iterable[str]) -> List[str]:
        proc = subprocess.run(args, text=True, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        if proc.returncode != 0:
            return []
        return [line.strip() for line in proc.stdout.splitlines() if line.strip()]

    # tracked changes
    proc = subprocess.run(
        ["git", "-C", str(git_root), "rev-parse", "--verify", "HEAD"],
        text=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    if proc.returncode == 0:
        files.update(git_lines(["git", "-C", str(git_root), "diff", "--name-only", "HEAD"]))

    # untracked
    files.update(git_lines(["git", "-C", str(git_root), "ls-files", "--others", "--exclude-standard"]))
    return sorted(files)


def is_cache_artifact(path: str) -> bool:
    return (
        path.startswith(".cache/")
        or path.startswith("aidd/.cache/")
        or path.startswith("reports/events/")
        or path.startswith("aidd/reports/events/")
        or path.startswith("reports/tests/")
        or path.startswith("aidd/reports/tests/")
    )


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


def normalize_cadence(value: object) -> str:
    raw = str(value or "").strip().lower()
    if raw in {"checkpoint", "manual"}:
        return raw
    return "on_stop"


def parse_checkpoint_triggers(value: object) -> Tuple[str, ...]:
    if value is None:
        return ("progress",)
    if isinstance(value, (list, tuple)):
        items = [str(item).strip().lower() for item in value if str(item).strip()]
    else:
        items = [chunk.strip().lower() for chunk in str(value).replace(",", " ").split() if chunk.strip()]
    if not items:
        return ("progress",)
    return dedupe_preserve(items)


def load_test_checkpoint(path: Path) -> Dict[str, str]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(payload, dict):
        return {}
    return {str(k): str(v) for k, v in payload.items() if v is not None}


def resolve_checkpoint(project_root: Path, ticket: str, triggers: Tuple[str, ...]) -> Tuple[bool, str, Path]:
    path = project_root / CHECKPOINT_PATH
    payload = load_test_checkpoint(path)
    if not payload:
        return False, "", path
    stored_ticket = (payload.get("ticket") or "").strip()
    if stored_ticket and ticket and stored_ticket != ticket:
        return False, "ticket-mismatch", path
    trigger = (payload.get("trigger") or payload.get("source") or "").strip().lower()
    if triggers and trigger and trigger not in triggers:
        return False, f"trigger={trigger}", path
    return True, trigger or "checkpoint", path


def clear_checkpoint(path: Path) -> None:
    try:
        path.unlink()
    except OSError:
        return


def resolve_workspace_root(ctx: object | None) -> Path:
    env_path = os.environ.get("CLAUDE_SETTINGS_PATH")
    if env_path:
        settings_path = Path(env_path).expanduser().resolve()
        if settings_path.name == "settings.json" and settings_path.parent.name == ".claude":
            return settings_path.parent.parent.resolve()
        return settings_path.parent.resolve()
    if ctx is not None:
        from hooks import hooklib

        base = hooklib.resolve_project_dir(ctx)
    else:
        base = Path.cwd().resolve()
    if base.name == "aidd":
        return base.parent.resolve()
    return base.resolve()

def read_active_stage(project_root: Path) -> str:
    override = os.environ.get("CLAUDE_ACTIVE_STAGE")
    if override:
        return override.strip().lower()
    stage_path = project_root / "docs" / ".active_stage"
    if not stage_path.exists():
        return ""
    try:
        return stage_path.read_text(encoding="utf-8").strip().lower()
    except OSError:
        return ""


def read_active_work_item(project_root: Path) -> str:
    path = project_root / "docs" / ".active_work_item"
    if not path.exists():
        return ""
    try:
        return path.read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def read_active_mode(project_root: Path) -> str:
    mode_path = project_root / "docs" / ".active_mode"
    if not mode_path.exists():
        return ""
    try:
        return mode_path.read_text(encoding="utf-8").strip().lower()
    except OSError:
        return ""


def collect_diff_files(base: Path) -> List[str]:
    files: set[str] = set()
    git_root = resolve_git_root(base)

    def git_lines(args: Iterable[str]) -> List[str]:
        proc = subprocess.run(args, text=True, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        if proc.returncode != 0:
            return []
        return [line.strip() for line in proc.stdout.splitlines() if line.strip()]

    files.update(git_lines(["git", "-C", str(git_root), "diff", "--name-only"]))
    files.update(git_lines(["git", "-C", str(git_root), "diff", "--cached", "--name-only"]))
    return sorted(files)


SERVICE_PREFIXES = (".claude/", ".cursor/")
SERVICE_FILES = {"AGENTS.md", "CLAUDE.md", ".github/copilot-instructions.md"}
AIDD_ROOT_PREFIXES = ("docs/", "reports/", "config/", ".cache/")

def normalize_service_path(path: str) -> str:
    normalized = path.replace("\\", "/")
    if normalized.startswith("./"):
        normalized = normalized[2:]
    return normalized


def is_service_file(path: str, *, aidd_root: bool) -> bool:
    normalized = normalize_service_path(path)
    if normalized in SERVICE_FILES:
        return True
    if normalized.startswith("aidd/"):
        inner = normalized[len("aidd/"):]
        if inner in SERVICE_FILES:
            return True
        if any(inner.startswith(prefix) for prefix in SERVICE_PREFIXES):
            return True
        if any(inner.startswith(prefix) for prefix in AIDD_ROOT_PREFIXES):
            return True
        return False
    if any(normalized.startswith(prefix) for prefix in SERVICE_PREFIXES):
        return True
    if aidd_root and any(normalized.startswith(prefix) for prefix in AIDD_ROOT_PREFIXES):
        return True
    return False


def service_only(files: List[str], *, aidd_root: bool) -> bool:
    if not files:
        return True
    return all(is_service_file(path, aidd_root=aidd_root) for path in files)


def main() -> int:
    from hooks import hooklib

    ctx = hooklib.read_hook_context()
    workspace_root = resolve_workspace_root(ctx)
    os.chdir(workspace_root)
    settings_path = resolve_settings_path(workspace_root)
    project_root = resolve_aidd_root(workspace_root)
    diff_files = collect_diff_files(workspace_root)
    stage = read_active_stage(project_root)
    active_mode = read_active_mode(project_root)
    aidd_root = project_root.name == "aidd"

    if env_flag("SKIP_AUTO_TESTS"):
        log("SKIP_AUTO_TESTS=1 — автоматический запуск форматирования и выборочных тестов пропущен.")
        return 0

    if not env_flag("CLAUDE_SKIP_STAGE_CHECKS"):
        if not stage:
            log("Активная стадия не задана — форматирование/тесты пропущены.")
            return 0
        if stage not in {"implement", "review"}:
            log(f"Активная стадия '{stage}' — форматирование/тесты пропущены.")
            return 0
        if stage == "review" and service_only(diff_files, aidd_root=aidd_root):
            log("Активная стадия review, diff пустой/только service — форматирование/тесты пропущены.")
            return 0

    config = load_config(settings_path)
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
    runner_cfg = tests_cfg.get("runner", "bash")
    if isinstance(runner_cfg, list):
        test_runner = [str(part) for part in runner_cfg]
    else:
        test_runner = [str(runner_cfg)]

    default_tasks = [str(task) for task in tests_cfg.get("defaultTasks", [])]
    fallback_tasks = [str(task) for task in tests_cfg.get("fallbackTasks", [])]
    fast_tasks = [str(task) for task in tests_cfg.get("fastTasks", [])]
    full_tasks = [str(task) for task in tests_cfg.get("fullTasks", [])]
    targeted_raw = tests_cfg.get("targetedTask", [])
    if isinstance(targeted_raw, list):
        targeted_tasks = [str(task) for task in targeted_raw]
    elif targeted_raw:
        targeted_tasks = [str(targeted_raw)]
    else:
        targeted_tasks = []
    filter_flag = str(tests_cfg.get("filterFlag") or "--tests")
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

    policy_path = project_root / ".cache" / "test-policy.env"
    policy_env = parse_env_file(policy_path)
    profile_env = os.environ.get("AIDD_TEST_PROFILE")
    profile_file = policy_env.get("AIDD_TEST_PROFILE")
    profile_default_env = os.environ.get("AIDD_TEST_PROFILE_DEFAULT")
    explicit_profile_raw = (profile_env or profile_file or "").strip()
    profile_source = "default"
    if profile_env:
        profile_raw = profile_env
        profile_source = "env"
    elif profile_file:
        profile_raw = profile_file
        profile_source = "test-policy.env"
    elif profile_default_env:
        profile_raw = profile_default_env
        profile_source = "default-env"
    else:
        profile_raw = ""
    test_profile = profile_raw.lower() if profile_raw else "fast"
    if test_profile not in {"fast", "targeted", "full", "none"}:
        log(f"Неизвестный AIDD_TEST_PROFILE={test_profile!r}; используем fast.")
        test_profile = "fast"
        profile_source = "default"
    policy_tasks_raw = (os.environ.get("AIDD_TEST_TASKS") or policy_env.get("AIDD_TEST_TASKS") or "").strip()
    policy_filters_raw = (os.environ.get("AIDD_TEST_FILTERS") or policy_env.get("AIDD_TEST_FILTERS") or "").strip()
    policy_force_raw = os.environ.get("AIDD_TEST_FORCE") or policy_env.get("AIDD_TEST_FORCE")
    parsed_force = parse_bool_value(policy_force_raw)
    policy_force = bool(parsed_force) if parsed_force is not None else False
    policy_active = bool(explicit_profile_raw or policy_tasks_raw or policy_filters_raw or policy_force_raw)
    if policy_path.exists():
        policy_active = True
        log(f"Test policy detected: {policy_path}")
    log(f"Test profile: {test_profile} (source: {profile_source}).")

    if test_profile == "full":
        changed_only_flag = False

    test_tasks: List[str] = []
    test_filters: List[str] = []
    manual_scope_requested = False
    test_scope_env = os.environ.get("TEST_SCOPE")
    if test_scope_env:
        for item in parse_scope(test_scope_env):
            append_unique(test_tasks, item)
        changed_only_flag = False
        manual_scope_requested = True

    if policy_tasks_raw:
        for item in parse_scope(policy_tasks_raw):
            append_unique(test_tasks, item)
        changed_only_flag = False
        manual_scope_requested = True

    if policy_filters_raw:
        test_filters = parse_scope(policy_filters_raw)
        if test_filters:
            changed_only_flag = False
            manual_scope_requested = True

    code_paths_raw = tests_cfg.get("codePaths")
    if code_paths_raw is None:
        code_paths_raw = tests_cfg.get("code_paths")
    if isinstance(code_paths_raw, list):
        code_prefixes = normalize_code_paths(code_paths_raw)
    elif code_paths_raw is None:
        code_prefixes = normalize_code_paths(None)
    else:
        code_prefixes = normalize_code_paths([code_paths_raw])

    code_ext_raw = tests_cfg.get("codeExtensions")
    if code_ext_raw is None:
        code_ext_raw = tests_cfg.get("code_extensions")
    if isinstance(code_ext_raw, list):
        code_suffixes = normalize_code_extensions(code_ext_raw)
    elif code_ext_raw is None:
        code_suffixes = normalize_code_extensions(None)
    else:
        code_suffixes = normalize_code_extensions([code_ext_raw])

    code_files_raw = tests_cfg.get("codeFiles")
    if code_files_raw is None:
        code_files_raw = tests_cfg.get("code_files")
    if isinstance(code_files_raw, list):
        code_exact = normalize_code_files(code_files_raw)
    elif code_files_raw is None:
        code_exact = normalize_code_files(None)
    else:
        code_exact = normalize_code_files([code_files_raw])

    changed_files = [path for path in collect_changed_files(workspace_root) if not is_cache_artifact(path)]
    identifiers = resolve_identifiers(project_root)
    active_ticket = identifiers.resolved_ticket or ""
    slug_hint = identifiers.slug_hint

    def record_event(status: str, reason: str = "") -> None:
        details: Dict[str, object] = {"profile": test_profile}
        if reason:
            details["reason"] = reason
        if test_tasks:
            details["task_count"] = len(test_tasks)
        append_event(project_root, identifiers, status, details)

    common_patterns_raw = tests_cfg.get("commonPatterns")
    if common_patterns_raw is None:
        common_patterns_raw = tests_cfg.get("common_patterns")
    if isinstance(common_patterns_raw, list):
        common_patterns = normalize_common_patterns(common_patterns_raw)
    elif common_patterns_raw is None:
        common_patterns = normalize_common_patterns(None)
    else:
        common_patterns = normalize_common_patterns([common_patterns_raw])

    common_hits = [
        path for path in changed_files if any(match_common_pattern(path, pattern) for pattern in common_patterns)
    ]

    reviewer_cfg = tests_cfg.get("reviewerGate") or {}
    reviewer_enabled = bool(reviewer_cfg.get("enabled", False))
    policy_gate_override = policy_active and test_profile != "none"
    if policy_gate_override and reviewer_enabled:
        reviewer_enabled = False
        log("Test policy активен — reviewer gate отключён.")
    force_env_name = str(reviewer_cfg.get("forceEnv", "FORCE_TESTS") or "")
    skip_env_name = str(reviewer_cfg.get("skipEnv", "SKIP_TESTS") or "")

    force_tests_flag = env_flag(force_env_name) if force_env_name else None
    skip_tests_flag = env_flag(skip_env_name) if skip_env_name else None

    force_tests = bool(force_tests_flag) if force_env_name else False
    skip_tests = bool(skip_tests_flag) if skip_env_name else False

    if manual_scope_requested:
        force_tests = True
        skip_tests = False
    if policy_force:
        force_tests = True
        skip_tests = False
    if force_tests:
        skip_tests = False

    reviewer_required = False
    reviewer_marker_source = ""
    if reviewer_enabled and not force_tests and not skip_tests:
        if active_ticket:
            reviewer_required, reviewer_marker_source = reviewer_tests_required(
                active_ticket,
                slug_hint,
                reviewer_cfg,
                project_root,
            )
        else:
            log("reviewerGate.enabled=1, но docs/.active_ticket не найден — тесты будут ожидать запроса reviewer.")

    cadence = normalize_cadence(tests_cfg.get("cadence"))
    checkpoint_triggers = parse_checkpoint_triggers(
        tests_cfg.get("checkpointTrigger") or tests_cfg.get("checkpoint_trigger")
    )
    checkpoint_active = False
    checkpoint_reason = ""
    checkpoint_path = project_root / CHECKPOINT_PATH
    if cadence == "checkpoint":
        checkpoint_active, checkpoint_reason, checkpoint_path = resolve_checkpoint(
            project_root, active_ticket, checkpoint_triggers
        )
    manual_checkpoint = env_flag("AIDD_TEST_CHECKPOINT")
    if manual_checkpoint:
        checkpoint_active = True
        checkpoint_reason = "env"

    if cadence == "checkpoint":
        log(f"Test cadence: checkpoint (triggers: {', '.join(checkpoint_triggers)})")
        if checkpoint_active:
            log(f"Checkpoint trigger detected ({checkpoint_reason}).")
    elif cadence == "manual":
        log("Test cadence: manual (cadence=manual)")

    def update_stage_result_after_tests(scope_key: str, tests_log_rel: str, tests_status: str) -> None:
        ticket = identifiers.resolved_ticket or ""
        if not ticket or not scope_key:
            return
        stage_value = (stage or "implement").strip().lower()
        if not stage_value:
            return
        result_path = (
            project_root
            / "reports"
            / "loops"
            / ticket
            / scope_key
            / f"stage.{stage_value}.result.json"
        )
        if not result_path.exists():
            return
        try:
            payload = json.loads(result_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return
        if str(payload.get("schema") or "") != "aidd.stage_result.v1":
            return
        evidence_links = payload.get("evidence_links")
        if not isinstance(evidence_links, list):
            evidence_links = []
        if tests_log_rel and tests_log_rel not in evidence_links:
            evidence_links.append(tests_log_rel)
        status_value = str(tests_status or "").strip().lower()
        tests_evidence = status_value in {"pass", "fail"}
        requested_result = str(payload.get("requested_result") or "").strip().lower()
        result_value = str(payload.get("result") or "").strip().lower()
        reason_code = str(payload.get("reason_code") or "").strip()
        if reason_code == "missing_test_evidence" and tests_evidence:
            if requested_result in {"continue", "done"} and result_value == "blocked":
                payload["result"] = requested_result
            payload["reason"] = ""
            payload["reason_code"] = ""
        payload["evidence_links"] = evidence_links
        payload["updated_at"] = dt.datetime.now(dt.timezone.utc).isoformat()
        result_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    def record_tests_log(
        status: str,
        reason: str = "",
        *,
        exit_code: int | None = None,
        log_path: Path | None = None,
    ) -> None:
        status_value = str(status or "").strip().lower()
        profile_value = test_profile
        if status_value in {"skipped", "not-run"}:
            profile_value = "none"
        ticket = identifiers.resolved_ticket
        ticket_guess = ""
        ticket_file = project_root / "docs" / ".active_ticket"
        if not ticket_file.exists() and identifiers.slug_hint:
            ticket_guess = identifiers.slug_hint
        if not ticket:
            return
        details: Dict[str, object] = {
            "profile": test_profile,
            "cadence": cadence,
        }
        if reason:
            details["reason"] = reason
        if test_tasks:
            details["tasks"] = list(test_tasks)
        if test_filters:
            details["filters"] = list(test_filters)
        if manual_scope_requested:
            details["manual_scope"] = True
        if test_runner:
            details["runner"] = list(test_runner)
        try:
            from tools import runtime as _runtime
            from tools.reports import tests_log as _tests_log

            stage_value = (stage or "implement").strip().lower()
            work_item_key = read_active_work_item(project_root)
            if stage_value == "qa":
                scope_key = _runtime.resolve_scope_key("", ticket)
            else:
                scope_key = _runtime.resolve_scope_key(work_item_key, ticket)
            log_value = _runtime.rel_path(log_path, project_root) if log_path else ""
            _tests_log.append_log(
                project_root,
                ticket=ticket,
                slug_hint=identifiers.slug_hint,
                ticket_guess=ticket_guess,
                stage=stage_value,
                scope_key=scope_key,
                work_item_key=work_item_key or None,
                profile=profile_value,
                tasks=test_tasks,
                filters=test_filters,
                exit_code=exit_code,
                log_path=log_value or None,
                status=status,
                details=details,
                source="hook format-and-test",
                cwd=str(workspace_root),
            )
            tests_log_path = _tests_log.tests_log_path(project_root, ticket, scope_key)
            tests_log_rel = _runtime.rel_path(tests_log_path, project_root)
            update_stage_result_after_tests(scope_key, tests_log_rel, status_value)
        except Exception:
            return

    cadence_allows = True
    cadence_reason = ""
    if cadence == "manual":
        if not (force_tests or manual_scope_requested or policy_active or reviewer_required or checkpoint_active):
            cadence_allows = False
            cadence_reason = "cadence=manual — стадия тестов пропущена."
    elif cadence == "checkpoint":
        if not (force_tests or manual_scope_requested or policy_active or reviewer_required or checkpoint_active):
            cadence_allows = False
            cadence_reason = "cadence=checkpoint — стадия тестов пропущена (нет checkpoint)."

    tests_should_run = True
    skip_reason = ""
    if test_profile == "none":
        tests_should_run = False
        skip_reason = "AIDD_TEST_PROFILE=none — стадия тестов пропущена."
    elif skip_tests:
        tests_should_run = False
        skip_reason = f"{skip_env_name}=1 — стадия тестов пропущена."
    elif not cadence_allows:
        tests_should_run = False
        skip_reason = cadence_reason
    elif force_tests or manual_scope_requested or checkpoint_active:
        tests_should_run = True
        if manual_scope_requested:
            log("TEST_SCOPE/AIDD_TEST_TASKS/AIDD_TEST_FILTERS заданы — выполняем указанные задачи тестов.")
        elif force_env_name and force_tests:
            log(f"{force_env_name}=1 — тесты будут запущены независимо от маркера reviewer.")
        elif checkpoint_active:
            log("checkpoint trigger активен — тесты будут запущены.")
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

    loop_mode = active_mode == "loop"
    loop_tests_override = False
    loop_tests_flag = env_flag("AIDD_LOOP_TESTS")
    if loop_tests_flag is not None:
        loop_tests_override = bool(loop_tests_flag)
    if policy_force:
        loop_tests_override = True

    if loop_mode:
        if stage == "review":
            tests_should_run = False
            skip_reason = "loop-mode: review stage — тесты пропущены."
        elif stage == "implement" and not loop_tests_override:
            tests_should_run = False
            skip_reason = "loop-mode: тесты запускаются только с AIDD_LOOP_TESTS=1 или AIDD_TEST_FORCE=1."

    if tests_should_run and service_only(diff_files, aidd_root=aidd_root):
        tests_should_run = False
        skip_reason = "Diff пустой/только service — тесты пропущены."

    skip_format_flag = os.environ.get("SKIP_FORMAT", "0") == "1"
    format_only_flag = os.environ.get("FORMAT_ONLY", "0") == "1"
    if test_profile == "none":
        format_only_flag = True
        log("AIDD_TEST_PROFILE=none — тесты пропущены (FORMAT_ONLY=1).")

    if changed_only_flag and not (
        force_tests or reviewer_required or manual_scope_requested or policy_active or checkpoint_active
    ):
        if not changed_files:
            log("Изменения не обнаружены — форматирование и тесты пропущены.")
            if not format_only_flag:
                return 0
        elif not has_code_changes(changed_files, code_prefixes, code_suffixes, code_exact):
            if active_ticket and common_hits:
                changed_only_flag = False
            else:
                preview = " ".join(changed_files[:8])
                if len(changed_files) > 8:
                    preview = f"{preview} ..."
                if format_only_flag:
                    log(f"Изменены только некодовые файлы ({preview}) — FORMAT_ONLY=1, выполняем только форматирование.")
                else:
                    log(f"Изменены только некодовые файлы ({preview}) — форматирование и тесты пропущены.")
                    record_event("skipped", "non-code-changes")
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
        record_event("skipped", "format-only")
        record_tests_log("skipped", "format-only")
        return 0

    if not tests_should_run:
        if skip_reason:
            log(skip_reason)
        else:
            log("Стадия тестов пропущена (reviewerGate).")
        record_event("skipped", "tests-disabled")
        record_tests_log("skipped", skip_reason or "tests-disabled")
        return 0

    if checkpoint_active:
        clear_checkpoint(checkpoint_path)
        log("Checkpoint consumed — повторный запуск потребует нового checkpoint.")

    if active_ticket and common_hits:
        changed_only_flag = False
        if test_profile != "full":
            test_profile = "full"
            profile_source = "common-files"
        log(
            f"Активная фича '{feature_label(active_ticket, slug_hint)}', изменены общие файлы: {' '.join(common_hits)} — полный прогон тестов (profile=full)."
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

    if not test_tasks and test_profile != "none":
        profile_tasks: List[str] = []
        if test_profile == "full":
            profile_tasks = full_tasks or default_tasks
        elif test_profile == "fast":
            profile_tasks = fast_tasks or default_tasks
        elif test_profile == "targeted":
            profile_tasks = targeted_tasks or fast_tasks or default_tasks
        for task in profile_tasks:
            append_unique(test_tasks, task)

    if not test_tasks:
        for task in fallback_tasks:
            append_unique(test_tasks, task)

    if test_filters:
        for filter_item in test_filters:
            if filter_flag:
                test_tasks.append(filter_flag)
            test_tasks.append(filter_item)

    if not test_tasks:
        log("Нет задач для запуска тестов — проверка пропущена.")
        record_event("skipped", "no-tests")
        record_tests_log("skipped", "no-tests")
        return 0

    log(f"Выбранные задачи тестов ({test_profile}): {' '.join(test_tasks)}")

    if not test_runner or not test_runner[0]:
        log("Не указан runner для тестов — стадия пропущена.")
        record_event("skipped", "no-runner")
        return 0

    diff_parts: List[str] = []
    if git_has_head():
        diff_parts.append(git_output(["git", "diff", "--no-color"]))
        diff_parts.append(git_output(["git", "diff", "--no-color", "--cached"]))
    else:
        diff_parts.append(git_output(["git", "diff", "--no-color", "--cached"]))
    diff_text = "\n".join(part for part in diff_parts if part)
    diff_text = strip_event_diffs(diff_text)
    untracked_files = [path for path in list_untracked_files() if not is_cache_artifact(path)]
    dedupe_meta: Dict[str, object] = {
        "profile": test_profile,
        "tasks": test_tasks,
        "filters": test_filters,
        "runner": test_runner,
        "changed_only": changed_only_flag,
        "manual_scope": manual_scope_requested,
        "changed_files": changed_files,
    }
    fingerprint = compute_tests_fingerprint(dedupe_meta, diff_text, untracked_files)
    cache_path = project_root / ".cache" / "format-and-test.last.json"
    last_state = load_dedupe_state(cache_path)
    if policy_force:
        log("AIDD_TEST_FORCE=1 — повторяем тесты независимо от дедупа.")
    elif last_state.get("fingerprint") == fingerprint and last_state.get("status") == "success":
        log("Dedupe: тесты уже запускались для текущего diff/profile — пропускаем повтор.")
        record_event("skipped", "dedupe")
        return 0
    elif last_state.get("fingerprint") == fingerprint and last_state.get("status") == "failed":
        log("Dedupe: предыдущий прогон завершился ошибкой — повторяем.")

    command = test_runner + test_tasks
    log(f"Запуск тестов: {' '.join(command)}")
    test_log_mode = resolve_test_log_mode()
    test_log_path = ensure_test_log_path(project_root, active_ticket or "unknown")
    log(f"Test log: {test_log_path}")
    with test_log_path.open("w", encoding="utf-8") as handle:
        result = subprocess.run(
            command,
            text=True,
            stdout=handle,
            stderr=subprocess.STDOUT,
        )
    status = "success" if result.returncode == 0 else "failed"
    write_dedupe_state(
        cache_path,
        {
            "fingerprint": fingerprint,
            "status": status,
            "profile": test_profile,
            "tasks": test_tasks,
            "filters": test_filters,
            "ran_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        },
    )
    if result.returncode == 0:
        log("Тесты завершились успешно.")
        record_event("pass")
        record_tests_log("pass", exit_code=0, log_path=test_log_path)
        return 0

    if test_log_mode == "full":
        tail_lines = resolve_test_log_tail_lines()
        tail = tail_file_lines(test_log_path, tail_lines)
        if tail.strip():
            log(f"Последние {tail_lines} строк лога тестов:\n{tail.rstrip()}")

    if strict_flag:
        record_event("fail")
        record_tests_log("fail", exit_code=result.returncode, log_path=test_log_path)
        return fail("Тесты завершились с ошибкой (STRICT_TESTS=1).", result.returncode)

    log("Тесты завершились с ошибкой, но STRICT_TESTS != 1 — продолжаем.")
    record_event("fail")
    record_tests_log("fail", exit_code=result.returncode, log_path=test_log_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
