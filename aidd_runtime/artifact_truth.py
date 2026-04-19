from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Sequence

from aidd_runtime import gates
from aidd_runtime import runtime
from aidd_runtime import tasklist_check
from aidd_runtime import tasklist_parser
from aidd_runtime.plan_review_gate import parse_review_section as parse_plan_review_section
from aidd_runtime.prd_review_section import extract_prd_review_section

DEFAULT_POLICY = {
    "mode": "soft",
    "collapse_event_noise": True,
    "warn_on_missing_expected_reports": True,
    "warn_on_stage_doc_drift": True,
}

_STATUS_RE = re.compile(r"^\s*status\s*:\s*([A-Za-z][A-Za-z0-9_-]*)", re.IGNORECASE | re.MULTILINE)
_PATH_FIELD_KEYS = ("PRD", "Plan", "Research")
_SKIP_REFERENCE_VALUES = {"", "none", "n/a", "na", "-", "missing"}


def load_artifact_truth_config(root: Path) -> dict[str, Any]:
    config = gates.load_gates_config(root)
    raw = config.get("artifact_truth") if isinstance(config, dict) else {}
    if not isinstance(raw, dict):
        raw = {}
    merged = dict(DEFAULT_POLICY)
    merged.update(raw)
    mode = str(merged.get("mode") or "soft").strip().lower()
    merged["mode"] = mode if mode in {"soft", "hard"} else "soft"
    for key in ("collapse_event_noise", "warn_on_missing_expected_reports", "warn_on_stage_doc_drift"):
        merged[key] = bool(merged.get(key, DEFAULT_POLICY[key]))
    return merged


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""


def _parse_front_matter_tree(text: str) -> dict[str, Any]:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}
    end_idx = None
    for idx in range(1, len(lines)):
        if lines[idx].strip() == "---":
            end_idx = idx
            break
    if end_idx is None:
        return {}

    payload: dict[str, Any] = {}
    current_map_key: str | None = None
    for raw in lines[1:end_idx]:
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if raw[:1].isspace() and current_map_key and ":" in stripped:
            key, value = stripped.split(":", 1)
            nested = payload.get(current_map_key)
            if not isinstance(nested, dict):
                nested = {}
                payload[current_map_key] = nested
            nested[key.strip()] = value.strip()
            continue
        current_map_key = None
        if ":" not in stripped:
            continue
        key, value = stripped.split(":", 1)
        key = key.strip()
        value = value.strip()
        if value:
            payload[key] = value
            continue
        payload[key] = {}
        current_map_key = key
    return payload


def _normalize_doc_status(value: str) -> str:
    raw = str(value or "").strip()
    if not raw:
        return "UNKNOWN"
    token = raw.split()[0].strip("()[]{}.,;:")
    return token.upper() if token else "UNKNOWN"


def _normalize_stage(value: str) -> str:
    raw = str(value or "").strip().lower()
    return raw or "unknown"


def _front_path_to_abs(root: Path, raw: str) -> Path | None:
    value = str(raw or "").strip()
    if not value:
        return None
    lowered = value.lower()
    if lowered in _SKIP_REFERENCE_VALUES:
        return None
    if "<" in value or ">" in value:
        return None
    if "/" not in value and not value.endswith((".md", ".yaml", ".yml", ".json", ".jsonl")):
        return None
    try:
        return runtime.resolve_path_for_target(Path(value), root)
    except Exception:
        return None


def _front_path_to_rel(root: Path, raw: str) -> str:
    path = _front_path_to_abs(root, raw)
    if not path:
        return ""
    return runtime.rel_path(path, root)


def _extract_expected_reports(front: dict[str, Any], root: Path) -> list[str]:
    for key in ("ExpectedReports", "Reports", "expected_reports", "reports"):
        raw = front.get(key)
        if isinstance(raw, dict):
            values = raw.values()
        elif isinstance(raw, list):
            values = raw
        elif raw:
            values = [raw]
        else:
            continue
        paths: list[str] = []
        for value in values:
            rel = _front_path_to_rel(root, str(value))
            if rel and rel not in paths:
                paths.append(rel)
        return paths
    return []


