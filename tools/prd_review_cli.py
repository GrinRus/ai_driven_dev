from __future__ import annotations

from pathlib import Path
from typing import Optional

from tools import prd_review
from tools import runtime


def main(argv: Optional[list[str]] = None) -> int:
    args = prd_review.parse_args(argv)
    _, target = runtime.require_workflow_root(Path(args.target).resolve())
    args.target = str(target)
    exit_code = prd_review.run(args)
    if exit_code == 0:
        context = runtime.resolve_feature_context(
            target,
            ticket=getattr(args, "ticket", None),
            slug_hint=getattr(args, "slug_hint", None),
        )
        ticket = (context.resolved_ticket or "").strip()
        if ticket:
            slug_hint = (context.slug_hint or ticket).strip() or ticket
            runtime.maybe_sync_index(target, ticket, slug_hint, reason="prd-review")
    return exit_code


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
