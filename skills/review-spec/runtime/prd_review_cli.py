from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Optional

_PLUGIN_ROOT = Path(__file__).resolve().parents[3]
os.environ.setdefault("CLAUDE_PLUGIN_ROOT", str(_PLUGIN_ROOT))
if str(_PLUGIN_ROOT) not in sys.path:
    sys.path.insert(0, str(_PLUGIN_ROOT))

from aidd_runtime import prd_review
from aidd_runtime import runtime


def _resolve_report_target_path(target: Path, ticket: str, raw: object) -> Path:
    if raw:
        candidate = Path(str(raw))
        if candidate.is_absolute():
            return candidate.resolve()
        return runtime.resolve_path_for_target(candidate, target)
    return target / "reports" / "prd" / f"{ticket}.json"


def main(argv: Optional[list[str]] = None) -> int:
    args = prd_review.parse_args(argv)
    _, target = runtime.require_workflow_root()
    pack_only_requested = bool(getattr(args, "pack_only", False) or os.getenv("AIDD_PACK_ONLY", "").strip() == "1")
    raw_report_arg = getattr(args, "report", None)
    explicit_pack_report_arg = False
    if pack_only_requested and raw_report_arg:
        report_text = str(raw_report_arg)
        if report_text.endswith(".pack.json"):
            # Keep canonical producer semantics in prd_review.run (report=<base>.json),
            # but preserve operator intent to verify the explicit .pack.json output path.
            setattr(args, "report", Path(report_text[: -len(".pack.json")] + ".json"))
            explicit_pack_report_arg = True
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
            report_path = _resolve_report_target_path(target, ticket, getattr(args, "report", None))
            pack_only = pack_only_requested
            if pack_only and explicit_pack_report_arg:
                required_path = _resolve_report_target_path(target, ticket, raw_report_arg)
            elif pack_only and report_path.name.endswith(".pack.json"):
                required_path = report_path
            else:
                required_path = report_path.with_suffix(".pack.json") if pack_only else report_path
            if not required_path.exists():
                print(
                    "[prd-review] ERROR: mandatory review artifact missing "
                    f"(reason_code=review_artifacts_missing): {runtime.rel_path(required_path, target)}",
                    file=sys.stderr,
                )
                return 2
            try:
                payload = json.loads(required_path.read_text(encoding="utf-8"))
            except Exception as exc:
                print(
                    "[prd-review] ERROR: mandatory review artifact invalid JSON "
                    f"(reason_code=review_artifacts_invalid): {runtime.rel_path(required_path, target)} ({exc})",
                    file=sys.stderr,
                )
                return 2
            if not isinstance(payload, dict):
                print(
                    "[prd-review] ERROR: mandatory review artifact payload must be object "
                    f"(reason_code=review_artifacts_invalid): {runtime.rel_path(required_path, target)}",
                    file=sys.stderr,
                )
                return 2
            runtime.maybe_sync_index(target, ticket, slug_hint, reason="prd-review")
    return exit_code


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
