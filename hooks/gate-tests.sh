#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path
from typing import Iterable


HOOK_PREFIX = "[gate-tests]"

DEFAULT_SOURCE_ROOTS = [
    "src/main",
    "src",
    "app",
    "apps",
    "packages",
    "services",
    "service",
    "lib",
    "libs",
    "backend",
    "frontend",
]
DEFAULT_SOURCE_EXTS = [
    ".kt",
    ".java",
    ".kts",
    ".groovy",
    ".py",
    ".js",
    ".jsx",
    ".ts",
    ".tsx",
    ".go",
    ".rb",
    ".rs",
    ".cs",
    ".php",
]
DEFAULT_TEST_PATTERNS = [
    "src/test/{rel_dir}/{base}Test{ext}",
    "src/test/{rel_dir}/{base}Tests{ext}",
    "tests/{rel_dir}/test_{base}{ext}",
    "tests/{rel_dir}/{base}_test{ext}",
    "tests/{rel_dir}/{base}.test{ext}",
    "tests/{rel_dir}/{base}.spec{ext}",
    "test/{rel_dir}/test_{base}{ext}",
    "test/{rel_dir}/{base}_test{ext}",
    "spec/{rel_dir}/{base}_spec{ext}",
    "spec/{rel_dir}/{base}Spec{ext}",
    "__tests__/{rel_dir}/{base}.test{ext}",
    "__tests__/{rel_dir}/{base}.spec{ext}",
]
DEFAULT_EXCLUDE_DIRS = [
    "test",
    "tests",
    "spec",
    "specs",
    "__tests__",
    "androidTest",
    "integrationTest",
    "functionalTest",
    "testFixtures",
]


def _bootstrap() -> None:
    raw = os.environ.get("CLAUDE_PLUGIN_ROOT")
    if not raw:
        print(f"{HOOK_PREFIX} CLAUDE_PLUGIN_ROOT is required to run hooks.", file=sys.stderr)
        raise SystemExit(2)
    plugin_root = Path(raw).expanduser().resolve()
    if str(plugin_root) not in sys.path:
        sys.path.insert(0, str(plugin_root))
    vendor_dir = Path(__file__).resolve().parent / "_vendor"
    if vendor_dir.exists():
        sys.path.insert(0, str(vendor_dir))


def _log_stdout(message: str) -> None:
    from hooks import hooklib

    if message:
        print(hooklib.prefix_lines(HOOK_PREFIX, message))


def _log_stderr(message: str) -> None:
    from hooks import hooklib

    if message:
        print(hooklib.prefix_lines(HOOK_PREFIX, message), file=sys.stderr)


def _norm_list(value: object, default: list[str]) -> list[str]:
    if value is None:
        value = default
    if isinstance(value, str):
        value = [value]
    elif not isinstance(value, (list, tuple)):
        value = default
    items: list[str] = []
    for raw in value:
        text = str(raw).strip()
        if not text:
            continue
        text = text.lstrip("./")
        text = text.rstrip("/")
        if text:
            items.append(text)
    return items


def _norm_exts(value: object, default: list[str]) -> list[str]:
    if value is None:
        value = default
    if isinstance(value, str):
        value = [value]
    elif not isinstance(value, (list, tuple)):
        value = default
    items: list[str] = []
    for raw in value:
        text = str(raw).strip()
        if not text:
            continue
        if not text.startswith("."):
            text = f".{text}"
        items.append(text.lower())
    return items


def _unique(seq: Iterable[str]) -> list[str]:
    seen = set()
    out: list[str] = []
    for item in seq:
        if item in seen:
            continue
        seen.add(item)
        out.append(item)
    return out


def _load_tests_config(root: Path) -> dict[str, list[str]]:
    config_path = root / "config" / "gates.json"
    try:
        data = json.loads(config_path.read_text(encoding="utf-8"))
    except Exception:
        data = {}
    cfg = data.get("tests_gate")
    if not isinstance(cfg, dict):
        cfg = {}

    source_roots = _unique(_norm_list(cfg.get("source_roots"), DEFAULT_SOURCE_ROOTS))
    source_roots.sort(key=len, reverse=True)
    source_exts = _unique(_norm_exts(cfg.get("source_extensions"), DEFAULT_SOURCE_EXTS))
    test_patterns = _unique(_norm_list(cfg.get("test_patterns"), DEFAULT_TEST_PATTERNS))
    test_exts = _unique(_norm_exts(cfg.get("test_extensions"), []))
    exclude_dirs = _unique(
        _norm_list(cfg.get("exclude_dirs") or cfg.get("source_exclude_dirs"), DEFAULT_EXCLUDE_DIRS)
    )
    return {
        "source_roots": source_roots,
        "source_exts": source_exts,
        "test_patterns": test_patterns,
        "test_exts": test_exts,
        "exclude_dirs": exclude_dirs,
    }


