#!/usr/bin/env python3
"""Machine-readable artifact quality audit wrapper for AIDD workspaces."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Iterable


def _repo_root() -> Path:
    try:
        from aidd_runtime import repo_paths as _repo_paths

        return _repo_paths.repo_root(__file__)
    except Exception:
        here = Path(__file__).resolve()
        for candidate in (here.parent, *here.parents):
            if (candidate / ".claude-plugin").is_dir() and (candidate / "skills").is_dir():
                return candidate
        return here.parents[3]


if __package__ in {None, ""}:
    _ROOT_FOR_SYS_PATH = _repo_root()
    if str(_ROOT_FOR_SYS_PATH) not in sys.path:
        sys.path.insert(0, str(_ROOT_FOR_SYS_PATH))

from aidd_runtime import artifact_truth
from aidd_runtime.io_utils import utc_timestamp


_TEMPLATE_CODES = {"template_leakage", "context_template_leakage"}
_STATUS_CODES = {"status_drift"}
_SERIOUS_CODES = {
    "missing_expected_report",
    "tasklist_ready_without_actual_downstream_reports",
    "stale_reference",
    "template_leakage",
    "context_template_leakage",
    "status_drift",
    "expected_report_drift",
}
_ACTION_HINTS = {
    "missing_expected_report": "Generate or restore the missing downstream reports before trusting tasklist readiness.",
    "tasklist_ready_without_actual_downstream_reports": "Reconcile READY tasklist state with actual downstream artifacts and rerun the audit.",
    "stale_reference": "Fix broken front-matter references so documents point to existing canonical artifacts.",
    "template_leakage": "Replace leaked template placeholders in the tasklist before reusing the artifact.",
    "context_template_leakage": "Rebuild the rolling context pack from canonical sources to remove template contamination.",
    "status_drift": "Align top-level Status with review subsections so readiness signals stay deterministic.",
    "stage_doc_drift": "Sync docs/.active.json stage with the tasklist context pack before further loop work.",
    "active_stage_vs_plan_mismatch": "Bring the plan review status back to READY before treating loop stages as active.",
    "expected_report_drift": "Normalize ExpectedReports entries to canonical aidd/reports/** paths.",
    "test_execution_contract_weak": "Repair malformed AIDD:TEST_EXECUTION entries before using test metadata in downstream gates.",
}


def resolve_aidd_root(raw_root: Path) -> Path:
    candidate = raw_root.expanduser().resolve()
    if candidate.name == "aidd" and (candidate / "docs").exists():
        return candidate
    nested = candidate / "aidd"
    if nested.is_dir() and (nested / "docs").exists():
        return nested
    return candidate


def discover_actual_reports(aidd_root: Path) -> list[str]:
    reports_root = aidd_root / "reports"
    if not reports_root.exists():
        return []
    allowed_suffixes = {".json", ".jsonl", ".md"}
    discovered: list[str] = []
    for path in sorted(reports_root.rglob("*")):
        if not path.is_file():
            continue
        if path.suffix.lower() not in allowed_suffixes:
            continue
        rel = Path("aidd") / path.relative_to(aidd_root)
        discovered.append(rel.as_posix())
    return discovered


def _filter_checks(truth_checks: Iterable[dict[str, Any]], codes: set[str]) -> list[dict[str, Any]]:
    return [dict(item) for item in truth_checks if str(item.get("code") or "") in codes]


def _severity_counts(truth_checks: Iterable[dict[str, Any]]) -> dict[str, int]:
    counts = {"error": 0, "warn": 0}
    for item in truth_checks:
        severity = str(item.get("severity") or "").strip().lower()
        if severity in counts:
            counts[severity] += 1
    return counts


def determine_artifact_quality_gate(truth_checks: list[dict[str, Any]]) -> str:
    if any(str(item.get("severity") or "").strip().lower() == "error" for item in truth_checks):
        return "FAIL"
    if any(str(item.get("code") or "").strip() in _SERIOUS_CODES for item in truth_checks):
        return "WARN"
    if truth_checks:
        return "WARN"
    return "PASS"


def build_recommended_next_actions(truth_checks: list[dict[str, Any]]) -> list[str]:
    actions: list[str] = []
    seen: set[str] = set()
    for item in truth_checks:
        code = str(item.get("code") or "").strip()
        hint = _ACTION_HINTS.get(code)
        if not hint or hint in seen:
            continue
        seen.add(hint)
        actions.append(hint)
    if not actions:
        if truth_checks:
            actions.append(
                "Inspect truth_checks in the artifact audit output and reconcile the reported inconsistencies "
                "before trusting downstream readiness."
            )
        else:
            actions.append("No artifact issues detected; the current artifact set is internally consistent.")
    return actions


def build_summary(
    *,
    input_root: Path,
    ticket: str,
    actual_reports: list[str] | None = None,
) -> dict[str, Any]:
    aidd_root = resolve_aidd_root(input_root)
    discovered_reports = actual_reports if actual_reports is not None else discover_actual_reports(aidd_root)
    truth_payload = artifact_truth.evaluate_artifact_truth(aidd_root, ticket, actual_reports=discovered_reports)
    truth_checks = [dict(item) for item in truth_payload.get("truth_checks") or [] if isinstance(item, dict)]

    return {
        "schema": "aidd.artifact_audit.summary.v1",
        "pack_version": "1",
        "generated_at": utc_timestamp(),
        "ticket": ticket,
        "input_root": str(input_root.resolve()),
        "artifact_root": str(aidd_root),
        "artifact_quality_gate": determine_artifact_quality_gate(truth_checks),
        "severity_counts": _severity_counts(truth_checks),
        "doc_statuses": truth_payload.get("doc_statuses") or {},
        "actual_reports": truth_payload.get("actual_reports") or [],
        "expected_reports": truth_payload.get("expected_reports") or [],
        "expected_reports_required_now": truth_payload.get("expected_reports_required_now") or [],
        "missing_expected_reports": truth_payload.get("missing_expected_reports") or [],
        "template_leakage": _filter_checks(truth_checks, _TEMPLATE_CODES),
        "status_drift": _filter_checks(truth_checks, _STATUS_CODES),
        "stale_references": _filter_checks(truth_checks, {"stale_reference"}),
        "truth_checks": truth_checks,
        "recommended_next_actions": build_recommended_next_actions(truth_checks),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit AIDD artifact consistency and quality.")
    parser.add_argument("--root", required=True, help="Workspace root or direct aidd root.")
    parser.add_argument("--ticket", required=True, help="Feature ticket to audit.")
    parser.add_argument(
        "--actual-report",
        action="append",
        default=[],
        help="Optional explicit report path(s) relative to workspace, repeatable.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    input_root = Path(args.root).expanduser().resolve()
    actual_reports = [str(item).strip() for item in args.actual_report or [] if str(item).strip()]
    payload = build_summary(input_root=input_root, ticket=str(args.ticket), actual_reports=actual_reports or None)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
