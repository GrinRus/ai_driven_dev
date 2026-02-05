#!/usr/bin/env python3
"""Validate AIDD actions v0 payloads."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Iterable, List

try:
    from tools.tasklist_check import PROGRESS_KINDS, PROGRESS_SOURCES
except Exception:  # pragma: no cover - allow standalone runs
    PROGRESS_SOURCES = {"implement", "review", "qa", "research", "normalize"}
    PROGRESS_KINDS = {"iteration", "handoff"}

SCHEMA_VERSION = "aidd.actions.v0"
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
    source = params.get("source")
    if source and (_is_str(source)) and source.lower() not in PROGRESS_SOURCES:
        errors.append(f"{prefix}invalid source: {source}")
    kind = params.get("kind")
    if kind and (_is_str(kind)) and kind.lower() not in PROGRESS_KINDS:
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


def validate_actions_data(payload: dict) -> List[str]:
    errors: List[str] = []
    if not isinstance(payload, dict):
        return ["payload must be a JSON object"]

    schema_version = payload.get("schema_version")
    if schema_version != SCHEMA_VERSION:
        errors.append(f"schema_version must be '{SCHEMA_VERSION}'")

    for key in ("stage", "ticket", "scope_key", "work_item_key"):
        if key not in payload:
            errors.append(f"missing field: {key}")
        elif not _is_str(payload.get(key)):
            errors.append(f"field {key} must be string")

    actions = payload.get("actions")
    if actions is None:
        errors.append("missing field: actions")
    elif not isinstance(actions, list):
        errors.append("actions must be a list")
    else:
        for idx, action in enumerate(actions):
            prefix = f"actions[{idx}]: "
            if not isinstance(action, dict):
                errors.append(f"{prefix}action must be object")
                continue
            action_type = action.get("type")
            if not action_type or not _is_str(action_type):
                errors.append(f"{prefix}missing or invalid type")
                continue
            if action_type not in KNOWN_TYPES:
                errors.append(f"{prefix}unsupported type '{action_type}'")
                continue
            params = action.get("params", {})
            if params is None:
                params = {}
            if not isinstance(params, dict):
                errors.append(f"{prefix}params must be object")
                continue
            if action_type == "tasklist_ops.set_iteration_done":
                _validate_set_done_params(params, errors, prefix=prefix)
            elif action_type == "tasklist_ops.append_progress_log":
                _validate_progress_params(params, errors, prefix=prefix)
            elif action_type == "tasklist_ops.next3_recompute":
                if params:
                    errors.append(f"{prefix}params must be empty for next3_recompute")
            elif action_type == "context_pack_ops.context_pack_update":
                _validate_context_pack_params(params, errors, prefix=prefix)

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
    parser = argparse.ArgumentParser(description="Validate AIDD actions v0 payload.")
    parser.add_argument("--actions", required=True, help="Path to actions.json file")
    parser.add_argument("--quiet", action="store_true", help="Suppress OK output")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
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
        print(f"[actions-validate] OK: {path}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