def _is_excluded_path(path: str, exclude_dirs: list[str]) -> bool:
    if not exclude_dirs:
        return False
    parts = path.split("/")
    for exclude in exclude_dirs:
        if not exclude:
            continue
        if "/" in exclude:
            if path == exclude or path.startswith(f"{exclude}/"):
                return True
            continue
        if exclude in parts:
            return True
    return False


def _emit_research_hint(root: Path, file_path: str, ticket: str, slug_hint: str) -> None:
    config_path = root / "config" / "gates.json"
    try:
        config = json.loads(config_path.read_text(encoding="utf-8"))
    except Exception:
        return
    research = config.get("researcher") or {}
    if not research.get("enabled", True):
        return

    targets_path = root / "reports" / "research" / f"{ticket}-targets.json"
    try:
        targets = json.loads(targets_path.read_text(encoding="utf-8"))
    except Exception:
        return

    paths = targets.get("paths") or []
    for candidate in paths:
        raw = Path(candidate)
        if raw.is_absolute():
            try:
                candidate_rel = raw.relative_to(root).as_posix()
            except ValueError:
                continue
        else:
            candidate_rel = raw.as_posix().lstrip("./")
        if not candidate_rel:
            continue
        normalized = candidate_rel.rstrip("/")
        if file_path.startswith(f"{normalized}/") or file_path == normalized:
            return

    label = ticket if not slug_hint or slug_hint == ticket else f"{ticket} (slug hint: {slug_hint})"
    _log_stdout(
        "WARN: {} не входит в список Researcher targets → обновите "
        "${{CLAUDE_PLUGIN_ROOT}}/tools/research.sh для {} или настройте paths.".format(file_path, label)
    )


def _reviewer_notice(root: Path, ticket: str, slug_hint: str) -> str:
    config_path = root / "config" / "gates.json"
    try:
        config = json.loads(config_path.read_text(encoding="utf-8"))
    except Exception:
        return ""

    reviewer_cfg = config.get("reviewer") or {}
    if not reviewer_cfg or not reviewer_cfg.get("enabled", True):
        return ""

    template = str(
        reviewer_cfg.get("tests_marker")
        or reviewer_cfg.get("marker")
        or "aidd/reports/reviewer/{ticket}.json"
    )
    field = str(reviewer_cfg.get("tests_field") or reviewer_cfg.get("field") or "tests")
    required_values_source = reviewer_cfg.get("requiredValues", reviewer_cfg.get("required_values", ["required"]))
    if isinstance(required_values_source, list):
        required_values = [str(value).strip().lower() for value in required_values_source]
    else:
        required_values = ["required"]

    slug_value = slug_hint.strip() or ticket
    marker_path = Path(template.replace("{ticket}", ticket).replace("{slug}", slug_value))
    if not marker_path.is_absolute() and marker_path.parts and marker_path.parts[0] == "aidd" and root.name == "aidd":
        marker_path = root / Path(*marker_path.parts[1:])
    elif not marker_path.is_absolute():
        marker_path = root / marker_path

    if not marker_path.exists():
        return ""

    try:
        data = json.loads(marker_path.read_text(encoding="utf-8"))
    except Exception:
        return (
            "WARN: reviewer маркер повреждён ({}). Пересоздайте его командой "
            "`${{CLAUDE_PLUGIN_ROOT}}/tools/reviewer-tests.sh --status required`.".format(marker_path)
        )

    value = str(data.get(field, "")).strip().lower()
    if value in required_values:
        label = ticket if not slug_hint or slug_hint == ticket else f"{ticket} (slug hint: {slug_hint})"
        return (
            "WARN: reviewer запросил обязательный запуск тестов для {} ({}). "
            "Не забудьте подтвердить выполнение перед merge.".format(label, marker_path)
        )
    return ""


