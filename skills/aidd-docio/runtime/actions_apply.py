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
from aidd_runtime import runtime
from aidd_runtime.io_utils import utc_timestamp


def _apply_action(root: Path, ticket: str, action: Dict[str, object]) -> tuple[str, bool, bool]:
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

    return f"unsupported action type: {action_type}", False, True


def _apply_actions(root: Path, payload: Dict[str, object], apply_log: Path) -> List[Dict[str, object]]:
    ticket = str(payload.get("ticket") or "")
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
            message, changed, errored = _apply_action(root, ticket, action)
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
