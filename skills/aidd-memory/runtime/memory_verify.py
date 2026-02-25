#!/usr/bin/env python3
"""Validate Memory v2 artifacts (semantic/decision/decisions-pack)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Sequence

from aidd_runtime import aidd_schemas
from aidd_runtime import runtime
from aidd_runtime import validation_helpers
from aidd_runtime import memory_common as common

SUPPORTED_SCHEMA_VERSIONS = tuple(sorted(aidd_schemas.supported_schema_versions("aidd.memory.")))
_DECISION_STATUS = {"active", "superseded", "rejected"}
_SEVERITY_LEVELS = {"low", "medium", "high", "critical"}


class ValidationError(ValueError):
    pass


def _err(reason_code: str, message: str) -> str:
    return f"{reason_code}: {message}"


def _is_str(value: Any) -> bool:
    return isinstance(value, str)


def _validate_columnar(
    payload: Dict[str, Any],
    field: str,
    expected_cols: Sequence[str],
    errors: List[str],
) -> None:
    value = payload.get(field)
    if not isinstance(value, dict):
        errors.append(_err("memory_invalid_field_type", f"{field} must be object"))
        return
    cols = value.get("cols")
    rows = value.get("rows")
    if not isinstance(cols, list) or not all(isinstance(item, str) and item.strip() for item in cols):
        errors.append(_err("memory_invalid_field_type", f"{field}.cols must be list[str]"))
        return
    if list(cols) != list(expected_cols):
        errors.append(
            _err(
                "memory_invalid_column_schema",
                f"{field}.cols must match {list(expected_cols)}",
            )
        )
    if not isinstance(rows, list):
        errors.append(_err("memory_invalid_field_type", f"{field}.rows must be list"))
        return
    for idx, row in enumerate(rows):
        if not isinstance(row, list):
            errors.append(_err("memory_invalid_row_shape", f"{field}.rows[{idx}] must be list"))
            continue
        if len(row) != len(cols):
            errors.append(
                _err(
                    "memory_invalid_row_shape",
                    f"{field}.rows[{idx}] size {len(row)} does not match cols size {len(cols)}",
                )
            )


def _validate_semantic_data(payload: Dict[str, Any], *, max_chars: int | None, max_lines: int | None) -> List[str]:
    errors: List[str] = []
    validation_helpers.require_fields(
        payload,
        (
            "schema",
            "schema_version",
            "pack_version",
            "type",
            "kind",
            "ticket",
            "slug_hint",
            "generated_at",
            "source_path",
            "terms",
            "defaults",
            "constraints",
            "invariants",
            "open_questions",
            "stats",
        ),
        errors,
    )
    if payload.get("schema") != common.SCHEMA_SEMANTIC:
        errors.append(_err("memory_schema_mismatch", f"schema must be {common.SCHEMA_SEMANTIC}"))
    if payload.get("schema_version") != common.SCHEMA_SEMANTIC:
        errors.append(_err("memory_schema_mismatch", f"schema_version must be {common.SCHEMA_SEMANTIC}"))
    if payload.get("type") != "memory-semantic":
        errors.append(_err("memory_invalid_enum", "type must be memory-semantic"))
    if payload.get("kind") != "pack":
        errors.append(_err("memory_invalid_enum", "kind must be pack"))

    for field in ("ticket", "slug_hint", "generated_at", "source_path", "pack_version"):
        value = payload.get(field)
        if value is not None and not _is_str(value):
            errors.append(_err("memory_invalid_field_type", f"{field} must be string"))

    _validate_columnar(payload, "terms", ("term", "definition", "aliases", "scope", "confidence"), errors)
    _validate_columnar(payload, "defaults", ("key", "value", "source", "rationale"), errors)
    _validate_columnar(payload, "constraints", ("id", "text", "source", "severity"), errors)
    _validate_columnar(payload, "invariants", ("id", "text", "source"), errors)

    terms = payload.get("terms")
    if isinstance(terms, dict):
        for idx, row in enumerate(terms.get("rows") or []):
            if not isinstance(row, list) or len(row) != 5:
                continue
            if not isinstance(row[2], list):
                errors.append(_err("memory_invalid_field_type", f"terms.rows[{idx}][2] aliases must be list"))
            if row[4] is not None and not isinstance(row[4], (int, float)):
                errors.append(
                    _err(
                        "memory_invalid_field_type",
                        f"terms.rows[{idx}][4] confidence must be numeric",
                    )
                )

    constraints = payload.get("constraints")
    if isinstance(constraints, dict):
        for idx, row in enumerate(constraints.get("rows") or []):
            if not isinstance(row, list) or len(row) != 4:
                continue
            severity = str(row[3] or "").strip().lower()
            if severity and severity not in _SEVERITY_LEVELS:
                errors.append(
                    _err(
                        "memory_invalid_enum",
                        f"constraints.rows[{idx}][3] severity must be one of {sorted(_SEVERITY_LEVELS)}",
                    )
                )

    open_questions = payload.get("open_questions")
    if not isinstance(open_questions, list) or not all(isinstance(item, str) for item in open_questions):
        errors.append(_err("memory_invalid_field_type", "open_questions must be list[str]"))
    if not isinstance(payload.get("stats"), dict):
        errors.append(_err("memory_invalid_field_type", "stats must be object"))

    if max_chars is not None or max_lines is not None:
        size = common.payload_size(payload)
        if max_chars is not None and size["chars"] > max_chars:
            errors.append(
                _err("memory_budget_chars_exceeded", f"{size['chars']} > {max_chars}")
            )
        if max_lines is not None and size["lines"] > max_lines:
            errors.append(
                _err("memory_budget_lines_exceeded", f"{size['lines']} > {max_lines}")
            )
    return errors


def validate_decision_data(payload: Dict[str, Any]) -> List[str]:
    errors: List[str] = []
    validation_helpers.require_fields(
        payload,
        (
            "schema",
            "schema_version",
            "ts",
            "ticket",
            "scope_key",
            "stage",
            "decision_id",
            "topic",
            "decision",
            "alternatives",
            "rationale",
            "source_path",
            "status",
        ),
        errors,
    )
    if payload.get("schema") != common.SCHEMA_DECISION:
        errors.append(_err("memory_schema_mismatch", f"schema must be {common.SCHEMA_DECISION}"))
    if payload.get("schema_version") != common.SCHEMA_DECISION:
        errors.append(_err("memory_schema_mismatch", f"schema_version must be {common.SCHEMA_DECISION}"))

    for field in (
        "ts",
        "ticket",
        "scope_key",
        "stage",
        "decision_id",
        "topic",
        "decision",
        "rationale",
        "source_path",
        "status",
    ):
        value = payload.get(field)
        if value is not None and not _is_str(value):
            errors.append(_err("memory_invalid_field_type", f"{field} must be string"))

    alternatives = payload.get("alternatives")
    if not isinstance(alternatives, list) or not all(isinstance(item, str) for item in alternatives):
        errors.append(_err("memory_invalid_field_type", "alternatives must be list[str]"))

    status = str(payload.get("status") or "").strip().lower()
    if status and status not in _DECISION_STATUS:
        errors.append(_err("memory_invalid_enum", f"status must be one of {sorted(_DECISION_STATUS)}"))

    supersedes = payload.get("supersedes")
    if supersedes is not None and not _is_str(supersedes):
        errors.append(_err("memory_invalid_field_type", "supersedes must be string"))
    return errors


def _validate_decisions_pack_data(
    payload: Dict[str, Any],
    *,
    max_chars: int | None,
    max_lines: int | None,
) -> List[str]:
    errors: List[str] = []
    validation_helpers.require_fields(
        payload,
        (
            "schema",
            "schema_version",
            "pack_version",
            "type",
            "kind",
            "ticket",
            "slug_hint",
            "generated_at",
            "source_path",
            "active_decisions",
            "superseded_heads",
            "conflicts",
            "stats",
        ),
        errors,
    )
    if payload.get("schema") != common.SCHEMA_DECISIONS_PACK:
        errors.append(_err("memory_schema_mismatch", f"schema must be {common.SCHEMA_DECISIONS_PACK}"))
    if payload.get("schema_version") != common.SCHEMA_DECISIONS_PACK:
        errors.append(
            _err("memory_schema_mismatch", f"schema_version must be {common.SCHEMA_DECISIONS_PACK}")
        )
    if payload.get("type") != "memory-decisions":
        errors.append(_err("memory_invalid_enum", "type must be memory-decisions"))
    if payload.get("kind") != "pack":
        errors.append(_err("memory_invalid_enum", "kind must be pack"))

    _validate_columnar(
        payload,
        "active_decisions",
        ("decision_id", "topic", "decision", "status", "ts", "scope_key", "stage", "source_path"),
        errors,
    )
    _validate_columnar(
        payload,
        "superseded_heads",
        ("decision_id", "supersedes", "topic", "status", "ts"),
        errors,
    )
    conflicts = payload.get("conflicts")
    if not isinstance(conflicts, list) or not all(isinstance(item, str) for item in conflicts):
        errors.append(_err("memory_invalid_field_type", "conflicts must be list[str]"))
    if not isinstance(payload.get("stats"), dict):
        errors.append(_err("memory_invalid_field_type", "stats must be object"))

    if max_chars is not None or max_lines is not None:
        size = common.payload_size(payload)
        if max_chars is not None and size["chars"] > max_chars:
            errors.append(_err("memory_budget_chars_exceeded", f"{size['chars']} > {max_chars}"))
        if max_lines is not None and size["lines"] > max_lines:
            errors.append(_err("memory_budget_lines_exceeded", f"{size['lines']} > {max_lines}"))
    return errors


def validate_memory_data(
    payload: Dict[str, Any],
    *,
    max_chars: int | None = None,
    max_lines: int | None = None,
) -> List[str]:
    if not isinstance(payload, dict):
        return [_err("memory_payload_not_object", "payload must be a JSON object")]

    schema_version = str(payload.get("schema_version") or payload.get("schema") or "").strip()
    if schema_version not in SUPPORTED_SCHEMA_VERSIONS:
        return [
            _err(
                "memory_schema_unsupported",
                f"schema_version must be one of {list(SUPPORTED_SCHEMA_VERSIONS)}",
            )
        ]

    if schema_version == common.SCHEMA_SEMANTIC:
        return _validate_semantic_data(payload, max_chars=max_chars, max_lines=max_lines)
    if schema_version == common.SCHEMA_DECISION:
        return validate_decision_data(payload)
    if schema_version == common.SCHEMA_DECISIONS_PACK:
        return _validate_decisions_pack_data(payload, max_chars=max_chars, max_lines=max_lines)
    return [_err("memory_schema_unsupported", f"unsupported schema_version: {schema_version}")]


def _load_json(path: Path) -> Dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ValidationError(f"cannot read input: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ValidationError(f"invalid JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValidationError("JSON payload must be an object")
    return payload


def _resolve_defaults(schema_version: str) -> Dict[str, int]:
    try:
        _, project_root = runtime.require_workflow_root(Path.cwd())
        settings = common.load_memory_settings(project_root)
    except Exception:
        settings = {}
    if schema_version == common.SCHEMA_SEMANTIC:
        semantic = common.semantic_limits(settings)
        return {"max_chars": int(semantic["max_chars"]), "max_lines": int(semantic["max_lines"])}
    if schema_version == common.SCHEMA_DECISIONS_PACK:
        decisions = common.decisions_limits(settings)
        return {"max_chars": int(decisions["max_chars"]), "max_lines": int(decisions["max_lines"])}
    return {}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate Memory v2 artifacts.")
    parser.add_argument("--input", help="Path to JSON/JSONL memory artifact.")
    parser.add_argument("--schema-version", help="Override schema version (optional).")
    parser.add_argument("--max-chars", type=int, default=None, help="Optional chars budget override.")
    parser.add_argument("--max-lines", type=int, default=None, help="Optional lines budget override.")
    parser.add_argument("--quiet", action="store_true", help="Suppress OK output.")
    parser.add_argument(
        "--print-supported-versions",
        action="store_true",
        help="Print supported schema versions and exit.",
    )
    return parser.parse_args(argv)


def _validate_jsonl(path: Path, schema_version_override: str | None) -> List[str]:
    errors: List[str] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise ValidationError(f"cannot read input: {path}") from exc
    for idx, raw in enumerate(lines, start=1):
        line = raw.strip()
        if not line:
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError as exc:
            errors.append(_err("memory_json_invalid", f"line {idx}: {exc}"))
            continue
        if not isinstance(payload, dict):
            errors.append(_err("memory_payload_not_object", f"line {idx}: payload must be object"))
            continue
        if schema_version_override:
            payload["schema"] = schema_version_override
            payload["schema_version"] = schema_version_override
        line_errors = validate_memory_data(payload)
        for err in line_errors:
            errors.append(f"line {idx}: {err}")
    return errors


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.print_supported_versions:
        print(",".join(SUPPORTED_SCHEMA_VERSIONS))
        return 0

    if not args.input:
        print("[memory-verify] ERROR: --input is required unless --print-supported-versions is used", file=sys.stderr)
        return 2

    path = Path(args.input)
    if path.suffix == ".jsonl":
        try:
            errors = _validate_jsonl(path, args.schema_version)
        except ValidationError as exc:
            print(f"[memory-verify] ERROR: {exc}", file=sys.stderr)
            return 2
        if errors:
            for err in errors:
                print(f"[memory-verify] ERROR: {err}", file=sys.stderr)
            return 2
        if not args.quiet:
            print(f"[memory-verify] OK: {path} ({common.SCHEMA_DECISION} jsonl)")
        return 0

    try:
        payload = _load_json(path)
    except ValidationError as exc:
        print(f"[memory-verify] ERROR: {exc}", file=sys.stderr)
        return 2

    if args.schema_version:
        payload["schema"] = args.schema_version
        payload["schema_version"] = args.schema_version

    schema_version = str(payload.get("schema_version") or payload.get("schema") or "").strip()
    defaults = _resolve_defaults(schema_version)
    max_chars = args.max_chars if args.max_chars is not None else defaults.get("max_chars")
    max_lines = args.max_lines if args.max_lines is not None else defaults.get("max_lines")

    errors = validate_memory_data(payload, max_chars=max_chars, max_lines=max_lines)
    if errors:
        for err in errors:
            print(f"[memory-verify] ERROR: {err}", file=sys.stderr)
        return 2

    if not args.quiet:
        print(f"[memory-verify] OK: {path} ({schema_version})")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())