def _extract_referenced_paths(front: dict[str, Any], root: Path) -> list[str]:
    refs: list[str] = []
    for key in _PATH_FIELD_KEYS:
        value = front.get(key) or front.get(key.lower())
        rel = _front_path_to_rel(root, str(value or ""))
        if rel and rel not in refs:
            refs.append(rel)
    return refs


def _extract_first_status(text: str) -> str:
    match = _STATUS_RE.search(text)
    return _normalize_doc_status(match.group(1)) if match else "UNKNOWN"


def _read_prd_status(path: Path) -> str:
    if not path.exists():
        return "MISSING"
    text = _read_text(path)
    return _extract_first_status(text)


def _read_plan_status(path: Path) -> str:
    if not path.exists():
        return "MISSING"
    text = _read_text(path)
    _found, status, _items = parse_plan_review_section(text)
    if status:
        return _normalize_doc_status(status)
    return _extract_first_status(text)


def _check_severity(code: str, policy: dict[str, Any]) -> str:
    mode = str(policy.get("mode") or "soft").strip().lower()
    if mode != "hard":
        return "warn"
    if code in {"missing_expected_report", "stale_reference"}:
        return "error"
    if code in {
        "stage_doc_drift",
        "tasklist_ready_without_actual_downstream_reports",
        "active_stage_vs_plan_mismatch",
    }:
        return "error"
    return "warn"


def evaluate_artifact_truth(
    root: Path,
    ticket: str,
    *,
    tasklist_text: str | None = None,
    actual_reports: Sequence[str] | None = None,
) -> dict[str, Any]:
    policy = load_artifact_truth_config(root)
    tasklist_path = root / "docs" / "tasklist" / f"{ticket}.md"
    tasklist_body = tasklist_text if tasklist_text is not None else _read_text(tasklist_path)
    front = _parse_front_matter_tree(tasklist_body)

    lines = tasklist_body.splitlines()
    _sections, section_map = tasklist_check.parse_sections(lines)
    context_pack = tasklist_check.section_body(section_map.get("AIDD:CONTEXT_PACK", [None])[0]) if section_map.get("AIDD:CONTEXT_PACK") else []
    test_execution = (
        tasklist_check.section_body(section_map.get("AIDD:TEST_EXECUTION", [None])[0])
        if section_map.get("AIDD:TEST_EXECUTION")
        else []
    )
    parsed_test_execution = tasklist_parser.parse_test_execution(test_execution)

    active_stage = _normalize_stage(runtime.read_active_stage(root))
    context_stage = _normalize_stage(tasklist_check.extract_field_value(context_pack, "Stage") or "")
    tasklist_status = _normalize_doc_status(front.get("Status") or tasklist_check.extract_field_value(context_pack, "Status") or "")

    plan_path = tasklist_check.resolve_plan_path(root, dict(front), ticket)
    prd_path = tasklist_check.resolve_prd_path(root, dict(front), ticket)

    doc_statuses = {
        "prd": _read_prd_status(prd_path),
        "plan": _read_plan_status(plan_path),
        "tasklist": tasklist_status,
        "active_stage": active_stage,
    }

    expected_reports = _extract_expected_reports(front, root)
    actual_report_set = {str(item).strip() for item in (actual_reports or []) if str(item).strip()}
    if not actual_report_set:
        for rel in expected_reports:
            abs_path = runtime.resolve_path_for_target(Path(rel), root)
            if abs_path.exists():
                actual_report_set.add(rel)
    actual_reports_list = sorted(actual_report_set)
    missing_expected_reports = [
        rel
        for rel in expected_reports
        if rel not in actual_report_set and not runtime.resolve_path_for_target(Path(rel), root).exists()
    ]

    referenced_paths = _extract_referenced_paths(front, root)
    stale_references = [
        rel for rel in referenced_paths if not runtime.resolve_path_for_target(Path(rel), root).exists()
    ]

    truth_checks: list[dict[str, Any]] = []

    def add_check(code: str, summary: str, *, paths: Sequence[str] | None = None) -> None:
        entry = {
            "code": code,
            "severity": _check_severity(code, policy),
            "summary": summary,
        }
        if paths:
            entry["paths"] = list(paths)
        truth_checks.append(entry)

    if policy.get("warn_on_stage_doc_drift", True) and active_stage != "unknown" and context_stage != "unknown" and active_stage != context_stage:
        add_check(
            "stage_doc_drift",
            f"active stage {active_stage} does not match tasklist context stage {context_stage}",
            paths=[runtime.rel_path(tasklist_path, root)],
        )

    if policy.get("warn_on_stage_doc_drift", True) and active_stage in {"implement", "review", "qa"} and doc_statuses["plan"] != "READY":
        add_check(
            "active_stage_vs_plan_mismatch",
            f"active stage {active_stage} while plan status is {doc_statuses['plan']}",
            paths=[runtime.rel_path(plan_path, root)],
        )

    if policy.get("warn_on_missing_expected_reports", True) and missing_expected_reports:
        add_check(
            "missing_expected_report",
            f"missing expected reports: {', '.join(missing_expected_reports)}",
            paths=missing_expected_reports,
        )

    if tasklist_status == "READY" and missing_expected_reports:
        add_check(
            "tasklist_ready_without_actual_downstream_reports",
            "tasklist is READY but expected downstream reports are still missing",
            paths=missing_expected_reports,
        )

    if stale_references:
        add_check(
            "stale_reference",
            f"front-matter references point to missing files: {', '.join(stale_references)}",
            paths=stale_references,
        )

    malformed_tasks = parsed_test_execution.get("malformed_tasks") or []
    if malformed_tasks:
        reasons = sorted(
            {
                str(item.get("reason_code") or "malformed_task").strip()
                for item in malformed_tasks
                if isinstance(item, dict)
            }
        )
        add_check(
            "test_execution_contract_weak",
            f"AIDD:TEST_EXECUTION contains malformed task entries: {', '.join(reasons)}",
            paths=[runtime.rel_path(tasklist_path, root)],
        )

    return {
        "policy": policy,
        "doc_statuses": doc_statuses,
        "expected_reports": expected_reports,
        "actual_reports": actual_reports_list,
        "missing_expected_reports": missing_expected_reports,
        "truth_checks": truth_checks,
    }


