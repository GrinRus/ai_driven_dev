from __future__ import annotations

import io
import json
import os
import re
import sys
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from typing import Any, Optional

_PLUGIN_ROOT = Path(__file__).resolve().parents[3]
os.environ.setdefault("CLAUDE_PLUGIN_ROOT", str(_PLUGIN_ROOT))
if str(_PLUGIN_ROOT) not in sys.path:
    sys.path.insert(0, str(_PLUGIN_ROOT))

from aidd_runtime import prd_review
from aidd_runtime import reports_pack
from aidd_runtime import rlm_finalize
from aidd_runtime import rlm_links_build
from aidd_runtime import runtime
from aidd_runtime.research_guard import (
    ResearchValidationError,
    load_settings as load_research_settings,
    validate_research,
)

_REASON_CODE_RE = re.compile(r"reason_code=([a-z0-9_:-]+)", re.IGNORECASE)


def _extract_reason_code(message: str) -> str:
    match = _REASON_CODE_RE.search(str(message or ""))
    if not match:
        return ""
    return str(match.group(1) or "").strip().lower()


def _invoke_runtime(main_fn: Any, argv: list[str]) -> tuple[int, str, str]:
    stdout_buffer = io.StringIO()
    stderr_buffer = io.StringIO()
    exit_code = 0
    try:
        with redirect_stdout(stdout_buffer), redirect_stderr(stderr_buffer):
            result = main_fn(argv)
        if isinstance(result, int):
            exit_code = int(result)
    except SystemExit as exc:
        code = exc.code
        if isinstance(code, int):
            exit_code = code
        elif code in (None, 0):
            exit_code = 0
        else:
            exit_code = 1
            stderr_buffer.write(str(code))
    except Exception as exc:  # pragma: no cover - defensive
        exit_code = 1
        stderr_buffer.write(str(exc))
    return exit_code, stdout_buffer.getvalue(), stderr_buffer.getvalue()


def _parse_last_json_line(text: str) -> dict[str, object]:
    for raw_line in reversed(str(text or "").splitlines()):
        line = raw_line.strip()
        if not line.startswith("{"):
            continue
        try:
            payload = json.loads(line)
        except Exception:
            continue
        if isinstance(payload, dict):
            return payload
    return {}


def _bounded_links_auto_heal(ticket: str) -> dict[str, object]:
    links_code, _, links_stderr = _invoke_runtime(rlm_links_build.main, ["--ticket", ticket])
    finalize_code, finalize_stdout, finalize_stderr = _invoke_runtime(
        rlm_finalize.main,
        ["--ticket", ticket, "--emit-json"],
    )
    finalize_payload = _parse_last_json_line(finalize_stdout)
    return {
        "auto_recovery_attempted": True,
        "recovery_path": "review_spec_links_build_then_finalize",
        "links_build_exit_code": links_code,
        "links_build_stderr_tail": "\n".join(str(links_stderr).splitlines()[-3:]).strip(),
        "finalize_exit_code": finalize_code,
        "finalize_reason_code": str(finalize_payload.get("reason_code") or "").strip(),
        "finalize_status": str(finalize_payload.get("status") or "").strip(),
        "finalize_next_action": str(finalize_payload.get("next_action") or "").strip(),
        "finalize_empty_reason": str(finalize_payload.get("empty_reason") or "").strip(),
        "finalize_stderr_tail": "\n".join(str(finalize_stderr).splitlines()[-3:]).strip(),
    }


def _resolve_report_target_path(target: Path, ticket: str, raw: object) -> Path:
    if raw:
        candidate = Path(str(raw))
        if candidate.is_absolute():
            return candidate.resolve()
        return runtime.resolve_path_for_target(candidate, target)
    return target / "reports" / "prd" / f"{ticket}.json"


def _persist_review_research_warning(
    *,
    target: Path,
    report_path: Path,
    evidence: dict[str, object],
) -> None:
    if not report_path.exists():
        return
    try:
        payload = json.loads(report_path.read_text(encoding="utf-8"))
    except Exception:
        return
    if not isinstance(payload, dict):
        return
    payload["research_validation"] = {
        "status": "warn",
        "reason_code": "rlm_links_empty_warn",
        **evidence,
    }
    report_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    # report_path can be either raw <ticket>.json or already-packed <ticket>.pack.json.
    # Re-packing the latter treats pack payload as raw and can corrupt findings columns.
    if report_path.suffix == ".json" and not report_path.name.endswith(".pack.json"):
        try:
            reports_pack.write_prd_pack(report_path, root=target)
        except Exception:
            pass


def main(argv: Optional[list[str]] = None) -> int:
    args = prd_review.parse_args(argv)
    _, target = runtime.require_workflow_root()
    context = runtime.resolve_feature_context(
        target,
        ticket=getattr(args, "ticket", None),
        slug_hint=getattr(args, "slug_hint", None),
    )
    ticket = (context.resolved_ticket or "").strip()
    review_research_warn: dict[str, object] = {}
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
            message = str(exc)
            if _extract_reason_code(message) != "rlm_links_empty_warn":
                print(message, file=sys.stderr)
                return 2
            recovery = _bounded_links_auto_heal(ticket)
            try:
                validate_research(
                    target,
                    ticket,
                    settings=research_settings,
                    expected_stage="review",
                    allow_review_links_empty_warn=True,
                    auto_recovery_attempted=True,
                )
            except ResearchValidationError as retry_exc:
                print(str(retry_exc), file=sys.stderr)
                return 2
            review_research_warn = {
                "reason_code": "rlm_links_empty_warn",
                "non_blocking": True,
                **recovery,
            }
            print(
                "[prd-review] WARN: review-spec continues with non-blocking rlm links warning "
                f"(reason_code=rlm_links_empty_warn, auto_recovery_attempted=1, "
                f"links_build_exit={recovery.get('links_build_exit_code')}, "
                f"finalize_exit={recovery.get('finalize_exit_code')}, "
                f"finalize_reason_code={recovery.get('finalize_reason_code') or '-'})",
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
            if bool(getattr(args, "require_ready", False)):
                recommended_status = str(
                    payload.get("recommended_status") or payload.get("status") or ""
                ).strip().lower()
                if recommended_status != "ready":
                    print(
                        "[prd-review] ERROR: ready-path requires READY report "
                        "(reason_code=review_not_ready, "
                        f"recommended_status={recommended_status or '-'})",
                        file=sys.stderr,
                    )
                    return 2
            if review_research_warn:
                _persist_review_research_warning(
                    target=target,
                    report_path=required_path,
                    evidence=review_research_warn,
                )
            runtime.maybe_sync_index(target, ticket, slug_hint, reason="prd-review")
    return exit_code


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
