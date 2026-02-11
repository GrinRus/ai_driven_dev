from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from pathlib import Path

_PLUGIN_ROOT = Path(__file__).resolve().parents[3]
os.environ.setdefault("CLAUDE_PLUGIN_ROOT", str(_PLUGIN_ROOT))
if str(_PLUGIN_ROOT) not in sys.path:
    sys.path.insert(0, str(_PLUGIN_ROOT))

from aidd_runtime import actions_validate
from aidd_runtime import launcher
from aidd_runtime import runtime

DEFAULT_STAGE = "implement"
_ALLOWED_ACTION_TYPES = [
    "tasklist_ops.set_iteration_done",
    "tasklist_ops.append_progress_log",
    "tasklist_ops.next3_recompute",
    "context_pack_ops.context_pack_update",
]


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate implement actions payload with the Python-only stage run contract.",
    )
    parser.add_argument("--ticket", help="Ticket identifier override.")
    parser.add_argument("--scope-key", dest="scope_key", help="Scope key override.")
    parser.add_argument("--work-item-key", dest="work_item_key", help="Work item key override.")
    parser.add_argument("--stage", help="Stage override (defaults to implement).")
    parser.add_argument("--actions", help="Explicit actions payload path.")
    return parser.parse_args(argv)


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
    if rc != 0:
        return rc

    print(f"log_path={runtime.rel_path(log_path, context.root)}")
    if not actions_provided:
        print(f"actions_path={runtime.rel_path(actions_path, context.root)}")
    print("summary=actions validated")
    return 0


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    context = launcher.resolve_context(
        ticket=args.ticket,
        scope_key=args.scope_key,
        work_item_key=args.work_item_key,
        stage=args.stage,
        default_stage=DEFAULT_STAGE,
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
    return result.exit_code


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
