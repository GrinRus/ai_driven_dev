from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

try:
    from aidd_runtime._bootstrap import ensure_repo_root
except ImportError:  # pragma: no cover - direct script execution
    from _bootstrap import ensure_repo_root

ensure_repo_root(__file__)

from aidd_runtime import rlm_finalize  # noqa: E402
from aidd_runtime import runtime  # noqa: E402
from aidd_runtime.research_guard import (  # noqa: E402
    ResearchCheckSummary,
    ResearchValidationError,
    _extract_status,
    _normalize_research_status,
    load_settings,
    validate_research,
)

_REASON_CODE_RE = re.compile(r"reason_code=([a-z0-9_:-]+)", re.IGNORECASE)


def _extract_reason_code(message: str) -> str:
    match = _REASON_CODE_RE.search(str(message or ""))
    if not match:
        return ""
    return str(match.group(1) or "").strip().lower()


def _is_downstream_soft_mode(expected_stage: str) -> bool:
    return str(expected_stage or "").strip().lower() in {"plan", "review", "qa"}


def _soft_pending_summary(status: str = "pending", reason_code: str = "rlm_status_pending") -> ResearchCheckSummary:
    return ResearchCheckSummary(
        status=status,
        warnings=[
            "downstream_research_gate_softened",
            f"downstream_research_gate_softened:{reason_code}",
        ],
    )


def _read_research_doc_status(target: Path, ticket: str) -> str:
    doc_path = target / "docs" / "research" / f"{ticket}.md"
    try:
        text = doc_path.read_text(encoding="utf-8")
    except Exception:
        return ""
    normalized, _marker = _normalize_research_status(_extract_status(text))
    return str(normalized or "").strip().lower()


def _is_softenable_reason(
    *,
    target: Path,
    ticket: str,
    expected_stage: str,
    reason_code: str,
) -> bool:
    if not _is_downstream_soft_mode(expected_stage):
        return False
    if reason_code in {"rlm_status_pending", "rlm_links_empty_warn"}:
        return True
    if reason_code != "research_status_invalid":
        return False
    return _read_research_doc_status(target, ticket) in {"pending", "warn"}


