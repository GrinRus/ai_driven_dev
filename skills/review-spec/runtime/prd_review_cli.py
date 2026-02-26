from __future__ import annotations

import io
import json
import os
import sys
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from typing import Optional

_PLUGIN_ROOT = Path(__file__).resolve().parents[3]
os.environ.setdefault("CLAUDE_PLUGIN_ROOT", str(_PLUGIN_ROOT))
if str(_PLUGIN_ROOT) not in sys.path:
    sys.path.insert(0, str(_PLUGIN_ROOT))

from aidd_runtime import prd_review
from aidd_runtime import ast_index
from aidd_runtime import memory_autoslice
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


def _run_memory_autoslice(*, target: Path, ticket: str, stage: str) -> dict[str, object]:
    scope_key = runtime.resolve_scope_key(runtime.read_active_work_item(target), ticket)
    outcome: dict[str, object] = {
        "status": "error",
        "reason_code": "",
        "manifest_pack": "",
        "stderr": "",
    }
    stdout_buffer = io.StringIO()
    stderr_buffer = io.StringIO()
    exit_code = 1
    try:
        with redirect_stdout(stdout_buffer), redirect_stderr(stderr_buffer):
            exit_code = int(
                memory_autoslice.main(
                    [
                        "--ticket",
                        ticket,
                        "--stage",
                        stage,
                        "--scope-key",
                        scope_key,
                        "--format",
                        "json",
                    ]
                )
            )
    except SystemExit as exc:
        try:
            exit_code = int(exc.code or 1)
        except (TypeError, ValueError):
            exit_code = 1
    except Exception as exc:  # pragma: no cover - defensive
        outcome["reason_code"] = "memory_autoslice_failed"
        outcome["stderr"] = str(exc)
        return outcome

    stderr_text = stderr_buffer.getvalue().strip()
    if stderr_text:
        outcome["stderr"] = stderr_text

    payload: dict[str, object] = {}
    stdout_text = stdout_buffer.getvalue().strip()
    if stdout_text:
        try:
            parsed = json.loads(stdout_text)
        except json.JSONDecodeError:
            parsed = None
        if isinstance(parsed, dict):
            payload = parsed
        else:
            for line in reversed(stdout_text.splitlines()):
                try:
                    parsed_line = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(parsed_line, dict):
                    payload = parsed_line
                    break
    status = str(payload.get("status") or "").strip().lower()
    outcome["status"] = status or ("ok" if exit_code == 0 else "error")
    outcome["reason_code"] = str(payload.get("reason_code") or "").strip()
    outcome["manifest_pack"] = str(payload.get("manifest_pack") or "").strip()
    if exit_code != 0 and outcome["status"] not in {"warn", "blocked"}:
        outcome["status"] = "error"
        if not outcome["reason_code"]:
            outcome["reason_code"] = "memory_autoslice_failed"
    return outcome


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
        autoslice = _run_memory_autoslice(target=target, ticket=ticket, stage="review-spec")
        autoslice_status = str(autoslice.get("status") or "error")
        autoslice_reason = str(autoslice.get("reason_code") or "").strip()
        if autoslice_status == "blocked":
            reason = autoslice_reason or "memory_slice_missing"
            print(
                "[prd-review] ERROR: memory autoslice blocked review-spec stage "
                f"(reason_code={reason}).",
                file=sys.stderr,
            )
            return 2
        if autoslice_status == "warn":
            reason = autoslice_reason or "memory_slice_missing_warn"
            print(
                "[prd-review] WARN: memory autoslice degraded "
                f"(reason_code={reason}).",
                file=sys.stderr,
            )
        elif autoslice_status != "ok":
            reason = autoslice_reason or "memory_autoslice_failed"
            print(
                "[prd-review] WARN: failed to materialize memory autoslice "
                f"(reason_code={reason}).",
                file=sys.stderr,
            )
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
