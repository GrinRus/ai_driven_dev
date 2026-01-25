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

from tools import runtime
from tools.rlm_config import file_id_for_path, load_conventions, load_rlm_settings

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
}

RESEARCH_BUDGET = {
    "max_chars": 2000,
    "max_lines": 120,
}

QA_LIMITS: Dict[str, int] = {
    "findings": 20,
    "tests_executed": 10,
}

PRD_LIMITS: Dict[str, int] = {
    "findings": 20,
    "action_items": 10,
}

AST_GREP_LIMITS: Dict[str, int] = {
    "rules": 10,
    "matches_per_rule": 5,
    "snippet_chars": 200,
}

AST_GREP_BUDGET = {
    "max_chars": 1600,
    "max_lines": 80,
}

RLM_LIMITS: Dict[str, int] = {
    "entrypoints": 15,
    "hotspots": 15,
    "integration_points": 15,
    "test_hooks": 10,
    "recommended_reads": 15,
    "risks": 10,
    "links": 20,
    "evidence_snippet_chars": 160,
}

RLM_BUDGET = {
    "max_chars": 12000,
    "max_lines": 240,
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
    tmp_path = pack_path.with_suffix(pack_path.suffix + ".tmp")
    tmp_path.write_text(text, encoding="utf-8")
    tmp_path.replace(pack_path)
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


def _trim_list_field(payload: Dict[str, Any], key: str, *, min_len: int = 0) -> bool:
    items = payload.get(key)
    if not isinstance(items, list) or len(items) <= min_len:
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
    trimmed_steps: List[str] = []
    steps = [
        ("matches", lambda: _trim_columnar_rows(payload, "matches")),
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
        ("ast_grep_stats", lambda: _drop_field(payload, "ast_grep_stats")),
        ("ast_grep_path", lambda: _drop_field(payload, "ast_grep_path")),
        ("ast_grep_schema", lambda: _drop_field(payload, "ast_grep_schema")),
        ("drop.matches", lambda: _drop_columnar_if_empty(payload, "matches")),
        ("drop.reuse_candidates", lambda: _drop_columnar_if_empty(payload, "reuse_candidates")),
        ("drop.profile", lambda: _drop_field(payload, "profile")),
        ("drop.stats", lambda: _drop_field(payload, "stats")),
        ("drop.rlm_targets_path", lambda: _drop_field(payload, "rlm_targets_path")),
        ("drop.rlm_manifest_path", lambda: _drop_field(payload, "rlm_manifest_path")),
        ("drop.rlm_worklist_path", lambda: _drop_field(payload, "rlm_worklist_path")),
        ("drop.rlm_nodes_path", lambda: _drop_field(payload, "rlm_nodes_path")),
        ("drop.rlm_links_path", lambda: _drop_field(payload, "rlm_links_path")),
        ("drop.rlm_pack_path", lambda: _drop_field(payload, "rlm_pack_path")),
        ("drop.rlm_status", lambda: _drop_field(payload, "rlm_status")),
        ("drop.deep_mode", lambda: _drop_field(payload, "deep_mode")),
        ("drop.auto_mode", lambda: _drop_field(payload, "auto_mode")),
        ("drop.tags", lambda: _drop_field(payload, "tags")),
        ("drop.keywords_raw", lambda: _drop_field(payload, "keywords_raw")),
        ("drop.keywords", lambda: _drop_field(payload, "keywords")),
        ("drop.non_negotiables", lambda: _drop_field(payload, "non_negotiables")),
    ]

    for name, action in steps:
        while errors and action():
            trimmed_counts[name] = trimmed_counts.get(name, 0) + 1
            trimmed_steps.append(name)
            text = _serialize_pack(payload)
            errors = check_budget(text, max_chars=max_chars, max_lines=max_lines, label="research")
        if not errors:
            break

    if trimmed_counts:
        trim_stats = {"fields_trimmed": trimmed_counts}
        if trimmed_steps:
            trim_stats["steps"] = trimmed_steps
        payload["pack_trim_stats"] = trim_stats
        text = _serialize_pack(payload)
        errors = check_budget(text, max_chars=max_chars, max_lines=max_lines, label="research")
        if errors and "pack_trim_stats" in payload:
            payload.pop("pack_trim_stats", None)
            trimmed_counts["drop.pack_trim_stats"] = trimmed_counts.get("drop.pack_trim_stats", 0) + 1
            text = _serialize_pack(payload)
            errors = check_budget(text, max_chars=max_chars, max_lines=max_lines, label="research")

    trimmed = [f"{name}(-{count})" for name, count in trimmed_counts.items()]
    return text, trimmed, errors


def _max_snippet_len(payload: Dict[str, Any]) -> Optional[int]:
    links = payload.get("links")
    if not isinstance(links, list) or not links:
        return None
    lengths = [len(str(link.get("evidence_snippet") or "")) for link in links if isinstance(link, dict)]
    return max(lengths, default=0)


def _trim_evidence_snippets(payload: Dict[str, Any], max_chars: int) -> bool:
    links = payload.get("links")
    if not isinstance(links, list) or not links:
        return False
    trimmed = False
    for link in links:
        if not isinstance(link, dict):
            continue
        snippet = link.get("evidence_snippet")
        if not isinstance(snippet, str):
            continue
        if len(snippet) <= max_chars:
            continue
        link["evidence_snippet"] = snippet[:max_chars].rstrip()
        trimmed = True
    return trimmed


def _auto_trim_rlm_pack(
    payload: Dict[str, Any],
    max_chars: int,
    max_lines: int,
    *,
    enforce: bool = False,
    trim_priority: Optional[Iterable[str]] = None,
) -> tuple[str, List[str], List[str], Dict[str, Any]]:
    text = _serialize_pack(payload)
    errors = check_budget(text, max_chars=max_chars, max_lines=max_lines, label="rlm")
    if not errors:
        return text, [], errors, {}

    trimmed_counts: Dict[str, int] = {}
    trimmed_steps: List[str] = []
    list_fields = (
        "links",
        "recommended_reads",
        "hotspots",
        "integration_points",
        "entrypoints",
        "test_hooks",
        "risks",
    )
    if trim_priority:
        ordered: List[str] = []
        for raw in trim_priority:
            key = str(raw or "").strip()
            if not key or key not in list_fields or key in ordered:
                continue
            ordered.append(key)
        for key in list_fields:
            if key not in ordered:
                ordered.append(key)
        list_fields = tuple(ordered)
    snippet_chars: Optional[int] = None
    snippet_floor = 0 if enforce else 40

    def _trim_pass(min_len: int, snippet_floor_limit: int) -> None:
        nonlocal text, errors, snippet_chars
        while errors:
            progress = False
            for key in list_fields:
                if _trim_list_field(payload, key, min_len=min_len):
                    trimmed_counts[key] = trimmed_counts.get(key, 0) + 1
                    trimmed_steps.append(key)
                    progress = True
                    break
            if progress:
                text = _serialize_pack(payload)
                errors = check_budget(text, max_chars=max_chars, max_lines=max_lines, label="rlm")
                continue

            current_snippet = _max_snippet_len(payload)
            if current_snippet is not None and current_snippet > snippet_floor_limit:
                next_limit = max(snippet_floor_limit, current_snippet - 20)
                if next_limit < current_snippet and _trim_evidence_snippets(payload, next_limit):
                    snippet_chars = next_limit
                    trimmed_steps.append("evidence_snippet_chars")
                    progress = True
                    text = _serialize_pack(payload)
                    errors = check_budget(text, max_chars=max_chars, max_lines=max_lines, label="rlm")
                    continue

            if not progress:
                break

    _trim_pass(0 if enforce else 1, snippet_floor)
    if errors and not enforce:
        _trim_pass(0, 0)

    trim_stats: Dict[str, Any] = {}
    if trimmed_counts or snippet_chars is not None:
        trim_stats = {"enforce": enforce}
        if trimmed_counts:
            trim_stats["fields_trimmed"] = trimmed_counts
        if snippet_chars is not None:
            trim_stats["evidence_snippet_chars"] = snippet_chars
        if not enforce:
            trim_stats["steps"] = trimmed_steps
        payload["pack_trim_stats"] = trim_stats
        text = _serialize_pack(payload)
        errors = check_budget(text, max_chars=max_chars, max_lines=max_lines, label="rlm")

    if errors and not enforce and "pack_trim_stats" in payload:
        payload["pack_trim_stats"] = {"enforce": False}
        trimmed_counts["drop.pack_trim_stats_details"] = (
            trimmed_counts.get("drop.pack_trim_stats_details", 0) + 1
        )
        text = _serialize_pack(payload)
        errors = check_budget(text, max_chars=max_chars, max_lines=max_lines, label="rlm")
        if errors:
            payload.pop("pack_trim_stats", None)
            trimmed_counts["drop.pack_trim_stats"] = trimmed_counts.get("drop.pack_trim_stats", 0) + 1
            text = _serialize_pack(payload)
            errors = check_budget(text, max_chars=max_chars, max_lines=max_lines, label="rlm")

    if errors and enforce:
        drop_fields = (
            "warnings",
            "stats",
            "entrypoints",
            "hotspots",
            "integration_points",
            "test_hooks",
            "risks",
            "recommended_reads",
            "links",
            "slug_hint",
            "source_path",
        )
        for key in drop_fields:
            if key not in payload:
                continue
            payload.pop(key, None)
            drop_key = f"drop.{key}"
            trimmed_counts[drop_key] = trimmed_counts.get(drop_key, 0) + 1
            trimmed_steps.append(drop_key)
            trim_stats = {"enforce": enforce}
            if trimmed_counts:
                trim_stats["fields_trimmed"] = trimmed_counts
            if snippet_chars is not None:
                trim_stats["evidence_snippet_chars"] = snippet_chars
            payload["pack_trim_stats"] = trim_stats
            text = _serialize_pack(payload)
            errors = check_budget(text, max_chars=max_chars, max_lines=max_lines, label="rlm")
            if not errors:
                break
        if errors and "pack_trim_stats" in payload:
            payload["pack_trim_stats"] = {"enforce": enforce}
            trimmed_counts["drop.pack_trim_stats_details"] = (
                trimmed_counts.get("drop.pack_trim_stats_details", 0) + 1
            )
            text = _serialize_pack(payload)
            errors = check_budget(text, max_chars=max_chars, max_lines=max_lines, label="rlm")
    trimmed = [f"{name}(-{count})" for name, count in trimmed_counts.items()]
    return text, trimmed, errors, trim_stats


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


def _extract_evidence_snippet(
    root: Optional[Path],
    evidence_ref: Dict[str, Any],
    *,
    max_chars: int,
) -> str:
    if not root or not evidence_ref:
        return ""
    raw_path = evidence_ref.get("path")
    if not raw_path:
        return ""
    path = Path(str(raw_path))
    abs_path = path if path.is_absolute() else (root / path)
    if not abs_path.exists() and root.name == "aidd":
        alt_path = root.parent / path
        if alt_path.exists():
            abs_path = alt_path
    if not abs_path.exists():
        return ""
    try:
        lines = abs_path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return ""
    try:
        line_start = int(evidence_ref.get("line_start") or 0)
        line_end = int(evidence_ref.get("line_end") or line_start)
    except (TypeError, ValueError):
        return ""
    if line_start <= 0 or line_end <= 0:
        return ""
    start_idx = max(0, line_start - 1)
    end_idx = max(start_idx, line_end - 1)
    snippet = "\n".join(lines[start_idx : end_idx + 1]).strip()
    normalized = " ".join(snippet.split())
    return _truncate_text(normalized, max_chars)


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


def _find_pack_variant(root: Path, name: str) -> Optional[Path]:
    base = root / "reports" / "research"
    for suffix in (".pack.yaml", ".pack.toon"):
        candidate = base / f"{name}{suffix}"
        if candidate.exists():
            return candidate
    return None


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


def _resolve_reports_root(root: Optional[Path], path: Path) -> Optional[Path]:
    if root:
        return root
    for parent in (path, *path.parents):
        if (parent / "config" / "conventions.json").exists():
            return parent
    return None


def _load_research_pack_budget(root: Optional[Path], path: Path) -> Dict[str, int]:
    resolved = _resolve_reports_root(root, path)
    if not resolved:
        return {}
    cfg = load_conventions(resolved)
    reports_cfg = cfg.get("reports") if isinstance(cfg.get("reports"), dict) else {}
    budget = reports_cfg.get("research_pack_budget") if isinstance(reports_cfg.get("research_pack_budget"), dict) else {}
    parsed: Dict[str, int] = {}
    for key in ("max_chars", "max_lines"):
        if key not in budget:
            continue
        try:
            value = int(budget[key])
        except (TypeError, ValueError):
            continue
        if value > 0:
            parsed[key] = value
    return parsed


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
        "ast_grep_path": payload.get("ast_grep_path"),
        "ast_grep_schema": payload.get("ast_grep_schema"),
        "ast_grep_stats": payload.get("ast_grep_stats"),
        "rlm_targets_path": payload.get("rlm_targets_path"),
        "rlm_manifest_path": payload.get("rlm_manifest_path"),
        "rlm_worklist_path": payload.get("rlm_worklist_path"),
        "rlm_nodes_path": payload.get("rlm_nodes_path"),
        "rlm_links_path": payload.get("rlm_links_path"),
        "rlm_pack_path": payload.get("rlm_pack_path"),
        "rlm_status": payload.get("rlm_status"),
        "deep_mode": payload.get("deep_mode"),
        "auto_mode": payload.get("auto_mode"),
        "stats": {
            "matches": len(payload.get("matches") or []),
            "reuse_candidates": len(payload.get("reuse_candidates") or []),
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
    snippet_chars = int(lim.get("snippet_chars", 0) or 0)
    for rule_id, rule_matches in sorted(rules.items()):
        examples: List[Dict[str, Any]] = []
        for entry in _truncate_list(rule_matches, lim["matches_per_rule"]):
            snippet = entry.get("snippet")
            if isinstance(snippet, str) and snippet_chars > 0:
                snippet = snippet[:snippet_chars]
            examples.append(
                {
                    "path": entry.get("path"),
                    "line": entry.get("line"),
                    "col": entry.get("col"),
                    "snippet": snippet,
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


def _load_jsonl(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    items: List[Dict[str, Any]] = []
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
                    items.append(payload)
    except OSError:
        return []
    return items


def _load_rlm_links_stats(root: Path, ticket: str) -> Optional[Dict[str, Any]]:
    path = root / "reports" / "research" / f"{ticket}-rlm.links.stats.json"
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return payload if isinstance(payload, dict) else None


def _rlm_link_warnings(stats: Dict[str, Any]) -> List[str]:
    warnings: List[str] = []
    if stats.get("links_truncated"):
        warnings.append("rlm links truncated: max_links reached")
    if int(stats.get("target_files_trimmed") or 0) > 0:
        warnings.append("rlm link targets trimmed: max_files reached")
    if int(stats.get("symbols_truncated") or 0) > 0:
        warnings.append("rlm link symbols truncated: max_symbols_per_file reached")
    if int(stats.get("candidate_truncated") or 0) > 0:
        warnings.append("rlm link candidates truncated: max_definition_hits_per_symbol reached")
    if int(stats.get("rg_timeouts") or 0) > 0:
        warnings.append("rlm rg timeout during link search")
    if int(stats.get("rg_errors") or 0) > 0:
        warnings.append("rlm rg errors during link search")
    if "target_files_total" in stats and int(stats.get("target_files_total") or 0) == 0:
        warnings.append("rlm link targets empty")
    return warnings


def _pack_rlm_nodes(nodes: Iterable[Dict[str, Any]], limit: int) -> List[Dict[str, Any]]:
    packed: List[Dict[str, Any]] = []
    for node in _truncate_list(nodes, limit):
        if not isinstance(node, dict):
            continue
        packed.append(
            {
                "file_id": node.get("file_id") or node.get("id"),
                "path": node.get("path"),
                "summary": node.get("summary"),
                "framework_roles": node.get("framework_roles") or [],
                "test_hooks": node.get("test_hooks") or [],
                "risks": node.get("risks") or [],
            }
        )
    return packed


def _pack_rlm_links(
    links: Iterable[Dict[str, Any]],
    *,
    limit: int,
    root: Optional[Path],
    snippet_chars: int,
) -> List[Dict[str, Any]]:
    packed: List[Dict[str, Any]] = []
    for link in _truncate_list(links, limit):
        if not isinstance(link, dict):
            continue
        evidence_ref = link.get("evidence_ref") or {}
        snippet = _extract_evidence_snippet(root, evidence_ref, max_chars=snippet_chars)
        packed.append(
            {
                "link_id": link.get("link_id"),
                "src_file_id": link.get("src_file_id"),
                "dst_file_id": link.get("dst_file_id"),
                "type": link.get("type"),
                "evidence_ref": evidence_ref,
                "evidence_snippet": snippet,
            }
        )
    return packed


def _load_rlm_worklist_summary(
    root: Optional[Path],
    ticket: Optional[str],
    *,
    context: Optional[Dict[str, Any]] = None,
) -> tuple[Optional[str], Optional[int], Optional[Path]]:
    if not root or not ticket:
        return None, None, None
    worklist_path = None
    if context:
        raw = context.get("rlm_worklist_path")
        if isinstance(raw, str) and raw.strip():
            worklist_path = runtime.resolve_path_for_target(Path(raw), root)
    if worklist_path is None and ticket:
        worklist_path = _find_pack_variant(root, f"{ticket}-rlm.worklist") or (
            root / "reports" / "research" / f"{ticket}-rlm.worklist.pack.yaml"
        )
    if not worklist_path or not worklist_path.exists():
        return None, None, worklist_path
    try:
        payload = json.loads(worklist_path.read_text(encoding="utf-8"))
    except Exception:
        return None, None, worklist_path
    if not isinstance(payload, dict):
        return None, None, worklist_path
    worklist_status = str(payload.get("status") or "").strip().lower() or None
    entries = payload.get("entries")
    worklist_entries = len(entries) if isinstance(entries, list) else None
    return worklist_status, worklist_entries, worklist_path


def build_rlm_pack(
    nodes: List[Dict[str, Any]],
    links: List[Dict[str, Any]],
    *,
    ticket: Optional[str],
    slug_hint: Optional[str] = None,
    source_path: Optional[str] = None,
    limits: Optional[Dict[str, int]] = None,
    root: Optional[Path] = None,
) -> Dict[str, Any]:
    env_limits = _env_limits().get("rlm") or {}
    lim = {**RLM_LIMITS, **env_limits, **(limits or {})}

    file_nodes = [node for node in nodes if node.get("node_kind") == "file"]
    link_counts: Dict[str, int] = {}
    for link in links:
        if link.get("unverified"):
            continue
        src = str(link.get("src_file_id") or "")
        dst = str(link.get("dst_file_id") or "")
        if src:
            link_counts[src] = link_counts.get(src, 0) + 1
        if dst:
            link_counts[dst] = link_counts.get(dst, 0) + 1

    keyword_hits: set[str] = set()
    if root and ticket:
        targets_path = root / "reports" / "research" / f"{ticket}-rlm-targets.json"
        if targets_path.exists():
            try:
                targets_payload = json.loads(targets_path.read_text(encoding="utf-8"))
            except Exception:
                targets_payload = {}
            for raw_path in targets_payload.get("keyword_hits") or []:
                path_text = str(raw_path).strip()
                if not path_text:
                    continue
                keyword_hits.add(file_id_for_path(Path(path_text)))

    def by_link_count(node: Dict[str, Any]) -> tuple:
        file_id = str(node.get("file_id") or node.get("id") or "")
        boost = 1 if file_id and file_id in keyword_hits else 0
        return (-(link_counts.get(file_id, 0) + boost), str(node.get("path") or ""))

    entry_roles = {"web", "controller", "job", "config", "infra"}
    exclude_roles = {"model", "dto"}

    def _roles(node: Dict[str, Any]) -> set[str]:
        return {str(role) for role in (node.get("framework_roles") or []) if str(role)}

    entrypoints = [
        node for node in file_nodes if (_roles(node) & entry_roles) and not (_roles(node) & exclude_roles)
    ]
    entrypoints = sorted(entrypoints, key=by_link_count)

    hotspots = sorted(file_nodes, key=by_link_count)

    integration_roles = {"service", "repo", "config", "infra"}
    integration_points = [
        node
        for node in file_nodes
        if (_roles(node) & integration_roles) and not (_roles(node) & exclude_roles)
    ]
    integration_points = sorted(integration_points, key=by_link_count)

    test_hooks = [node for node in file_nodes if node.get("test_hooks")]
    test_hooks = sorted(test_hooks, key=by_link_count)

    risks = [node for node in file_nodes if node.get("risks")]
    risks = sorted(risks, key=by_link_count)

    recommended = []
    seen: set[str] = set()
    for group in (entrypoints, hotspots, integration_points):
        for node in group:
            file_id = str(node.get("file_id") or node.get("id") or "")
            if not file_id or file_id in seen:
                continue
            seen.add(file_id)
            recommended.append(node)
            if len(recommended) >= lim["recommended_reads"]:
                break
        if len(recommended) >= lim["recommended_reads"]:
            break

    links_total = len(links)
    verified_links = [link for link in links if not link.get("unverified")]
    links_unverified = links_total - len(verified_links)
    links_sample = _pack_rlm_links(
        verified_links,
        limit=lim["links"],
        root=root,
        snippet_chars=lim["evidence_snippet_chars"],
    )
    link_stats = _load_rlm_links_stats(root, ticket) if root and ticket else None
    link_warnings = _rlm_link_warnings(link_stats) if link_stats else []
    fallback_warn_ratio: Optional[float] = None
    unverified_warn_ratio: Optional[float] = None
    if root:
        settings = load_rlm_settings(root)
        raw_ratio = settings.get("link_fallback_warn_ratio")
        raw_unverified_ratio = settings.get("link_unverified_warn_ratio")
        try:
            ratio_value = float(raw_ratio)
        except (TypeError, ValueError):
            ratio_value = None
        try:
            unverified_value = float(raw_unverified_ratio)
        except (TypeError, ValueError):
            unverified_value = None
        if ratio_value is not None and 0 < ratio_value <= 1:
            fallback_warn_ratio = ratio_value
        if unverified_value is not None and 0 < unverified_value <= 1:
            unverified_warn_ratio = unverified_value
    if link_stats and fallback_warn_ratio and file_nodes:
        fallback_nodes = int(link_stats.get("fallback_nodes") or 0)
        total_nodes = len(file_nodes)
        if total_nodes:
            ratio = fallback_nodes / total_nodes
            if ratio >= fallback_warn_ratio:
                link_warnings.append(
                    "rlm link fallback ratio high: "
                    f"fallback_nodes={fallback_nodes} total_nodes={total_nodes} ratio={ratio:.2f}"
                )
    if unverified_warn_ratio and links_total:
        ratio = links_unverified / links_total
        if ratio >= unverified_warn_ratio:
            link_warnings.append(
                "rlm unverified links ratio high: "
                f"unverified={links_unverified} total={links_total} ratio={ratio:.2f}"
            )

    worklist_status, worklist_entries, _ = _load_rlm_worklist_summary(root, ticket)
    if worklist_status == "ready" and worklist_entries == 0:
        pack_status = "ready"
    elif worklist_status:
        pack_status = "pending"
    else:
        pack_status = "ready"

    packed = {
        "schema": SCHEMA,
        "pack_version": PACK_VERSION,
        "type": "rlm",
        "kind": "pack",
        "ticket": ticket,
        "slug": slug_hint or ticket,
        "slug_hint": slug_hint,
        "generated_at": _utc_timestamp(),
        "status": pack_status,
        "source_path": source_path,
        "stats": {
            "nodes": len(file_nodes),
            "nodes_total": len(file_nodes),
        "links": links_total,
        "links_unverified": links_unverified,
            "links_included": len(links_sample),
        },
        "entrypoints": _pack_rlm_nodes(entrypoints, lim["entrypoints"]),
        "hotspots": _pack_rlm_nodes(hotspots, lim["hotspots"]),
        "integration_points": _pack_rlm_nodes(integration_points, lim["integration_points"]),
        "test_hooks": _pack_rlm_nodes(test_hooks, lim["test_hooks"]),
        "risks": _pack_rlm_nodes(risks, lim["risks"]),
        "recommended_reads": _pack_rlm_nodes(recommended, lim["recommended_reads"]),
        "links": links_sample,
    }
    if link_stats:
        packed["stats"]["link_search"] = {
            "links_truncated": bool(link_stats.get("links_truncated")),
            "symbols_total": int(link_stats.get("symbols_total") or 0),
            "symbols_scanned": int(link_stats.get("symbols_scanned") or 0),
            "symbols_truncated": int(link_stats.get("symbols_truncated") or 0),
            "candidate_truncated": int(link_stats.get("candidate_truncated") or 0),
            "rg_calls": int(link_stats.get("rg_calls") or 0),
            "rg_timeouts": int(link_stats.get("rg_timeouts") or 0),
            "rg_errors": int(link_stats.get("rg_errors") or 0),
        }
    warnings = list(link_warnings)
    if worklist_status is not None:
        packed["stats"]["worklist_status"] = worklist_status
    if worklist_entries is not None:
        packed["stats"]["worklist_entries"] = worklist_entries
        if worklist_entries > 0:
            warnings.append(f"rlm worklist pending: entries={worklist_entries}")
            nodes_total = len(file_nodes)
            threshold = max(1, int(worklist_entries * 0.5))
            if nodes_total < threshold:
                warnings.append(
                    f"rlm pack partial: nodes_total={nodes_total} worklist_entries={worklist_entries}"
                )
    if warnings:
        packed["warnings"] = warnings
    return packed


def write_rlm_pack(
    nodes_path: Path,
    links_path: Path,
    *,
    output: Optional[Path] = None,
    ticket: Optional[str] = None,
    slug_hint: Optional[str] = None,
    limits: Optional[Dict[str, int]] = None,
    root: Optional[Path] = None,
) -> Path:
    target = root or nodes_path.parents[2]
    nodes = _load_jsonl(nodes_path)
    links = _load_jsonl(links_path)
    rlm_limits: Dict[str, int] = {}
    rlm_settings = load_rlm_settings(target)
    pack_budget_cfg = rlm_settings.get("pack_budget") if isinstance(rlm_settings.get("pack_budget"), dict) else {}
    enforce_budget = bool(pack_budget_cfg.get("enforce"))
    enforce_flag = enforce_budget or _enforce_budget()
    trim_priority = None
    raw_priority = pack_budget_cfg.get("trim_priority")
    if isinstance(raw_priority, list):
        trim_priority = [str(item).strip() for item in raw_priority if str(item).strip()]
    if isinstance(rlm_settings.get("pack_budget"), dict):
        for key, value in (rlm_settings.get("pack_budget") or {}).items():
            if key == "enforce":
                continue
            try:
                rlm_limits[str(key)] = int(value)
            except (TypeError, ValueError):
                continue
    if limits:
        for key, value in limits.items():
            try:
                rlm_limits[str(key)] = int(value)
            except (TypeError, ValueError):
                continue
    max_chars = int(rlm_limits.get("max_chars") or RLM_BUDGET["max_chars"])
    max_lines = int(rlm_limits.get("max_lines") or RLM_BUDGET["max_lines"])
    if not ticket:
        name = nodes_path.name
        if "-rlm.nodes.jsonl" in name:
            ticket = name.replace("-rlm.nodes.jsonl", "")
    pack = build_rlm_pack(
        nodes,
        links,
        ticket=ticket,
        slug_hint=slug_hint,
        source_path=runtime.rel_path(nodes_path, target),
        limits=rlm_limits or limits,
        root=target,
    )
    ext = _pack_extension()
    default_name = nodes_path.name.replace("-rlm.nodes.jsonl", f"-rlm{ext}")
    default_path = nodes_path.with_name(default_name)
    pack_path = (output or default_path).resolve()
    text, trimmed, errors, _trim_stats = _auto_trim_rlm_pack(
        pack,
        max_chars=max_chars,
        max_lines=max_lines,
        enforce=enforce_flag,
        trim_priority=trim_priority,
    )
    if trimmed:
        print(f"[pack-trim] rlm pack trimmed: {', '.join(trimmed)}", file=sys.stderr)
    for error in errors:
        print(f"[pack-budget] {error}", file=sys.stderr)
    if errors and enforce_flag:
        raise ValueError("; ".join(errors))
    return _write_pack_text(text, pack_path)


def _update_rlm_context(
    context_path: Path,
    *,
    root: Path,
    nodes_path: Path,
    links_path: Path,
    pack_path: Path,
) -> Path:
    payload = json.loads(context_path.read_text(encoding="utf-8"))
    ticket = str(payload.get("ticket") or "").strip()
    worklist_status, worklist_entries, worklist_path = _load_rlm_worklist_summary(
        root,
        ticket,
        context=payload,
    )
    if worklist_path and worklist_path.exists():
        payload["rlm_worklist_path"] = runtime.rel_path(worklist_path, root)
    nodes_ready = nodes_path.exists() and nodes_path.stat().st_size > 0
    links_ready = links_path.exists() and links_path.stat().st_size > 0
    if worklist_status is not None:
        if worklist_status == "ready" and worklist_entries == 0 and nodes_ready and links_ready:
            rlm_status = "ready"
        else:
            rlm_status = "pending"
    else:
        rlm_status = "ready" if nodes_ready and links_ready else "pending"
    payload["rlm_status"] = rlm_status
    payload["rlm_nodes_path"] = runtime.rel_path(nodes_path, root)
    payload["rlm_links_path"] = runtime.rel_path(links_path, root)
    payload["rlm_pack_path"] = runtime.rel_path(pack_path, root)
    tmp_path = context_path.with_suffix(context_path.suffix + ".tmp")
    tmp_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp_path.replace(context_path)
    return context_path


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
    ext = _pack_extension()
    default_path = jsonl_path.with_name(f"{ticket}-ast-grep{ext}")
    pack_path = (output or default_path).resolve()

    base_limits = {**AST_GREP_LIMITS, **(limits or {})}
    current_limits = dict(base_limits)
    trimmed = False
    errors: List[str] = []
    text = ""

    def _shrink_limits(lim: Dict[str, int]) -> bool:
        for key in ("matches_per_rule", "rules"):
            value = int(lim.get(key, 0) or 0)
            if value > 1:
                lim[key] = value - 1
                return True
        snippet_chars = int(lim.get("snippet_chars", 0) or 0)
        if snippet_chars > 40:
            lim["snippet_chars"] = max(40, snippet_chars - 20)
            return True
        return False

    while True:
        pack = build_ast_grep_pack(payload, source_path=source_path, limits=current_limits)
        text = _serialize_pack(pack)
        errors = check_budget(
            text,
            max_chars=AST_GREP_BUDGET["max_chars"],
            max_lines=AST_GREP_BUDGET["max_lines"],
            label="ast-grep",
        )
        if not errors:
            break
        if not _shrink_limits(current_limits):
            break
        trimmed = True

    if errors:
        for error in errors:
            print(f"[pack-budget] {error}", file=sys.stderr)
        if _enforce_budget():
            raise ValueError("; ".join(errors))
    elif trimmed:
        print("[pack-trim] ast-grep pack trimmed to fit budget.", file=sys.stderr)

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

    budget_override = _load_research_pack_budget(root, path)
    max_chars = int(budget_override.get("max_chars") or RESEARCH_BUDGET["max_chars"])
    max_lines = int(budget_override.get("max_lines") or RESEARCH_BUDGET["max_lines"])
    text, trimmed, errors = _auto_trim_research_pack(
        pack,
        max_chars=max_chars,
        max_lines=max_lines,
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


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Generate pack sidecar for research context JSON.")
    parser.add_argument("path", nargs="?", help="Path to aidd/reports/research/<ticket>-context.json")
    parser.add_argument(
        "--output",
        help="Optional output path (default: *.pack.yaml or *.pack.toon when AIDD_PACK_FORMAT=toon).",
    )
    parser.add_argument("--rlm-nodes", help="Path to <ticket>-rlm.nodes.jsonl to build RLM pack.")
    parser.add_argument("--rlm-links", help="Path to <ticket>-rlm.links.jsonl to build RLM pack.")
    parser.add_argument("--ticket", help="Ticket identifier to label RLM pack (optional).")
    parser.add_argument("--slug-hint", help="Slug hint for RLM pack (optional).")
    parser.add_argument(
        "--update-context",
        action="store_true",
        help="Update research context.json and regenerate context pack when building RLM pack.",
    )
    args = parser.parse_args(argv)

    if args.rlm_nodes or args.rlm_links:
        if not args.rlm_nodes or not args.rlm_links:
            raise SystemExit("--rlm-nodes and --rlm-links must be provided together.")
        nodes_path = Path(args.rlm_nodes)
        links_path = Path(args.rlm_links)
        output = Path(args.output) if args.output else None
        ticket = args.ticket
        if not ticket and "-rlm.nodes.jsonl" in nodes_path.name:
            ticket = nodes_path.name.replace("-rlm.nodes.jsonl", "")
        pack_path = write_rlm_pack(
            nodes_path,
            links_path,
            output=output,
            ticket=ticket,
            slug_hint=args.slug_hint,
        )
        if args.update_context:
            root = nodes_path.resolve().parents[2]
            if not ticket:
                raise SystemExit("ticket is required to update context.json.")
            context_path = root / "reports" / "research" / f"{ticket}-context.json"
            if not context_path.exists():
                raise SystemExit(f"research context not found: {context_path}")
            _update_rlm_context(
                context_path,
                root=root,
                nodes_path=nodes_path,
                links_path=links_path,
                pack_path=pack_path,
            )
            write_research_context_pack(context_path, root=root)
            rel_context = runtime.rel_path(context_path, root)
            try:
                payload = json.loads(context_path.read_text(encoding="utf-8"))
            except Exception:
                payload = {}
            status = str(payload.get("rlm_status") or "ready").strip().lower()
            print(f"[aidd] updated rlm_status={status} in {rel_context}.", file=sys.stderr)
        print(pack_path.as_posix())
        return 0

    if not args.path:
        raise SystemExit("context.json path is required unless using --rlm-nodes/--rlm-links.")
    json_path = Path(args.path)
    output = Path(args.output) if args.output else None
    pack_path = write_research_context_pack(json_path, output=output)
    print(pack_path.as_posix())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
