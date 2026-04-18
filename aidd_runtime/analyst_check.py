from __future__ import annotations

import argparse
import sys

try:
    from ._bootstrap import ensure_repo_root
except ImportError:  # pragma: no cover - direct script execution
    from _bootstrap import ensure_repo_root

ensure_repo_root(__file__)

from aidd_runtime import runtime
from aidd_runtime.analyst_guard import AnalystValidationError, load_settings, validate_prd


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate the analyst dialog (Вопрос/Ответ) for the active feature PRD.",
    )
    parser.add_argument(
        "--ticket",
        dest="ticket",
        help="Ticket identifier to validate (defaults to docs/.active.json).",
    )
    parser.add_argument(
        "--slug-hint",
        dest="slug_hint",
        help="Optional slug hint override for messaging (defaults to docs/.active.json if present).",
    )
    parser.add_argument(
        "--branch",
        help="Current Git branch used to evaluate config.gates analyst branch rules.",
    )
    parser.add_argument(
        "--allow-blocked",
        action="store_true",
        help="Allow PRD with Status: blocked (skip blocking).",
    )
    parser.add_argument(
        "--no-ready-required",
        action="store_true",
        help="Do not require PRD Status: READY.",
    )
    parser.add_argument(
        "--min-questions",
        type=int,
        help="Override minimum number of analyst questions.",
    )
    parser.add_argument(
        "--docs-only",
        action="store_true",
        help="Enable docs-only rewrite mode for this invocation.",
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
    settings = load_settings(target)
    docs_only_mode = runtime.docs_only_mode_requested(explicit=getattr(args, "docs_only", False))
    try:
        summary = validate_prd(
            target,
            ticket,
            settings=settings,
            branch=args.branch,
            require_ready_override=False if args.no_ready_required else None,
            allow_blocked_override=True if args.allow_blocked else None,
            min_questions_override=args.min_questions,
        )
    except AnalystValidationError as exc:
        runtime.maybe_sync_index(target, ticket, context.slug_hint, reason="idea-analyst-check")
        if docs_only_mode:
            print(
                "[aidd] WARN: docs-only rewrite mode bypasses analyst validation blocker "
                f"(diagnostics={str(exc).strip() or 'validation_error'}).",
                file=sys.stderr,
            )
            return 0
        raise RuntimeError(str(exc)) from exc
    runtime.maybe_sync_index(target, ticket, context.slug_hint, reason="idea-analyst-check")

    if summary.status is None:
        print("[aidd] analyst gate disabled; nothing to validate.")
        return 0

    label = runtime.format_ticket_label(context, fallback=ticket)
    print(f"[aidd] analyst dialog ready for `{label}` "
          f"(status: {summary.status}, questions: {summary.question_count}).")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
