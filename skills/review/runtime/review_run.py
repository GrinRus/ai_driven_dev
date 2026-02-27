from __future__ import annotations

import datetime as dt
import json
import os
import sys
from pathlib import Path

_PLUGIN_ROOT = Path(__file__).resolve().parents[3]
os.environ.setdefault("CLAUDE_PLUGIN_ROOT", str(_PLUGIN_ROOT))
if str(_PLUGIN_ROOT) not in sys.path:
    sys.path.insert(0, str(_PLUGIN_ROOT))

from aidd_runtime import launcher
from aidd_runtime import runtime
from aidd_runtime import stage_actions_run

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


def _ensure_review_report_exists(context: launcher.LaunchContext, report_path: Path) -> bool:
    if report_path.exists():
        return True
    now = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    feature_context = runtime.resolve_feature_context(context.root, ticket=context.ticket)
    slug = (feature_context.slug_hint or context.ticket).strip() or context.ticket
    payload = {
        "ticket": context.ticket,
        "slug": slug,
        "kind": "review",
        "stage": "review",
        "scope_key": context.scope_key,
        "work_item_key": context.work_item_key,
        "status": "WARN",
        "summary": "auto-generated placeholder review report",
        "generated_at": now,
        "updated_at": now,
        "findings": [],
        "blocking_findings_count": 0,
    }
    try:
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    except OSError:
        return False
    return True


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    context = launcher.resolve_context(
        ticket=args.ticket,
        scope_key=args.scope_key,
        work_item_key=args.work_item_key,
        stage=args.stage,
        default_stage=DEFAULT_STAGE,
    )
    report_path = _resolve_review_report_path(context)
    if not _ensure_review_report_exists(context, report_path):
        report_rel = runtime.rel_path(report_path, context.root)
        print("[aidd] ERROR: reason_code=review_report_missing", file=sys.stderr)
        print(f"[aidd] ERROR: report_path={report_rel}", file=sys.stderr)
        print(
            "[aidd] ERROR: diagnostics=canonical_review_report_bootstrap_failed",
            file=sys.stderr,
        )
        return 2
    if not report_path.exists():
        report_rel = runtime.rel_path(report_path, context.root)
        print(
            "[aidd] WARN: reason_code=review_report_missing_auto_generated",
            file=sys.stderr,
        )
        print(f"[aidd] WARN: report_path={report_rel}", file=sys.stderr)
    return stage_actions_run.main(
        argv,
        default_stage=DEFAULT_STAGE,
        description=DESCRIPTION,
    )


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
