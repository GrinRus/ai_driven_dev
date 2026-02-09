#!/usr/bin/env python3
"""Context-pack shaping helpers for researcher context."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

from aidd_runtime import researcher_context as core


def write_targets(builder, scope: "core.Scope") -> Path:
    builder._resolve_search_roots(scope)
    report_dir = builder.root / core._REPORT_DIR
    report_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "ticket": scope.ticket,
        "slug": scope.slug_hint or scope.ticket,
        "slug_hint": scope.slug_hint,
        "generated_at": core._utc_timestamp(),
        "config_source": os.path.relpath(builder.config_path, builder.root) if builder.config_path.exists() else None,
        "tags": scope.tags,
        "paths": scope.paths,
        "paths_discovered": scope.paths_discovered,
        "invalid_paths": scope.invalid_paths,
        "docs": scope.docs,
        "keywords": scope.keywords,
        "keywords_raw": scope.keywords_raw,
        "non_negotiables": scope.non_negotiables,
    }
    target_path = report_dir / f"{scope.ticket}-targets.json"
    target_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return target_path


def collect_context(builder, scope: "core.Scope", *, limit: int = core._MAX_MATCHES) -> Dict[str, Any]:
    path_infos, doc_infos, search_roots = builder._resolve_search_roots(scope)
    matches = builder._scan_matches(search_roots, scope.keywords, limit=limit)
    code_index: List[Dict[str, Any]] = []
    reuse_candidates: List[Dict[str, Any]] = []
    profile = builder._build_project_profile(scope, matches)

    return {
        "ticket": scope.ticket,
        "slug": scope.slug_hint or scope.ticket,
        "slug_hint": scope.slug_hint,
        "generated_at": core._utc_timestamp(),
        "config_source": os.path.relpath(builder.config_path, builder.root) if builder.config_path.exists() else None,
        "tags": scope.tags,
        "keywords": scope.keywords,
        "keywords_raw": scope.keywords_raw,
        "paths": path_infos,
        "paths_discovered": scope.paths_discovered,
        "invalid_paths": scope.invalid_paths,
        "docs": doc_infos,
        "matches": matches,
        "code_index": code_index,
        "reuse_candidates": reuse_candidates,
        "profile": profile,
        "manual_notes": scope.manual_notes,
        "non_negotiables": scope.non_negotiables,
    }


def write_context(builder, scope: "core.Scope", context: Dict[str, Any], *, output: Optional[Path] = None) -> Path:
    report_dir = builder.root / core._REPORT_DIR
    report_dir.mkdir(parents=True, exist_ok=True)
    target_path = output or (report_dir / f"{scope.ticket}-context.json")
    target_path = core._normalize_output_path(builder.root, target_path)
    target_path.parent.mkdir(parents=True, exist_ok=True)
    target_path.write_text(json.dumps(context, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return target_path


def build_project_profile(builder, scope: "core.Scope", matches: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    tests_detected, tests_evidence, suggested_test_tasks = detect_tests(builder)
    profile = {
        "is_new_project": len(matches) == 0,
        "src_layers": detect_src_layers(builder),
        "tests_detected": tests_detected,
        "tests_evidence": tests_evidence,
        "suggested_test_tasks": suggested_test_tasks,
        "config_detected": detect_configs(builder),
        "logging_artifacts": detect_logging_artifacts(builder),
        "recommendations": [],
    }
    profile["recommendations"] = baseline_recommendations(builder, profile, scope)
    return profile


def detect_src_layers(builder, limit: int = 8) -> List[str]:
    candidates = [builder._paths_base / "src"]
    if builder._paths_base != builder.root:
        candidates.append(builder.root / "src")
    src_dir = next((candidate for candidate in candidates if candidate.exists()), None)
    if not src_dir:
        return []
    layers: List[str] = []
    for child in sorted(src_dir.iterdir()):
        if not child.is_dir():
            continue
        layers.append(builder._rel_to_base(child))
        if len(layers) >= limit:
            break
    return layers


def detect_tests(builder) -> Tuple[bool, List[str], List[str]]:
    evidence: List[str] = []
    suggested_tasks: List[str] = []
    patterns = [
        "**/src/test",
        "**/src/tests",
        "**/test",
        "**/tests",
        "**/spec",
        "**/specs",
        "**/__tests__",
    ]
    roots = [builder._paths_base]
    if builder._paths_base != builder.root:
        roots.append(builder.root)
    for root in roots:
        if not root.exists():
            continue
        for pattern in patterns:
            try:
                iterator = root.glob(pattern)
            except OSError:
                continue
            for candidate in iterator:
                if not candidate.exists():
                    continue
                if is_excluded_test_path(builder, candidate):
                    continue
                evidence.append(builder._rel_to_base(candidate))
                if len(evidence) >= 12:
                    break
            if len(evidence) >= 12:
                break
        if len(evidence) >= 12:
            break

    try:
        from aidd_runtime.test_settings_defaults import detect_build_tools

        build_tools = detect_build_tools(builder._paths_base if builder._paths_base.exists() else builder.root)
    except Exception:
        build_tools = set()
    if "gradle" in build_tools:
        suggested_tasks.append("./gradlew test")
    if "npm" in build_tools:
        suggested_tasks.append("npm test")
    if "python" in build_tools:
        suggested_tasks.append("pytest")
    if "go" in build_tools:
        suggested_tasks.append("go test ./...")
    if "rust" in build_tools:
        suggested_tasks.append("cargo test")
    if "dotnet" in build_tools:
        suggested_tasks.append("dotnet test")

    return bool(evidence), core._unique(evidence), core._unique(suggested_tasks)


def is_excluded_test_path(builder, path: Path) -> bool:
    excluded_roots = {
        "docs",
        "reports",
        ".cache",
        ".git",
        "aidd",
        "node_modules",
        ".venv",
        "venv",
        "vendor",
        "dist",
        "build",
        "out",
        "target",
    }
    for base in (builder._paths_base, builder.root):
        try:
            rel = path.relative_to(base)
            parts = rel.parts
            if not parts:
                return False
            if any(part in excluded_roots for part in parts):
                return True
            return False
        except ValueError:
            continue
    return False


def detect_configs(builder) -> bool:
    candidates = [
        builder._paths_base / "config",
        builder._paths_base / "configs",
        builder._paths_base / "settings",
        builder._paths_base / "src" / "main" / "resources",
    ]
    if builder._paths_base != builder.root:
        candidates.extend(
            [
                builder.root / "config",
                builder.root / "configs",
                builder.root / "settings",
                builder.root / "src" / "main" / "resources",
            ]
        )
    for candidate in candidates:
        if candidate.exists():
            return True
    return False


def detect_logging_artifacts(builder, limit: int = 5) -> List[str]:
    tokens = ("logback", "logging", "logger", "log4j")
    candidates: List[str] = []
    search_roots = [
        builder._paths_base / "config",
        builder._paths_base / "configs",
        builder._paths_base / "src",
    ]
    if builder._paths_base != builder.root:
        search_roots.extend(
            [
                builder.root / "config",
                builder.root / "configs",
                builder.root / "src",
            ]
        )
    for root in search_roots:
        if not root.exists():
            continue
        try:
            iterator = root.rglob("*")
        except OSError:
            continue
        for path in iterator:
            if len(candidates) >= limit:
                break
            if not path.is_file():
                continue
            lowered = path.name.lower()
            if any(token in lowered for token in tokens):
                candidates.append(builder._rel_to_base(path))
        if len(candidates) >= limit:
            break
    return candidates


def baseline_recommendations(builder, profile: Dict[str, Any], scope: "core.Scope") -> List[str]:
    recommendations: List[str] = []
    defaults = builder._settings.get("defaults", {})
    default_paths = [item for item in defaults.get("paths", []) if isinstance(item, str) and item.strip()]
    default_docs = [item for item in defaults.get("docs", []) if isinstance(item, str) and item.strip()]
    default_keywords = [item for item in defaults.get("keywords", []) if isinstance(item, str) and item.strip()]

    if profile["is_new_project"] and default_paths:
        recommendations.append(
            "Создайте базовые директории для разработки: " + ", ".join(default_paths)
        )
    if profile["is_new_project"] and default_docs:
        recommendations.append(
            "Подготовьте документацию по умолчанию: " + ", ".join(default_docs)
        )
    if profile["is_new_project"] and default_keywords:
        recommendations.append(
            "Добавьте ключевые термины в код/доки: " + ", ".join(default_keywords[:5])
        )
    if not profile["tests_detected"]:
        recommendations.append("Добавьте tests/ или src/test для smoke-покрытия.")
    if not profile["config_detected"]:
        recommendations.append("Создайте config/ или settings/ с базовыми конфигурациями.")
    if not profile["logging_artifacts"]:
        recommendations.append("Настройте логирование (logback/logging.yaml) для наблюдаемости.")

    if scope.manual_notes:
        recommendations.append("Проверьте ручные заметки исследователя и перенесите их в отчёт.")

    return core._unique(recommendations)
