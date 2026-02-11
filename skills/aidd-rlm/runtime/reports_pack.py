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

from aidd_runtime import runtime
from aidd_runtime.rlm_config import file_id_for_path, load_rlm_settings

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
    "rlm_warnings": 10,
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
    from aidd_runtime import reports_pack_assemble as _assemble

    return _assemble.truncate_list(items, limit)


def _truncate_text(text: str, limit: int) -> str:
    from aidd_runtime import reports_pack_assemble as _assemble

    return _assemble.truncate_text(text, limit)


def _extract_evidence_snippet(
    root: Optional[Path],
    evidence_ref: Dict[str, Any],
    *,
    max_chars: int,
) -> str:
    from aidd_runtime import reports_pack_assemble as _assemble

    return _assemble.extract_evidence_snippet(root, evidence_ref, max_chars=max_chars)


def _stable_id(*parts: Any) -> str:
    from aidd_runtime import reports_pack_assemble as _assemble

    return _assemble.stable_id(*parts)


def _columnar(cols: List[str], rows: List[List[Any]]) -> Dict[str, Any]:
    from aidd_runtime import reports_pack_assemble as _assemble

    return _assemble.columnar(cols, rows)


def _pack_paths(entries: Iterable[Any], limit: int, sample_limit: int) -> List[Dict[str, Any]]:
    from aidd_runtime import reports_pack_assemble as _assemble

    return _assemble.pack_paths(entries, limit, sample_limit)


def _pack_matches(entries: Iterable[Any], limit: int, snippet_limit: int) -> Dict[str, Any]:
    from aidd_runtime import reports_pack_assemble as _assemble

    return _assemble.pack_matches(entries, limit, snippet_limit)


def _pack_reuse(entries: Iterable[Any], limit: int) -> Dict[str, Any]:
    from aidd_runtime import reports_pack_assemble as _assemble

    return _assemble.pack_reuse(entries, limit)


def _pack_findings(entries: Iterable[Any], limit: int, cols: List[str]) -> Dict[str, Any]:
    from aidd_runtime import reports_pack_assemble as _assemble

    return _assemble.pack_findings(entries, limit, cols)


def _pack_extension() -> str:
    return ".pack.json"


def _find_pack_variant(root: Path, name: str) -> Optional[Path]:
    base = root / "reports" / "research"
    candidate = base / f"{name}.pack.json"
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


def _pack_tests_executed(entries: Iterable[Any], limit: int) -> Dict[str, Any]:
    from aidd_runtime import reports_pack_assemble as _assemble

    return _assemble.pack_tests_executed(entries, limit)


def build_research_pack(
    payload: Dict[str, Any],
    *,
    source_path: Optional[str] = None,
    limits: Optional[Dict[str, int]] = None,
) -> Dict[str, Any]:
    from aidd_runtime import reports_pack_assemble as _assemble

    return _assemble.build_research_pack(payload, source_path=source_path, limits=limits)


def build_research_context_pack(
    payload: Dict[str, Any],
    *,
    source_path: Optional[str] = None,
    limits: Optional[Dict[str, int]] = None,
) -> Dict[str, Any]:
    print(
        "[aidd] WARN: build_research_context_pack is deprecated; use build_research_pack.",
        file=sys.stderr,
    )
    return build_research_pack(payload, source_path=source_path, limits=limits)


def build_qa_pack(
    payload: Dict[str, Any],
    *,
    source_path: Optional[str] = None,
    limits: Optional[Dict[str, int]] = None,
) -> Dict[str, Any]:
    from aidd_runtime import reports_pack_assemble as _assemble

    return _assemble.build_qa_pack(payload, source_path=source_path, limits=limits)


def build_prd_pack(
    payload: Dict[str, Any],
    *,
    source_path: Optional[str] = None,
    limits: Optional[Dict[str, int]] = None,
) -> Dict[str, Any]:
    from aidd_runtime import reports_pack_assemble as _assemble

    return _assemble.build_prd_pack(payload, source_path=source_path, limits=limits)


def _load_rlm_links_stats(root: Path, ticket: str) -> Optional[Dict[str, Any]]:
    from aidd_runtime import reports_pack_assemble as _assemble

    return _assemble.load_rlm_links_stats(root, ticket)


def _rlm_link_warnings(stats: Dict[str, Any]) -> List[str]:
    from aidd_runtime import reports_pack_assemble as _assemble

    return _assemble.rlm_link_warnings(stats)


def _pack_rlm_nodes(nodes: Iterable[Dict[str, Any]], limit: int) -> List[Dict[str, Any]]:
    from aidd_runtime import reports_pack_assemble as _assemble

    return _assemble.pack_rlm_nodes(nodes, limit)


def _pack_rlm_links(
    links: Iterable[Dict[str, Any]],
    *,
    limit: int,
    root: Optional[Path],
    snippet_chars: int,
) -> List[Dict[str, Any]]:
    from aidd_runtime import reports_pack_assemble as _assemble

    return _assemble.pack_rlm_links(
        links,
        limit=limit,
        root=root,
        snippet_chars=snippet_chars,
    )


def _load_rlm_worklist_summary(
    root: Optional[Path],
    ticket: Optional[str],
    *,
    context: Optional[Dict[str, Any]] = None,
) -> tuple[Optional[str], Optional[int], Optional[Path]]:
    from aidd_runtime import reports_pack_assemble as _assemble

    return _assemble.load_rlm_worklist_summary(root, ticket, context=context)


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
    from aidd_runtime import reports_pack_assemble as _assemble

    return _assemble.build_rlm_pack(
        nodes,
        links,
        ticket=ticket,
        slug_hint=slug_hint,
        source_path=source_path,
        limits=limits,
        root=root,
    )


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


def write_research_pack(
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

    pack = build_research_pack(payload, source_path=source_path, limits=limits)
    pack_path = (output or _pack_path_for(path)).resolve()

    max_chars = int(RESEARCH_BUDGET["max_chars"])
    max_lines = int(RESEARCH_BUDGET["max_lines"])
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


def write_research_context_pack(
    json_path: Path,
    *,
    output: Optional[Path] = None,
    root: Optional[Path] = None,
    limits: Optional[Dict[str, int]] = None,
) -> Path:
    print(
        "[aidd] WARN: write_research_context_pack is deprecated; use write_research_pack.",
        file=sys.stderr,
    )
    return write_research_pack(
        json_path,
        output=output,
        root=root,
        limits=limits,
    )


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
    parser = argparse.ArgumentParser(description="Generate RLM pack from nodes/links JSONL.")
    parser.add_argument(
        "--output",
        help="Optional output path (default: <ticket>-rlm.pack.json).",
    )
    parser.add_argument("--rlm-nodes", help="Path to <ticket>-rlm.nodes.jsonl to build RLM pack.")
    parser.add_argument("--rlm-links", help="Path to <ticket>-rlm.links.jsonl to build RLM pack.")
    parser.add_argument("--ticket", help="Ticket identifier to label RLM pack (optional).")
    parser.add_argument("--slug-hint", help="Slug hint for RLM pack (optional).")
    args = parser.parse_args(argv)

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
    print(pack_path.as_posix())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
