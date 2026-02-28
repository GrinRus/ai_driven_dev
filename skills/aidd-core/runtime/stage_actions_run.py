from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path
from typing import Any

from aidd_runtime import actions_validate
from aidd_runtime import launcher
from aidd_runtime import runtime

_ALLOWED_ACTION_TYPES = [
    "tasklist_ops.set_iteration_done",
    "tasklist_ops.append_progress_log",
    "tasklist_ops.next3_recompute",
    "context_pack_ops.context_pack_update",
]
_CONTRACT_MISMATCH_REASON_CODE = "contract_mismatch_actions_shape"
_ACTION_PARAM_KEYS = (
    "date",
    "source",
    "item_id",
    "kind",
    "hash",
    "msg",
    "link",
    "read_log",
    "read_next",
    "artefact_links",
    "what_to_do",
    "user_note",
    "generated_at",
)


def _find_first_action_type_mismatch(payload: Any, *, known_types: set[str]) -> str:
    if not isinstance(payload, dict):
        return "payload:not_object"
    schema_version = str(payload.get("schema_version") or "").strip()
    if schema_version != "aidd.actions.v1":
        rendered = schema_version or "<missing>"
        return f"schema_version='{rendered}':expected='aidd.actions.v1'"
    allowed_types = payload.get("allowed_action_types")
    if not isinstance(allowed_types, list):
        return "allowed_action_types:<missing_or_invalid>"
    normalized_allowed: set[str] = set()
    for idx, raw in enumerate(allowed_types):
        if not isinstance(raw, str):
            return f"allowed_action_types[{idx}]={raw!r}:not_string"
        value = str(raw)
        if value not in known_types:
            return f"allowed_action_types[{idx}]='{value}':unsupported_type"
        normalized_allowed.add(value)
    actions = payload.get("actions")
    if not isinstance(actions, list):
        return "actions:<missing_or_invalid>"
    for idx, action in enumerate(actions):
        if not isinstance(action, dict):
            return f"actions[{idx}]:not_object"
        action_type = action.get("type")
        if not isinstance(action_type, str) or not action_type.strip():
            return f"actions[{idx}].type=<missing_or_invalid>"
        value = str(action_type)
        if value not in known_types:
            return f"actions[{idx}].type='{value}':unsupported_type"
        if value not in normalized_allowed:
            return f"actions[{idx}].type='{value}':not_allowed_by_payload"
    return ""


def _build_actions_contract_diagnostics(actions_path: Path, *, context: launcher.LaunchContext) -> list[str]:
    supported = sorted(str(item) for item in getattr(actions_validate, "KNOWN_TYPES", set()) if str(item).strip())
    if not supported:
        supported = list(_ALLOWED_ACTION_TYPES)
    known_types = set(supported)
    lines: list[str] = [f"supported_action_types={','.join(supported)}"]
    try:
        payload: Any = json.loads(actions_path.read_text(encoding="utf-8"))
    except OSError as exc:
        lines.append(f"first_action_type_mismatch=payload_read_error:{exc}")
    except json.JSONDecodeError as exc:
        lines.append(f"first_action_type_mismatch=payload_json_error:{exc}")
    else:
        mismatch = _find_first_action_type_mismatch(payload, known_types=known_types)
        if mismatch:
            lines.append(f"first_action_type_mismatch={mismatch}")
    example_payload = {
        "schema_version": "aidd.actions.v1",
        "stage": context.stage,
        "ticket": context.ticket,
        "scope_key": context.scope_key,
        "work_item_key": context.work_item_key,
        "allowed_action_types": supported,
        "actions": [
            {
                "type": "tasklist_ops.append_progress_log",
                "params": {
                    "date": "1970-01-01",
                    "source": "implement",
                    "item_id": "iteration_id=I1",
                    "kind": "iteration",
                    "hash": "sha256:example",
                    "msg": "progress update",
                },
            }
        ],
    }
    lines.append(
        "canonical_example_aidd_actions_v1="
        + json.dumps(example_payload, ensure_ascii=False, separators=(",", ":"))
    )
    return lines


def build_parser(*, default_stage: str, description: str) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("--ticket", help="Ticket identifier override.")
    parser.add_argument("--scope-key", dest="scope_key", help="Scope key override.")
    parser.add_argument("--work-item-key", dest="work_item_key", help="Work item key override.")
    parser.add_argument("--stage", help=f"Stage override (defaults to {default_stage}).")
    parser.add_argument("--actions", help="Explicit actions payload path.")
    return parser


def parse_args(
    argv: list[str] | None = None,
    *,
    default_stage: str,
    description: str,
) -> argparse.Namespace:
    return build_parser(default_stage=default_stage, description=description).parse_args(argv)


def _resolve_actions_path(raw: str, root: Path) -> Path:
    candidate = Path(raw).expanduser()
    if candidate.is_absolute():
        return candidate.resolve()
    resolved = (Path.cwd() / candidate).resolve()
    if resolved.exists() or str(raw).startswith("."):
        return resolved
    return runtime.resolve_path_for_target(candidate, root)


