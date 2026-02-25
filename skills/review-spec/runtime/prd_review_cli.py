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
from aidd_runtime import ast_index
from aidd_runtime.research_guard import ResearchValidationError, load_settings as load_research_settings, validate_research
from aidd_runtime import runtime


def _resolve_report_target_path(target: Path, ticket: str, raw: object) -> Path:
    if raw:
        candidate = Path(str(raw))
        if candidate.is_absolute():
            return candidate.resolve()
        return runtime.resolve_path_for_target(candidate, target)
    return target / "reports" / "prd" / f"{ticket}.json"


def _ast_research_hint(ticket: str) -> str:
    return f"python3 ${{CLAUDE_PLUGIN_ROOT}}/skills/researcher/runtime/research.py --ticket {ticket} --auto"


def _enforce_ast_pack_policy(target: Path, ticket: str) -> int:
    cfg = ast_index.load_ast_index_config(target)
    if cfg.mode == "off":
        return 0
    ast_pack = target / "reports" / "research" / f"{ticket}-ast.pack.json"
    if not ast_pack.exists():
        if cfg.required:
            print(
                "[prd-review] ERROR: mandatory AST evidence pack missing "
                f"(reason_code=ast_index_pack_missing). Next action: `{_ast_research_hint(ticket)}`.",
                file=sys.stderr,
            )
            return 2
        print(
            "[prd-review] WARN: optional AST evidence pack missing "
            f"(reason_code=ast_index_pack_missing_warn). Hint: `{_ast_research_hint(ticket)}`.",
            file=sys.stderr,
        )
        return 0
    try:
        payload = json.loads(ast_pack.read_text(encoding="utf-8"))
    except Exception as exc:
        if cfg.required:
            print(
                "[prd-review] ERROR: mandatory AST evidence pack invalid JSON "
                f"(reason_code=ast_index_pack_invalid): {runtime.rel_path(ast_pack, target)} ({exc}). "
                f"Next action: `{_ast_research_hint(ticket)}`.",
                file=sys.stderr,
            )
            return 2
        print(
            "[prd-review] WARN: optional AST evidence pack invalid JSON "
            f"(reason_code=ast_index_pack_invalid_warn): {runtime.rel_path(ast_pack, target)}.",
            file=sys.stderr,
        )
        return 0
    if not isinstance(payload, dict):
        if cfg.required:
            print(
                "[prd-review] ERROR: mandatory AST evidence payload must be object "
                f"(reason_code=ast_index_pack_invalid): {runtime.rel_path(ast_pack, target)}. "
                f"Next action: `{_ast_research_hint(ticket)}`.",
                file=sys.stderr,
            )
            return 2
        print(
            "[prd-review] WARN: optional AST evidence payload must be object "
            f"(reason_code=ast_index_pack_invalid_warn): {runtime.rel_path(ast_pack, target)}.",
            file=sys.stderr,
        )
    return 0


def main(argv: Optional[list[str]] = None) -> int:
    args = prd_review.parse_args(argv)
    _, target = runtime.require_workflow_root()
    context = runtime.resolve_feature_context(
        target,
        ticket=getattr(args, "ticket", None),
        slug_hint=getattr(args, "slug_hint", None),
    )
    ticket = (context.resolved_ticket or "").strip()
    if ticket:
        research_settings = load_research_settings(target)
        try:
            validate_research(
                target,
                ticket,
                settings=research_settings,
                expected_stage="review",
            )
        except ResearchValidationError as exc:
            print(str(exc), file=sys.stderr)
            return 2
        ast_policy_code = _enforce_ast_pack_policy(target, ticket)
        if ast_policy_code != 0:
            return ast_policy_code
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
