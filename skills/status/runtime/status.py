from __future__ import annotations

import argparse
import json

from aidd_runtime import runtime


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Show summary for a ticket (index + recent events).",
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
        "--refresh",
        action="store_true",
        help="Rebuild index before showing status.",
    )
    parser.add_argument(
        "--events",
        type=int,
        default=5,
        help="Number of recent events to show (default: 5).",
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
    slug = context.slug_hint or ticket

    from aidd_runtime import index_sync as _index_sync
    from aidd_runtime.reports import events as _events
    from aidd_runtime.reports import tests_log as _tests_log

    index_path = target / "docs" / "index" / f"{ticket}.json"
    if args.refresh or not index_path.exists():
        _index_sync.write_index(target, ticket, slug)

    try:
        index_payload = json.loads(index_path.read_text(encoding="utf-8"))
    except Exception:
        index_payload = {}

    stage = index_payload.get("stage") or ""
    summary = index_payload.get("summary") or ""
    print(f"[status] {ticket}" + (f" (stage: {stage})" if stage else ""))
    if summary:
        print(f"- Summary: {summary}")
    updated = index_payload.get("updated")
    if updated:
        print(f"- Updated: {updated}")
    artifacts = index_payload.get("artifacts") or []
    if artifacts:
        print("- Artifacts:")
        for item in artifacts:
            print(f"  - {item}")
    reports = index_payload.get("reports") or []
    if reports:
        print("- Reports:")
        for item in reports:
            print(f"  - {item}")
    next3 = index_payload.get("next3") or []
    if next3:
        print("- AIDD:NEXT_3:")
        for item in next3:
            print(f"  - {item}")
    open_questions = index_payload.get("open_questions") or []
    if open_questions:
        print("- Open questions:")
        for item in open_questions:
            print(f"  - {item}")
    risks = index_payload.get("risks_top5") or []
    if risks:
        print("- Risks:")
        for item in risks:
            print(f"  - {item}")
    checks = index_payload.get("checks") or []
    if checks:
        print("- Checks:")
        for item in checks:
            name = item.get("name") if isinstance(item, dict) else None
            status = item.get("status") if isinstance(item, dict) else None
            path = item.get("path") if isinstance(item, dict) else None
            label = f"{name}: {status}" if name else str(item)
            if path:
                label += f" ({path})"
            print(f"  - {label}")

    events = _events.read_events(target, ticket, limit=args.events)
    if events:
        print("- Events:")
        for entry in events:
            line = f"{entry.get('ts')} [{entry.get('type')}]"
            status = entry.get("status")
            if status:
                line += f" {status}"
            details = entry.get("details")
            if isinstance(details, dict) and details.get("summary"):
                line += f" — {details.get('summary')}"
            print(f"  - {line}")
    test_events = _tests_log.read_log(target, ticket, limit=args.events)
    if test_events:
        print("- Tests log:")
        for entry in test_events:
            timestamp = entry.get("updated_at") or entry.get("ts") or ""
            stage = entry.get("stage") or ""
            scope_key = entry.get("scope_key") or ""
            label = entry.get("status") or entry.get("result") or ""
            line = f"{timestamp} [{label}]"
            if stage:
                line += f" stage={stage}"
            if scope_key:
                line += f" scope={scope_key}"
            details = entry.get("details")
            if isinstance(details, dict) and details.get("summary"):
                line += f" — {details.get('summary')}"
            print(f"  - {line}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
