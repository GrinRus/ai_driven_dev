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
RUN_SUMMARY_RE = re.compile(r"^(?P<step>.+)_run(?P<run>[0-9]+)\.summary\.txt$")
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
    step, run = _parse_summary_identity(summary_path)
    if not step or run <= 0:
        return None
    candidates = [
        summary_path.with_name(f"{step}_stream_liveness_check_run{run}.txt"),
        summary_path.with_name(f"{step}_stream_liveness_check.txt"),
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def _parse_summary_identity(summary_path: Path) -> tuple[str, int]:
    name = summary_path.name
    match = RUN_SUMMARY_RE.match(name)
    if not match:
        return "", 0
    step = str(match.group("step") or "").strip()
    run = _safe_int(match.group("run"), 0)
    return step, run


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


def detect_top_level_result_event(log_text: str) -> bool:
    return bool(re.search(r'"type"\s*:\s*"result"', str(log_text or "")))


def parse_kv_text(text: str) -> Dict[str, str]:
    payload: Dict[str, str] = {}
    for raw in str(text or "").splitlines():
        line = raw.strip()
        if not line or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if not key:
            continue
        payload[key] = value.strip()
    return payload


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


def _derive_readiness_failure_mode(
    *,
    readiness_reason: str,
    precondition: Mapping[str, str],
    diagnostics: Mapping[str, str],
) -> str:
    reason = str(readiness_reason or "").strip().lower()
    if not reason:
        return ""
    prd_status = str(precondition.get("prd_status") or diagnostics.get("prd_status") or "").strip().lower()
    review_recommended_status = str(
        diagnostics.get("recommended_status")
        or precondition.get("review_spec_recommended_status")
        or ""
    ).strip().lower()
    if (
        reason == "prd_not_ready"
        and prd_status == "ready"
        and review_recommended_status
        and review_recommended_status != "ready"
    ):
        return "report_recommended_status_not_ready"
    return reason


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
    step_key, run_index = _parse_summary_identity(summary_path)
    summary_mtime = 0.0
    try:
        summary_mtime = float(summary_path.stat().st_mtime)
    except OSError:
        summary_mtime = 0.0
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
    diagnostics = parse_kv_text(aux_text)

    top_level_status = detect_top_level_status(log_text)
    if not top_level_status and aux_text:
        top_level_status = detect_top_level_status(aux_text)
    top_level_result_present = detect_top_level_result_event(log_text) or detect_top_level_result_event(aux_text) or bool(top_level_status)
    result_count_interpretation = interpret_result_count(summary, top_level_present=top_level_result_present)

    classified = contract.classify_incident(
        summary=summary,
        termination=termination,
        log_text=log_text,
        top_level_status=top_level_status,
        preflight=preflight,
        diagnostics_text=aux_text,
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
    review_mismatch_value = str(
        diagnostics.get("narrative_vs_report_mismatch")
        or diagnostics.get("narrative_vs_structured_mismatch")
        or ""
    ).strip().lower()
    review_mismatch_detected = review_mismatch_value in {"1", "true", "yes", "on"}
    review_recommended_status = str(diagnostics.get("recommended_status") or "").strip().lower()
    review_findings_count = _safe_int(diagnostics.get("findings_count"), -1)
    review_open_questions_count = _safe_int(diagnostics.get("open_questions_count"), -1)
    review_mismatch_non_blocking = bool(
        review_mismatch_detected
        and review_recommended_status == "ready"
        and review_findings_count == 0
        and review_open_questions_count == 0
    )
    if review_mismatch_non_blocking and classified.classification in {"FLOW_BUG", "TELEMETRY_ONLY"}:
        classified = contract.Classification(
            classification="TELEMETRY_ONLY",
            subtype="review_spec_report_mismatch_non_blocking",
            source="diagnostics",
            label="INFO(review_spec_report_mismatch_non_blocking)",
        )
    readiness_reason = _detect_readiness_gate_reason(
        summary=summary,
        precondition=precondition,
        diagnostics_text=aux_text,
    )
    readiness_failure_mode = _derive_readiness_failure_mode(
        readiness_reason=readiness_reason,
        precondition=precondition,
        diagnostics=diagnostics,
    )
    readiness_gate_failed = bool(readiness_reason)
    if readiness_gate_failed and _allow_readiness_override(classified):
        classified = contract.Classification(
            classification="PROMPT_EXEC_ISSUE",
            subtype="readiness_gate_failed",
            source="precondition" if precondition else "diagnostics",
            label="NOT_VERIFIED(readiness_gate_failed)+PROMPT_EXEC_ISSUE(readiness_gate_failed)",
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

    recoverable_ralph_observed = _detect_recoverable_ralph(aux_text)
    effective_terminal_status = classified.label
    if top_level_status == "blocked" and recoverable_ralph_observed:
        effective_terminal_status = "BLOCKED(recoverable ralph path observed)"
    termination_exit_code = str(
        termination.get("exit_code") or summary.get("effective_exit_code") or summary.get("exit_code") or ""
    ).strip()
    termination_signal = str(termination.get("signal") or "").strip()
    termination_killed_flag = _safe_int(termination.get("killed_flag"), _safe_int(summary.get("killed_flag"), 0))
    termination_watchdog_marker = _safe_int(
        termination.get("watchdog_marker"),
        _safe_int(summary.get("watchdog_marker"), 0),
    )
    termination_secondary_telemetry = int(classified.subtype == "cwd_wrong" and termination_exit_code == "143")
    step_hint = "\n".join(
        [
            summary_path.name,
            str(summary.get("step") or ""),
            str(summary.get("step_key") or ""),
            str(summary.get("stage") or ""),
            str(summary.get("stage_command") or ""),
        ]
    )
    downstream_skip_hint = ""
    if classified.classification == "ENV_MISCONFIG" and classified.subtype == "cwd_wrong":
        if re.search(r"05[_-].*tasks[-_ ]new|05_tasks_new", step_hint, flags=re.IGNORECASE):
            downstream_skip_hint = "NOT VERIFIED (upstream_tasks_new_failed)"
    primary_cause = f"{classified.classification}:{classified.subtype}"
    secondary_symptoms: List[str] = []
    if result_count_interpretation == "no_top_level_result_confirmed":
        secondary_symptoms.append("no_top_level_result")
    if invalid_fallback_paths:
        secondary_symptoms.append("invalid_fallback_path_detected")
    if review_mismatch_detected:
        secondary_symptoms.append("review_spec_report_mismatch")
    if readiness_gate_failed:
        secondary_symptoms.append("readiness_gate_failed")

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
            "termination_exit_code": termination_exit_code,
            "termination_signal": termination_signal,
            "termination_killed_flag": int(termination_killed_flag),
            "termination_watchdog_marker": int(termination_watchdog_marker),
            "termination_secondary_telemetry": termination_secondary_telemetry,
            "recoverable_ralph_observed": int(recoverable_ralph_observed),
            "partial_success_no_top_level_result": int(tasks_new_partial_success),
            "invalid_fallback_path_count": len(invalid_fallback_paths),
            "invalid_fallback_paths": invalid_fallback_paths,
            "review_spec_report_mismatch_detected": int(review_mismatch_detected),
            "review_spec_report_mismatch_non_blocking": int(review_mismatch_non_blocking),
            "review_spec_report_recommended_status": review_recommended_status,
            "review_spec_report_findings_count": review_findings_count,
            "review_spec_report_open_questions_count": review_open_questions_count,
            "readiness_gate_failed": int(readiness_gate_failed),
            "readiness_reason": readiness_reason,
            "readiness_failure_mode": readiness_failure_mode,
            "liveness_classification": liveness_classification,
            "liveness_active_source": liveness_active_source,
            "liveness_valid_stream_count": liveness_valid_stream_count,
            "liveness_stagnation_seconds": liveness_stagnation_seconds,
            "liveness_run_start_epoch": liveness_run_start_epoch,
            "primary_cause": primary_cause,
            "secondary_symptoms": secondary_symptoms,
            "superseded_runs": [],
            "summary_path": str(summary_path),
            "summary_mtime": summary_mtime,
            "step_key": step_key or str(summary.get("step") or ""),
            "run_index": run_index,
        }
    )
    if downstream_skip_hint:
        payload["downstream_skip_hint"] = downstream_skip_hint
        payload["downstream_skip_scope"] = "06,07,08"
    if precondition:
        payload["precondition"] = dict(precondition)
    if liveness:
        payload["liveness"] = dict(liveness)
    return payload


def rollup_latest_runs(run_payloads: List[Mapping[str, object]]) -> Dict[str, object]:
    grouped: Dict[str, List[Dict[str, object]]] = {}
    for raw in run_payloads:
        payload = dict(raw)
        step_key = str(payload.get("step_key") or payload.get("step") or "").strip() or "unknown"
        grouped.setdefault(step_key, []).append(payload)

    rolled: Dict[str, Dict[str, object]] = {}
    for step_key, rows in grouped.items():
        ordered = sorted(
            rows,
            key=lambda item: (
                _safe_int(item.get("run_index"), 0),
                float(item.get("summary_mtime") or 0.0),
                str(item.get("summary_path") or ""),
            ),
        )
        latest = dict(ordered[-1])
        superseded_runs: List[str] = []
        for stale in ordered[:-1]:
            label = str(stale.get("summary_path") or "").strip()
            if not label:
                stale_run = _safe_int(stale.get("run_index"), 0)
                label = f"{step_key}:run{stale_run}"
            superseded_runs.append(label)
        latest["superseded_runs"] = superseded_runs
        rolled[step_key] = latest

    return {
        "runs_total": len(run_payloads),
        "steps_total": len(rolled),
        "step_order": sorted(rolled.keys()),
        "steps": rolled,
    }


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

    rollup_parser = sub.add_parser("rollup", help="Analyze multiple runs and roll up latest-wins per step.")
    rollup_parser.add_argument("--summary", action="append", default=[], help="Path to *_runN.summary.txt (repeatable).")
    rollup_parser.add_argument("--audit-dir", help="Directory with *_runN.summary.txt artifacts.")
    rollup_parser.add_argument("--project-dir")
    rollup_parser.add_argument("--plugin-dir")
    rollup_parser.add_argument("--min-free-bytes", type=int, default=DEFAULT_MIN_FREE_BYTES)
    rollup_parser.add_argument("--skip-preflight", action="store_true")

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

    if args.command == "rollup":
        summary_paths: List[Path] = []
        summary_paths.extend(Path(item) for item in (args.summary or []))
        if args.audit_dir:
            summary_paths.extend(sorted(Path(args.audit_dir).glob("*_run*.summary.txt")))
        unique_paths: List[Path] = []
        seen: set[str] = set()
        for path in summary_paths:
            key = str(path.resolve())
            if key in seen:
                continue
            seen.add(key)
            if path.exists():
                unique_paths.append(path)
        if not unique_paths:
            raise SystemExit("rollup requires --summary or --audit-dir with existing *_run*.summary.txt files")

        preflight_payload: Mapping[str, object] | None = None
        if not args.skip_preflight and args.project_dir and args.plugin_dir:
            preflight_payload = collect_preflight(
                project_dir=Path(args.project_dir),
                plugin_dir=Path(args.plugin_dir),
                min_free_bytes=args.min_free_bytes,
            )

        analyzed: List[Dict[str, object]] = []
        for summary_path in sorted(unique_paths):
            payload = analyze_run(
                summary_path=summary_path,
                preflight=preflight_payload,
            )
            if preflight_payload is not None:
                payload["runner_preflight"] = dict(preflight_payload)
            analyzed.append(payload)
        rollup = rollup_latest_runs(analyzed)
        if preflight_payload is not None:
            rollup["runner_preflight"] = dict(preflight_payload)
        print(json.dumps(rollup, ensure_ascii=False, indent=2))
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
