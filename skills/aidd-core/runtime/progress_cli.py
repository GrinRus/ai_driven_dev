from __future__ import annotations

import argparse
import json
from typing import Sequence

from aidd_runtime import progress as _progress
from aidd_runtime import runtime


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Check that docs/tasklist/<ticket>.md has new completed items after code changes.",
    )
    parser.add_argument(
        "--ticket",
        dest="ticket",
        help="Ticket identifier to use (defaults to docs/.active.json).",
    )
    parser.add_argument(
        "--slug-hint",
        dest="slug_hint",
        help="Optional slug hint override used for messaging.",
    )
    parser.add_argument(
        "--branch",
        help="Current Git branch used to evaluate branch/skip rules in config/gates.json.",
    )
    parser.add_argument(
        "--source",
        choices=("manual", "implement", "qa", "review", "gate", "handoff"),
        default="manual",
        help="Source label stored in events (default: manual).",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print JSON result to stdout instead of human-readable text.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print details about modified files and new tasklist items.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    _, target = runtime.require_workflow_root()

    context = runtime.resolve_feature_context(
        target,
        ticket=getattr(args, "ticket", None),
        slug_hint=getattr(args, "slug_hint", None),
    )
    ticket = context.resolved_ticket
    branch = args.branch or runtime.detect_branch(target)
    config = _progress.ProgressConfig.load(target)
    result = _progress.check_progress(
        root=target,
        ticket=ticket,
        slug_hint=context.slug_hint,
        source=args.source,
        branch=branch,
        config=config,
    )

    try:
        from aidd_runtime.reports import events as _events

        _events.append_event(
            target,
            ticket=ticket or "",
            slug_hint=context.slug_hint,
            event_type="progress",
            status=result.status,
            details={
                "source": args.source,
                "message": result.message,
                "code_files": len(result.code_files),
                "new_items": len(result.new_items),
            },
            source="aidd progress",
        )
    except Exception:
        pass
    try:
        if result.status == "ok":
            runtime.maybe_write_test_checkpoint(target, ticket, context.slug_hint, args.source)
    except Exception:
        pass
    runtime.maybe_sync_index(target, ticket, context.slug_hint, reason="progress")

    if args.json:
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
        return result.exit_code()

    def _print_items(items: Sequence[str], prefix: str = "  - ", limit: int = 5) -> None:
        for index, item in enumerate(items):
            if index == limit:
                remaining = len(items) - limit
                print(f"{prefix}… (+{remaining})")
                break
            print(f"{prefix}{item}")

    if result.status.startswith("error:"):
        print(result.message or "BLOCK: проверка прогресса не пройдена.")
        if args.verbose and result.code_files:
            print("Изменённые файлы:")
            _print_items(result.code_files)
        return result.exit_code()

    if result.status.startswith("skip:"):
        print(result.message or "Прогресс-чек пропущен.")
        if args.verbose and result.code_files:
            print("Изменённые файлы:")
            _print_items(result.code_files)
        return 0

    label = runtime.format_ticket_label(context)
    print(f"✅ Прогресс tasklist для `{label}` подтверждён.")
    if result.new_items:
        print("Новые чекбоксы:")
        _print_items(result.new_items)
    if args.verbose and result.code_files:
        print("Затронутые файлы:")
        _print_items(result.code_files)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
