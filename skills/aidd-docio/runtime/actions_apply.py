#!/usr/bin/env python3
"""Apply AIDD actions via DocOps and write apply log."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List

from aidd_runtime import actions_validate
from aidd_runtime import docops
from aidd_runtime import io_utils
from aidd_runtime import memory_common
from aidd_runtime import memory_verify
from aidd_runtime import runtime
from aidd_runtime.io_utils import utc_timestamp


def _normalize_text(value: object) -> str:
    return memory_common.normalize_text(value)


def _coalesce(*values: object) -> str:
    for value in values:
        text = _normalize_text(value)
        if text:
            return text
    return ""


def _memory_alternatives(raw: object) -> List[str]:
    if isinstance(raw, list):
        values = [_normalize_text(item) for item in raw]
        return memory_common.dedupe_preserve_order(item for item in values if item)
    if isinstance(raw, str):
        return memory_common.dedupe_preserve_order(item.strip() for item in raw.split(",") if item.strip())
    return []


def _apply_memory_decision_append(
    root: Path,
    *,
    ticket: str,
    stage: str,
    scope_key: str,
    params: Dict[str, object],
) -> tuple[str, bool, bool]:
    topic = _coalesce(params.get("topic"))
    decision_text = _coalesce(params.get("decision"))
    if not topic:
        return "memory decision append requires topic", False, True
    if not decision_text:
        return "memory decision append requires decision", False, True

    payload: Dict[str, object] = {
        "schema": memory_common.SCHEMA_DECISION,
        "schema_version": memory_common.SCHEMA_DECISION,
        "ts": utc_timestamp(),
        "ticket": ticket,
        "scope_key": scope_key,
        "stage": stage,
        "decision_id": _coalesce(
            params.get("decision_id"),
            memory_common.stable_id(ticket, topic.lower(), decision_text.lower()),
        ),
        "topic": topic,
        "decision": decision_text,
        "alternatives": _memory_alternatives(params.get("alternatives")),
        "rationale": _coalesce(params.get("rationale")),
        "source_path": _coalesce(params.get("source_path"), f"aidd/reports/context/{ticket}.pack.md"),
        "status": _coalesce(params.get("status"), "active").lower(),
    }
    supersedes = _coalesce(params.get("supersedes"))
    if supersedes:
        payload["supersedes"] = supersedes

    errors = memory_verify.validate_decision_data(payload)
    if errors:
        return "; ".join(errors), False, True

    log_path = memory_common.decision_log_path(root, ticket)
    io_utils.append_jsonl(log_path, payload)
    return f"memory decision appended ({runtime.rel_path(log_path, root)})", True, False


def _apply_action(
    root: Path,
    ticket: str,
    action: Dict[str, object],
    *,
    stage: str,
    scope_key: str,
) -> tuple[str, bool, bool]:
    action_type = str(action.get("type", ""))
    params = action.get("params") or {}
    if not isinstance(params, dict):
        params = {}

    if action_type == "tasklist_ops.set_iteration_done":
        item_id = str(params.get("item_id", ""))
        kind = str(params.get("kind", "iteration"))
        result = docops.tasklist_set_iteration_done(root, ticket, item_id, kind=kind)
        return result.message, result.changed, result.error
    if action_type == "tasklist_ops.append_progress_log":
        entry = {
            "date": params.get("date"),
            "source": str(params.get("source", "")).lower(),
            "item_id": params.get("item_id"),
            "kind": str(params.get("kind", "")).lower(),
            "hash": params.get("hash"),
            "link": params.get("link"),
            "msg": params.get("msg"),
        }
        result = docops.tasklist_append_progress_log(root, ticket, entry)
        return result.message, result.changed, result.error
    if action_type == "tasklist_ops.next3_recompute":
        result = docops.tasklist_next3_recompute(root, ticket)
        return result.message, result.changed, result.error
    if action_type == "context_pack_ops.context_pack_update":
        result = docops.context_pack_update(root, ticket, params)
        return result.message, result.changed, result.error
    if action_type == "memory_ops.decision_append":
        return _apply_memory_decision_append(
            root,
            ticket=ticket,
            stage=stage,
            scope_key=scope_key,
            params=params,
        )

    return f"unsupported action type: {action_type}", False, True


def _apply_actions(root: Path, payload: Dict[str, object], apply_log: Path) -> List[Dict[str, object]]:
    ticket = str(payload.get("ticket") or "")
    stage = str(payload.get("stage") or "")
    scope_key = str(payload.get("scope_key") or "")
    actions = payload.get("actions") or []
    if not isinstance(actions, list):
        raise ValueError("actions must be a list")

    results: List[Dict[str, object]] = []
    for idx, action in enumerate(actions):
        if not isinstance(action, dict):
            results.append(
                {
                    "timestamp": utc_timestamp(),
                    "index": idx,
                    "type": "",
                    "status": "error",
                    "message": "action must be object",
                }
            )
            continue
        action_type = str(action.get("type", ""))
        try:
            message, changed, errored = _apply_action(
                root,
                ticket,
                action,
                stage=stage,
                scope_key=scope_key,
            )
            if errored:
                status = "error"
            else:
                status = "applied" if changed else "skipped"
        except Exception as exc:  # pragma: no cover - defensive
            message = f"exception: {exc}"
            status = "error"
        results.append(
            {
                "timestamp": utc_timestamp(),
                "index": idx,
                "type": action_type,
                "status": status,
                "message": message,
            }
        )
    if not results:
        results.append(
            {
                "timestamp": utc_timestamp(),
                "index": 0,
                "type": "(none)",
                "status": "skipped",
                "message": "no actions to apply",
            }
        )

    apply_log.parent.mkdir(parents=True, exist_ok=True)
    with apply_log.open("a", encoding="utf-8") as fh:
        for entry in results:
            fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return results


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Apply AIDD actions via DocOps.")
    parser.add_argument("--actions", required=True, help="Path to actions.json file")
    parser.add_argument("--apply-log", default=None, help="Override apply log path")
    parser.add_argument("--root", default=None, help="Workflow root (aidd/) override")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    actions_path = Path(args.actions)
    try:
        payload = actions_validate.load_actions(actions_path)
    except actions_validate.ValidationError as exc:
        print(f"[actions-apply] ERROR: {exc}", file=sys.stderr)
        return 2
    errors = actions_validate.validate_actions_data(payload)
    if errors:
        for err in errors:
            print(f"[actions-apply] ERROR: {err}", file=sys.stderr)
        return 2

    if args.root:
        root = Path(args.root).resolve()
    else:
        _, root = runtime.require_workflow_root(Path.cwd())

    ticket = str(payload.get("ticket") or "")
    scope_key = str(payload.get("scope_key") or "")
    stage = str(payload.get("stage") or "")

    if args.apply_log:
        apply_log = Path(args.apply_log)
    else:
        apply_log = root / "reports" / "actions" / ticket / scope_key / f"{stage}.apply.jsonl"

    results = _apply_actions(root, payload, apply_log)
    status = "ok" if all(entry.get("status") != "error" for entry in results) else "error"
    print(f"[actions-apply] {status}: {runtime.rel_path(apply_log, root)}")
    return 0 if status == "ok" else 2


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