def _write_default_actions(path: Path, *, stage: str, ticket: str, scope_key: str, work_item_key: str) -> None:
    payload = {
        "schema_version": "aidd.actions.v1",
        "stage": stage,
        "ticket": ticket,
        "scope_key": scope_key,
        "work_item_key": work_item_key,
        "allowed_action_types": list(_ALLOWED_ACTION_TYPES),
        "actions": [],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _canonicalize_actions_payload_once(path: Path, *, context: launcher.LaunchContext) -> tuple[bool, str]:
    try:
        payload: Any = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        return False, f"read_error:{exc}"
    except json.JSONDecodeError as exc:
        return False, f"invalid_json:{exc}"
    if not isinstance(payload, dict):
        return False, "payload_not_object"

    changed = False

    if not payload.get("schema_version") and isinstance(payload.get("schema"), str):
        payload["schema_version"] = str(payload.get("schema") or "")
        changed = True
    if payload.get("schema_version") != "aidd.actions.v1":
        payload["schema_version"] = "aidd.actions.v1"
        changed = True

    expected = {
        "stage": context.stage,
        "ticket": context.ticket,
        "scope_key": context.scope_key,
        "work_item_key": context.work_item_key,
    }
    for key, expected_value in expected.items():
        if str(payload.get(key) or "") != expected_value:
            payload[key] = expected_value
            changed = True

    allowed_action_types = payload.get("allowed_action_types")
    if not isinstance(allowed_action_types, list) or not all(isinstance(item, str) for item in allowed_action_types):
        payload["allowed_action_types"] = list(_ALLOWED_ACTION_TYPES)
        changed = True
    else:
        normalized_allowed: list[str] = []
        for item in allowed_action_types:
            text = str(item or "")
            if text in _ALLOWED_ACTION_TYPES and text not in normalized_allowed:
                normalized_allowed.append(text)
        if not normalized_allowed:
            normalized_allowed = list(_ALLOWED_ACTION_TYPES)
        if normalized_allowed != allowed_action_types:
            payload["allowed_action_types"] = normalized_allowed
            changed = True

    actions = payload.get("actions")
    if not isinstance(actions, list):
        payload["actions"] = []
        actions = []
        changed = True

    normalized_actions: list[Any] = []
    for raw_action in actions:
        if not isinstance(raw_action, dict):
            normalized_actions.append(raw_action)
            continue
        action = dict(raw_action)
        if "type" not in action and isinstance(action.get("action"), str):
            action["type"] = str(action.pop("action") or "")
            changed = True
        params = action.get("params")
        if not isinstance(params, dict):
            normalized_params: dict[str, Any] = {}
            for key in _ACTION_PARAM_KEYS:
                if key in action:
                    normalized_params[key] = action.pop(key)
                    changed = True
            action["params"] = normalized_params
            changed = True
        normalized_actions.append(action)
    if normalized_actions != actions:
        payload["actions"] = normalized_actions
        changed = True

    if not changed:
        return False, "no_changes_applied"

    try:
        path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    except OSError as exc:
        return False, f"write_error:{exc}"
    return True, "canonicalized_once"


def _run(args: argparse.Namespace, *, context: launcher.LaunchContext, log_path: Path) -> int:
    paths = launcher.actions_paths(context)
    actions_provided = bool(args.actions)
    if actions_provided:
        actions_path = _resolve_actions_path(str(args.actions), context.root)
    else:
        actions_path = paths["actions_path"]

    if not actions_path.exists():
        template_path = paths["actions_template"]
        if template_path.exists():
            actions_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(template_path, actions_path)
        else:
            _write_default_actions(
                actions_path,
                stage=context.stage,
                ticket=context.ticket,
                scope_key=context.scope_key,
                work_item_key=context.work_item_key,
            )

    rc = actions_validate.main(["--actions", str(actions_path)])
    retry_applied = False
    retry_diag = ""
    if rc != 0:
        retry_applied, retry_diag = _canonicalize_actions_payload_once(actions_path, context=context)
        if retry_applied:
            rc = actions_validate.main(["--actions", str(actions_path)])
    if rc != 0:
        reason = retry_diag or "validate_failed_without_retry"
        rel_actions = runtime.rel_path(actions_path, context.root)
        print(f"[aidd] ERROR: reason_code={_CONTRACT_MISMATCH_REASON_CODE}", file=sys.stderr)
        print(f"[aidd] ERROR: diagnostics=actions_contract_retry_failed:{reason}", file=sys.stderr)
        print(f"[aidd] ERROR: actions_path={rel_actions}", file=sys.stderr)
        for entry in _build_actions_contract_diagnostics(actions_path, context=context):
            print(f"[aidd] ERROR: {entry}", file=sys.stderr)
        return rc
    print(f"log_path={runtime.rel_path(log_path, context.root)}")
    if not actions_provided:
        print(f"actions_path={runtime.rel_path(actions_path, context.root)}")
    if retry_applied:
        print("actions_contract_retry=1")
    print("summary=actions validated")
    return 0


def main(
    argv: list[str] | None = None,
    *,
    default_stage: str,
    description: str,
) -> int:
    args = parse_args(argv, default_stage=default_stage, description=description)
    context = launcher.resolve_context(
        ticket=args.ticket,
        scope_key=args.scope_key,
        work_item_key=args.work_item_key,
        stage=args.stage,
        default_stage=default_stage,
    )
    log_path = launcher.log_path(context.root, context.stage, context.ticket, context.scope_key, "run")
    result = launcher.run_guarded(
        lambda: _run(args, context=context, log_path=log_path),
        log_path_value=log_path,
    )
    if result.stdout:
        sys.stdout.write(result.stdout)
    if result.stderr:
        sys.stderr.write(result.stderr)
    if result.launcher_error_reason:
        marker = f"[aidd] ERROR: reason_code={result.launcher_error_reason}\n"
        if marker not in result.stderr:
            sys.stderr.write(marker)
    return result.exit_code
