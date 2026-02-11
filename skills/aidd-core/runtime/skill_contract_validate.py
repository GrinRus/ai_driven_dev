#!/usr/bin/env python3
"""Validate skills/<stage>/CONTRACT.yaml payloads."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Iterable, List, Sequence

from aidd_runtime import aidd_schemas

SUPPORTED_SCHEMA_VERSIONS = ("aidd.skill_contract.v1",)
REQUIRED_TOP_LEVEL = (
    "schema",
    "skill_id",
    "stage",
    "entrypoints",
    "reads",
    "writes",
    "outputs",
    "gates",
    "context_budget",
    "actions",
)
CANONICAL_READMAP_MD = "aidd/reports/context/{ticket}/{scope_key}.readmap.md"
CANONICAL_PREFLIGHT_FILES = (
    "aidd/reports/context/{ticket}/{scope_key}.readmap.json",
    "aidd/reports/context/{ticket}/{scope_key}.readmap.md",
    "aidd/reports/context/{ticket}/{scope_key}.writemap.json",
    "aidd/reports/context/{ticket}/{scope_key}.writemap.md",
    "aidd/reports/loops/{ticket}/{scope_key}/stage.preflight.result.json",
)
LEGACY_PREFLIGHT_FILES = (
    "aidd/reports/actions/{ticket}/{scope_key}/readmap.json",
    "aidd/reports/actions/{ticket}/{scope_key}/readmap.md",
    "aidd/reports/actions/{ticket}/{scope_key}/writemap.json",
    "aidd/reports/actions/{ticket}/{scope_key}/writemap.md",
    "aidd/reports/actions/{ticket}/{scope_key}/stage.preflight.result.json",
)


class ValidationError(ValueError):
    pass


def _repo_root() -> Path:
    here = Path(__file__).resolve()
    for candidate in (here.parent, *here.parents):
        if (candidate / ".claude-plugin").is_dir() and (candidate / "skills").is_dir():
            return candidate
    return here.parents[2]


def _is_str(value: Any) -> bool:
    return isinstance(value, str)


def _load_yaml_fallback(text: str) -> dict[str, Any]:
    try:
        import yaml  # type: ignore
    except Exception as exc:  # pragma: no cover - optional
        raise ValidationError("CONTRACT.yaml is not JSON and PyYAML is unavailable") from exc

    payload = yaml.safe_load(text)
    if not isinstance(payload, dict):
        raise ValidationError("CONTRACT payload must be an object")
    return payload


def load_contract(path: Path) -> dict[str, Any]:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValidationError(f"cannot read contract: {path}") from exc

    normalized = text.strip()
    if normalized.startswith("---"):
        lines = text.splitlines()
        if lines and lines[0].strip() == "---":
            body = lines[1:]
            if body and body[-1].strip() == "...":
                body = body[:-1]
            normalized = "\n".join(body).strip()

    try:
        payload = json.loads(normalized)
    except json.JSONDecodeError:
        payload = _load_yaml_fallback(text)

    if not isinstance(payload, dict):
        raise ValidationError("contract payload must be a JSON/YAML object")
    return payload


def _require_fields(obj: dict[str, Any], fields: Iterable[str], errors: List[str], *, prefix: str = "") -> None:
    for field in fields:
        if field not in obj:
            errors.append(f"{prefix}missing field: {field}")


def _validate_list_of_strings(value: Any, errors: List[str], *, field: str) -> None:
    if not isinstance(value, list) or not all(isinstance(item, str) and item.strip() for item in value):
        errors.append(f"field {field} must be list[str]")


def _validate_read_items(value: Any, errors: List[str], *, field: str) -> None:
    if not isinstance(value, list):
        errors.append(f"field {field} must be list")
        return
    for idx, item in enumerate(value):
        prefix = f"{field}[{idx}]."
        if isinstance(item, str):
            if not item.strip():
                errors.append(f"{prefix}must be non-empty string")
            continue
        if not isinstance(item, dict):
            errors.append(f"{prefix}must be string or object")
            continue
        ref = item.get("ref")
        if not isinstance(ref, str) or not ref.strip():
            errors.append(f"{prefix}ref must be non-empty string")


def _strip_ref_selector(value: str) -> str:
    raw = str(value or "").strip()
    if "#AIDD:" in raw:
        return raw.split("#", 1)[0].strip()
    if "@handoff:" in raw:
        return raw.split("@handoff:", 1)[0].strip()
    return raw


def _collect_ref_paths(items: Any) -> List[str]:
    paths: List[str] = []
    if not isinstance(items, list):
        return paths
    for item in items:
        if isinstance(item, str):
            path = _strip_ref_selector(item)
        elif isinstance(item, dict):
            path = _strip_ref_selector(str(item.get("ref") or ""))
        else:
            continue
        if path:
            paths.append(path)
    return paths


def _collect_string_set(items: Any) -> set[str]:
    values: set[str] = set()
    if not isinstance(items, list):
        return values
    for item in items:
        if not isinstance(item, str):
            continue
        value = item.strip()
        if value:
            values.add(value)
    return values


def validate_contract_data(payload: dict[str, Any], *, contract_path: Path | None = None) -> List[str]:
    errors: List[str] = []
    if not isinstance(payload, dict):
        return ["payload must be a JSON/YAML object"]

    schema = payload.get("schema")
    if schema not in SUPPORTED_SCHEMA_VERSIONS:
        errors.append("schema must be one of: " + ", ".join(SUPPORTED_SCHEMA_VERSIONS))
        return errors

    _require_fields(payload, REQUIRED_TOP_LEVEL, errors)

    skill_id = payload.get("skill_id")
    stage = payload.get("stage")
    if not isinstance(skill_id, str) or not skill_id.strip():
        errors.append("field skill_id must be non-empty string")
    if not isinstance(stage, str) or not stage.strip():
        errors.append("field stage must be non-empty string")

    if isinstance(contract_path, Path) and contract_path.name == "CONTRACT.yaml":
        stage_from_path = contract_path.parent.name
        if isinstance(stage, str) and stage and stage != stage_from_path:
            errors.append(f"field stage ({stage}) must match directory name ({stage_from_path})")

    _validate_list_of_strings(payload.get("entrypoints"), errors, field="entrypoints")

    reads = payload.get("reads")
    if not isinstance(reads, dict):
        errors.append("field reads must be object")
    else:
        _validate_read_items(reads.get("required"), errors, field="reads.required")
        _validate_read_items(reads.get("optional"), errors, field="reads.optional")

    writes = payload.get("writes")
    if not isinstance(writes, dict):
        errors.append("field writes must be object")
    else:
        _validate_list_of_strings(writes.get("files"), errors, field="writes.files")
        _validate_list_of_strings(writes.get("patterns"), errors, field="writes.patterns")
        _validate_read_items(writes.get("blocks"), errors, field="writes.blocks")
        via = writes.get("via")
        if not isinstance(via, dict):
            errors.append("field writes.via must be object")
        else:
            _validate_list_of_strings(via.get("docops_only"), errors, field="writes.via.docops_only")

    _validate_list_of_strings(payload.get("outputs"), errors, field="outputs")

    gates = payload.get("gates")
    if not isinstance(gates, dict):
        errors.append("field gates must be object")
    else:
        _validate_list_of_strings(gates.get("before"), errors, field="gates.before")
        _validate_list_of_strings(gates.get("after"), errors, field="gates.after")

    context_budget = payload.get("context_budget")
    if not isinstance(context_budget, dict):
        errors.append("field context_budget must be object")

    actions = payload.get("actions")
    if not isinstance(actions, dict):
        errors.append("field actions must be object")
    else:
        if actions.get("schema") != "aidd.actions.v1":
            errors.append("field actions.schema must be 'aidd.actions.v1'")
        required_value = actions.get("required")
        if not isinstance(required_value, bool):
            errors.append("field actions.required must be boolean")
        allowed_types = actions.get("allowed_types")
        if allowed_types is not None:
            _validate_list_of_strings(allowed_types, errors, field="actions.allowed_types")

    if isinstance(stage, str) and stage in {"implement", "review", "qa"}:
        required_paths = set(_collect_ref_paths((reads or {}).get("required") if isinstance(reads, dict) else []))
        if CANONICAL_READMAP_MD not in required_paths:
            errors.append(f"reads.required must include canonical path: {CANONICAL_READMAP_MD}")

        write_files = _collect_string_set((writes or {}).get("files") if isinstance(writes, dict) else [])
        for expected in CANONICAL_PREFLIGHT_FILES:
            if expected not in write_files:
                errors.append(f"writes.files must include canonical preflight artifact: {expected}")
        for legacy in LEGACY_PREFLIGHT_FILES:
            if legacy in write_files:
                errors.append(f"writes.files must not include legacy preflight artifact: {legacy}")

    return errors


def _iter_contract_paths(root: Path) -> Sequence[Path]:
    return sorted((root / "skills").glob("*/CONTRACT.yaml"))


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate AIDD skill CONTRACT.yaml files.")
    parser.add_argument("--contract", help="Path to CONTRACT.yaml file")
    parser.add_argument("--all", action="store_true", help="Validate all skills/*/CONTRACT.yaml")
    parser.add_argument("--quiet", action="store_true", help="Suppress OK output")
    parser.add_argument(
        "--print-supported-versions",
        action="store_true",
        help="Print supported schema versions and exit.",
    )
    return parser.parse_args(argv)


def _validate_one(path: Path) -> List[str]:
    payload = load_contract(path)
    return validate_contract_data(payload, contract_path=path)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.print_supported_versions:
        values = ",".join(aidd_schemas.supported_schema_versions("aidd.skill_contract.v"))
        print(values)
        return 0

    root = _repo_root()
    paths: list[Path] = []
    if args.all:
        paths.extend(_iter_contract_paths(root))
    if args.contract:
        paths.append(Path(args.contract).resolve())

    if not paths:
        print("[skill-contract-validate] ERROR: pass --contract <path> or --all", file=sys.stderr)
        return 2

    failed = False
    seen: set[Path] = set()
    for path in paths:
        if path in seen:
            continue
        seen.add(path)
        if not path.exists():
            print(f"[skill-contract-validate] ERROR: missing contract: {path}", file=sys.stderr)
            failed = True
            continue
        try:
            errors = _validate_one(path)
        except ValidationError as exc:
            print(f"[skill-contract-validate] ERROR: {path}: {exc}", file=sys.stderr)
            failed = True
            continue
        if errors:
            failed = True
            for err in errors:
                print(f"[skill-contract-validate] ERROR: {path}: {err}", file=sys.stderr)
            continue
        if not args.quiet:
            print(f"[skill-contract-validate] OK: {path}")

    return 2 if failed else 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
