#!/usr/bin/env python3
"""Validate AIDD actions payloads (v0 + v1)."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Iterable, List

from aidd_runtime import aidd_schemas

try:
    from aidd_runtime.tasklist_check import PROGRESS_KINDS, PROGRESS_SOURCES
except Exception:  # pragma: no cover - allow standalone runs
    PROGRESS_SOURCES = {"implement", "review", "qa", "research", "normalize"}
    PROGRESS_KINDS = {"iteration", "handoff"}

SCHEMA_V0 = "aidd.actions.v0"
SCHEMA_V1 = "aidd.actions.v1"
SUPPORTED_SCHEMA_VERSIONS = tuple(sorted({SCHEMA_V0, SCHEMA_V1}))
KNOWN_TYPES = {
    "tasklist_ops.set_iteration_done",
    "tasklist_ops.append_progress_log",
    "tasklist_ops.next3_recompute",
    "context_pack_ops.context_pack_update",
}
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class ValidationError(ValueError):
    pass


def _is_str(value: Any) -> bool:
    return isinstance(value, str)


def _require_fields(obj: dict, fields: Iterable[str], errors: List[str], *, prefix: str = "") -> None:
    for field in fields:
        if field not in obj:
            errors.append(f"{prefix}missing field: {field}")


def _validate_progress_params(params: dict, errors: List[str], *, prefix: str = "") -> None:
    required = ["date", "source", "item_id", "kind", "hash", "msg"]
    _require_fields(params, required, errors, prefix=prefix)
    date = params.get("date")
    if date and (not _is_str(date) or not DATE_RE.match(date)):
        errors.append(f"{prefix}invalid date (expected YYYY-MM-DD): {date}")
    if "source" in params:
        source = params.get("source")
        if not _is_str(source):
            errors.append(f"{prefix}source must be string")
        elif source.lower() not in PROGRESS_SOURCES:
            errors.append(f"{prefix}invalid source: {source}")
    if "kind" in params:
        kind = params.get("kind")
        if not _is_str(kind):
            errors.append(f"{prefix}kind must be string")
        elif kind.lower() not in PROGRESS_KINDS:
            errors.append(f"{prefix}invalid kind: {kind}")
    for key in ("item_id", "hash", "msg"):
        val = params.get(key)
        if val is not None and not _is_str(val):
            errors.append(f"{prefix}{key} must be string")
    link = params.get("link")
    if link is not None and not _is_str(link):
        errors.append(f"{prefix}link must be string")


def _validate_set_done_params(params: dict, errors: List[str], *, prefix: str = "") -> None:
    _require_fields(params, ["item_id"], errors, prefix=prefix)
    item_id = params.get("item_id")
    if item_id is not None and not _is_str(item_id):
        errors.append(f"{prefix}item_id must be string")
    kind = params.get("kind")
    if kind is not None:
        if not _is_str(kind):
            errors.append(f"{prefix}kind must be string")
        elif kind not in {"iteration", "handoff"}:
            errors.append(f"{prefix}kind must be 'iteration' or 'handoff'")


def _validate_context_pack_params(params: dict, errors: List[str], *, prefix: str = "") -> None:
    allowed_keys = {
        "read_log",
        "read_next",
        "artefact_links",
        "what_to_do",
        "user_note",
        "generated_at",
    }
    if not params:
        errors.append(f"{prefix}context_pack_update params cannot be empty")
        return
    unknown = [key for key in params.keys() if key not in allowed_keys]
    if unknown:
        errors.append(f"{prefix}unknown context_pack_update fields: {', '.join(sorted(unknown))}")
    for key in ("read_log", "read_next", "artefact_links"):
        if key in params:
            value = params.get(key)
            if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
                errors.append(f"{prefix}{key} must be list[str]")
    for key in ("what_to_do", "user_note", "generated_at"):
        if key in params and params.get(key) is not None and not _is_str(params.get(key)):
            errors.append(f"{prefix}{key} must be string")


def _validate_action_item(action: dict, errors: List[str], *, prefix: str, allowed_types: set[str]) -> None:
    action_type = action.get("type")
    if not action_type or not _is_str(action_type):
        errors.append(f"{prefix}missing or invalid type")
        return
    if action_type not in KNOWN_TYPES:
        errors.append(f"{prefix}unsupported type '{action_type}'")
        return
    if action_type not in allowed_types:
        errors.append(f"{prefix}type '{action_type}' is not allowed by payload")
        return
    params = action.get("params", {})
    if params is None:
        params = {}
    if not isinstance(params, dict):
        errors.append(f"{prefix}params must be object")
        return
    if action_type == "tasklist_ops.set_iteration_done":
        _validate_set_done_params(params, errors, prefix=prefix)
    elif action_type == "tasklist_ops.append_progress_log":
        _validate_progress_params(params, errors, prefix=prefix)
    elif action_type == "tasklist_ops.next3_recompute":
        if params:
            errors.append(f"{prefix}params must be empty for next3_recompute")
    elif action_type == "context_pack_ops.context_pack_update":
        _validate_context_pack_params(params, errors, prefix=prefix)


def _validate_v0(payload: dict, errors: List[str]) -> None:
    for key in ("stage", "ticket", "scope_key", "work_item_key"):
        if key not in payload:
            errors.append(f"missing field: {key}")
        elif not _is_str(payload.get(key)):
            errors.append(f"field {key} must be string")

    actions = payload.get("actions")
    if actions is None:
        errors.append("missing field: actions")
        return
    if not isinstance(actions, list):
        errors.append("actions must be a list")
        return

    allowed_types = set(KNOWN_TYPES)
    for idx, action in enumerate(actions):
        prefix = f"actions[{idx}]: "
        if not isinstance(action, dict):
            errors.append(f"{prefix}action must be object")
            continue
        _validate_action_item(action, errors, prefix=prefix, allowed_types=allowed_types)


def _validate_v1(payload: dict, errors: List[str]) -> None:
    for key in ("stage", "ticket", "scope_key", "work_item_key"):
        if key not in payload:
            errors.append(f"missing field: {key}")
        elif not _is_str(payload.get(key)):
            errors.append(f"field {key} must be string")

    allowed_action_types = payload.get("allowed_action_types")
    if allowed_action_types is None:
        errors.append("missing field: allowed_action_types")
        allowed_types: set[str] = set()
    elif not isinstance(allowed_action_types, list) or not all(_is_str(item) for item in allowed_action_types):
        errors.append("allowed_action_types must be list[str]")
        allowed_types = set()
    else:
        allowed_types = {str(item) for item in allowed_action_types}
        unknown = sorted(item for item in allowed_types if item not in KNOWN_TYPES)
        if unknown:
            errors.append(f"allowed_action_types contains unsupported values: {', '.join(unknown)}")

    actions = payload.get("actions")
    if actions is None:
        errors.append("missing field: actions")
        return
    if not isinstance(actions, list):
        errors.append("actions must be a list")
        return

    for idx, action in enumerate(actions):
        prefix = f"actions[{idx}]: "
        if not isinstance(action, dict):
            errors.append(f"{prefix}action must be object")
            continue
        _validate_action_item(action, errors, prefix=prefix, allowed_types=allowed_types)


def validate_actions_data(payload: dict) -> List[str]:
    errors: List[str] = []
    if not isinstance(payload, dict):
        return ["payload must be a JSON object"]

    schema_version = payload.get("schema_version")
    if schema_version not in SUPPORTED_SCHEMA_VERSIONS:
        values = ", ".join(sorted(SUPPORTED_SCHEMA_VERSIONS))
        errors.append(f"schema_version must be one of: {values}")
        return errors

    if schema_version == SCHEMA_V0:
        _validate_v0(payload, errors)
    elif schema_version == SCHEMA_V1:
        _validate_v1(payload, errors)

    return errors


def load_actions(path: Path) -> dict:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValidationError(f"cannot read actions file: {path}") from exc
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValidationError(f"invalid JSON in actions file: {exc}") from exc
    return payload


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate AIDD actions payload (v0 + v1).")
    parser.add_argument("--actions", help="Path to actions.json file")
    parser.add_argument("--quiet", action="store_true", help="Suppress OK output")
    parser.add_argument(
        "--print-supported-versions",
        action="store_true",
        help="Print supported schema versions and exit.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.print_supported_versions:
        values = ",".join(aidd_schemas.supported_schema_versions("aidd.actions.v"))
        print(values)
        return 0

    if not args.actions:
        print("[actions-validate] ERROR: --actions is required unless --print-supported-versions is used", file=sys.stderr)
        return 2

    path = Path(args.actions)
    try:
        payload = load_actions(path)
    except ValidationError as exc:
        print(f"[actions-validate] ERROR: {exc}", file=sys.stderr)
        return 2

    errors = validate_actions_data(payload)
    if errors:
        for err in errors:
            print(f"[actions-validate] ERROR: {err}", file=sys.stderr)
        return 2

    if not args.quiet:
        schema_version = str(payload.get("schema_version") or "")
        print(f"[actions-validate] OK: {path} ({schema_version})")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