def main() -> int:
    _bootstrap()
    from hooks import hooklib

    ctx = hooklib.read_hook_context()
    root, used_workspace = hooklib.resolve_project_root(ctx)
    if used_workspace:
        _log_stdout(f"WARN: detected workspace root; using {root} as project root")

    if not (root / "docs").is_dir():
        _log_stderr(
            "BLOCK: aidd/docs not found at {}. Run '/feature-dev-aidd:aidd-init' or "
            "'${CLAUDE_PLUGIN_ROOT}/tools/init.sh' from the workspace root to bootstrap ./aidd.".format(
                root / "docs"
            )
        )
        return 2

    if os.environ.get("CLAUDE_SKIP_STAGE_CHECKS") != "1":
        stage = hooklib.resolve_stage(root / "docs" / ".active_stage")
        if stage != "implement":
            return 0

    payload = ctx.raw
    file_path = hooklib.payload_file_path(payload) or ""

    config_path = root / "config" / "gates.json"
    ticket_path = root / "docs" / ".active_ticket"
    slug_path = root / "docs" / ".active_feature"
    ticket = hooklib.read_ticket(ticket_path, slug_path)
    slug_hint = hooklib.read_slug(slug_path) if slug_path.exists() else ""

    if ticket:
        reviewer_msg = _reviewer_notice(root, ticket, slug_hint)
        if reviewer_msg:
            _log_stdout(reviewer_msg)

    mode = hooklib.config_get_str(config_path, "tests_required", "disabled").lower()
    if mode == "disabled":
        return 0

    tests_cfg = _load_tests_config(root)
    source_roots = tests_cfg["source_roots"]
    source_exts = tests_cfg["source_exts"]
    test_patterns = tests_cfg["test_patterns"]
    test_exts = tests_cfg["test_exts"]
    exclude_dirs = tests_cfg["exclude_dirs"]

    changed_files = hooklib.collect_changed_files(root)
    if file_path:
        changed_files.insert(0, file_path)
    changed_files = _unique(changed_files)

    target_files: list[str] = []
    target_roots: list[str] = []
    for candidate in changed_files:
        ext_raw = candidate.rsplit(".", 1)
        if len(ext_raw) != 2 or not ext_raw[1]:
            continue
        ext = f".{ext_raw[1].lower()}"
        if ext not in source_exts:
            continue
        if _is_excluded_path(candidate, exclude_dirs):
            continue
        match_root = ""
        for root_dir in source_roots:
            if candidate.startswith(f"{root_dir}/"):
                match_root = root_dir
                break
        if not match_root:
            continue
        target_files.append(candidate)
        target_roots.append(match_root)

    if not target_files:
        return 0

    event_status = "fail"
    event_should_log = True
    try:
        missing_files: list[str] = []
        missing_tests: list[str] = []
        for path, root_dir in zip(target_files, target_roots):
            rel = path[len(root_dir) + 1 :]
            rel_dir = str(Path(rel).parent)
            rel_dir = "" if rel_dir == "." else rel_dir
            base = Path(path).stem
            ext = f".{path.rsplit('.', 1)[1].lower()}"

            expected_paths: list[str] = []
            for pattern in test_patterns:
                if not pattern:
                    continue
                use_test_ext = "{test_ext}" in pattern
                ext_candidates = test_exts if use_test_ext and test_exts else [ext]
                for test_ext in ext_candidates:
                    candidate_path = (
                        pattern.replace("{rel_dir}", rel_dir)
                        .replace("{rel_path}", rel)
                        .replace("{base}", base)
                        .replace("{ext}", ext)
                        .replace("{test_ext}", test_ext)
                    )
                    while "//" in candidate_path:
                        candidate_path = candidate_path.replace("//", "/")
                    candidate_path = candidate_path.lstrip("./")
                    expected_paths.append(candidate_path)

            expected_paths = _unique(expected_paths)
            has_tests = any((root / p).is_file() for p in expected_paths)
            if has_tests:
                if ticket:
                    _emit_research_hint(root, path, ticket, slug_hint)
                continue

            if len(expected_paths) == 1:
                hint = expected_paths[0]
            elif len(expected_paths) >= 2:
                hint = f"{expected_paths[0]} или {expected_paths[1]}"
                if len(expected_paths) > 2:
                    hint = f"{hint} (и ещё {len(expected_paths) - 2})"
            else:
                hint = "(не настроены шаблоны тестов)"

            missing_files.append(path)
            missing_tests.append(hint)

        if not missing_files:
            event_status = "pass"
            return 0

        if mode == "soft":
            for path, hint in zip(missing_files, missing_tests):
                _log_stdout(f"WARN: отсутствует тест для {path}. Рекомендуется создать {hint}.")
                if ticket:
                    _emit_research_hint(root, path, ticket, slug_hint)
            event_status = "warn"
            return 0

        for path, hint in zip(missing_files, missing_tests):
            _log_stderr(
                "BLOCK: нет теста для {}. Создайте {} либо переведите tests_required в config/gates.json в soft/disabled.".format(
                    path, hint
                )
            )
            if ticket:
                _emit_research_hint(root, path, ticket, slug_hint)
        return 2
    finally:
        if event_should_log:
            hooklib.append_event(root, "gate-tests", event_status, source="hook gate-tests")


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
