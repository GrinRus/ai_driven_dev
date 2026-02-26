#!/usr/bin/env python3
"""Extract deterministic semantic memory pack from docs/context artifacts."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

from aidd_runtime import io_utils
from aidd_runtime import memory_common as common
from aidd_runtime import memory_verify
from aidd_runtime import runtime

_KV_RE = re.compile(r"^\s*(?:[-*]\s+)?(?P<key>[A-Za-zА-Яа-я0-9_.\- /]{2,80})\s*:\s*(?P<value>.+?)\s*$")
_QUESTION_RE = re.compile(r"\?")
_CONSTRAINT_MARKERS = (
    "must",
    "must not",
    "should not",
    "forbidden",
    "cannot",
    "required",
    "не должен",
    "нельзя",
    "запрещ",
    "обязательно",
    "deny",
)
_INVARIANT_MARKERS = (
    "always",
    "invariant",
    "stable",
    "deterministic",
    "append-only",
    "immutable",
    "всегда",
    "инвариант",
    "детерминир",
    "неизмен",
)
_DEFAULT_HINTS = (
    "default",
    "defaults",
    "по умолч",
    "fallback",
    "mode",
    "timeout",
    "limit",
    "enabled",
    "required",
)


def _load_source_paths(project_root: Path, ticket: str) -> List[Path]:
    candidates = [
        project_root / "docs" / "prd" / f"{ticket}.prd.md",
        project_root / "docs" / "plan" / f"{ticket}.md",
        project_root / "docs" / "research" / f"{ticket}.md",
        project_root / "docs" / "tasklist" / f"{ticket}.md",
        project_root / "reports" / "context" / f"{ticket}.pack.md",
    ]
    return [path for path in candidates if path.exists()]


def _iter_clean_lines(path: Path) -> Iterable[Tuple[int, str]]:
    try:
        raw_lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return []
    output: List[Tuple[int, str]] = []
    for idx, raw in enumerate(raw_lines, start=1):
        line = common.normalize_text(raw)
        if not line:
            continue
        if line.startswith("```"):
            continue
        output.append((idx, line))
    return output


def _classify_default(key: str, value: str) -> bool:
    haystack = f"{key.lower()} {value.lower()}"
    return any(marker in haystack for marker in _DEFAULT_HINTS)


def _classify_constraint(text: str) -> Tuple[bool, str]:
    lowered = text.lower()
    if not any(marker in lowered for marker in _CONSTRAINT_MARKERS):
        return False, ""
    severity = "medium"
    if any(marker in lowered for marker in ("must not", "forbidden", "запрещ", "нельзя", "не должен")):
        severity = "high"
    if any(marker in lowered for marker in ("critical", "blocker")):
        severity = "critical"
    return True, severity


def _classify_invariant(text: str) -> bool:
    lowered = text.lower()
    return any(marker in lowered for marker in _INVARIANT_MARKERS)


def _truncate_rows(rows: List[List[Any]], limit: int) -> List[List[Any]]:
    return rows[: max(0, limit)]


def _trim_to_budget(
    payload: Dict[str, Any],
    *,
    max_chars: int,
    max_lines: int,
    trim_priority: List[str],
) -> Dict[str, int]:
    trim_stats: Dict[str, int] = {}
    while common.budget_exceeded(payload, max_chars=max_chars, max_lines=max_lines):
        trimmed = False
        for section in trim_priority:
            if section == "open_questions":
                questions = payload.get("open_questions")
                if isinstance(questions, list) and questions:
                    questions.pop()
                    trim_stats[section] = trim_stats.get(section, 0) + 1
                    trimmed = True
                    break
                continue
            block = payload.get(section)
            if not isinstance(block, dict):
                continue
            rows = block.get("rows")
            if not isinstance(rows, list) or not rows:
                continue
            rows.pop()
            trim_stats[section] = trim_stats.get(section, 0) + 1
            trimmed = True
            break
        if not trimmed:
            break
    return trim_stats


def _build_semantic_pack(
    project_root: Path,
    ticket: str,
    slug_hint: str,
    settings: Dict[str, Any],
    source_paths: List[Path],
) -> Dict[str, Any]:
    limits = common.semantic_limits(settings)
    max_items = max(20, int(limits["max_items"]))
    per_section = max(8, min(30, max_items // 4))

    term_rows: List[List[Any]] = []
    default_rows: List[List[Any]] = []
    constraint_rows: List[List[Any]] = []
    invariant_rows: List[List[Any]] = []
    questions: List[str] = []

    seen_terms: set[str] = set()
    seen_defaults: set[str] = set()
    seen_constraints: set[str] = set()
    seen_invariants: set[str] = set()

    scanned_lines = 0
    for source in source_paths:
        source_rel = runtime.rel_path(source, project_root)
        for line_no, text in _iter_clean_lines(source):
            scanned_lines += 1

            if _QUESTION_RE.search(text) and len(text) <= 220 and "http://" not in text and "https://" not in text:
                questions.append(text)

            kv = _KV_RE.match(text)
            if kv:
                key = common.normalize_text(kv.group("key"))
                value = common.normalize_text(kv.group("value"))
                if key and value:
                    if _classify_default(key, value):
                        key_lc = key.lower()
                        if key_lc not in seen_defaults:
                            seen_defaults.add(key_lc)
                            default_rows.append([key, value, source_rel, "auto-extracted"])
                    else:
                        key_lc = key.lower()
                        if key_lc not in seen_terms:
                            seen_terms.add(key_lc)
                            term_rows.append([key, value, [], source_rel, 0.6])

            is_constraint, severity = _classify_constraint(text)
            if is_constraint:
                normalized = text.lower()
                if normalized not in seen_constraints:
                    seen_constraints.add(normalized)
                    constraint_rows.append(
                        [common.stable_id(source_rel, line_no, text), text, source_rel, severity]
                    )

            if _classify_invariant(text):
                normalized = text.lower()
                if normalized not in seen_invariants:
                    seen_invariants.add(normalized)
                    invariant_rows.append([common.stable_id(source_rel, line_no, text), text, source_rel])

    term_rows = _truncate_rows(sorted(term_rows, key=lambda row: str(row[0]).lower()), per_section)
    default_rows = _truncate_rows(sorted(default_rows, key=lambda row: str(row[0]).lower()), per_section)
    constraint_rows = _truncate_rows(sorted(constraint_rows, key=lambda row: str(row[1]).lower()), per_section)
    invariant_rows = _truncate_rows(sorted(invariant_rows, key=lambda row: str(row[1]).lower()), per_section)
    questions = common.dedupe_preserve_order(questions)[:per_section]

    source_path = runtime.rel_path(source_paths[0], project_root) if source_paths else ""
    payload: Dict[str, Any] = {
        "schema": common.SCHEMA_SEMANTIC,
        "schema_version": common.SCHEMA_SEMANTIC,
        "pack_version": common.PACK_VERSION,
        "type": "memory-semantic",
        "kind": "pack",
        "ticket": ticket,
        "slug_hint": slug_hint,
        "generated_at": io_utils.utc_timestamp(),
        "source_path": source_path,
        "terms": common.columnar(
            ["term", "definition", "aliases", "scope", "confidence"],
            term_rows,
        ),
        "defaults": common.columnar(
            ["key", "value", "source", "rationale"],
            default_rows,
        ),
        "constraints": common.columnar(
            ["id", "text", "source", "severity"],
            constraint_rows,
        ),
        "invariants": common.columnar(
            ["id", "text", "source"],
            invariant_rows,
        ),
        "open_questions": questions,
        "stats": {
            "source_files": [runtime.rel_path(path, project_root) for path in source_paths],
            "source_files_count": len(source_paths),
            "scanned_lines": scanned_lines,
            "terms_count": len(term_rows),
            "defaults_count": len(default_rows),
            "constraints_count": len(constraint_rows),
            "invariants_count": len(invariant_rows),
            "open_questions_count": len(questions),
            "budget": {
                "max_chars": int(limits["max_chars"]),
                "max_lines": int(limits["max_lines"]),
            },
        },
    }

    trim_stats = _trim_to_budget(
        payload,
        max_chars=int(limits["max_chars"]),
        max_lines=int(limits["max_lines"]),
        trim_priority=list(limits["trim_priority"]),
    )
    size = common.payload_size(payload)
    payload["stats"]["size"] = size
    if trim_stats:
        payload["stats"]["trimmed"] = trim_stats
    return payload


def parse_args(argv: List[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Extract semantic memory pack for the active ticket.")
    parser.add_argument("--ticket", help="Ticket identifier (defaults to docs/.active.json).")
    parser.add_argument("--out", help="Optional output path for semantic pack.")
    parser.add_argument("--format", choices=("json", "text"), default="text", help="Output format.")
    return parser.parse_args(argv)


def main(argv: List[str] | None = None) -> int:
    try:
        args = parse_args(argv)
        _, project_root = runtime.require_workflow_root(Path.cwd())
        ticket, identifiers = runtime.require_ticket(project_root, ticket=args.ticket, slug_hint=None)
        settings = common.load_memory_settings(project_root)
        limits = common.semantic_limits(settings)

        source_paths = _load_source_paths(project_root, ticket)
        payload = _build_semantic_pack(
            project_root,
            ticket,
            (identifiers.slug_hint or ticket),
            settings,
            source_paths,
        )

        verify_errors = memory_verify.validate_memory_data(
            payload,
            max_chars=int(limits["max_chars"]),
            max_lines=int(limits["max_lines"]),
        )
        if verify_errors:
            joined = "; ".join(verify_errors[:5])
            raise RuntimeError(f"memory_semantic_validation_failed: {joined}")

        output_path = (
            runtime.resolve_path_for_target(Path(args.out), project_root)
            if args.out
            else common.semantic_pack_path(project_root, ticket)
        )
        io_utils.write_json(output_path, payload, sort_keys=True)

        result = {
            "schema": "aidd.memory.extract.result.v1",
            "status": "ok",
            "ticket": ticket,
            "semantic_pack": runtime.rel_path(output_path, project_root),
            "source_files_count": payload["stats"]["source_files_count"],
            "size": payload["stats"]["size"],
        }
        if args.format == "json":
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            print(f"semantic_pack={result['semantic_pack']}")
            print(
                "summary="
                f"sources={result['source_files_count']} chars={result['size']['chars']} lines={result['size']['lines']}"
            )
        return 0
    except Exception as exc:
        print(f"[memory-extract] ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
