#!/usr/bin/env python3
"""Validate stage.preflight.result.json payloads."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, List

from aidd_runtime import aidd_schemas
from aidd_runtime import runtime
from aidd_runtime import validation_helpers

CANONICAL_SCHEMA_VERSION = "aidd.stage_result.v1"
SUPPORTED_SCHEMA_VERSIONS = (CANONICAL_SCHEMA_VERSION,)
VALID_STAGES = {"implement", "review", "qa"}
VALID_STATUS = {"ok", "blocked"}
VALID_RESULTS = {"done", "blocked"}


class ValidationError(ValueError):
    pass

def _is_str(value: Any) -> bool:
    return isinstance(value, str)


def _allowed_artifact_paths(*, ticket: str, scope_key: str, stage: str) -> dict[str, list[str]]:
    context_base = f"aidd/reports/context/{ticket}"
    return {
        "actions_template": [f"aidd/reports/actions/{ticket}/{scope_key}/{stage}.actions.template.json"],
        "readmap_json": [f"{context_base}/{scope_key}.readmap.json"],
        "readmap_md": [f"{context_base}/{scope_key}.readmap.md"],
        "writemap_json": [f"{context_base}/{scope_key}.writemap.json"],
        "writemap_md": [f"{context_base}/{scope_key}.writemap.md"],
        "loop_pack": [f"aidd/reports/loops/{ticket}/{scope_key}.loop.pack.md"],
    }


def _normalized_schema(payload: dict[str, Any]) -> str:
    schema = str(payload.get("schema") or "").strip()
    schema_version = str(payload.get("schema_version") or "").strip()
    if not schema and schema_version == CANONICAL_SCHEMA_VERSION:
        return CANONICAL_SCHEMA_VERSION
    return schema


def _normalize_status_from_result(result: str) -> str:
    if result == "done":
        return "ok"
    if result == "blocked":
        return "blocked"
    return ""


def _validate_scope_alignment(*, payload: dict[str, Any], errors: List[str]) -> None:
    ticket = str(payload.get("ticket") or "").strip()
    scope_key = str(payload.get("scope_key") or "").strip()
    work_item_key = str(payload.get("work_item_key") or "").strip()
    if ticket and scope_key and runtime.is_iteration_work_item_key(work_item_key):
        expected_scope = runtime.resolve_scope_key(work_item_key, ticket)
        if scope_key != expected_scope:
            errors.append(
                "field scope_key must match canonical iteration scope for work_item_key "
                f"(expected '{expected_scope}', got '{scope_key}')"
            )


def _validate_artifacts_for_ok_status(
    *,
    payload: dict[str, Any],
    stage: str,
    status: str,
    artifacts: dict[str, Any] | None,
    errors: List[str],
) -> None:
    if status != "ok":
        return
    if not isinstance(artifacts, dict):
        errors.append("field artifacts must be object for status=ok")
        return

    required_artifacts = (
        "actions_template",
        "readmap_json",
        "readmap_md",
        "writemap_json",
        "writemap_md",
        "loop_pack",
    )
    for key in required_artifacts:
        value = artifacts.get(key)
        if not _is_str(value) or not str(value).strip():
            errors.append(f"artifacts.{key} must be non-empty string for status=ok")

    ticket = str(payload.get("ticket") or "").strip()
    scope_key = str(payload.get("scope_key") or "").strip()
    if ticket and scope_key and stage in VALID_STAGES:
        allowed = _allowed_artifact_paths(ticket=ticket, scope_key=scope_key, stage=stage)
        for key, allowed_values in allowed.items():
            value = str(artifacts.get(key) or "").strip()
            if value and value not in allowed_values:
                expected_text = " | ".join(allowed_values)
                errors.append(f"artifacts.{key} must be one of [{expected_text}], got '{value}'")


def validate_preflight_result_data(payload: dict[str, Any]) -> List[str]:
    errors: List[str] = []
    if not isinstance(payload, dict):
        return ["payload must be a JSON object"]

    schema = _normalized_schema(payload)
    if schema not in SUPPORTED_SCHEMA_VERSIONS:
        errors.append(
            "schema must be one of: " + ", ".join(SUPPORTED_SCHEMA_VERSIONS)
        )
        return errors

    validation_helpers.require_fields(
        payload,
        (
            "ticket",
            "stage",
            "scope_key",
            "work_item_key",
            "result",
            "updated_at",
        ),
        errors,
    )
    for key in ("ticket", "stage", "scope_key", "work_item_key", "updated_at"):
        if key in payload and not _is_str(payload.get(key)):
            errors.append(f"field {key} must be string")

    stage = str(payload.get("stage") or "").strip().lower()
    if stage and stage != "preflight":
        errors.append(f"invalid stage: {stage} (expected preflight)")

    result = str(payload.get("result") or "").strip().lower()
    if result and result not in VALID_RESULTS:
        errors.append(f"invalid result: {result}")
    status = str(payload.get("status") or "").strip().lower() or _normalize_status_from_result(result)
    if status and status not in VALID_STATUS:
        errors.append(f"invalid status: {status}")

    reason_code = payload.get("reason_code")
    reason = payload.get("reason")
    if reason_code is not None and not _is_str(reason_code):
        errors.append("field reason_code must be string")
    if reason is not None and not _is_str(reason):
        errors.append("field reason must be string")

    details = payload.get("details")
    if details is not None and not isinstance(details, dict):
        errors.append("field details must be object")
        details = {}
    details_obj = details if isinstance(details, dict) else {}
    target_stage = str(
        details_obj.get("target_stage")
        or payload.get("target_stage")
        or ""
    ).strip().lower()
    if target_stage and target_stage not in VALID_STAGES:
        errors.append(f"invalid target_stage: {target_stage}")
    if not target_stage and status == "ok":
        errors.append("target_stage is required for status=ok")

    details_status = str(details_obj.get("preflight_status") or "").strip().lower()
    if details_status:
        if details_status not in VALID_STATUS:
            errors.append(f"invalid details.preflight_status: {details_status}")
        elif status and details_status != status:
            errors.append(
                "details.preflight_status must match status "
                f"(got details.preflight_status='{details_status}', status='{status}')"
            )

    artifacts = details_obj.get("artifacts")
    if artifacts is None and isinstance(payload.get("artifacts"), dict):
        artifacts = payload.get("artifacts")
    if artifacts is not None and not isinstance(artifacts, dict):
        errors.append("field details.artifacts must be object")
        artifacts = None

    _validate_scope_alignment(payload=payload, errors=errors)
    _validate_artifacts_for_ok_status(
        payload=payload,
        stage=target_stage,
        status=status,
        artifacts=artifacts if isinstance(artifacts, dict) else None,
        errors=errors,
    )

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
    parser = argparse.ArgumentParser(
        description="Validate canonical preflight stage-result payloads."
    )
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
        declared = set(SUPPORTED_SCHEMA_VERSIONS)
        declared.update(aidd_schemas.supported_schema_versions("aidd.stage_result.v"))
        values = ",".join(sorted(declared))
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
