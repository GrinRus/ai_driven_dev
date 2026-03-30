#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
from pathlib import Path
from typing import Dict, List, Mapping


THIS_DIR = Path(__file__).resolve().parent
if str(THIS_DIR) not in sys.path:
    sys.path.insert(0, str(THIS_DIR))

import aidd_audit_contract as contract


DEFAULT_MIN_FREE_BYTES = 1_073_741_824
TOP_LEVEL_PATTERNS = (
    re.compile(r'"status"\s*:\s*"(blocked|done|ship|success|error|continue)"', re.IGNORECASE),
    re.compile(r"\bstatus=(blocked|done|ship|success|error|continue)\b", re.IGNORECASE),
    re.compile(r"\bresult=(blocked|done|ship|success|error|continue)\b", re.IGNORECASE),
)
TASKS_NEW_STAGE_HINT_RE = re.compile(r"(tasks[-_ ]new|05_tasks_new)", re.IGNORECASE)
TASKS_NEW_RUNTIME_RE = re.compile(
    r"python3\s+[^ \n]*/skills/tasks-new/runtime/tasks_new\.py\b",
    re.IGNORECASE,
)
INVALID_FALLBACK_RUNTIME_PATH_RE = re.compile(
    r"python3\s+/skills/[^ \n]*/runtime/[^ \n]*\.py\b",
    re.IGNORECASE,
)
READINESS_REASON_CODES = (
    "readiness_gate_failed",
    "prd_not_ready",
    "open_questions_present",
    "answers_format_invalid",
    "research_not_ready",
)
TRUTHY_VALUES = {"1", "true", "yes", "on"}
STATUS_ALIAS_ERROR_RE = re.compile(
    r"(unknown skill:\s*:status|command not found:\s*:status)",
    re.IGNORECASE,
)
SIBLING_TOOL_ERROR_RE = re.compile(r"sibling tool call errored", re.IGNORECASE)
CANONICAL_RUNTIME_CALL_RE = re.compile(
    r"skills/(?:implement/runtime/implement_run\.py|review/runtime/review_run\.py|qa/runtime/qa_run\.py|aidd-docio/runtime/actions_apply\.py|aidd-flow-state/runtime/stage_result\.py)\b",
    re.IGNORECASE,
)
MALFORMED_STAGE_ALIAS_RE = re.compile(
    r"(?:unknown skill|command not found):\s*:(?!status\b)([a-z0-9_-]+)",
    re.IGNORECASE,
)


def parse_kv_file(path: Path) -> Dict[str, str]:
    payload: Dict[str, str] = {}
    if not path.exists():
        return payload
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip()
        if not line or "=" not in line:
            continue
        key, value = line.split("=", 1)
        payload[key.strip()] = value.strip()
    return payload


def _safe_int(raw: object, default: int = 0) -> int:
    try:
        return int(str(raw).strip())
    except Exception:
        return default


