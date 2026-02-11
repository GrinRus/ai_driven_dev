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


def _allowed_artifact_paths(*, ticket: str, scope_key: str, stage: str) -> dict[str, list[str]]:
    actions_base = f"aidd/reports/actions/{ticket}/{scope_key}"
    context_base = f"aidd/reports/context/{ticket}"
    loops_base = f"aidd/reports/loops/{ticket}/{scope_key}"
    return {
        "actions_template": [f"{actions_base}/{stage}.actions.template.json"],
        "readmap_json": [f"{context_base}/{scope_key}.readmap.json", f"{actions_base}/readmap.json"],
        "readmap_md": [f"{context_base}/{scope_key}.readmap.md", f"{actions_base}/readmap.md"],
        "writemap_json": [f"{context_base}/{scope_key}.writemap.json", f"{actions_base}/writemap.json"],
        "writemap_md": [f"{context_base}/{scope_key}.writemap.md", f"{actions_base}/writemap.md"],
        "loop_pack": [f"aidd/reports/loops/{ticket}/{scope_key}.loop.pack.md"],
    }


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

    artifacts = payload.get("artifacts")
    if status == "ok" and isinstance(artifacts, dict):
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
        stage = str(payload.get("stage") or "").strip()
        if ticket and scope_key and stage in VALID_STAGES:
            allowed = _allowed_artifact_paths(ticket=ticket, scope_key=scope_key, stage=stage)
            for key, allowed_values in allowed.items():
                value = str(artifacts.get(key) or "").strip()
                if value and value not in allowed_values:
                    expected_text = " | ".join(allowed_values)
                    errors.append(f"artifacts.{key} must be one of [{expected_text}], got '{value}'")

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
