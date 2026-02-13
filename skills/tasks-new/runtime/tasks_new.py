from __future__ import annotations

import argparse
import os
import sys
from datetime import date
from pathlib import Path

_PLUGIN_ROOT = Path(__file__).resolve().parents[3]
os.environ.setdefault("CLAUDE_PLUGIN_ROOT", str(_PLUGIN_ROOT))
if str(_PLUGIN_ROOT) not in sys.path:
    sys.path.insert(0, str(_PLUGIN_ROOT))

from aidd_runtime import runtime
from aidd_runtime import tasklist_check


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Ensure tasklist artifact exists for the active ticket and run tasklist validation.",
    )
    parser.add_argument(
        "--ticket",
        dest="ticket",
        help="Ticket identifier (defaults to docs/.active.json).",
    )
    parser.add_argument(
        "--slug-hint",
        dest="slug_hint",
        help="Optional slug hint override (defaults to docs/.active.json).",
    )
    parser.add_argument(
        "--tasklist",
        dest="tasklist_path",
        help="Optional tasklist path override (defaults to docs/tasklist/<ticket>.md).",
    )
    parser.add_argument(
        "--force-template",
        action="store_true",
        help="Rewrite tasklist from template even when the file already exists.",
    )
    parser.add_argument(
        "--strict",
        dest="strict",
        action="store_true",
        default=True,
        help="Return non-zero when tasklist-check returns an error (default).",
    )
    parser.add_argument(
        "--no-strict",
        dest="strict",
        action="store_false",
        help="Allow execution to continue even when tasklist-check returns an error.",
    )
    return parser.parse_args(argv)


def _replace_placeholders(text: str, ticket: str, slug: str, today: str, scope_key: str) -> str:
    return (
        text.replace("<ABC-123>", ticket)
        .replace("<short-slug>", slug)
        .replace("<YYYY-MM-DD>", today)
        .replace("<scope_key>", scope_key)
    )


def _resolve_tasklist_path(target: Path, override: str | None, ticket: str) -> Path:
    if not override:
        return target / "docs" / "tasklist" / f"{ticket}.md"
    candidate = Path(override)
    if candidate.is_absolute():
        return candidate
    return runtime.resolve_path_for_target(candidate, target)


def _validate_tasklist_postcondition(tasklist_path: Path) -> tuple[bool, str]:
    if not tasklist_path.exists():
        return False, "tasklist_missing"
    try:
        text = tasklist_path.read_text(encoding="utf-8")
    except OSError:
        return False, "tasklist_unreadable"
    if not text.strip():
        return False, "tasklist_empty"
    return True, ""


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    _, target = runtime.require_workflow_root()
    ticket, context = runtime.require_ticket(
        target,
        ticket=getattr(args, "ticket", None),
        slug_hint=getattr(args, "slug_hint", None),
    )
    slug = (context.slug_hint or ticket).strip() or ticket
    today = date.today().isoformat()
    scope_key = runtime.resolve_scope_key(work_item_key=None, ticket=ticket)

    plugin_root = runtime.require_plugin_root()
    template_path = plugin_root / "skills" / "tasks-new" / "templates" / "tasklist.template.md"
    if not template_path.exists():
        raise FileNotFoundError(f"tasklist template not found: {template_path}")
    template_text = template_path.read_text(encoding="utf-8")

    tasklist_path = _resolve_tasklist_path(target, getattr(args, "tasklist_path", None), ticket)
    tasklist_path.parent.mkdir(parents=True, exist_ok=True)

    created = not tasklist_path.exists()
    if created or args.force_template:
        rendered = _replace_placeholders(template_text, ticket, slug, today, scope_key)
        tasklist_path.write_text(rendered, encoding="utf-8")
    else:
        current = tasklist_path.read_text(encoding="utf-8")
        updated = _replace_placeholders(current, ticket, slug, today, scope_key)
        if updated != current:
            tasklist_path.write_text(updated, encoding="utf-8")

    result = tasklist_check.check_tasklist(target, ticket)
    rel_path = runtime.rel_path(tasklist_path, target)
    print(f"[tasks-new] tasklist: {rel_path}")
    if result.status == "ok":
        print("[tasks-new] tasklist-check: ok")
    elif result.status == "warn":
        print("[tasks-new] tasklist-check: warn", file=sys.stderr)
        for detail in result.details or []:
            print(f"[tasks-new] {detail}", file=sys.stderr)
    elif result.status == "error":
        print("[tasks-new] tasklist-check: error", file=sys.stderr)
        print(f"[tasks-new] {result.message}", file=sys.stderr)
        for detail in result.details or []:
            print(f"[tasks-new] {detail}", file=sys.stderr)
        print(
            f"[tasks-new] remediation: fix plan/spec/tasklist prerequisites and rerun /feature-dev-aidd:tasks-new {ticket}",
            file=sys.stderr,
        )
        allow_error_success = os.getenv("AIDD_ALLOW_TASKLIST_ERROR_SUCCESS", "").strip() == "1"
        if args.strict or not allow_error_success:
            return result.exit_code()
        print(
            "[tasks-new] WARN: non-strict success override enabled "
            "(AIDD_ALLOW_TASKLIST_ERROR_SUCCESS=1).",
            file=sys.stderr,
        )
    else:
        print(f"[tasks-new] tasklist-check: {result.status}")

    ok_postcondition, postcondition_code = _validate_tasklist_postcondition(tasklist_path)
    if not ok_postcondition:
        print(
            "[tasks-new] ERROR: mandatory tasklist artifact postcondition failed "
            f"(reason_code={postcondition_code}): {runtime.rel_path(tasklist_path, target)}",
            file=sys.stderr,
        )
        return 2

    runtime.maybe_sync_index(target, ticket, slug, reason="tasks-new")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
