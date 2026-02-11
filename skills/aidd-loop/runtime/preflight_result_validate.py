#!/usr/bin/env python3
"""Validate stage.preflight.result.json payloads."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Iterable, List

from aidd_runtime import aidd_schemas

SUPPORTED_SCHEMA_VERSIONS = ("aidd.stage_result.preflight.v1",)
VALID_STAGES = {"implement", "review", "qa"}
VALID_STATUS = {"ok", "blocked"}


class ValidationError(ValueError):
    pass


def _require_fields(obj: dict[str, Any], fields: Iterable[str], errors: List[str], *, prefix: str = "") -> None:
    for field in fields:
        if field not in obj:
            errors.append(f"{prefix}missing field: {field}")


def _is_str(value: Any) -> bool:
    return isinstance(value, str)


def validate_preflight_result_data(payload: dict[str, Any]) -> List[str]:
    errors: List[str] = []
    if not isinstance(payload, dict):
        return ["payload must be a JSON object"]

    schema = payload.get("schema")
    if schema not in SUPPORTED_SCHEMA_VERSIONS:
        errors.append(
            "schema must be one of: " + ", ".join(SUPPORTED_SCHEMA_VERSIONS)
        )
        return errors

    _require_fields(
        payload,
        (
            "schema",
            "ticket",
            "stage",
            "scope_key",
            "work_item_key",
            "status",
            "generated_at",
            "artifacts",
        ),
        errors,
    )

    for key in ("ticket", "stage", "scope_key", "work_item_key", "generated_at"):
        if key in payload and not _is_str(payload.get(key)):
            errors.append(f"field {key} must be string")

    stage = str(payload.get("stage") or "")
    if stage and stage not in VALID_STAGES:
        errors.append(f"invalid stage: {stage}")

    status = str(payload.get("status") or "")
    if status and status not in VALID_STATUS:
        errors.append(f"invalid status: {status}")

    if "artifacts" in payload and not isinstance(payload.get("artifacts"), dict):
        errors.append("field artifacts must be object")

    reason_code = payload.get("reason_code")
    reason = payload.get("reason")
    if reason_code is not None and not _is_str(reason_code):
        errors.append("field reason_code must be string")
    if reason is not None and not _is_str(reason):
        errors.append("field reason must be string")

    return errors


def load_result(path: Path) -> dict[str, Any]:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValidationError(f"cannot read preflight result file: {path}") from exc
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValidationError(f"invalid JSON in preflight result file: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValidationError("preflight result payload must be JSON object")
    return payload


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate aidd.stage_result.preflight.v1 payload.")
    parser.add_argument("--result", help="Path to stage.preflight.result.json file")
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
        values = ",".join(aidd_schemas.supported_schema_versions("aidd.stage_result.preflight.v"))
        print(values)
        return 0

    if not args.result:
        print(
            "[preflight-result-validate] ERROR: --result is required unless --print-supported-versions is used",
            file=sys.stderr,
        )
        return 2

    path = Path(args.result)
    try:
        payload = load_result(path)
    except ValidationError as exc:
        print(f"[preflight-result-validate] ERROR: {exc}", file=sys.stderr)
        return 2

    errors = validate_preflight_result_data(payload)
    if errors:
        for err in errors:
            print(f"[preflight-result-validate] ERROR: {err}", file=sys.stderr)
        return 2

    if not args.quiet:
        schema = payload.get("schema")
        print(f"[preflight-result-validate] OK: {path} ({schema})")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
