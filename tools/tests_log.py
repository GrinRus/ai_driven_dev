from __future__ import annotations

import argparse
import json

from tools import runtime


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Append entry to tests JSONL log (aidd/reports/tests/<ticket>.jsonl).",
    )
    parser.add_argument(
        "--ticket",
        dest="ticket",
        help="Ticket identifier (defaults to docs/.active_ticket).",
    )
    parser.add_argument(
        "--slug-hint",
        dest="slug_hint",
        help="Optional slug hint override (defaults to docs/.active_feature).",
    )
    parser.add_argument(
        "--status",
        required=True,
        help="Status label for the test entry (pass|fail|skipped|...).",
    )
    parser.add_argument(
        "--summary",
        default="",
        help="Optional summary string stored in details.summary.",
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
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    _, target = runtime.require_workflow_root()
    ticket, context = runtime.require_ticket(
        target,
        ticket=getattr(args, "ticket", None),
        slug_hint=getattr(args, "slug_hint", None),
    )
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
    from tools.reports import tests_log as _tests_log

    _tests_log.append_log(
        target,
        ticket=ticket,
        slug_hint=context.slug_hint,
        status=args.status,
        details=details or None,
        source=args.source,
    )
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
