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


def analyze_run(
    *,
    summary_path: Path,
    run_log_path: Path | None = None,
    termination_path: Path | None = None,
    preflight: Mapping[str, object] | None = None,
    aux_log_paths: List[Path] | None = None,
) -> Dict[str, object]:
    summary = parse_kv_file(summary_path)
    termination = parse_kv_file(termination_path) if termination_path else {}
    run_log = run_log_path
    if run_log is None:
        candidate = Path(str(summary_path).replace(".summary.txt", ".log"))
        if candidate.exists():
            run_log = candidate
    log_text = read_log_text(run_log)
    aux_text_parts: List[str] = []
    for path in aux_log_paths or []:
        aux_text_parts.append(read_log_text(path))
    aux_text = "\n".join(part for part in aux_text_parts if part)

    top_level_status = detect_top_level_status(log_text)
    if not top_level_status and aux_text:
        top_level_status = detect_top_level_status(aux_text)
    top_level_result_present = bool(top_level_status)
    result_count_interpretation = interpret_result_count(summary, top_level_present=top_level_result_present)

    classified = contract.classify_incident(
        summary=summary,
        termination=termination,
        log_text=log_text,
        top_level_status=top_level_status,
        preflight=preflight,
        diagnostics_text=aux_text,
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
        }
    )
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
        preflight=preflight_payload,
        aux_log_paths=[Path(item) for item in args.aux_log],
    )
    if preflight_payload is not None:
        payload["runner_preflight"] = dict(preflight_payload)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
