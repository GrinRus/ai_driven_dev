from __future__ import annotations

import argparse
import json

from aidd_runtime import runtime


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Append entry to tests JSONL log (aidd/reports/tests/<ticket>/<scope_key>.jsonl).",
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
        "--status",
        required=True,
        help="Status label for the test entry (pass|fail|skipped|...).",
    )
    parser.add_argument(
        "--stage",
        default="",
        help="Stage name for the entry (implement|review|qa).",
    )
    parser.add_argument(
        "--scope-key",
        default="",
        help="Scope key for per-work-item logs (defaults to active work item or ticket).",
    )
    parser.add_argument(
        "--work-item-key",
        default="",
        help="Optional work_item_key (iteration_id=... / id=...).",
    )
    parser.add_argument(
        "--profile",
        default="",
        help="Optional test profile (fast|targeted|full|none).",
    )
    parser.add_argument(
        "--tasks",
        default="",
        help="Optional test tasks (comma/space separated).",
    )
    parser.add_argument(
        "--filters",
        default="",
        help="Optional test filters (comma/space separated).",
    )
    parser.add_argument(
        "--exit-code",
        type=int,
        default=None,
        help="Optional exit code for the test run.",
    )
    parser.add_argument(
        "--log-path",
        default="",
        help="Optional path to the test log file.",
    )
    parser.add_argument(
        "--summary",
        default="",
        help="Optional summary string stored in details.summary.",
    )
    parser.add_argument(
        "--reason-code",
        default="",
        help="Optional machine-readable reason code (used for skipped entries).",
    )
    parser.add_argument(
        "--reason",
        default="",
        help="Optional human-readable reason (used for skipped entries).",
    )
    parser.add_argument(
        "--details",
        default="",
        help="Optional JSON object with extra fields for details.",
    )
    parser.add_argument(
        "--source",
        default="aidd tests-log",
        help="Optional source label stored in the log entry.",
    )
    parser.add_argument(
        "--cwd",
        default="",
        help="Optional cwd metadata.",
    )
    parser.add_argument(
        "--worktree",
        default="",
        help="Optional worktree metadata.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    _, target = runtime.require_workflow_root()
    ticket, context = runtime.require_ticket(
        target,
        ticket=getattr(args, "ticket", None),
        slug_hint=getattr(args, "slug_hint", None),
    )
    ticket_guess = ""
    if not getattr(args, "ticket", None) and not runtime.read_active_ticket(target) and context.slug_hint:
        ticket_guess = context.slug_hint
    details: dict = {}
    if args.summary:
        details["summary"] = args.summary
    if args.details:
        try:
            extra = json.loads(args.details)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid --details JSON: {exc}") from exc
        if isinstance(extra, dict):
            details.update(extra)
    from aidd_runtime.reports import tests_log as _tests_log

    stage = (args.stage or "").strip().lower()
    work_item_key = (args.work_item_key or "").strip()
    scope_key = (args.scope_key or "").strip()
    if not stage:
        stage = runtime.read_active_stage(target)
    if not scope_key:
        if stage == "qa":
            scope_key = runtime.resolve_scope_key("", ticket)
        else:
            active_work_item = runtime.read_active_work_item(target)
            scope_key = runtime.resolve_scope_key(active_work_item or work_item_key, ticket)

    tasks_list = [item for item in args.tasks.replace(",", " ").split() if item.strip()]
    filters_list = [item for item in args.filters.replace(",", " ").split() if item.strip()]

    _tests_log.append_log(
        target,
        ticket=ticket,
        slug_hint=context.slug_hint,
        ticket_guess=ticket_guess,
        status=args.status,
        stage=stage,
        scope_key=scope_key,
        work_item_key=work_item_key or None,
        profile=args.profile or None,
        tasks=tasks_list or None,
        filters=filters_list or None,
        exit_code=args.exit_code,
        log_path=args.log_path or None,
        reason_code=args.reason_code or None,
        reason=args.reason or None,
        details=details or None,
        source=args.source,
        cwd=args.cwd or None,
        worktree=args.worktree or None,
    )
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
