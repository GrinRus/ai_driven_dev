#!/usr/bin/env python3
"""Apply AIDD actions via DocOps and write apply log."""

from __future__ import annotations

import argparse
import io
import json
import os
import sys
from contextlib import contextmanager, redirect_stderr, redirect_stdout
from pathlib import Path
from typing import Dict, Iterator, List


def _ensure_plugin_root_on_path() -> None:
    env_root = os.environ.get("CLAUDE_PLUGIN_ROOT", "").strip()
    if env_root:
        root = Path(env_root).resolve()
        if (root / "aidd_runtime").is_dir():
            if str(root) not in sys.path:
                sys.path.insert(0, str(root))
            return

    probe = Path(__file__).resolve()
    for parent in (probe.parent, *probe.parents):
        if (parent / "aidd_runtime").is_dir():
            os.environ.setdefault("CLAUDE_PLUGIN_ROOT", str(parent))
            if str(parent) not in sys.path:
                sys.path.insert(0, str(parent))
            return


_ensure_plugin_root_on_path()

from aidd_runtime import actions_validate
from aidd_runtime import decision_append
from aidd_runtime import docops
from aidd_runtime import memory_pack
from aidd_runtime import runtime
from aidd_runtime.io_utils import utc_timestamp


def _derive_ticket_from_actions_path(path: Path) -> str:
    parts = list(path.parts)
    for idx, part in enumerate(parts):
        if part != "actions":
            continue
        if idx + 1 < len(parts):
            value = str(parts[idx + 1]).strip()
            if value:
                return value
    return ""


@contextmanager
def _pushd(path: Path) -> Iterator[None]:
    previous = Path.cwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(previous)


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
    if action_type == "memory_ops.decision_append":
        title = str(params.get("title") or "").strip()
        decision = str(params.get("decision") or "").strip()
        if not title or not decision:
            return "memory decision append requires title and decision", False, True
        argv: List[str] = ["--ticket", ticket, "--title", title, "--decision", decision]
        rationale = str(params.get("rationale") or "").strip()
        if rationale:
            argv.extend(["--rationale", rationale])
        decision_id = str(params.get("decision_id") or "").strip()
        if decision_id:
            argv.extend(["--decision-id", decision_id])
        stage = str(params.get("stage") or "").strip()
        if stage:
            argv.extend(["--stage", stage])
        scope_key = str(params.get("scope_key") or "").strip()
        if scope_key:
            argv.extend(["--scope-key", scope_key])
        source = str(params.get("source") or "").strip()
        if source:
            argv.extend(["--source", source])
        status = str(params.get("status") or "").strip()
        if status:
            argv.extend(["--status", status])
        for field in ("tags", "supersedes", "conflicts_with"):
            value = params.get(field)
            if isinstance(value, list):
                rendered = ",".join(str(item).strip() for item in value if str(item).strip())
                if rendered:
                    flag = "--conflicts-with" if field == "conflicts_with" else f"--{field}"
                    argv.extend([flag, rendered])

        with _pushd(root):
            append_stdout = io.StringIO()
            append_stderr = io.StringIO()
            with redirect_stdout(append_stdout), redirect_stderr(append_stderr):
                append_rc = int(decision_append.main(argv))
            if append_rc != 0:
                detail = append_stderr.getvalue().strip() or append_stdout.getvalue().strip() or f"exit={append_rc}"
                return f"memory decision append failed: {detail}", False, True

            pack_stdout = io.StringIO()
            pack_stderr = io.StringIO()
            with redirect_stdout(pack_stdout), redirect_stderr(pack_stderr):
                pack_rc = int(memory_pack.main(["--ticket", ticket]))
            if pack_rc != 0:
                detail = pack_stderr.getvalue().strip() or pack_stdout.getvalue().strip() or f"exit={pack_rc}"
                return f"memory decision pack rebuild failed: {detail}", True, True

        return "memory decision appended", True, False

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


def parse_args(argv: list[str] | None = None) -> tuple[argparse.Namespace, list[str]]:
    parser = argparse.ArgumentParser(description="Apply AIDD actions via DocOps.")
    parser.add_argument("--actions", required=True, help="Path to actions.json file")
    parser.add_argument("--apply-log", default=None, help="Override apply log path")
    parser.add_argument("--root", default=None, help="Workflow root (aidd/) override")
    args, unknown = parser.parse_known_args(argv)
    return args, list(unknown)


def main(argv: list[str] | None = None) -> int:
    args, unknown_args = parse_args(argv)
    if unknown_args:
        rendered = " ".join(str(item) for item in unknown_args if str(item).strip())
        if not rendered:
            rendered = "<empty>"
        print(
            "[actions-apply] BLOCK: invalid cli arguments "
            "(reason_code=runtime_cli_contract_mismatch): "
            f"unrecognized arguments: {rendered}. "
            "Allowed flags: --actions, --apply-log, --root.",
            file=sys.stderr,
        )
        return 2
    actions_path = Path(args.actions)
    ticket_hint = _derive_ticket_from_actions_path(actions_path)
    next_action_hint = (
        f" Next action: `/feature-dev-aidd:tasks-new {ticket_hint}`."
        if ticket_hint
        else ""
    )
    try:
        payload = actions_validate.load_actions(actions_path)
    except actions_validate.ValidationError as exc:
        print(
            f"[actions-apply] BLOCK: invalid actions payload (reason_code=contract_mismatch_actions_shape): "
            f"{exc}.{next_action_hint}",
            file=sys.stderr,
        )
        return 2
    errors = actions_validate.validate_actions_data(payload)
    if errors:
        for err in errors:
            print(
                "[actions-apply] BLOCK: invalid actions payload "
                f"(reason_code=contract_mismatch_actions_shape): {err}.{next_action_hint}",
                file=sys.stderr,
            )
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