def infer_liveness_path(summary_path: Path) -> Path | None:
    name = summary_path.name
    match = re.match(r"^(?P<step>.+)_run(?P<run>[0-9]+)\.summary\.txt$", name)
    if not match:
        return None
    step = match.group("step")
    run = match.group("run")
    candidates = [
        summary_path.with_name(f"{step}_stream_liveness_check_run{run}.txt"),
        summary_path.with_name(f"{step}_stream_liveness_check.txt"),
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def infer_review_spec_report_check_path(summary_path: Path) -> Path | None:
    name = summary_path.name
    match = re.match(r"^(?P<step>.+)_run(?P<run>[0-9]+)\.summary\.txt$", name)
    if not match:
        return None
    step = match.group("step")
    if "review_spec" not in step.lower():
        return None
    run = match.group("run")
    candidates = [
        summary_path.with_name(f"{step}_report_check_run{run}.txt"),
        summary_path.with_name(f"{step}_report_check.txt"),
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def infer_workspace_layout_check_path(summary_path: Path) -> Path | None:
    name = summary_path.name
    match = re.match(r"^(?P<step>.+)_run(?P<run>[0-9]+)\.summary\.txt$", name)
    if not match:
        return None
    step = match.group("step")
    if "99" not in step.lower() and "post" not in step.lower():
        return None
    run = match.group("run")
    candidates = [
        summary_path.with_name(f"{step}_workspace_layout_check_run{run}.txt"),
        summary_path.with_name(f"{step}_workspace_layout_check.txt"),
        summary_path.with_name("99_workspace_layout_check.txt"),
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def _is_truthy(value: object) -> bool:
    return str(value or "").strip().lower() in TRUTHY_VALUES


def _summary_count_or_scan(
    *,
    summary: Mapping[str, str],
    key: str,
    text: str,
    pattern: re.Pattern[str],
) -> int:
    value = _safe_int(summary.get(key), -1)
    if value >= 0:
        return value
    return len(pattern.findall(text))


def _is_seed_stage_context(summary: Mapping[str, str], summary_path: Path) -> bool:
    hint = "\n".join(
        [
            summary_path.name,
            str(summary.get("step") or ""),
            str(summary.get("stage") or ""),
            str(summary.get("stage_name") or ""),
            str(summary.get("command") or ""),
            str(summary.get("stage_command") or ""),
        ]
    ).lower()
    return "implement" in hint or "seed" in hint


def _load_review_spec_report_check(summary_path: Path, aux_log_paths: List[Path] | None) -> tuple[Dict[str, str], str]:
    candidates: List[Path] = []
    seen: set[Path] = set()
    inferred = infer_review_spec_report_check_path(summary_path)
    if inferred is not None:
        resolved = inferred.resolve()
        if resolved not in seen:
            seen.add(resolved)
            candidates.append(inferred)
    for path in aux_log_paths or []:
        if "review_spec_report_check" not in path.name.lower():
            continue
        resolved = path.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        candidates.append(path)

    for path in candidates:
        payload = parse_kv_file(path)
        if payload:
            return payload, str(path)
    return {}, ""


def _load_workspace_layout_check(summary_path: Path, aux_log_paths: List[Path] | None) -> tuple[Dict[str, str], str, str]:
    candidates: List[Path] = []
    seen: set[Path] = set()
    inferred = infer_workspace_layout_check_path(summary_path)
    if inferred is not None:
        resolved = inferred.resolve()
        if resolved not in seen:
            seen.add(resolved)
            candidates.append(inferred)
    for path in aux_log_paths or []:
        if "workspace_layout_check" not in path.name.lower():
            continue
        resolved = path.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        candidates.append(path)
    for path in candidates:
        raw = read_log_text(path)
        payload = parse_kv_file(path)
        if payload or raw.strip():
            return payload, raw, str(path)
    return {}, "", ""


def _has_review_spec_report_payload(report_check: Mapping[str, str]) -> bool:
    if not report_check:
        return False
    report_path = str(report_check.get("report_path") or "").strip()
    if not report_path:
        return False
    recommended_status = str(report_check.get("recommended_status") or "").strip().lower()
    if recommended_status:
        return True
    if _safe_int(report_check.get("findings_count"), -1) >= 0:
        return True
    if _safe_int(report_check.get("open_questions_count"), -1) >= 0:
        return True
    return False


def _parse_workspace_layout_flags(
    payload: Mapping[str, str],
    raw_text: str,
) -> tuple[bool, bool]:
    text = str(raw_text or "").lower()

    def _truthy(*keys: str) -> bool:
        return any(_is_truthy(payload.get(key)) for key in keys)

    mutated = _truthy(
        "workspace_layout_mutated",
        "workspace_layout_delta_detected",
        "workspace_layout_non_canonical_root_delta",
        "root_delta_detected",
        "mutated_noncanonical_root",
        "mutated_paths_detected",
    )
    present = _truthy(
        "workspace_layout_non_canonical_root_detected",
        "non_canonical_root_detected",
        "preexisting_noncanonical_root",
        "root_paths_present",
    )

    numeric_mutated = (
        _safe_int(payload.get("workspace_layout_delta_count"), 0)
        + _safe_int(payload.get("workspace_layout_mutated_count"), 0)
        + _safe_int(payload.get("mutated_paths_count"), 0)
    )
    if numeric_mutated > 0:
        mutated = True
        present = True

    if re.search(r"\bworkspace_layout_non_canonical_root_detected\s*=\s*(?:1|true|yes|on)\b", text):
        present = True
    if re.search(r"\bpreexisting_noncanonical_root\s*=\s*(?:1|true|yes|on)\b", text):
        present = True
    if re.search(r"\bworkspace_layout_delta_detected\s*=\s*(?:1|true|yes|on)\b", text):
        mutated = True
        present = True
    if re.search(r"\bmutated_noncanonical_root\s*=\s*(?:1|true|yes|on)\b", text):
        mutated = True
        present = True

    if mutated:
        present = True
    preexisting_only = bool(present and not mutated)
    return bool(present), preexisting_only


def _allow_workspace_layout_override(classification: contract.Classification) -> bool:
    return classification.classification in {"FLOW_BUG", "TELEMETRY_ONLY"}


def resolve_min_free_bytes(raw: str | None = None) -> int:
    value = raw or os.environ.get("AIDD_AUDIT_MIN_FREE_BYTES", "")
    if not str(value).strip():
        return DEFAULT_MIN_FREE_BYTES
    try:
        parsed = int(str(value).strip())
    except ValueError:
        return DEFAULT_MIN_FREE_BYTES
    return max(parsed, 0)


def collect_preflight(
    *,
    project_dir: Path,
    plugin_dir: Path,
    min_free_bytes: int | None = None,
) -> Dict[str, object]:
    min_bytes = resolve_min_free_bytes(str(min_free_bytes) if min_free_bytes is not None else None)
    disk_free_bytes = int(shutil.disk_usage(project_dir).free)
    disk_low = disk_free_bytes < min_bytes
    runner_env_snapshot = {
        "CLAUDE_PLUGIN_ROOT": os.environ.get("CLAUDE_PLUGIN_ROOT", ""),
        "AIDD_PLUGIN_DIR": os.environ.get("AIDD_PLUGIN_DIR", ""),
        "PYTHONPATH": os.environ.get("PYTHONPATH", ""),
    }
    return {
        "cwd": str(Path.cwd().resolve()),
        "project_dir": str(project_dir.resolve()),
        "plugin_dir": str(plugin_dir.resolve()),
        "plugin_root_exists": int(plugin_dir.exists()),
        "disk_free_bytes": disk_free_bytes,
        "min_free_bytes": min_bytes,
        "disk_low": int(disk_low),
        "runner_env_snapshot": runner_env_snapshot,
    }


def read_log_text(path: Path | None) -> str:
    if path is None or not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="replace")


def detect_top_level_status(log_text: str) -> str:
    text = str(log_text or "")
    for pattern in TOP_LEVEL_PATTERNS:
        match = pattern.search(text)
        if match:
            return str(match.group(1) or "").strip().lower()
    return ""


def interpret_result_count(summary: Mapping[str, str], *, top_level_present: bool) -> str:
    raw = str(summary.get("result_count", "")).strip()
    if not raw:
        return "result_count_missing"
    try:
        value = int(raw)
    except ValueError:
        return "result_count_invalid"
    if value == 0 and top_level_present:
        return "telemetry_only_top_level_present"
    if value == 0 and not top_level_present:
        return "no_top_level_result_confirmed"
    if value > 0 and top_level_present:
        return "non_zero_top_level_present"
    return "non_zero_top_level_not_detected"


def _detect_recoverable_ralph(aux_text: str) -> bool:
    lowered = str(aux_text or "").lower()
    return "recoverable_blocked=1" in lowered and "reason_code=rlm_links_empty_warn" in lowered


def _is_tasks_new_context(summary: Mapping[str, str], summary_path: Path, log_text: str, aux_text: str) -> bool:
    summary_text = "\n".join(
        [
            summary_path.name,
            str(summary.get("step") or ""),
            str(summary.get("stage") or ""),
            str(summary.get("stage_name") or ""),
            str(summary.get("command") or ""),
        ]
    )
    merged = "\n".join(part for part in [summary_text, log_text, aux_text] if part)
    return bool(TASKS_NEW_STAGE_HINT_RE.search(merged))


def _has_tasks_new_nested_runtime(log_text: str, aux_text: str) -> bool:
    merged = "\n".join(part for part in [log_text, aux_text] if part)
    if TASKS_NEW_RUNTIME_RE.search(merged):
        return True
    return "tasklist-check" in merged.lower() and "tasks-new" in merged.lower()


def _extract_invalid_fallback_paths(log_text: str, aux_text: str) -> List[str]:
    merged = "\n".join(part for part in [log_text, aux_text] if part)
    if "can't open file" not in merged.lower() and "no such file" not in merged.lower():
        return []
    seen: List[str] = []
    for match in INVALID_FALLBACK_RUNTIME_PATH_RE.findall(merged):
        token = str(match).strip()
        if token and token not in seen:
            seen.append(token)
    return seen


def _detect_readiness_gate_reason(
    *,
    summary: Mapping[str, str],
    precondition: Mapping[str, str],
    diagnostics_text: str,
) -> str:
    direct_candidates = [
        str(summary.get("reason_code") or "").strip().lower(),
        str(summary.get("precondition_reason") or "").strip().lower(),
        str(precondition.get("reason_code") or "").strip().lower(),
        str(precondition.get("gate_reason") or "").strip().lower(),
    ]
    for candidate in direct_candidates:
        if candidate in READINESS_REASON_CODES:
            return candidate

    merged = "\n".join(
        [
            "\n".join(f"{key}={value}" for key, value in summary.items()),
            "\n".join(f"{key}={value}" for key, value in precondition.items()),
            diagnostics_text,
        ]
    ).lower()
    for reason_code in READINESS_REASON_CODES:
        if reason_code in merged:
            return reason_code
    return ""


def _allow_readiness_override(classification: contract.Classification) -> bool:
    if classification.subtype == "readiness_gate_failed":
        return False
    return classification.classification in {"FLOW_BUG", "TELEMETRY_ONLY"}


def analyze_run(
    *,
    summary_path: Path,
    run_log_path: Path | None = None,
    termination_path: Path | None = None,
    precondition_path: Path | None = None,
    liveness_path: Path | None = None,
    preflight: Mapping[str, object] | None = None,
    aux_log_paths: List[Path] | None = None,
) -> Dict[str, object]:
    summary = parse_kv_file(summary_path)
    termination = parse_kv_file(termination_path) if termination_path else {}
    precondition = parse_kv_file(precondition_path) if precondition_path else {}
    if liveness_path is None:
        inferred = infer_liveness_path(summary_path)
        if inferred is not None:
            liveness_path = inferred
    liveness = parse_kv_file(liveness_path) if liveness_path else {}
    run_log = run_log_path
    if run_log is None:
        candidate = Path(str(summary_path).replace(".summary.txt", ".log"))
        if candidate.exists():
            run_log = candidate
    log_text = read_log_text(run_log)
    aux_text_parts: List[str] = []
    if precondition_path:
        aux_text_parts.append(read_log_text(precondition_path))
    for path in aux_log_paths or []:
        aux_text_parts.append(read_log_text(path))
    aux_text = "\n".join(part for part in aux_text_parts if part)
    review_spec_report_check, review_spec_report_check_path = _load_review_spec_report_check(summary_path, aux_log_paths)
    review_spec_report_mismatch = _is_truthy(review_spec_report_check.get("narrative_vs_report_mismatch"))
    review_spec_payload_valid = _has_review_spec_report_payload(review_spec_report_check)
    workspace_layout_check, workspace_layout_check_raw, workspace_layout_check_path = _load_workspace_layout_check(
        summary_path, aux_log_paths
    )
    workspace_layout_detected, workspace_layout_preexisting_only = _parse_workspace_layout_flags(
        workspace_layout_check, workspace_layout_check_raw
    )

    top_level_status = detect_top_level_status(log_text)
    if not top_level_status and aux_text:
        top_level_status = detect_top_level_status(aux_text)
    telemetry_text = "\n".join(part for part in [log_text, aux_text] if part)
    status_alias_error_count = _summary_count_or_scan(
        summary=summary,
        key="status_alias_error_count",
        text=telemetry_text,
        pattern=STATUS_ALIAS_ERROR_RE,
    )
    sibling_tool_error_count = _summary_count_or_scan(
        summary=summary,
        key="sibling_tool_error_count",
        text=telemetry_text,
        pattern=SIBLING_TOOL_ERROR_RE,
    )
    canonical_runtime_call_count = _summary_count_or_scan(
        summary=summary,
        key="canonical_runtime_call_count",
        text=telemetry_text,
        pattern=CANONICAL_RUNTIME_CALL_RE,
    )
    malformed_stage_alias_count = _summary_count_or_scan(
        summary=summary,
        key="malformed_stage_alias_count",
        text=telemetry_text,
        pattern=MALFORMED_STAGE_ALIAS_RE,
    )
    summary_reason_code = str(summary.get("reason_code") or "").strip().lower()
    seed_stage_context = _is_seed_stage_context(summary, summary_path)
    seed_stage_non_converging_command = int(
        _is_truthy(summary.get("seed_stage_non_converging_command"))
        or summary_reason_code == "seed_stage_non_converging_command"
        or (
            seed_stage_context
            and
            status_alias_error_count > 0
            and sibling_tool_error_count > 0
            and canonical_runtime_call_count == 0
            and not top_level_status
        )
    )
    terminal_marker_present = bool(
        re.search(r'"terminal_marker"\s*:\s*(?:1|true)\b', log_text, re.IGNORECASE)
        or re.search(r"\bterminal_marker=(?:1|true)\b", log_text, re.IGNORECASE)
        or re.search(r"\bterminal_marker=(?:1|true)\b", aux_text, re.IGNORECASE)
        or _is_truthy(summary.get("terminal_marker"))
    )
    top_level_result_present = bool(top_level_status)
    result_count_interpretation = interpret_result_count(summary, top_level_present=top_level_result_present)
    if not top_level_result_present and terminal_marker_present and result_count_interpretation in {
        "result_count_missing",
        "no_top_level_result_confirmed",
    }:
        result_count_interpretation = "terminal_marker_present"

    classified = contract.classify_incident(
        summary=summary,
        termination=termination,
        log_text=log_text,
        top_level_status=top_level_status,
        preflight=preflight,
        diagnostics_text=aux_text,
    )
    if seed_stage_non_converging_command and classified.classification in {"FLOW_BUG", "TELEMETRY_ONLY"}:
        classified = contract.Classification(
            classification="PROMPT_EXEC_ISSUE",
            subtype="seed_stage_non_converging_command",
            source="summary" if _is_truthy(summary.get("seed_stage_non_converging_command")) else "run_log",
            label="PROMPT_EXEC_ISSUE(seed_stage_non_converging_command)",
        )
    liveness_classification = str(liveness.get("classification") or "").strip().lower()
    liveness_active_source = str(liveness.get("active_source") or "").strip().lower()
    liveness_valid_stream_count = _safe_int(liveness.get("valid_stream_count"), 0)
    liveness_stagnation_seconds = _safe_int(liveness.get("stagnation_seconds"), 0)
    liveness_run_start_epoch = _safe_int(liveness.get("run_start_epoch"), 0)

    if liveness_classification == "silent_stall" and classified.classification in {"FLOW_BUG", "TELEMETRY_ONLY"}:
        classified = contract.Classification(
            classification="PROMPT_EXEC_ISSUE",
            subtype="silent_stall",
            source="liveness",
            label="NOT_VERIFIED(silent_stall)+PROMPT_EXEC_ISSUE(silent_stall)",
        )

    if (
        top_level_result_present
        and liveness_classification == "no_stream_emitted"
        and classified.classification in {"FLOW_BUG", "TELEMETRY_ONLY"}
    ):
        classified = contract.Classification(
            classification="TELEMETRY_ONLY",
            subtype="stream_path_not_emitted_by_cli",
            source="liveness",
            label="INFO(stream_path_not_emitted_by_cli)",
        )

    readiness_reason = _detect_readiness_gate_reason(
        summary=summary,
        precondition=precondition,
        diagnostics_text=aux_text,
    )
    readiness_gate_failed = bool(readiness_reason)
    if readiness_gate_failed and _allow_readiness_override(classified):
        classified = contract.Classification(
            classification="PROMPT_EXEC_ISSUE",
            subtype="readiness_gate_failed",
            source="precondition" if precondition else "diagnostics",
            label="NOT_VERIFIED(readiness_gate_failed)+PROMPT_EXEC_ISSUE(readiness_gate_failed)",
        )
    if (
        not readiness_gate_failed
        and result_count_interpretation == "no_top_level_result_confirmed"
        and not terminal_marker_present
        and classified.classification in {"FLOW_BUG", "TELEMETRY_ONLY"}
    ):
        classified = contract.Classification(
            classification="PROMPT_EXEC_ISSUE",
            subtype="no_top_level_result",
            source="summary",
            label="NOT_VERIFIED(no_top_level_result)+PROMPT_EXEC_ISSUE(no_top_level_result)",
        )

    if (
        result_count_interpretation == "terminal_marker_present"
        and classified.classification == "FLOW_BUG"
    ):
        classified = contract.Classification(
            classification="TELEMETRY_ONLY",
            subtype="terminal_marker_present",
            source="run_log",
            label="TELEMETRY_ONLY(terminal_marker_present)",
        )
    invalid_fallback_paths = _extract_invalid_fallback_paths(log_text, aux_text)
    tasks_new_partial_success = (
        result_count_interpretation == "no_top_level_result_confirmed"
        and not top_level_result_present
        and _is_tasks_new_context(summary, summary_path, log_text, aux_text)
        and _has_tasks_new_nested_runtime(log_text, aux_text)
    )
    if tasks_new_partial_success and not invalid_fallback_paths:
        classified = contract.Classification(
            classification="TELEMETRY_ONLY",
            subtype="partial_success_no_top_level_result",
            source="run_log",
            label="WARN(partial_success_no_top_level_result)",
        )
    if (
        review_spec_report_mismatch
        and not review_spec_payload_valid
        and classified.classification in {"FLOW_BUG", "TELEMETRY_ONLY"}
    ):
        classified = contract.Classification(
            classification="PROMPT_EXEC_ISSUE",
            subtype="review_spec_report_mismatch",
            source="review_spec_report_check",
            label="PROMPT_EXEC_ISSUE(review_spec_report_mismatch)",
        )
    if workspace_layout_detected and _allow_workspace_layout_override(classified):
        if workspace_layout_preexisting_only:
            classified = contract.Classification(
                classification="TELEMETRY_ONLY",
                subtype="preexisting_noncanonical_root",
                source="workspace_layout_check",
                label="INFO(preexisting_noncanonical_root)",
            )
        else:
            classified = contract.Classification(
                classification="TELEMETRY_ONLY",
                subtype="workspace_layout_non_canonical_root_detected",
                source="workspace_layout_check",
                label="WARN(workspace_layout_non_canonical_root_detected)",
            )

    recoverable_ralph_observed = _detect_recoverable_ralph(aux_text)
    effective_terminal_status = classified.label
    if top_level_status == "blocked" and recoverable_ralph_observed:
        effective_terminal_status = "BLOCKED(recoverable ralph path observed)"

    payload: Dict[str, object] = dict(summary)
    payload.update(
        {
            "top_level_result_present": int(top_level_result_present),
            "top_level_status": top_level_status,
            "result_count_interpretation": result_count_interpretation,
            "classification": classified.classification,
            "classification_subtype": classified.subtype,
            "classification_source": classified.source,
            "effective_classification": classified.label,
            "effective_terminal_status": effective_terminal_status,
            "recoverable_ralph_observed": int(recoverable_ralph_observed),
            "partial_success_no_top_level_result": int(tasks_new_partial_success),
            "invalid_fallback_path_count": len(invalid_fallback_paths),
            "invalid_fallback_paths": invalid_fallback_paths,
            "readiness_gate_failed": int(readiness_gate_failed),
            "readiness_reason": readiness_reason,
            "liveness_classification": liveness_classification,
            "liveness_active_source": liveness_active_source,
            "liveness_valid_stream_count": liveness_valid_stream_count,
            "liveness_stagnation_seconds": liveness_stagnation_seconds,
            "liveness_run_start_epoch": liveness_run_start_epoch,
            "review_spec_report_mismatch": int(review_spec_report_mismatch),
            "review_spec_payload_valid": int(review_spec_payload_valid),
            "review_spec_report_check_path": review_spec_report_check_path,
            "review_spec_report_path": str(review_spec_report_check.get("report_path") or ""),
            "review_spec_recommended_status": str(review_spec_report_check.get("recommended_status") or ""),
            "review_spec_recovery_source": "report_payload" if review_spec_payload_valid else "",
            "terminal_marker_present": int(terminal_marker_present),
            "status_alias_error_count": int(status_alias_error_count),
            "sibling_tool_error_count": int(sibling_tool_error_count),
            "canonical_runtime_call_count": int(canonical_runtime_call_count),
            "malformed_stage_alias_count": int(malformed_stage_alias_count),
            "seed_stage_non_converging_command": int(seed_stage_non_converging_command),
            "workspace_layout_check_path": workspace_layout_check_path,
            "workspace_layout_noncanonical_detected": int(workspace_layout_detected),
            "workspace_layout_preexisting_only": int(workspace_layout_preexisting_only),
        }
    )
    if precondition:
        payload["precondition"] = dict(precondition)
    if liveness:
        payload["liveness"] = dict(liveness)
    if review_spec_report_check:
        payload["review_spec_report_check"] = dict(review_spec_report_check)
    if workspace_layout_check:
        payload["workspace_layout_check"] = dict(workspace_layout_check)
    return payload


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="AIDD audit replay runner and classifier.")
    sub = parser.add_subparsers(dest="command", required=True)

    preflight_parser = sub.add_parser("preflight", help="Collect environment preflight for audit run.")
    preflight_parser.add_argument("--project-dir", required=True)
    preflight_parser.add_argument("--plugin-dir", required=True)
    preflight_parser.add_argument("--min-free-bytes", type=int, default=DEFAULT_MIN_FREE_BYTES)

    classify_parser = sub.add_parser("classify", help="Classify one stage-run from existing artifacts.")
    classify_parser.add_argument("--summary", required=True)
    classify_parser.add_argument("--log")
    classify_parser.add_argument("--termination")
    classify_parser.add_argument("--precondition")
    classify_parser.add_argument("--liveness")
    classify_parser.add_argument("--aux-log", action="append", default=[])
    classify_parser.add_argument("--project-dir")
    classify_parser.add_argument("--plugin-dir")
    classify_parser.add_argument("--min-free-bytes", type=int, default=DEFAULT_MIN_FREE_BYTES)
    classify_parser.add_argument("--skip-preflight", action="store_true")

    return parser


def main(argv: List[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    if args.command == "preflight":
        payload = collect_preflight(
            project_dir=Path(args.project_dir),
            plugin_dir=Path(args.plugin_dir),
            min_free_bytes=args.min_free_bytes,
        )
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0

    preflight_payload: Mapping[str, object] | None = None
    if not args.skip_preflight and args.project_dir and args.plugin_dir:
        preflight_payload = collect_preflight(
            project_dir=Path(args.project_dir),
            plugin_dir=Path(args.plugin_dir),
            min_free_bytes=args.min_free_bytes,
        )
    payload = analyze_run(
        summary_path=Path(args.summary),
        run_log_path=Path(args.log) if args.log else None,
        termination_path=Path(args.termination) if args.termination else None,
        precondition_path=Path(args.precondition) if args.precondition else None,
        liveness_path=Path(args.liveness) if args.liveness else None,
        preflight=preflight_payload,
        aux_log_paths=[Path(item) for item in args.aux_log],
    )
    if preflight_payload is not None:
        payload["runner_preflight"] = dict(preflight_payload)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