def collapse_events(events: Sequence[dict[str, Any]], *, enabled: bool = True) -> list[dict[str, Any]]:
    if not enabled:
        return [dict(item) for item in events if isinstance(item, dict)]

    collapsed: list[dict[str, Any]] = []
    for raw in events:
        if not isinstance(raw, dict):
            continue
        event = dict(raw)
        details = event.get("details") if isinstance(event.get("details"), dict) else {}
        sample_reason = str(
            details.get("summary") or details.get("reason") or details.get("reason_code") or ""
        ).strip()
        signature = (
            str(event.get("type") or "").strip(),
            str(event.get("status") or "").strip(),
            str(event.get("source") or "").strip(),
            sample_reason,
        )
        if collapsed:
            prev = collapsed[-1]
            prev_signature = prev.get("_signature")
            if prev_signature == signature:
                prev["repeat_count"] = int(prev.get("repeat_count") or 1) + 1
                prev["last_seen"] = event.get("ts") or prev.get("last_seen") or prev.get("ts")
                if sample_reason:
                    prev["sample_reason"] = sample_reason
                continue
        event["_signature"] = signature
        event["repeat_count"] = 1
        event["first_seen"] = event.get("ts")
        event["last_seen"] = event.get("ts")
        if sample_reason:
            event["sample_reason"] = sample_reason
        collapsed.append(event)

    finalized: list[dict[str, Any]] = []
    for event in collapsed:
        event.pop("_signature", None)
        if int(event.get("repeat_count") or 1) <= 1:
            event.pop("repeat_count", None)
            event.pop("first_seen", None)
            event.pop("last_seen", None)
            event.pop("sample_reason", None)
        finalized.append(event)
    return finalized
