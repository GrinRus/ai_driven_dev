#!/usr/bin/env python3
"""Generate pack sidecars for reports."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

SCHEMA = "aidd.report.pack.v1"
PACK_VERSION = "v1"

RESEARCH_LIMITS: Dict[str, int] = {
    "tags": 10,
    "keywords": 10,
    "keywords_raw": 10,
    "non_negotiables": 10,
    "paths": 10,
    "paths_discovered": 10,
    "invalid_paths": 10,
    "docs": 10,
    "path_samples": 4,
    "matches": 20,
    "match_snippet_chars": 240,
    "reuse_candidates": 8,
    "manual_notes": 10,
    "tests_evidence": 10,
    "suggested_test_tasks": 10,
    "recommendations": 10,
    "import_graph": 30,
}

RESEARCH_BUDGET = {
    "max_chars": 1200,
    "max_lines": 60,
}

QA_LIMITS: Dict[str, int] = {
    "findings": 20,
    "tests_executed": 10,
}

PRD_LIMITS: Dict[str, int] = {
    "findings": 20,
    "action_items": 10,
}

CALL_GRAPH_LIMITS: Dict[str, int] = {
    "entrypoints": 10,
    "hotspots": 10,
    "edges": 30,
}

CALL_GRAPH_BUDGET = {
    "max_chars": 2000,
    "max_lines": 80,
}

AST_GREP_LIMITS: Dict[str, int] = {
    "rules": 10,
    "matches_per_rule": 5,
}

AST_GREP_BUDGET = {
    "max_chars": 1600,
    "max_lines": 80,
}

_PACK_FORMATS = {"yaml", "toon"}
_ESSENTIAL_FIELDS = {
    "schema",
    "pack_version",
    "type",
    "kind",
    "ticket",
    "slug",
    "slug_hint",
    "generated_at",
    "source_path",
    "call_graph_warning",
    "call_graph_engine",
    "call_graph_supported_languages",
    "call_graph_filter",
    "call_graph_limit",
    "call_graph_edges_path",
}
_ENV_LIMITS_CACHE: Dict[str, Dict[str, int]] | None = None
_BUDGET_HINT = "Reduce top-N, trim snippets, or set AIDD_PACK_LIMITS to lower pack size."


def _utc_timestamp() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def check_budget(text: str, *, max_chars: int, max_lines: int, label: str) -> List[str]:
    errors: List[str] = []
    char_count = len(text)
    line_count = text.count("\n") + (1 if text else 0)
    if char_count > max_chars:
        errors.append(
            f"{label} pack budget exceeded: {char_count} chars > {max_chars}. {_BUDGET_HINT}"
        )
    if line_count > max_lines:
        errors.append(
            f"{label} pack budget exceeded: {line_count} lines > {max_lines}. {_BUDGET_HINT}"
        )
    return errors


def _check_count_budget(label: str, *, field: str, actual: int, limit: int) -> List[str]:
    if actual <= limit:
        return []
    return [f"{label} pack budget exceeded: {field} {actual} > {limit}. {_BUDGET_HINT}"]


def _is_empty(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    if isinstance(value, list):
        return len(value) == 0
    if isinstance(value, dict):
        return len(value) == 0
    return False


def _compact_value(value: Any) -> Any:
    if isinstance(value, dict):
        is_columnar = "cols" in value and "rows" in value
        compacted: Dict[str, Any] = {}
        for key, val in value.items():
            cleaned = _compact_value(val)
            if is_columnar and key in {"cols", "rows"}:
                compacted[key] = cleaned if cleaned is not None else []
                continue
            if _is_empty(cleaned):
                continue
            compacted[key] = cleaned
        return compacted
    if isinstance(value, list):
        cleaned_items = []
        for item in value:
            cleaned = _compact_value(item)
            if _is_empty(cleaned):
                continue
            cleaned_items.append(cleaned)
        return cleaned_items
    return value


def _compact_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    compacted: Dict[str, Any] = {}
    for key, value in payload.items():
        cleaned = _compact_value(value)
        if key in _ESSENTIAL_FIELDS:
            compacted[key] = cleaned
            continue
        if _is_empty(cleaned):
            continue
        compacted[key] = cleaned
    return compacted


def _serialize_pack(payload: Dict[str, Any]) -> str:
    payload = _apply_field_filters(payload)
    payload = _compact_payload(payload)
    return json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n"


def _write_pack_text(text: str, pack_path: Path) -> Path:
    pack_path.parent.mkdir(parents=True, exist_ok=True)
    pack_path.write_text(text, encoding="utf-8")
    return pack_path


def _enforce_budget() -> bool:
    return os.getenv("AIDD_PACK_ENFORCE_BUDGET", "").strip() == "1"


def _trim_columnar_rows(payload: Dict[str, Any], key: str) -> bool:
    section = payload.get(key)
    if not isinstance(section, dict):
        return False
    rows = section.get("rows")
    if not isinstance(rows, list) or not rows:
        return False
    rows.pop()
    return True


def _trim_list_field(payload: Dict[str, Any], key: str) -> bool:
    items = payload.get(key)
    if not isinstance(items, list) or not items:
        return False
    items.pop()
    return True


def _trim_profile_recommendations(payload: Dict[str, Any]) -> bool:
    profile = payload.get("profile")
    if not isinstance(profile, dict):
        return False
    recs = profile.get("recommendations")
    if not isinstance(recs, list) or not recs:
        return False
    recs.pop()
    return True


def _trim_profile_list(payload: Dict[str, Any], key: str) -> bool:
    profile = payload.get("profile")
    if not isinstance(profile, dict):
        return False
    items = profile.get(key)
    if not isinstance(items, list) or not items:
        return False
    items.pop()
    return True


def _trim_path_samples(payload: Dict[str, Any], key: str) -> bool:
    entries = payload.get(key)
    if not isinstance(entries, list) or not entries:
        return False
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        samples = entry.get("sample")
        if isinstance(samples, list) and samples:
            samples.pop()
            return True
    return False


def _drop_columnar_if_empty(payload: Dict[str, Any], key: str) -> bool:
    section = payload.get(key)
    if not isinstance(section, dict):
        return False
    rows = section.get("rows")
    if not isinstance(rows, list) or rows:
        return False
    payload.pop(key, None)
    return True


def _drop_field(payload: Dict[str, Any], key: str) -> bool:
    if key not in payload:
        return False
    payload.pop(key, None)
    return True


def _auto_trim_research_pack(payload: Dict[str, Any], max_chars: int, max_lines: int) -> tuple[str, List[str], List[str]]:
    text = _serialize_pack(payload)
    errors = check_budget(text, max_chars=max_chars, max_lines=max_lines, label="research")
    if not errors:
        return text, [], []

    trimmed_counts: Dict[str, int] = {}
    steps = [
        ("matches", lambda: _trim_columnar_rows(payload, "matches")),
        ("import_graph", lambda: _trim_columnar_rows(payload, "import_graph")),
        ("reuse_candidates", lambda: _trim_columnar_rows(payload, "reuse_candidates")),
        ("manual_notes", lambda: _trim_list_field(payload, "manual_notes")),
        ("profile.recommendations", lambda: _trim_profile_recommendations(payload)),
        ("paths.sample", lambda: _trim_path_samples(payload, "paths")),
        ("docs.sample", lambda: _trim_path_samples(payload, "docs")),
        ("paths", lambda: _trim_list_field(payload, "paths")),
        ("docs", lambda: _trim_list_field(payload, "docs")),
        ("paths_discovered", lambda: _trim_list_field(payload, "paths_discovered")),
        ("invalid_paths", lambda: _trim_list_field(payload, "invalid_paths")),
        ("keywords_raw", lambda: _trim_list_field(payload, "keywords_raw")),
        ("keywords", lambda: _trim_list_field(payload, "keywords")),
        ("profile.tests_evidence", lambda: _trim_profile_list(payload, "tests_evidence")),
        ("profile.suggested_test_tasks", lambda: _trim_profile_list(payload, "suggested_test_tasks")),
        ("profile.logging_artifacts", lambda: _trim_profile_list(payload, "logging_artifacts")),
        ("filter_stats", lambda: _drop_field(payload, "filter_stats")),
        ("filter_trimmed", lambda: _drop_field(payload, "filter_trimmed")),
        ("ast_grep_stats", lambda: _drop_field(payload, "ast_grep_stats")),
        ("ast_grep_path", lambda: _drop_field(payload, "ast_grep_path")),
        ("ast_grep_schema", lambda: _drop_field(payload, "ast_grep_schema")),
        ("call_graph_edges_stats", lambda: _drop_field(payload, "call_graph_edges_stats")),
        ("call_graph_edges_truncated", lambda: _drop_field(payload, "call_graph_edges_truncated")),
        ("call_graph_filter", lambda: _drop_field(payload, "call_graph_filter")),
        ("drop.matches", lambda: _drop_columnar_if_empty(payload, "matches")),
        ("drop.import_graph", lambda: _drop_columnar_if_empty(payload, "import_graph")),
        ("drop.reuse_candidates", lambda: _drop_columnar_if_empty(payload, "reuse_candidates")),
        ("drop.profile", lambda: _drop_field(payload, "profile")),
        ("drop.stats", lambda: _drop_field(payload, "stats")),
    ]

    for name, action in steps:
        while errors and action():
            trimmed_counts[name] = trimmed_counts.get(name, 0) + 1
            text = _serialize_pack(payload)
            errors = check_budget(text, max_chars=max_chars, max_lines=max_lines, label="research")
        if not errors:
            break

    trimmed = [f"{name}(-{count})" for name, count in trimmed_counts.items()]
    return text, trimmed, errors


def _truncate_list(items: Iterable[Any], limit: int) -> List[Any]:
    if limit <= 0:
        return []
    return list(items)[:limit]


def _truncate_text(text: str, limit: int) -> str:
    if limit <= 0:
        return ""
    if len(text) <= limit:
        return text
    return text[:limit].rstrip()


def _stable_id(*parts: Any) -> str:
    digest = hashlib.sha1()
    for part in parts:
        digest.update(str(part).encode("utf-8"))
        digest.update(b"|")
    return digest.hexdigest()[:12]


def _columnar(cols: List[str], rows: List[List[Any]]) -> Dict[str, Any]:
    return {
        "cols": cols,
        "rows": rows,
    }


def _pack_paths(entries: Iterable[Any], limit: int, sample_limit: int) -> List[Dict[str, Any]]:
    packed: List[Dict[str, Any]] = []
    for entry in _truncate_list(entries, limit):
        if not isinstance(entry, dict):
            continue
        samples = entry.get("sample") or []
        packed.append(
            {
                "path": entry.get("path"),
                "type": entry.get("type"),
                "exists": entry.get("exists"),
                "sample": _truncate_list(samples, sample_limit),
            }
        )
    return packed


def _pack_matches(entries: Iterable[Any], limit: int, snippet_limit: int) -> Dict[str, Any]:
    cols = ["id", "token", "file", "line", "snippet"]
    rows: List[List[Any]] = []
    for entry in _truncate_list(entries, limit):
        if not isinstance(entry, dict):
            continue
        token = str(entry.get("token") or "").strip()
        file_path = str(entry.get("file") or "").strip()
        line = entry.get("line")
        snippet = _truncate_text(str(entry.get("snippet") or ""), snippet_limit)
        if not file_path:
            continue
        rows.append([_stable_id(file_path, line, token), token, file_path, line, snippet])
    return _columnar(cols, rows)


def _pack_reuse(entries: Iterable[Any], limit: int) -> Dict[str, Any]:
    cols = ["id", "path", "language", "score", "has_tests", "top_symbols", "imports"]
    rows: List[List[Any]] = []
    for entry in _truncate_list(entries, limit):
        if not isinstance(entry, dict):
            continue
        path = str(entry.get("path") or "").strip()
        if not path:
            continue
        score = entry.get("score")
        rows.append(
            [
                _stable_id(path, score, entry.get("language")),
                path,
                entry.get("language"),
                score,
                entry.get("has_tests"),
                _truncate_list(entry.get("top_symbols") or [], 3),
                _truncate_list(entry.get("imports") or [], 5),
            ]
        )
    return _columnar(cols, rows)


def _pack_call_graph(entries: Iterable[Any], limit: int) -> Dict[str, Any]:
    cols = ["caller", "callee", "file", "line", "language"]
    rows: List[List[Any]] = []
    for entry in _truncate_list(entries, limit):
        if not isinstance(entry, dict):
            continue
        rows.append(
            [
                entry.get("caller"),
                entry.get("callee"),
                entry.get("file"),
                entry.get("line"),
                entry.get("language"),
            ]
        )
    return _columnar(cols, rows)


def _pack_import_graph(entries: Iterable[Any], limit: int) -> Dict[str, Any]:
    cols = ["import"]
    rows = [[value] for value in _truncate_list(entries or [], limit)]
    return _columnar(cols, rows)


def _pack_findings(entries: Iterable[Any], limit: int, cols: List[str]) -> Dict[str, Any]:
    rows: List[List[Any]] = []
    for entry in _truncate_list(entries, limit):
        if not isinstance(entry, dict):
            continue
        rows.append([entry.get(col) for col in cols])
    return _columnar(cols, rows)


def _pack_format() -> str:
    value = os.getenv("AIDD_PACK_FORMAT", "yaml").strip().lower()
    return value if value in _PACK_FORMATS else "yaml"


def _pack_extension() -> str:
    return ".pack.toon" if _pack_format() == "toon" else ".pack.yaml"


def _split_env(name: str) -> List[str]:
    raw = os.getenv(name, "").strip()
    if not raw:
        return []
    return [item.strip() for item in raw.split(",") if item.strip()]


def _apply_field_filters(payload: Dict[str, Any]) -> Dict[str, Any]:
    allow_fields = _split_env("AIDD_PACK_ALLOW_FIELDS")
    strip_fields = _split_env("AIDD_PACK_STRIP_FIELDS")
    if not allow_fields and not strip_fields:
        return payload

    filtered = payload
    if allow_fields:
        filtered = {key: value for key, value in payload.items() if key in allow_fields or key in _ESSENTIAL_FIELDS}
    if strip_fields:
        filtered = dict(filtered)
        for key in strip_fields:
            if key in _ESSENTIAL_FIELDS:
                continue
            filtered.pop(key, None)
    return filtered


def _env_limits() -> Dict[str, Dict[str, int]]:
    global _ENV_LIMITS_CACHE
    if _ENV_LIMITS_CACHE is not None:
        return _ENV_LIMITS_CACHE
    raw = os.getenv("AIDD_PACK_LIMITS", "").strip()
    if not raw:
        _ENV_LIMITS_CACHE = {}
        return _ENV_LIMITS_CACHE
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        _ENV_LIMITS_CACHE = {}
        return _ENV_LIMITS_CACHE
    if not isinstance(payload, dict):
        _ENV_LIMITS_CACHE = {}
        return _ENV_LIMITS_CACHE
    parsed: Dict[str, Dict[str, int]] = {}
    for key, value in payload.items():
        if not isinstance(value, dict):
            continue
        limits: Dict[str, int] = {}
        for limit_key, limit_value in value.items():
            try:
                limits[limit_key] = int(limit_value)
            except (TypeError, ValueError):
                continue
        if limits:
            parsed[key] = limits
    _ENV_LIMITS_CACHE = parsed
    return _ENV_LIMITS_CACHE


def _pack_tests_executed(entries: Iterable[Any], limit: int) -> Dict[str, Any]:
    cols = ["command", "status", "log", "exit_code"]
    rows: List[List[Any]] = []
    for entry in _truncate_list(entries, limit):
        if not isinstance(entry, dict):
            continue
        rows.append(
            [
                entry.get("command"),
                entry.get("status"),
                entry.get("log") or entry.get("log_path"),
                entry.get("exit_code"),
            ]
        )
    return _columnar(cols, rows)


def build_research_context_pack(
    payload: Dict[str, Any],
    *,
    source_path: Optional[str] = None,
    limits: Optional[Dict[str, int]] = None,
) -> Dict[str, Any]:
    env_limits = _env_limits().get("research") or {}
    lim = {**RESEARCH_LIMITS, **env_limits, **(limits or {})}

    profile = payload.get("profile") or {}
    recommendations = _truncate_list(profile.get("recommendations") or [], lim["recommendations"])
    tests_evidence = _truncate_list(profile.get("tests_evidence") or [], lim["tests_evidence"])
    suggested_test_tasks = _truncate_list(profile.get("suggested_test_tasks") or [], lim["suggested_test_tasks"])
    manual_notes = _truncate_list(payload.get("manual_notes") or [], lim["manual_notes"])

    packed = {
        "schema": SCHEMA,
        "pack_version": PACK_VERSION,
        "type": "research",
        "kind": "context",
        "ticket": payload.get("ticket"),
        "slug": payload.get("slug"),
        "slug_hint": payload.get("slug_hint"),
        "generated_at": payload.get("generated_at"),
        "source_path": source_path,
        "tags": _truncate_list(payload.get("tags") or [], lim["tags"]),
        "keywords": _truncate_list(payload.get("keywords") or [], lim["keywords"]),
        "keywords_raw": _truncate_list(payload.get("keywords_raw") or [], lim["keywords_raw"]),
        "non_negotiables": _truncate_list(payload.get("non_negotiables") or [], lim["non_negotiables"]),
        "paths": _pack_paths(payload.get("paths") or [], lim["paths"], lim["path_samples"]),
        "paths_discovered": _truncate_list(payload.get("paths_discovered") or [], lim["paths_discovered"]),
        "invalid_paths": _truncate_list(payload.get("invalid_paths") or [], lim["invalid_paths"]),
        "docs": _pack_paths(payload.get("docs") or [], lim["docs"], lim["path_samples"]),
        "profile": {
            "is_new_project": profile.get("is_new_project"),
            "src_layers": profile.get("src_layers") or [],
            "tests_detected": profile.get("tests_detected"),
            "tests_evidence": tests_evidence,
            "suggested_test_tasks": suggested_test_tasks,
            "config_detected": profile.get("config_detected"),
            "logging_artifacts": profile.get("logging_artifacts") or [],
            "recommendations": recommendations,
        },
        "manual_notes": manual_notes,
        "reuse_candidates": _pack_reuse(payload.get("reuse_candidates") or [], lim["reuse_candidates"]),
        "matches": _pack_matches(payload.get("matches") or [], lim["matches"], lim["match_snippet_chars"]),
        "import_graph": _pack_import_graph(payload.get("import_graph") or [], lim["import_graph"]),
        "call_graph_warning": payload.get("call_graph_warning"),
        "call_graph_engine": payload.get("call_graph_engine"),
        "call_graph_supported_languages": payload.get("call_graph_supported_languages") or [],
        "call_graph_filter": payload.get("call_graph_filter"),
        "call_graph_limit": payload.get("call_graph_limit"),
        "call_graph_edges_path": payload.get("call_graph_edges_path"),
        "call_graph_edges_schema": payload.get("call_graph_edges_schema"),
        "call_graph_edges_stats": payload.get("call_graph_edges_stats"),
        "call_graph_edges_truncated": payload.get("call_graph_edges_truncated"),
        "ast_grep_path": payload.get("ast_grep_path"),
        "ast_grep_schema": payload.get("ast_grep_schema"),
        "ast_grep_stats": payload.get("ast_grep_stats"),
        "filter_stats": payload.get("filter_stats"),
        "filter_trimmed": payload.get("filter_trimmed"),
        "deep_mode": payload.get("deep_mode"),
        "auto_mode": payload.get("auto_mode"),
        "stats": {
            "matches": len(payload.get("matches") or []),
            "reuse_candidates": len(payload.get("reuse_candidates") or []),
            "import_graph": len(payload.get("import_graph") or []),
        },
    }

    return packed


def build_qa_pack(
    payload: Dict[str, Any],
    *,
    source_path: Optional[str] = None,
    limits: Optional[Dict[str, int]] = None,
) -> Dict[str, Any]:
    env_limits = _env_limits().get("qa") or {}
    lim = {**QA_LIMITS, **env_limits, **(limits or {})}
    findings = payload.get("findings") or []

    packed = {
        "schema": SCHEMA,
        "pack_version": PACK_VERSION,
        "type": "qa",
        "kind": "report",
        "ticket": payload.get("ticket"),
        "slug_hint": payload.get("slug_hint"),
        "generated_at": payload.get("generated_at"),
        "status": payload.get("status"),
        "summary": payload.get("summary"),
        "branch": payload.get("branch"),
        "source_path": source_path,
        "counts": payload.get("counts") or {},
        "findings": _pack_findings(
            findings,
            lim["findings"],
            ["id", "severity", "scope", "blocking", "title", "details", "recommendation"],
        ),
        "tests_summary": payload.get("tests_summary"),
        "tests_executed": _pack_tests_executed(payload.get("tests_executed") or [], lim["tests_executed"]),
        "inputs": payload.get("inputs") or {},
        "stats": {
            "findings": len(findings),
        },
    }
    return packed


def build_prd_pack(
    payload: Dict[str, Any],
    *,
    source_path: Optional[str] = None,
    limits: Optional[Dict[str, int]] = None,
) -> Dict[str, Any]:
    env_limits = _env_limits().get("prd") or {}
    lim = {**PRD_LIMITS, **env_limits, **(limits or {})}
    findings = payload.get("findings") or []
    action_items = _truncate_list(payload.get("action_items") or [], lim["action_items"])

    packed = {
        "schema": SCHEMA,
        "pack_version": PACK_VERSION,
        "type": "prd",
        "kind": "review",
        "ticket": payload.get("ticket"),
        "slug": payload.get("slug"),
        "generated_at": payload.get("generated_at"),
        "status": payload.get("status"),
        "recommended_status": payload.get("recommended_status"),
        "source_path": source_path,
        "findings": _pack_findings(findings, lim["findings"], ["id", "severity", "title", "details"]),
        "action_items": action_items,
        "stats": {
            "findings": len(findings),
            "action_items": len(payload.get("action_items") or []),
        },
    }
    return packed


def _pack_call_graph_edges(entries: Iterable[Any], limit: int) -> List[Dict[str, Any]]:
    packed: List[Dict[str, Any]] = []
    for entry in _truncate_list(entries, limit):
        if not isinstance(entry, dict):
            continue
        packed.append(
            {
                "caller": entry.get("caller"),
                "callee": entry.get("callee"),
                "caller_file": entry.get("caller_file") or entry.get("file"),
                "caller_line": entry.get("caller_line") or entry.get("line"),
                "callee_file": entry.get("callee_file") or entry.get("file"),
                "callee_line": entry.get("callee_line") or entry.get("line"),
                "lang": entry.get("lang") or entry.get("language"),
                "type": entry.get("type"),
            }
        )
    return packed


def _call_graph_how_to_enable(warning: str) -> Optional[str]:
    lowered = (warning or "").lower()
    if "tree-sitter" in lowered or "tree_sitter" in lowered:
        return "Install tree_sitter_language_pack: python3 -m pip install tree_sitter_language_pack"
    if "graph-engine none" in lowered or "call graph disabled" in lowered:
        return "Run research with --graph-engine ts --call-graph (or enable graph in auto mode)."
    if "engine not available" in lowered:
        return "Ensure the call-graph engine is installed and configured for JVM sources."
    return None


def build_call_graph_pack(
    payload: Dict[str, Any],
    *,
    source_path: Optional[str] = None,
    limits: Optional[Dict[str, int]] = None,
    edges_path: Optional[Path] = None,
) -> Dict[str, Any]:
    lim = {**CALL_GRAPH_LIMITS, **(limits or {})}
    caller_counts: Dict[str, int] = {}
    file_counts: Dict[str, int] = {}
    edges_sample: List[Dict[str, Any]] = []
    edges_total = 0
    if edges_path is None:
        edges_rel = payload.get("call_graph_edges_path")
        if edges_rel:
            edges_path = Path(edges_rel)

    for edge in _iter_jsonl(edges_path) if edges_path and edges_path.exists() else []:
        edges_total += 1
        caller = str(edge.get("caller") or "").strip()
        if caller:
            caller_counts[caller] = caller_counts.get(caller, 0) + 1
        file_path = str(edge.get("caller_file") or edge.get("file") or "").strip()
        if file_path:
            file_counts[file_path] = file_counts.get(file_path, 0) + 1
        if len(edges_sample) < lim["edges"]:
            edges_sample.append(edge)

    entrypoints = [
        {"caller": caller, "count": count}
        for caller, count in sorted(caller_counts.items(), key=lambda item: item[1], reverse=True)
    ]
    hotspots = [
        {"file": path, "count": count}
        for path, count in sorted(file_counts.items(), key=lambda item: item[1], reverse=True)
    ]
    warning = (payload.get("call_graph_warning") or "").strip()
    if edges_total == 0 and not warning:
        warning = "call graph produced 0 edges (check filters/paths)."
    warning_lower = warning.lower()
    unavailable = edges_total == 0 or any(
        token in warning_lower
        for token in ("tree-sitter", "tree_sitter", "graph-engine none", "call graph disabled", "engine not available")
    )
    status = "unavailable" if unavailable else "ok"
    how_to_enable = _call_graph_how_to_enable(warning) if status != "ok" else None
    edges_stats = payload.get("call_graph_edges_stats") or {}
    packed = {
        "schema": SCHEMA,
        "pack_version": PACK_VERSION,
        "type": "call-graph",
        "kind": "pack",
        "ticket": payload.get("ticket"),
        "slug": payload.get("slug"),
        "slug_hint": payload.get("slug_hint"),
        "generated_at": payload.get("generated_at"),
        "source_path": source_path,
        "status": status,
        "warning": warning,
        "how_to_enable": how_to_enable,
        "links": {
            "edges": payload.get("call_graph_edges_path"),
        },
        "entrypoints": _truncate_list(entrypoints, lim["entrypoints"]),
        "hotspots": _truncate_list(hotspots, lim["hotspots"]),
        "edges": _pack_call_graph_edges(edges_sample, lim["edges"]),
        "stats": {
            "edges": len(edges_sample),
            "edges_total": edges_total,
            "edges_scanned": edges_stats.get("edges_scanned"),
            "edges_written": edges_stats.get("edges_written"),
            "edges_truncated": payload.get("call_graph_edges_truncated"),
        },
        "schema_version": payload.get("call_graph_edges_schema"),
    }
    return packed


def _iter_jsonl(path: Path) -> Iterable[Dict[str, Any]]:
    try:
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                raw = line.strip()
                if not raw:
                    continue
                try:
                    payload = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                if isinstance(payload, dict):
                    yield payload
    except OSError:
        return


def _load_jsonl(path: Path) -> List[Dict[str, Any]]:
    return list(_iter_jsonl(path)) if path.exists() else []


def build_ast_grep_pack(
    payload: Dict[str, Any],
    *,
    source_path: Optional[str] = None,
    limits: Optional[Dict[str, int]] = None,
) -> Dict[str, Any]:
    lim = {**AST_GREP_LIMITS, **(limits or {})}
    matches = payload.get("matches") or []
    stats_payload = payload.get("stats") or {}
    rules: Dict[str, List[Dict[str, Any]]] = {}
    schema_version = None
    for match in matches:
        if not isinstance(match, dict):
            continue
        rule_id = str(match.get("rule_id") or match.get("ruleId") or match.get("rule") or "").strip()
        if not rule_id:
            rule_id = "unknown"
        schema_version = schema_version or match.get("schema")
        rules.setdefault(rule_id, []).append(match)
    if schema_version is None:
        schema_version = stats_payload.get("schema")
    packed_rules = []
    for rule_id, rule_matches in sorted(rules.items()):
        examples: List[Dict[str, Any]] = []
        for entry in _truncate_list(rule_matches, lim["matches_per_rule"]):
            examples.append(
                {
                    "path": entry.get("path"),
                    "line": entry.get("line"),
                    "col": entry.get("col"),
                    "snippet": entry.get("snippet"),
                    "message": entry.get("message"),
                    "tags": entry.get("tags"),
                }
            )
        packed_rules.append(
            {
                "rule_id": rule_id,
                "count": len(rule_matches),
                "examples": examples,
            }
        )
    packed = {
        "schema": SCHEMA,
        "pack_version": PACK_VERSION,
        "type": "ast-grep",
        "kind": "pack",
        "ticket": payload.get("ticket"),
        "slug": payload.get("slug"),
        "slug_hint": payload.get("slug_hint"),
        "generated_at": payload.get("generated_at"),
        "source_path": source_path,
        "schema_version": schema_version,
        "rules": _truncate_list(packed_rules, lim["rules"]),
        "stats": {
            "matches_total": stats_payload.get("matches_total", len(matches)),
            "matches_written": stats_payload.get("matches_written", len(matches)),
            "rules_total": len(rules),
            "truncated": stats_payload.get("truncated", False),
        },
    }
    return packed


def write_ast_grep_pack(
    jsonl_path: Path,
    *,
    ticket: str,
    slug_hint: Optional[str],
    stats: Optional[Dict[str, Any]] = None,
    output: Optional[Path] = None,
    root: Optional[Path] = None,
    limits: Optional[Dict[str, int]] = None,
) -> Path:
    matches = _load_jsonl(jsonl_path)
    payload = {
        "ticket": ticket,
        "slug": slug_hint or ticket,
        "slug_hint": slug_hint,
        "generated_at": _utc_timestamp(),
        "matches": matches,
        "stats": stats or {},
    }
    source_path = None
    if root:
        try:
            source_path = jsonl_path.relative_to(root).as_posix()
        except ValueError:
            source_path = jsonl_path.as_posix()
    else:
        source_path = jsonl_path.as_posix()
    pack = build_ast_grep_pack(payload, source_path=source_path, limits=limits)
    ext = _pack_extension()
    default_path = jsonl_path.with_name(f"{ticket}-ast-grep{ext}")
    pack_path = (output or default_path).resolve()
    text = _serialize_pack(pack)
    errors = check_budget(
        text,
        max_chars=AST_GREP_BUDGET["max_chars"],
        max_lines=AST_GREP_BUDGET["max_lines"],
        label="ast-grep",
    )
    if errors:
        for error in errors:
            print(f"[pack-budget] {error}", file=sys.stderr)
        if _enforce_budget():
            raise ValueError("; ".join(errors))
    return _write_pack_text(text, pack_path)


def _pack_path_for(json_path: Path) -> Path:
    ext = _pack_extension()
    if json_path.name.endswith(ext):
        return json_path
    if json_path.suffix == ".json":
        return json_path.with_suffix(ext)
    return json_path.with_name(json_path.name + ext)


def _write_pack(payload: Dict[str, Any], pack_path: Path) -> Path:
    text = _serialize_pack(payload)
    return _write_pack_text(text, pack_path)


def write_research_context_pack(
    json_path: Path,
    *,
    output: Optional[Path] = None,
    root: Optional[Path] = None,
    limits: Optional[Dict[str, int]] = None,
) -> Path:
    path = json_path.resolve()
    payload = json.loads(path.read_text(encoding="utf-8"))
    source_path = None
    if root:
        try:
            source_path = path.relative_to(root).as_posix()
        except ValueError:
            source_path = path.as_posix()
    else:
        source_path = path.as_posix()

    pack = build_research_context_pack(payload, source_path=source_path, limits=limits)
    pack_path = (output or _pack_path_for(path)).resolve()

    text, trimmed, errors = _auto_trim_research_pack(
        pack,
        max_chars=RESEARCH_BUDGET["max_chars"],
        max_lines=RESEARCH_BUDGET["max_lines"],
    )
    if trimmed:
        print(f"[pack-trim] research pack trimmed: {', '.join(trimmed)}", file=sys.stderr)
    if errors:
        for error in errors:
            print(f"[pack-budget] {error}", file=sys.stderr)
        if _enforce_budget():
            raise ValueError("; ".join(errors))
    return _write_pack_text(text, pack_path)


def write_qa_pack(
    json_path: Path,
    *,
    output: Optional[Path] = None,
    root: Optional[Path] = None,
    limits: Optional[Dict[str, int]] = None,
) -> Path:
    path = json_path.resolve()
    payload = json.loads(path.read_text(encoding="utf-8"))
    source_path = None
    if root:
        try:
            source_path = path.relative_to(root).as_posix()
        except ValueError:
            source_path = path.as_posix()
    else:
        source_path = path.as_posix()

    env_limits = _env_limits().get("qa") or {}
    lim = {**QA_LIMITS, **env_limits, **(limits or {})}
    findings = payload.get("findings") or []
    tests_executed = payload.get("tests_executed") or []
    errors: List[str] = []
    errors.extend(_check_count_budget("qa", field="findings", actual=len(findings), limit=lim["findings"]))
    errors.extend(
        _check_count_budget("qa", field="tests_executed", actual=len(tests_executed), limit=lim["tests_executed"])
    )
    if errors:
        for error in errors:
            print(f"[pack-budget] {error}", file=sys.stderr)
        if _enforce_budget():
            raise ValueError("; ".join(errors))

    pack = build_qa_pack(payload, source_path=source_path, limits=lim)
    pack_path = (output or _pack_path_for(path)).resolve()
    return _write_pack(pack, pack_path)


def write_prd_pack(
    json_path: Path,
    *,
    output: Optional[Path] = None,
    root: Optional[Path] = None,
    limits: Optional[Dict[str, int]] = None,
) -> Path:
    path = json_path.resolve()
    payload = json.loads(path.read_text(encoding="utf-8"))
    source_path = None
    if root:
        try:
            source_path = path.relative_to(root).as_posix()
        except ValueError:
            source_path = path.as_posix()
    else:
        source_path = path.as_posix()

    env_limits = _env_limits().get("prd") or {}
    lim = {**PRD_LIMITS, **env_limits, **(limits or {})}
    findings = payload.get("findings") or []
    action_items = payload.get("action_items") or []
    errors: List[str] = []
    errors.extend(_check_count_budget("prd", field="findings", actual=len(findings), limit=lim["findings"]))
    errors.extend(_check_count_budget("prd", field="action_items", actual=len(action_items), limit=lim["action_items"]))
    if errors:
        for error in errors:
            print(f"[pack-budget] {error}", file=sys.stderr)
        if _enforce_budget():
            raise ValueError("; ".join(errors))

    pack = build_prd_pack(payload, source_path=source_path, limits=lim)
    pack_path = (output or _pack_path_for(path)).resolve()
    return _write_pack(pack, pack_path)


def write_call_graph_pack(
    json_path: Path,
    *,
    output: Optional[Path] = None,
    root: Optional[Path] = None,
    limits: Optional[Dict[str, int]] = None,
) -> Path:
    path = json_path.resolve()
    payload = json.loads(path.read_text(encoding="utf-8"))
    source_path = None
    if root:
        try:
            source_path = path.relative_to(root).as_posix()
        except ValueError:
            source_path = path.as_posix()
    else:
        source_path = path.as_posix()

    edges_path = None
    edges_rel = payload.get("call_graph_edges_path")
    if edges_rel:
        candidate = Path(edges_rel)
        if root and not candidate.is_absolute():
            candidate = (root / candidate).resolve()
        edges_path = candidate
    pack = build_call_graph_pack(payload, source_path=source_path, limits=limits, edges_path=edges_path)
    ext = _pack_extension()
    ticket = payload.get("ticket") or "unknown"
    default_path = path.with_name(f"{ticket}-call-graph{ext}")
    pack_path = (output or default_path).resolve()
    text = _serialize_pack(pack)
    errors = check_budget(
        text,
        max_chars=CALL_GRAPH_BUDGET["max_chars"],
        max_lines=CALL_GRAPH_BUDGET["max_lines"],
        label="call-graph",
    )
    if errors:
        for error in errors:
            print(f"[pack-budget] {error}", file=sys.stderr)
        if _enforce_budget():
            raise ValueError("; ".join(errors))
    return _write_pack_text(text, pack_path)


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Generate pack sidecar for research context JSON.")
    parser.add_argument("path", help="Path to aidd/reports/research/<ticket>-context.json")
    parser.add_argument(
        "--output",
        help="Optional output path (default: *.pack.yaml or *.pack.toon when AIDD_PACK_FORMAT=toon).",
    )
    args = parser.parse_args(argv)

    json_path = Path(args.path)
    output = Path(args.output) if args.output else None
    pack_path = write_research_context_pack(json_path, output=output)
    print(pack_path.as_posix())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