def _enforce_minimum_rlm_artifacts(target: Path, ticket: str) -> None:
    required = [
        target / "reports" / "research" / f"{ticket}-rlm-targets.json",
        target / "reports" / "research" / f"{ticket}-rlm-manifest.json",
        target / "reports" / "research" / f"{ticket}-rlm.worklist.pack.json",
        target / "reports" / "research" / f"{ticket}-rlm.pack.json",
    ]
    missing = [runtime.rel_path(path, target) for path in required if not path.exists()]
    if missing:
        raise RuntimeError(
            "BLOCK: missing mandatory RLM artifacts for plan gate "
            f"(reason_code=research_artifacts_missing): {', '.join(missing)}"
        )
    for path in required:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            raise RuntimeError(
                "BLOCK: invalid RLM artifact JSON "
                f"(reason_code=research_artifacts_invalid): {runtime.rel_path(path, target)} ({exc})"
            ) from exc
        if not isinstance(payload, dict):
            raise RuntimeError(
                "BLOCK: invalid RLM artifact payload "
                f"(reason_code=research_artifacts_invalid): {runtime.rel_path(path, target)} (expected object)"
            )
    nodes_path = target / "reports" / "research" / f"{ticket}-rlm.nodes.jsonl"
    if not nodes_path.exists():
        raise RuntimeError(
            "BLOCK: missing mandatory RLM artifacts for plan gate "
            f"(reason_code=research_artifacts_missing): {runtime.rel_path(nodes_path, target)}"
        )
    try:
        has_node = any(line.strip() for line in nodes_path.read_text(encoding="utf-8").splitlines())
    except Exception as exc:
        raise RuntimeError(
            "BLOCK: invalid RLM artifact payload "
            f"(reason_code=research_artifacts_invalid): {runtime.rel_path(nodes_path, target)} ({exc})"
        ) from exc
    if not has_node:
        raise RuntimeError(
            "BLOCK: missing mandatory RLM artifacts for plan gate "
            f"(reason_code=research_artifacts_missing): {runtime.rel_path(nodes_path, target)} (empty)"
        )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate the Researcher report status for the active feature.",
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
        help="Current Git branch used to evaluate config.gates researcher branch rules.",
    )
    parser.add_argument(
        "--expected-stage",
        choices=("research", "plan", "review", "qa", "implement"),
        default="plan",
        help="Stage context override for downstream research validation (default: plan).",
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
        summary = validate_research(
            target,
            ticket,
            settings=settings,
            branch=args.branch,
            expected_stage=args.expected_stage,
            allow_scoped_links_empty_warn=args.expected_stage in {"plan", "review", "qa"},
        )
    except ResearchValidationError as exc:
        reason_code = _extract_reason_code(str(exc))
        if not _is_softenable_reason(
            target=target,
            ticket=ticket,
            expected_stage=args.expected_stage,
            reason_code=reason_code,
        ):
            if docs_only_mode:
                print(
                    "[aidd] WARN: docs-only rewrite mode bypasses research gate blocker "
                    f"(diagnostics={str(exc).strip() or 'validation_error'}).",
                    file=sys.stderr,
                )
                return 0
            raise RuntimeError(str(exc)) from exc
        finalize_exit_code = rlm_finalize.main(["--ticket", ticket, "--emit-json"])
        if finalize_exit_code != 0:
            raise RuntimeError(
                f"{exc}\n[aidd] ERROR: reason_code={reason_code or 'research_gate'}_finalize_failed "
                f"(exit_code={finalize_exit_code})"
            ) from exc
        else:
            try:
                summary = validate_research(
                    target,
                    ticket,
                    settings=settings,
                    branch=args.branch,
                    expected_stage=args.expected_stage,
                    allow_scoped_links_empty_warn=args.expected_stage in {"plan", "review", "qa"},
                )
            except ResearchValidationError as retry_exc:
                retry_reason_code = _extract_reason_code(str(retry_exc))
                if not _is_softenable_reason(
                    target=target,
                    ticket=ticket,
                    expected_stage=args.expected_stage,
                    reason_code=retry_reason_code,
                ):
                    if docs_only_mode:
                        print(
                            "[aidd] WARN: docs-only rewrite mode bypasses research finalize blocker "
                            f"(diagnostics={str(retry_exc).strip() or 'validation_error'}).",
                            file=sys.stderr,
                        )
                        return 0
                    raise RuntimeError(
                        f"{exc}\n[aidd] INFO: auto_recovery_attempted=1 "
                            "(recovery_path=research_finalize_probe)\n"
                            f"{retry_exc}"
                        ) from retry_exc
                softened_status = _read_research_doc_status(target, ticket) or "pending"
                print(
                    "[aidd] WARN: downstream research gate softened after finalize probe "
                    f"(reason_code={retry_reason_code or reason_code or 'research_gate'}, "
                    "auto_recovery_attempted=1, policy=warn_continue).",
                    file=sys.stderr,
                )
                summary = _soft_pending_summary(
                    status=softened_status,
                    reason_code=retry_reason_code or reason_code or "research_gate",
                )
            else:
                print(
                    "[aidd] WARN: research gate auto-recovery applied "
                    f"(reason_code={reason_code or 'research_gate'}, recovery_path=research_finalize_probe).",
                    file=sys.stderr,
                )

    if summary.status is None:
        if summary.skipped_reason:
            print(f"[aidd] research gate skipped ({summary.skipped_reason}).")
        else:
            print("[aidd] research gate disabled; nothing to validate.")
        return 0

    try:
        _enforce_minimum_rlm_artifacts(target, ticket)
    except RuntimeError as exc:
        if docs_only_mode:
            print(
                "[aidd] WARN: docs-only rewrite mode bypasses missing/invalid RLM artifact blocker "
                f"(diagnostics={str(exc).strip()}).",
                file=sys.stderr,
            )
            return 0
        raise

    label = runtime.format_ticket_label(context, fallback=ticket)
    details = [f"status: {summary.status}"]
    if summary.path_count is not None:
        details.append(f"paths: {summary.path_count}")
    if summary.age_days is not None:
        details.append(f"age: {summary.age_days}d")
    print(f"[aidd] research gate OK for `{label}` ({', '.join(details)}).")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
