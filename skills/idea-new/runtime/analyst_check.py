from __future__ import annotations

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from aidd_runtime import analyst_check as _impl

AnalystValidationError = _impl.AnalystValidationError
load_settings = _impl.load_settings
parse_args = _impl.parse_args
runtime = _impl.runtime
validate_prd = _impl.validate_prd


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
