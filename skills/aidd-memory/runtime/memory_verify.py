#!/usr/bin/env python3
"""Validate Memory v2 artifacts (semantic/decision/decisions-pack)."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, List


def _ensure_plugin_root_on_path() -> None:
    env_root = os.environ.get("CLAUDE_PLUGIN_ROOT", "").strip()
    if env_root:
        root = Path(env_root).resolve()
        if (root / "aidd_runtime").is_dir():
            if str(root) not in sys.path:
                sys.path.insert(0, str(root))
            return

    probe = Path(__file__).resolve()
    for parent in (probe.parent, *probe.parents):
        if (parent / "aidd_runtime").is_dir():
            os.environ.setdefault("CLAUDE_PLUGIN_ROOT", str(parent))
            if str(parent) not in sys.path:
                sys.path.insert(0, str(parent))
            return


_ensure_plugin_root_on_path()

from aidd_runtime import aidd_schemas

SEMANTIC_SCHEMA = "aidd.memory.semantic.v1"
DECISION_SCHEMA = "aidd.memory.decision.v1"
DECISIONS_PACK_SCHEMA = "aidd.memory.decisions.pack.v1"
SUPPORTED_SCHEMAS = (SEMANTIC_SCHEMA, DECISION_SCHEMA, DECISIONS_PACK_SCHEMA)

_TIMESTAMP_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T")
_MAX_SEMANTIC_CHARS = 12000
_MAX_SECTION_ITEMS = 64
_MAX_DECISIONS_TOTAL = 200
_MAX_TOP_N = 20


def _is_str(value: Any) -> bool:
    return isinstance(value, str)


def _is_iso_like(value: Any) -> bool:
    return _is_str(value) and bool(_TIMESTAMP_RE.match(str(value)))


def _validate_str_list(value: Any, errors: List[str], *, field: str, allow_empty: bool = True) -> List[str]:
    if not isinstance(value, list):
        errors.append(f"{field} must be list[str]")
        return []
    out: List[str] = []
    for idx, item in enumerate(value):
        if not isinstance(item, str):
            errors.append(f"{field}[{idx}] must be string")
            continue
        cleaned = item.strip()
        if not cleaned and not allow_empty:
            errors.append(f"{field}[{idx}] must be non-empty")
            continue
        out.append(item)
    return out


def validate_semantic_data(payload: Dict[str, Any]) -> List[str]:
    errors: List[str] = []
    if not isinstance(payload, dict):
        return ["payload must be an object"]

    if payload.get("schema") != SEMANTIC_SCHEMA:
        errors.append(f"schema must be {SEMANTIC_SCHEMA}")
    if payload.get("schema_version") != SEMANTIC_SCHEMA:
        errors.append(f"schema_version must be {SEMANTIC_SCHEMA}")

    ticket = payload.get("ticket")
    if not _is_str(ticket) or not str(ticket).strip():
        errors.append("ticket must be non-empty string")

    generated_at = payload.get("generated_at")
    if not _is_iso_like(generated_at):
        errors.append("generated_at must be ISO timestamp string")

    status = str(payload.get("status") or "").strip().lower()
    if status not in {"ok", "warn"}:
        errors.append("status must be one of: ok, warn")

    _validate_str_list(payload.get("source_paths"), errors, field="source_paths", allow_empty=False)

    sections = payload.get("sections")
    if not isinstance(sections, dict):
        errors.append("sections must be object")
        return errors

    total_chars = 0
    for field in ("terms", "defaults", "constraints", "invariants", "open_questions"):
        values = _validate_str_list(sections.get(field), errors, field=f"sections.{field}", allow_empty=False)
        if len(values) > _MAX_SECTION_ITEMS:
            errors.append(f"sections.{field} exceeds max items ({_MAX_SECTION_ITEMS})")
        total_chars += sum(len(str(item)) for item in values)

    if total_chars > _MAX_SEMANTIC_CHARS:
        errors.append(f"semantic payload exceeds char budget ({_MAX_SEMANTIC_CHARS})")

    return errors


def validate_decision_data(payload: Dict[str, Any]) -> List[str]:
    errors: List[str] = []
    if not isinstance(payload, dict):
        return ["payload must be an object"]

    if payload.get("schema") != DECISION_SCHEMA:
        errors.append(f"schema must be {DECISION_SCHEMA}")
    if payload.get("schema_version") != DECISION_SCHEMA:
        errors.append(f"schema_version must be {DECISION_SCHEMA}")

    for field in ("ticket", "decision_id", "title", "decision", "stage", "scope_key", "source"):
        value = payload.get(field)
        if not _is_str(value) or not str(value).strip():
            errors.append(f"{field} must be non-empty string")

    created_at = payload.get("created_at")
    if not _is_iso_like(created_at):
        errors.append("created_at must be ISO timestamp string")

    status = str(payload.get("status") or "").strip().lower()
    if status not in {"active", "superseded"}:
        errors.append("status must be one of: active, superseded")

    _validate_str_list(payload.get("tags") or [], errors, field="tags")
    _validate_str_list(payload.get("supersedes") or [], errors, field="supersedes")
    _validate_str_list(payload.get("conflicts_with") or [], errors, field="conflicts_with")

    for hash_field in ("content_hash", "entry_hash"):
        value = payload.get(hash_field)
        if not _is_str(value) or not str(value).strip():
            errors.append(f"{hash_field} must be non-empty string")

    prev_hash = payload.get("prev_hash")
    if prev_hash is not None and not _is_str(prev_hash):
        errors.append("prev_hash must be string when provided")

    return errors


def validate_decisions_pack_data(payload: Dict[str, Any]) -> List[str]:
    errors: List[str] = []
    if not isinstance(payload, dict):
        return ["payload must be an object"]

    if payload.get("schema") != DECISIONS_PACK_SCHEMA:
        errors.append(f"schema must be {DECISIONS_PACK_SCHEMA}")
    if payload.get("schema_version") != DECISIONS_PACK_SCHEMA:
        errors.append(f"schema_version must be {DECISIONS_PACK_SCHEMA}")

    ticket = payload.get("ticket")
    if not _is_str(ticket) or not str(ticket).strip():
        errors.append("ticket must be non-empty string")

    generated_at = payload.get("generated_at")
    if not _is_iso_like(generated_at):
        errors.append("generated_at must be ISO timestamp string")

    status = str(payload.get("status") or "").strip().lower()
    if status not in {"ok", "warn"}:
        errors.append("status must be one of: ok, warn")

    active = payload.get("active")
    superseded = payload.get("superseded")
    top = payload.get("top")

    active_list = (
        _validate_str_list([json.dumps(item, sort_keys=True) for item in active], errors, field="active")
        if isinstance(active, list)
        else []
    )
    superseded_list = (
        _validate_str_list([json.dumps(item, sort_keys=True) for item in superseded], errors, field="superseded")
        if isinstance(superseded, list)
        else []
    )
    top_list = (
        _validate_str_list([json.dumps(item, sort_keys=True) for item in top], errors, field="top")
        if isinstance(top, list)
        else []
    )

    if not isinstance(active, list):
        errors.append("active must be list")
    if not isinstance(superseded, list):
        errors.append("superseded must be list")
    if not isinstance(top, list):
        errors.append("top must be list")

    if len(active_list) + len(superseded_list) > _MAX_DECISIONS_TOTAL:
        errors.append(f"decisions pack exceeds max entries ({_MAX_DECISIONS_TOTAL})")
    if len(top_list) > _MAX_TOP_N:
        errors.append(f"top exceeds max entries ({_MAX_TOP_N})")

    for field_name, entries in (("active", active), ("superseded", superseded), ("top", top)):
        if not isinstance(entries, list):
            continue
        for idx, entry in enumerate(entries):
            if not isinstance(entry, dict):
                errors.append(f"{field_name}[{idx}] must be object")
                continue
            entry_errors = validate_decision_data(entry)
            if entry_errors:
                errors.append(f"{field_name}[{idx}] invalid decision: {entry_errors[0]}")

    return errors


def load_payload(path: Path) -> Dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ValueError(f"cannot read file: {path}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid JSON: {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"payload must be object: {path}")
    return payload


def validate_payload(payload: Dict[str, Any], expected_schema: str) -> List[str]:
    if expected_schema == SEMANTIC_SCHEMA:
        return validate_semantic_data(payload)
    if expected_schema == DECISION_SCHEMA:
        return validate_decision_data(payload)
    if expected_schema == DECISIONS_PACK_SCHEMA:
        return validate_decisions_pack_data(payload)
    return [f"unsupported schema: {expected_schema}"]


def _validate_path(path: Path, expected_schema: str, quiet: bool = False) -> int:
    try:
        payload = load_payload(path)
    except ValueError as exc:
        print(f"[memory-verify] ERROR: {exc}", file=sys.stderr)
        return 2

    schema = str(payload.get("schema_version") or payload.get("schema") or "").strip()
    if schema != expected_schema:
        print(
            f"[memory-verify] ERROR: schema mismatch for {path}: expected={expected_schema} got={schema or '<missing>'}",
            file=sys.stderr,
        )
        return 2

    errors = validate_payload(payload, expected_schema)
    if errors:
        for err in errors:
            print(f"[memory-verify] ERROR: {path}: {err}", file=sys.stderr)
        return 2

    if not quiet:
        print(f"[memory-verify] OK: {path} ({expected_schema})")
    return 0


def parse_args(argv: List[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate memory v2 artifacts.")
    parser.add_argument("--semantic", help="Path to <ticket>.semantic.pack.json")
    parser.add_argument("--decision", help="Path to single decision payload JSON")
    parser.add_argument("--decisions-pack", help="Path to <ticket>.decisions.pack.json")
    parser.add_argument("--print-supported-versions", action="store_true", help="Print supported schema versions and exit")
    parser.add_argument("--quiet", action="store_true", help="Suppress OK output")
    return parser.parse_args(argv)


def main(argv: List[str] | None = None) -> int:
    args = parse_args(argv)
    if args.print_supported_versions:
        values = [
            item
            for item in aidd_schemas.supported_schema_versions("aidd.memory.")
            if item in SUPPORTED_SCHEMAS
        ]
        print(",".join(values))
        return 0

    checks: List[tuple[Path, str]] = []
    if args.semantic:
        checks.append((Path(args.semantic), SEMANTIC_SCHEMA))
    if args.decision:
        checks.append((Path(args.decision), DECISION_SCHEMA))
    if args.decisions_pack:
        checks.append((Path(args.decisions_pack), DECISIONS_PACK_SCHEMA))

    if not checks:
        print("[memory-verify] ERROR: at least one of --semantic/--decision/--decisions-pack is required", file=sys.stderr)
        return 2

    exit_code = 0
    for path, schema in checks:
        rc = _validate_path(path, schema, quiet=bool(args.quiet))
        if rc != 0:
            exit_code = rc
    return exit_code


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
