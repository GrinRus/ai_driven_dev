from __future__ import annotations

import sys
from pathlib import Path

try:
    from aidd_runtime._bootstrap import ensure_repo_root
except ImportError:  # pragma: no cover - direct script execution
    from _bootstrap import ensure_repo_root

ensure_repo_root(__file__)

from aidd_runtime import launcher  # noqa: E402
from aidd_runtime import runtime  # noqa: E402
from aidd_runtime import stage_actions_run  # noqa: E402

DEFAULT_STAGE = "review"
DESCRIPTION = "Validate review actions payload with canonical aidd.actions.v1 contract and fail-fast diagnostics."


def parse_args(argv: list[str] | None = None):
    return stage_actions_run.parse_args(
        argv,
        default_stage=DEFAULT_STAGE,
        description=DESCRIPTION,
    )


def _resolve_review_report_path(context: launcher.LaunchContext) -> Path:
    feature_context = runtime.resolve_feature_context(context.root, ticket=context.ticket)
    slug = (feature_context.slug_hint or context.ticket).strip() or context.ticket
    report_template = runtime.review_report_template(context.root)
    if "{scope_key}" not in report_template:
        report_template = runtime.DEFAULT_REVIEW_REPORT
    report_rel = (
        str(report_template)
        .replace("{ticket}", context.ticket)
        .replace("{slug}", slug)
        .replace("{scope_key}", context.scope_key)
    )
    return runtime.resolve_path_for_target(Path(report_rel), context.root)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    context = launcher.resolve_context(
        ticket=args.ticket,
        scope_key=args.scope_key,
        work_item_key=args.work_item_key,
        stage=args.stage,
        default_stage=DEFAULT_STAGE,
    )
    docs_only_mode = runtime.docs_only_mode_requested(explicit=getattr(args, "docs_only", False))
    report_path = _resolve_review_report_path(context)
    if not report_path.exists() and not docs_only_mode:
        report_rel = runtime.rel_path(report_path, context.root)
        print("[aidd] ERROR: reason_code=review_report_missing", file=sys.stderr)
        print(f"[aidd] ERROR: report_path={report_rel}", file=sys.stderr)
        print(
            "[aidd] ERROR: diagnostics=canonical_review_report_required",
            file=sys.stderr,
        )
        return 2
    if not report_path.exists() and docs_only_mode:
        report_rel = runtime.rel_path(report_path, context.root)
        print(
            f"[aidd] WARN: docs-only rewrite mode bypasses missing review report ({report_rel}).",
            file=sys.stderr,
        )
    return stage_actions_run.main(
        argv,
        default_stage=DEFAULT_STAGE,
        description=DESCRIPTION,
    )


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
