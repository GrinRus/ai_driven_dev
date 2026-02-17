#!/usr/bin/env python3
"""Run loop-step repeatedly until SHIP or limits reached."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import time
import sys
import datetime as dt
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from aidd_runtime import runtime
from aidd_runtime import stage_result_contract
from aidd_runtime.feature_ids import write_active_state
from aidd_runtime.loop_pack import (
    is_open_item,
    parse_iteration_items,
    parse_next3_refs,
    parse_sections,
    select_first_open,
)
from aidd_runtime.io_utils import dump_yaml, utc_timestamp

DONE_CODE = 0
CONTINUE_CODE = 10
BLOCKED_CODE = 20
MAX_ITERATIONS_CODE = 11
ERROR_CODE = 30
STREAM_MODE_ALIASES = {
    "text-only": "text",
    "text": "text",
    "tools": "tools",
    "text+tools": "tools",
    "raw": "raw",
    "1": "text",
    "true": "text",
    "yes": "text",
}
_APPROVAL_MARKERS = (
    "requires approval",
    "command requires approval",
    "manual approval",
)
_PERMISSION_MODE_MARKERS = (
    '"permissionmode":"default"',
    '"permissionmode": "default"',
)
_MARKER_SEMANTIC_TOKENS = ("id=review:", "id_review_")
_MARKER_INLINE_PATH_RE = re.compile(r"(?P<path>(?:aidd|docs|reports)/[^\s,;]+)", re.IGNORECASE)
DEFAULT_LOOP_STEP_TIMEOUT_SECONDS = 900
DEFAULT_BLOCKED_POLICY = "strict"
DEFAULT_RECOVERABLE_BLOCK_RETRIES = 2
BLOCKED_POLICY_VALUES = {"strict", "ralph"}
HARD_BLOCK_REASON_CODES = {
    "loop_runner_permissions",
    "user_approval_required",
    "diff_boundary_violation",
    "wrappers_skipped_unsafe",
    "preflight_contract_mismatch",
    "plugin_root_missing",
    "command_unavailable",
    "invalid_work_item_key",
    "review_pack_invalid_schema",
    "review_pack_v2_required",
    "review_pack_regen_failed",
    "review_pack_missing",
    "review_fix_plan_missing",
    "qa_stage_result_emit_failed",
    "output_contract_warn",
    "wrapper_output_missing",
    "work_item_resolution_failed",
    "active_stage_sync_failed",
    "prompt_flow_blocker",
}
RECOVERABLE_BLOCK_REASON_CODES = {
    "",
    "stage_result_missing_or_invalid",
    "stage_result_blocked",
    "blocked_without_reason",
    "blocking_findings",
    "invalid_loop_step_payload",
    "stage_result_missing",
    "wrapper_chain_missing",
    "actions_missing",
    "preflight_missing",
    "qa_repair_missing_work_item",
    "qa_repair_no_handoff",
    "qa_repair_multiple_handoffs",
    "qa_repair_tasklist_missing",
    "unsupported_stage_result",
}


def clear_active_mode(root: Path) -> None:
    path = root / "docs" / ".active_mode"
    try:
        path.unlink()
    except OSError:
        return


def append_log(log_path: Path, message: str) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(message + "\n")


def append_stream_file(dest: Path, source: Path, *, header: str | None = None) -> None:
    if not source.exists():
        return
    dest.parent.mkdir(parents=True, exist_ok=True)
    with dest.open("a", encoding="utf-8") as out_handle:
        if header:
            out_handle.write(header + "\n")
        out_handle.write(source.read_text(encoding="utf-8"))


def write_active_stage(root: Path, stage: str) -> None:
    write_active_state(root, stage=stage)


def select_next_work_item(target: Path, ticket: str, current_work_item: str) -> tuple[str, int]:
    tasklist_path = target / "docs" / "tasklist" / f"{ticket}.md"
    if not tasklist_path.exists():
        return "", 0
    lines = tasklist_path.read_text(encoding="utf-8").splitlines()
    sections = parse_sections(lines)
    iterations = parse_iteration_items(sections.get("AIDD:ITERATIONS_FULL", []))
    open_items = [
        item
        for item in iterations
        if is_open_item(item) and item.work_item_key != current_work_item
    ]
    pending_count = len(open_items)
    if not open_items:
        return "", pending_count
    next3_refs = parse_next3_refs(sections.get("AIDD:NEXT_3", []))
    candidate = select_first_open(next3_refs, open_items)
    if not candidate:
        candidate = open_items[0]
    return candidate.work_item_key, pending_count


def resolve_runner_label(raw: str | None) -> str:
    if raw:
        return raw.strip()
    env_value = (os.environ.get("AIDD_LOOP_RUNNER_LABEL") or os.environ.get("AIDD_RUNNER") or "").strip()
    if env_value:
        return env_value
    if os.environ.get("CI"):
        return "ci"
    return "local"


def resolve_stream_mode(raw: str | None) -> str:
    if raw is None:
        raw = os.environ.get("AIDD_AGENT_STREAM_MODE", "")
    value = str(raw or "").strip().lower()
    if not value:
        return ""
    return STREAM_MODE_ALIASES.get(value, "text")


def _resolve_optional_path(target: Path, value: str) -> Optional[Path]:
    raw = str(value or "").strip()
    if not raw:
        return None
    return runtime.resolve_path_for_target(Path(raw), target)


def _safe_size(path: Optional[Path]) -> int:
    if path is None or not path.exists():
        return 0
    try:
        return int(path.stat().st_size)
    except OSError:
        return 0


def _safe_updated_at(path: Optional[Path]) -> str:
    if path is None or not path.exists():
        return ""
    try:
        ts = dt.datetime.fromtimestamp(path.stat().st_mtime, tz=dt.timezone.utc)
        return ts.isoformat()
    except OSError:
        return ""


def _permission_mismatch_from_text(reason: str, diag: str, code: str) -> bool:
    reason_code = str(code or "").strip().lower()
    if reason_code == "loop_runner_permissions":
        return True
    if reason_code not in {"stage_result_missing_or_invalid", "stage_result_blocked", "blocked_without_reason", ""}:
        return False
    joined = f"{reason}\n{diag}".lower()
    approval_hit = any(marker in joined for marker in _APPROVAL_MARKERS)
    permission_mode_default = any(marker in joined for marker in _PERMISSION_MODE_MARKERS)
    return approval_hit and (permission_mode_default or reason_code == "stage_result_missing_or_invalid")


def _extract_marker_source(line: str) -> str:
    text = str(line or "").strip()
    if not text:
        return "inline"
    match = _MARKER_INLINE_PATH_RE.search(text)
    if match:
        return match.group("path").strip()
    return "inline"


def _is_marker_noise_source(source: str, line: str) -> bool:
    source_lower = str(source or "").strip().lower()
    line_lower = str(line or "").strip().lower()
    if "aidd/docs/tasklist/templates/" in source_lower or "aidd/docs/tasklist/templates/" in line_lower:
        return True
    return (
        source_lower.endswith(".bak")
        or source_lower.endswith(".tmp")
        or ".bak:" in source_lower
        or ".tmp:" in source_lower
        or ".bak" in line_lower
        or ".tmp" in line_lower
    )


def _scan_marker_semantics(entries: List[Tuple[str, str]]) -> Tuple[List[str], List[str]]:
    signal: List[str] = []
    noise: List[str] = []
    seen_signal: set[str] = set()
    seen_noise: set[str] = set()
    for source_name, text in entries:
        for raw_line in str(text or "").splitlines():
            line = raw_line.strip()
            if not line:
                continue
            line_lower = line.lower()
            if not any(token in line_lower for token in _MARKER_SEMANTIC_TOKENS):
                continue
            marker_source = _extract_marker_source(line)
            item = f"{source_name}:{marker_source}"
            if _is_marker_noise_source(marker_source, line):
                if item not in seen_noise:
                    seen_noise.add(item)
                    noise.append(item)
                continue
            if item not in seen_signal:
                seen_signal.add(item)
                signal.append(item)
    return signal, noise


def _resolve_step_timeout_seconds(raw: object) -> int:
    if raw is None or str(raw).strip() == "":
        raw = os.environ.get("AIDD_LOOP_STEP_TIMEOUT_SECONDS", str(DEFAULT_LOOP_STEP_TIMEOUT_SECONDS))
    try:
        value = int(str(raw).strip())
    except (TypeError, ValueError):
        value = DEFAULT_LOOP_STEP_TIMEOUT_SECONDS
    return max(value, 0)


def _resolve_blocked_policy(raw: str | None) -> str:
    value = str(raw or os.environ.get("AIDD_LOOP_BLOCKED_POLICY") or DEFAULT_BLOCKED_POLICY).strip().lower()
    if value not in BLOCKED_POLICY_VALUES:
        return DEFAULT_BLOCKED_POLICY
    return value


def _resolve_recoverable_retry_budget(raw: object) -> int:
    if raw is None or str(raw).strip() == "":
        raw = os.environ.get("AIDD_LOOP_RECOVERABLE_BLOCK_RETRIES", str(DEFAULT_RECOVERABLE_BLOCK_RETRIES))
    try:
        value = int(str(raw).strip())
    except (TypeError, ValueError):
        value = DEFAULT_RECOVERABLE_BLOCK_RETRIES
    return max(value, 0)


def _is_recoverable_block_reason(code: str) -> bool:
    reason_code = str(code or "").strip().lower()
    if reason_code in HARD_BLOCK_REASON_CODES:
        return False
    if reason_code in RECOVERABLE_BLOCK_REASON_CODES:
        return True
    if reason_code.startswith("stage_result_"):
        return True
    if reason_code.startswith("qa_repair_"):
        return True
    if reason_code.endswith("_warn"):
        return True
    return False


def _scope_to_work_item_key(scope_key: str) -> str:
    raw = runtime.sanitize_scope_key(scope_key or "")
    if raw.startswith("iteration_id_"):
        suffix = raw[len("iteration_id_"):].strip()
        if suffix:
            return f"iteration_id={suffix}"
    return ""


def _apply_recoverable_block_recovery(
    *,
    target: Path,
    ticket: str,
    stage: str,
    chosen_scope: str,
) -> Tuple[str, str]:
    active_work_item = str(runtime.read_active_work_item(target) or "").strip()
    if not runtime.is_valid_work_item_key(active_work_item):
        from_scope = _scope_to_work_item_key(chosen_scope)
        if from_scope:
            active_work_item = from_scope
            write_active_state(target, ticket=ticket, work_item=active_work_item)
    if stage in {"review", "qa"} and runtime.is_iteration_work_item_key(active_work_item):
        write_active_stage(target, "implement")
        return "handoff_to_implement", active_work_item
    if stage == "implement" and runtime.is_iteration_work_item_key(active_work_item):
        write_active_stage(target, "implement")
        return "retry_implement", active_work_item
    selected_next, _pending = select_next_work_item(target, ticket, active_work_item)
    if selected_next:
        write_active_state(target, ticket=ticket, work_item=selected_next)
        write_active_stage(target, "implement")
        return "select_next_open_work_item", selected_next
    if runtime.is_valid_work_item_key(active_work_item):
        fallback_stage = stage if stage in {"implement", "review", "qa"} else "implement"
        write_active_stage(target, fallback_stage)
        return "retry_active_stage", active_work_item
    return "retry_without_state", ""


def _latest_valid_stage_result_candidate(target: Path, ticket: str, stage: str) -> tuple[str, str]:
    if stage not in {"implement", "review", "qa"}:
        return "", ""
    base = target / "reports" / "loops" / ticket
    if not base.exists():
        return "", ""
    newest: tuple[float, str, str] | None = None
    pattern = f"stage.{stage}.result.json"
    for path in base.rglob(pattern):
        if not path.is_file():
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        normalized, error = stage_result_contract.normalize_stage_result_payload(payload, stage)
        if normalized is None or error:
            continue
        try:
            mtime = float(path.stat().st_mtime)
        except OSError:
            continue
        rel = runtime.rel_path(path, target)
        updated = str(normalized.get("updated_at") or "")
        if newest is None or mtime > newest[0]:
            newest = (mtime, rel, updated)
    if newest is None:
        return "", ""
    return newest[1], newest[2]


def _latest_loop_step_stream_artifact(
    target: Path,
    ticket: str,
    suffix: str,
    *,
    min_mtime: float | None = None,
) -> Optional[Path]:
    base = target / "reports" / "loops" / ticket
    if not base.exists():
        return None
    newest: tuple[float, Path] | None = None
    pattern = f"cli.loop-step.*.stream.{suffix}"
    for path in base.glob(pattern):
        if not path.is_file():
            continue
        try:
            mtime = float(path.stat().st_mtime)
        except OSError:
            continue
        if min_mtime is not None and mtime < min_mtime:
            continue
        if newest is None or mtime > newest[0]:
            newest = (mtime, path)
    return newest[1] if newest else None


def run_loop_step(
    plugin_root: Path,
    workspace_root: Path,
    target: Path,
    ticket: str,
    runner: str | None,
    *,
    from_qa: str | None,
    work_item_key: str | None,
    select_qa_handoff: bool,
    stream_mode: str | None,
    timeout_seconds: int,
) -> subprocess.CompletedProcess[str]:
    cmd = [
        sys.executable,
        str(plugin_root / "skills" / "aidd-loop" / "runtime" / "loop_step.py"),
        "--ticket",
        ticket,
        "--format",
        "json",
    ]
    if runner:
        cmd.extend(["--runner", runner])
    if from_qa:
        cmd.extend(["--from-qa", from_qa])
    if work_item_key:
        cmd.extend(["--work-item-key", work_item_key])
    if select_qa_handoff:
        cmd.append("--select-qa-handoff")
    if stream_mode:
        cmd.extend(["--stream", stream_mode])
    env = os.environ.copy()
    env["CLAUDE_PLUGIN_ROOT"] = str(plugin_root)
    env["PYTHONPATH"] = str(plugin_root) if not env.get("PYTHONPATH") else f"{plugin_root}:{env['PYTHONPATH']}"
    run_started_at = time.time()
    try:
        if stream_mode:
            return subprocess.run(
                cmd,
                text=True,
                stdout=subprocess.PIPE,
                stderr=None,
                cwd=workspace_root,
                env=env,
                timeout=timeout_seconds if timeout_seconds > 0 else None,
            )
        return subprocess.run(
            cmd,
            text=True,
            capture_output=True,
            cwd=workspace_root,
            env=env,
            timeout=timeout_seconds if timeout_seconds > 0 else None,
        )
    except subprocess.TimeoutExpired as exc:
        active_stage = str(runtime.read_active_stage(target) or "").strip().lower()
        active_work_item = str(runtime.read_active_work_item(target) or "").strip()
        if active_stage == "qa":
            scope_key = runtime.resolve_scope_key("", ticket)
        else:
            scope_key = runtime.resolve_scope_key(active_work_item, ticket)
        expected_stage_result_path = ""
        if active_stage in {"implement", "review", "qa"} and scope_key:
            expected_stage_result_path = f"aidd/reports/loops/{ticket}/{scope_key}/stage.{active_stage}.result.json"
        last_stage_result_path, last_stage_result_updated_at = _latest_valid_stage_result_candidate(
            target,
            ticket,
            active_stage,
        )
        diagnostics = {
            "active_stage": active_stage or None,
            "active_work_item": active_work_item or None,
            "scope_key": scope_key or None,
            "stall_timeout_seconds": timeout_seconds,
            "last_valid_stage_result_path": last_stage_result_path or None,
            "last_valid_stage_result_updated_at": last_stage_result_updated_at or None,
            "expected_stage_result_path": expected_stage_result_path or None,
        }
        stream_log_path = _latest_loop_step_stream_artifact(
            target,
            ticket,
            "log",
            min_mtime=max(run_started_at - 1.0, 0.0),
        )
        stream_jsonl_path = _latest_loop_step_stream_artifact(
            target,
            ticket,
            "jsonl",
            min_mtime=max(run_started_at - 1.0, 0.0),
        )
        stream_log_rel = runtime.rel_path(stream_log_path, target) if stream_log_path else ""
        stream_jsonl_rel = runtime.rel_path(stream_jsonl_path, target) if stream_jsonl_path else ""
        stream_liveness = {
            "main_log_bytes": 0,
            "main_log_updated_at": "",
            "step_stream_log_bytes": _safe_size(stream_log_path),
            "step_stream_log_updated_at": _safe_updated_at(stream_log_path),
            "step_stream_jsonl_bytes": _safe_size(stream_jsonl_path),
            "step_stream_jsonl_updated_at": _safe_updated_at(stream_jsonl_path),
            "observability_degraded": False,
        }
        if stream_liveness["step_stream_jsonl_bytes"] > 0 or stream_liveness["step_stream_log_bytes"] > 0:
            stream_liveness["active_source"] = "stream"
            reason_code = "seed_stage_active_stream_timeout"
            reason = (
                f"loop-step watchdog timeout after {timeout_seconds}s while stream artifacts remain active"
            )
        else:
            stream_liveness["active_source"] = "none"
            reason_code = "seed_stage_silent_stall"
            reason = f"loop-step watchdog timeout after {timeout_seconds}s without completion"
        diagnostics["stream_log_path"] = stream_log_rel or None
        diagnostics["stream_jsonl_path"] = stream_jsonl_rel or None
        diagnostics["stream_liveness"] = stream_liveness
        payload = {
            "status": "blocked",
            "stage": active_stage or None,
            "scope_key": scope_key or None,
            "work_item_key": active_work_item or None,
            "reason_code": reason_code,
            "reason": reason,
            "stage_result_path": expected_stage_result_path or last_stage_result_path or "",
            "stage_result_diagnostics": json.dumps(diagnostics, ensure_ascii=False),
            "stall_timeout_seconds": timeout_seconds,
            "stream_log_path": stream_log_rel,
            "stream_jsonl_path": stream_jsonl_rel,
            "stream_liveness": stream_liveness,
        }
        return subprocess.CompletedProcess(
            args=cmd,
            returncode=BLOCKED_CODE,
            stdout=json.dumps(payload, ensure_ascii=False),
            stderr=str(exc),
        )


def parse_args(argv: List[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run loop-step until SHIP.")
    parser.add_argument("--ticket", help="Ticket identifier (defaults to docs/.active.json).")
    parser.add_argument("--max-iterations", type=int, default=10, help="Maximum number of loop iterations.")
    parser.add_argument("--sleep-seconds", type=float, default=0.0, help="Sleep between iterations.")
    parser.add_argument("--runner", help="Runner command override.")
    parser.add_argument("--runner-label", help="Runner label for logs (claude_cli|ci|local).")
    parser.add_argument("--format", choices=("json", "yaml"), help="Emit structured output to stdout.")
    parser.add_argument(
        "--stream",
        nargs="?",
        const="text",
        help="Enable agent streaming output (text|tools|raw).",
    )
    parser.add_argument(
        "--agent-stream",
        dest="stream",
        nargs="?",
        const="text",
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--from-qa",
        nargs="?",
        const="manual",
        choices=("manual", "auto"),
        help="Allow repair from QA blocked stage (manual|auto).",
    )
    parser.add_argument(
        "--repair-from-qa",
        dest="from_qa",
        nargs="?",
        const="manual",
        choices=("manual", "auto"),
        help=argparse.SUPPRESS,
    )
    parser.add_argument("--work-item-key", help="Explicit work item key for QA repair (iteration_id=... or id=...).")
    parser.add_argument(
        "--select-qa-handoff",
        action="store_true",
        help="Auto-select blocking QA handoff item when repairing from QA.",
    )
    parser.add_argument(
        "--step-timeout-seconds",
        type=int,
        help="Watchdog timeout for each loop-step subprocess (default from env or 900).",
    )
    parser.add_argument(
        "--blocked-policy",
        choices=("strict", "ralph"),
        help="Blocked outcome policy (strict|ralph). In ralph mode recoverable blocked reasons trigger bounded retries.",
    )
    parser.add_argument(
        "--recoverable-block-retries",
        type=int,
        help="Retry budget for recoverable blocked outcomes in ralph mode (default from env or 2).",
    )
    return parser.parse_args(argv)


def emit(fmt: str | None, payload: Dict[str, object]) -> None:
    if fmt == "json":
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return
    if fmt == "yaml":
        print("\n".join(dump_yaml(payload)))
        return
    summary = f"[loop-run] status={payload.get('status')} iterations={payload.get('iterations')}"
    if payload.get("log_path"):
        summary += f" log={payload.get('log_path')}"
    print(summary)


def main(argv: List[str] | None = None) -> int:
    args = parse_args(argv)
    workspace_root, target = runtime.require_workflow_root()
    context = runtime.resolve_feature_context(target, ticket=args.ticket, slug_hint=None)
    ticket = (context.resolved_ticket or "").strip()
    if not ticket:
        raise ValueError("feature ticket is required; pass --ticket or set docs/.active.json via /feature-dev-aidd:idea-new.")

    plugin_root = runtime.require_plugin_root()
    log_path = target / "reports" / "loops" / ticket / "loop.run.log"
    max_iterations = max(1, int(args.max_iterations))
    sleep_seconds = max(0.0, float(args.sleep_seconds))
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%d-%H%M%S")
    cli_log_path = target / "reports" / "loops" / ticket / f"cli.loop-run.{stamp}.log"
    runner_label = resolve_runner_label(args.runner_label)
    stream_mode = resolve_stream_mode(getattr(args, "stream", None))
    step_timeout_seconds = _resolve_step_timeout_seconds(getattr(args, "step_timeout_seconds", None))
    blocked_policy = _resolve_blocked_policy(getattr(args, "blocked_policy", None))
    recoverable_retry_budget = _resolve_recoverable_retry_budget(getattr(args, "recoverable_block_retries", None))
    recoverable_retry_attempt = 0
    last_recovery_path = ""
    stream_log_path = None
    stream_jsonl_path = None
    if stream_mode:
        stream_log_path = target / "reports" / "loops" / ticket / f"cli.loop-run.{stamp}.stream.log"
        stream_jsonl_path = target / "reports" / "loops" / ticket / f"cli.loop-run.{stamp}.stream.jsonl"
        stream_jsonl_path.parent.mkdir(parents=True, exist_ok=True)
        stream_jsonl_path.touch(exist_ok=True)
        append_log(
            stream_log_path,
            f"==> loop-run: ticket={ticket} stream_mode={stream_mode}",
        )
    append_log(
        cli_log_path,
        (
            f"{utc_timestamp()} event=start ticket={ticket} max_iterations={max_iterations} runner={runner_label} "
            f"blocked_policy={blocked_policy} recoverable_retry_budget={recoverable_retry_budget}"
        ),
    )

    if args.work_item_key and not runtime.is_valid_work_item_key(args.work_item_key):
        clear_active_mode(target)
        payload = {
            "status": "blocked",
            "iterations": 0,
            "exit_code": BLOCKED_CODE,
            "log_path": runtime.rel_path(log_path, target),
            "cli_log_path": runtime.rel_path(cli_log_path, target),
            "runner_label": runner_label,
            "blocked_policy": blocked_policy,
            "reason": "--work-item-key must use iteration_id=... or id=...",
            "reason_code": "work_item_invalid_format",
            "updated_at": utc_timestamp(),
        }
        append_log(
            log_path,
            f"{utc_timestamp()} ticket={ticket} iteration=0 status=blocked reason_code=work_item_invalid_format",
        )
        append_log(cli_log_path, f"{utc_timestamp()} event=blocked iterations=0 reason_code=work_item_invalid_format")
        emit(args.format, payload)
        return BLOCKED_CODE

    if not args.work_item_key:
        active_work_item = runtime.read_active_work_item(target)
        if args.from_qa:
            if not runtime.is_valid_work_item_key(active_work_item):
                append_log(
                    log_path,
                    (
                        f"{utc_timestamp()} event=skip-auto-select-work-item ticket={ticket} "
                        "reason=from_qa_requested active_work_item=missing_or_invalid"
                    ),
                )
                append_log(
                    cli_log_path,
                    f"{utc_timestamp()} event=skip-auto-select-work-item reason=from_qa_requested",
                )
        elif not runtime.is_valid_work_item_key(active_work_item):
            selected_next, pending_count = select_next_work_item(target, ticket, active_work_item)
            if selected_next:
                write_active_state(target, ticket=ticket, work_item=selected_next)
                write_active_stage(target, "implement")
                append_log(
                    log_path,
                    (
                        f"{utc_timestamp()} event=auto-select-work-item ticket={ticket} "
                        f"selected={selected_next} pending_iterations_count={pending_count}"
                    ),
                )
                append_log(
                    cli_log_path,
                    f"{utc_timestamp()} event=auto-select-work-item selected={selected_next}",
                )
            else:
                clear_active_mode(target)
                payload = {
                    "status": "blocked",
                    "iterations": 0,
                    "exit_code": BLOCKED_CODE,
                    "log_path": runtime.rel_path(log_path, target),
                    "cli_log_path": runtime.rel_path(cli_log_path, target),
                    "runner_label": runner_label,
                    "blocked_policy": blocked_policy,
                    "reason": "no active work item and no open iteration found in tasklist",
                    "reason_code": "work_item_missing",
                    "updated_at": utc_timestamp(),
                }
                append_log(
                    log_path,
                    f"{utc_timestamp()} ticket={ticket} iteration=0 status=blocked reason_code=work_item_missing",
                )
                append_log(cli_log_path, f"{utc_timestamp()} event=blocked iterations=0 reason_code=work_item_missing")
                emit(args.format, payload)
                return BLOCKED_CODE

    last_payload: Dict[str, object] = {}
    for iteration in range(1, max_iterations + 1):
        result = run_loop_step(
            plugin_root,
            workspace_root,
            target,
            ticket,
            args.runner,
            from_qa=args.from_qa,
            work_item_key=args.work_item_key,
            select_qa_handoff=args.select_qa_handoff,
            stream_mode=stream_mode,
            timeout_seconds=step_timeout_seconds,
        )
        if result.returncode not in {DONE_CODE, CONTINUE_CODE, BLOCKED_CODE}:
            status = "error"
            payload = {
                "status": status,
                "iterations": iteration,
                "exit_code": ERROR_CODE,
                "log_path": runtime.rel_path(log_path, target),
                "cli_log_path": runtime.rel_path(cli_log_path, target),
                "runner_label": runner_label,
                "blocked_policy": blocked_policy,
                "retry_attempt": recoverable_retry_attempt,
                "recoverable_retry_budget": recoverable_retry_budget,
                "stream_log_path": runtime.rel_path(stream_log_path, target) if stream_log_path else "",
                "stream_jsonl_path": runtime.rel_path(stream_jsonl_path, target) if stream_jsonl_path else "",
                "reason": f"loop-step failed ({result.returncode})",
                "updated_at": utc_timestamp(),
            }
            append_log(
                log_path,
                f"{utc_timestamp()} iteration={iteration} status=error code={result.returncode} runner={runner_label}",
            )
            append_log(
                cli_log_path,
                f"{utc_timestamp()} event=error iteration={iteration} exit_code={result.returncode}",
            )
            clear_active_mode(target)
            emit(args.format, payload)
            return ERROR_CODE
        parse_error = ""
        try:
            step_payload = json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            step_payload = {}
            parse_error = str(exc)
        last_payload = step_payload
        reason = step_payload.get("reason") or ""
        reason_code = step_payload.get("reason_code") or ""
        repair_code = step_payload.get("repair_reason_code") or ""
        repair_scope = step_payload.get("repair_scope_key") or ""
        step_stage = str(step_payload.get("stage") or "").strip().lower()
        step_work_item = str(step_payload.get("work_item_key") or "").strip()
        scope_key = step_payload.get("scope_key") or ""
        mismatch_warn = step_payload.get("scope_key_mismatch_warn") or ""
        mismatch_from = step_payload.get("scope_key_mismatch_from") or ""
        mismatch_to = step_payload.get("scope_key_mismatch_to") or ""
        active_stage_before = str(step_payload.get("active_stage_before") or "").strip()
        active_stage_after = str(step_payload.get("active_stage_after") or "").strip()
        active_stage_sync_applied = bool(step_payload.get("active_stage_sync_applied"))
        step_command_log = step_payload.get("log_path") or ""
        step_cli_log_path = step_payload.get("cli_log_path") or ""
        tests_log_path = step_payload.get("tests_log_path") or ""
        stage_diag = step_payload.get("stage_result_diagnostics") or ""
        marker_signal_events = (
            [
                str(item).strip()
                for item in (step_payload.get("marker_signal_events") or [])
                if str(item).strip()
            ]
            if isinstance(step_payload.get("marker_signal_events"), list)
            else []
        )
        report_noise_events = (
            [
                str(item).strip()
                for item in (step_payload.get("report_noise_events") or [])
                if str(item).strip()
            ]
            if isinstance(step_payload.get("report_noise_events"), list)
            else []
        )
        if not marker_signal_events and not report_noise_events:
            marker_signal_events, report_noise_events = _scan_marker_semantics(
                [
                    ("reason", str(reason or "")),
                    ("stage_result_diagnostics", str(stage_diag or "")),
                ]
            )
        report_noise = "marker_semantics_noise_only" if report_noise_events and not marker_signal_events else ""
        stage_result_path = step_payload.get("stage_result_path") or ""
        wrapper_logs_raw = step_payload.get("wrapper_logs")
        wrapper_logs = (
            [str(item) for item in wrapper_logs_raw if str(item).strip()]
            if isinstance(wrapper_logs_raw, list)
            else []
        )
        runner_effective = step_payload.get("runner_effective") or ""
        if not str(runner_effective).strip():
            runner_effective = str(args.runner or os.environ.get("AIDD_LOOP_RUNNER") or "claude").strip() or "claude"
        step_stream_log = step_payload.get("stream_log_path") or ""
        step_stream_jsonl = step_payload.get("stream_jsonl_path") or ""
        step_status = step_payload.get("status")
        step_exit_code = result.returncode
        if step_exit_code == DONE_CODE:
            step_status = "done"
        elif step_exit_code == BLOCKED_CODE:
            step_status = "blocked"
        elif step_exit_code == CONTINUE_CODE and str(step_status).strip().lower() not in {"continue", "blocked", "done"}:
            step_status = "continue"
        work_item_resolution_invalid = (
            step_stage in {"implement", "review"}
            and not runtime.is_valid_work_item_key(step_work_item)
        )
        if work_item_resolution_invalid:
            step_exit_code = BLOCKED_CODE
            step_status = "blocked"
            reason = (
                f"{step_stage} loop-step payload missing valid work_item_key "
                f"(got '{step_work_item or 'null'}')"
            )
            reason_code = "work_item_resolution_failed"
        if step_exit_code == CONTINUE_CODE and str(reason_code).strip().lower() == "user_approval_required":
            step_exit_code = BLOCKED_CODE
            step_status = "blocked"
            if not reason:
                reason = "user approval required"
        log_reason_code = repair_code or reason_code
        if not str(log_reason_code).strip() and step_status == "blocked":
            log_reason_code = "stage_result_blocked" if stage_result_path else "blocked_without_reason"
        if parse_error and not str(log_reason_code).strip():
            log_reason_code = "invalid_loop_step_payload"
        if work_item_resolution_invalid:
            log_reason_code = "work_item_resolution_failed"
        if step_status == "blocked" and _permission_mismatch_from_text(str(reason), str(stage_diag), str(log_reason_code)):
            log_reason_code = "loop_runner_permissions"
            if not str(reason).strip():
                reason = "loop runner permission mismatch"
        if not str(reason).strip() and step_status == "blocked":
            if parse_error:
                reason = f"loop-step returned invalid JSON payload: {parse_error}"
            else:
                reason = f"{step_stage or 'stage'} blocked"
        chosen_scope = repair_scope or scope_key
        if mismatch_to:
            chosen_scope = mismatch_to
        if not str(chosen_scope).strip() and runtime.is_valid_work_item_key(step_work_item):
            chosen_scope = runtime.resolve_scope_key(step_work_item, ticket)
        recoverable_blocked = bool(step_status == "blocked" and _is_recoverable_block_reason(str(log_reason_code)))
        if not stage_result_path and step_status == "blocked":
            step_stage = str(step_payload.get("stage") or "").strip().lower()
            fallback_scope = str(chosen_scope or runtime.resolve_scope_key("", ticket)).strip()
            if step_stage:
                stage_result_path = f"aidd/reports/loops/{ticket}/{fallback_scope}/stage.{step_stage}.result.json"
        if stream_mode and stream_log_path and step_stream_log:
            step_stream_log_path = runtime.resolve_path_for_target(Path(step_stream_log), target)
            append_stream_file(
                stream_log_path,
                step_stream_log_path,
                header=(
                    f"==> loop-step iteration={iteration} stage={step_payload.get('stage')} "
                    f"stream_log={step_stream_log}"
                ),
            )
        if stream_mode and stream_jsonl_path and step_stream_jsonl:
            step_jsonl_path = runtime.resolve_path_for_target(Path(step_stream_jsonl), target)
            append_stream_file(stream_jsonl_path, step_jsonl_path)
        step_main_log_abs = _resolve_optional_path(target, step_command_log)
        main_log_abs = step_main_log_abs if step_main_log_abs and step_main_log_abs.exists() else log_path
        step_stream_log_abs = _resolve_optional_path(target, step_stream_log)
        step_stream_jsonl_abs = _resolve_optional_path(target, step_stream_jsonl)
        stream_liveness = {
            "main_log_path": runtime.rel_path(main_log_abs, target),
            "main_log_bytes": _safe_size(main_log_abs),
            "main_log_updated_at": _safe_updated_at(main_log_abs),
            "step_stream_log_bytes": _safe_size(step_stream_log_abs),
            "step_stream_log_updated_at": _safe_updated_at(step_stream_log_abs),
            "step_stream_jsonl_bytes": _safe_size(step_stream_jsonl_abs),
            "step_stream_jsonl_updated_at": _safe_updated_at(step_stream_jsonl_abs),
            "observability_degraded": False,
        }
        if stream_liveness["step_stream_jsonl_bytes"] > 0 or stream_liveness["step_stream_log_bytes"] > 0:
            stream_liveness["active_source"] = "stream"
        elif stream_liveness["main_log_bytes"] > 0:
            stream_liveness["active_source"] = "main_log"
        else:
            stream_liveness["active_source"] = "none"
        if stream_mode and stream_liveness["active_source"] == "main_log":
            stream_liveness["observability_degraded"] = True
            if step_stream_log or step_stream_jsonl:
                stream_liveness["degraded_reason"] = "stream_artifacts_missing_or_empty"
            else:
                stream_liveness["degraded_reason"] = "stream_paths_missing"
        append_log(
            log_path,
            (
                f"{utc_timestamp()} ticket={ticket} iteration={iteration} status={step_status} "
                f"result={step_status} stage={step_payload.get('stage')} scope_key={scope_key} "
                f"work_item_key={step_work_item or 'null'} "
                f"exit_code={step_exit_code} reason_code={log_reason_code} runner={runner_label} "
                f"runner_cmd={runner_effective} reason={reason} blocked_policy={blocked_policy} "
                f"recoverable_blocked={'1' if recoverable_blocked else '0'}"
                + (f" chosen_scope_key={chosen_scope}" if chosen_scope else "")
                + (f" scope_key_mismatch_warn={mismatch_warn}" if mismatch_warn else "")
                + (f" mismatch_from={mismatch_from} mismatch_to={mismatch_to}" if mismatch_to else "")
                + (f" active_stage_before={active_stage_before}" if active_stage_before else "")
                + (f" active_stage_after={active_stage_after}" if active_stage_after else "")
                + (f" active_stage_sync_applied={'1' if active_stage_sync_applied else '0'}")
                + (f" log_path={step_command_log}" if step_command_log else "")
                + (f" step_cli_log_path={step_cli_log_path}" if step_cli_log_path else "")
                + (f" tests_log_path={tests_log_path}" if tests_log_path else "")
                + (f" stage_result_diagnostics={stage_diag}" if stage_diag else "")
                + (f" stage_result_path={stage_result_path}" if stage_result_path else "")
                + (f" wrapper_logs={','.join(wrapper_logs)}" if wrapper_logs else "")
                + (
                    " stream_liveness="
                    f"main:{stream_liveness['main_log_bytes']},"
                    f"step_log:{stream_liveness['step_stream_log_bytes']},"
                    f"step_jsonl:{stream_liveness['step_stream_jsonl_bytes']},"
                    f"active:{stream_liveness['active_source']}"
                )
                + (
                    f" observability_degraded={'1' if stream_liveness.get('observability_degraded') else '0'}"
                )
                + (
                    f" observability_reason={stream_liveness.get('degraded_reason')}"
                    if stream_liveness.get("degraded_reason")
                    else ""
                )
                + f" marker_signals={len(marker_signal_events)} marker_noise={len(report_noise_events)}"
                + (f" report_noise={report_noise}" if report_noise else "")
            ),
        )
        append_log(
            cli_log_path,
            (
                f"{utc_timestamp()} event=step iteration={iteration} status={step_status} "
                f"stage={step_payload.get('stage')} scope_key={scope_key} exit_code={step_exit_code} "
                f"runner_cmd={runner_effective} blocked_policy={blocked_policy} "
                f"recoverable_blocked={'1' if recoverable_blocked else '0'} "
                f"work_item_key={step_work_item or 'null'} "
                f"active_stage_sync_applied={'1' if active_stage_sync_applied else '0'}"
            ),
        )
        if step_exit_code == DONE_CODE:
            step_stage = str(step_payload.get("stage") or "").strip().lower()
            selected_next = ""
            pending_count = 0
            if step_stage == "review":
                current_work_item = runtime.read_active_work_item(target)
                selected_next, pending_count = select_next_work_item(target, ticket, current_work_item)
                append_log(
                    log_path,
                    (
                        f"{utc_timestamp()} event=ship iteration={iteration} "
                        f"pending_iterations_count={pending_count} "
                        f"selected_next_work_item={selected_next or 'none'} "
                        f"runner_cmd={runner_effective}"
                    ),
                )
                append_log(
                    cli_log_path,
                    (
                        f"{utc_timestamp()} event=ship iteration={iteration} "
                        f"pending_iterations_count={pending_count} "
                        f"selected_next_work_item={selected_next or 'none'}"
                    ),
                )
                if selected_next:
                    write_active_state(target, ticket=ticket, work_item=selected_next)
                    write_active_stage(target, "implement")
                    append_log(
                        log_path,
                        (
                            f"{utc_timestamp()} event=continue "
                            f"next_work_item={selected_next} pending_iterations_count={pending_count}"
                        ),
                    )
                    append_log(
                        cli_log_path,
                        f"{utc_timestamp()} event=continue next_work_item={selected_next}",
                    )
                    continue
            clear_active_mode(target)
            payload = {
                "status": "ship",
                "iterations": iteration,
                "exit_code": DONE_CODE,
                "log_path": runtime.rel_path(log_path, target),
                "cli_log_path": runtime.rel_path(cli_log_path, target),
                "runner_label": runner_label,
                "blocked_policy": blocked_policy,
                "retry_attempt": recoverable_retry_attempt,
                "recoverable_retry_budget": recoverable_retry_budget,
                "stream_log_path": runtime.rel_path(stream_log_path, target) if stream_log_path else "",
                "stream_jsonl_path": runtime.rel_path(stream_jsonl_path, target) if stream_jsonl_path else "",
                "last_step": step_payload,
                "updated_at": utc_timestamp(),
            }
            append_log(cli_log_path, f"{utc_timestamp()} event=done iterations={iteration}")
            emit(args.format, payload)
            return DONE_CODE
        if step_exit_code == BLOCKED_CODE:
            step_stage = str(step_payload.get("stage") or "").strip().lower()
            if (
                blocked_policy == "ralph"
                and recoverable_blocked
                and recoverable_retry_attempt < recoverable_retry_budget
            ):
                recoverable_retry_attempt += 1
                recovery_path, recovery_work_item = _apply_recoverable_block_recovery(
                    target=target,
                    ticket=ticket,
                    stage=step_stage,
                    chosen_scope=str(chosen_scope or ""),
                )
                last_recovery_path = recovery_path
                step_payload = dict(step_payload)
                step_payload["recoverable_blocked"] = True
                step_payload["retry_attempt"] = recoverable_retry_attempt
                step_payload["recovery_path"] = recovery_path
                step_payload["blocked_policy"] = blocked_policy
                step_payload["recovery_work_item"] = recovery_work_item or None
                last_payload = step_payload
                append_log(
                    log_path,
                    (
                        f"{utc_timestamp()} event=recoverable-block iteration={iteration} "
                        f"reason_code={log_reason_code} retry_attempt={recoverable_retry_attempt}/"
                        f"{recoverable_retry_budget} recovery_path={recovery_path} "
                        f"recovery_work_item={recovery_work_item or 'n/a'}"
                    ),
                )
                append_log(
                    cli_log_path,
                    (
                        f"{utc_timestamp()} event=recoverable-block iteration={iteration} "
                        f"reason_code={log_reason_code} retry_attempt={recoverable_retry_attempt}/"
                        f"{recoverable_retry_budget} recovery_path={recovery_path}"
                    ),
                )
                if sleep_seconds:
                    time.sleep(sleep_seconds)
                continue
            clear_active_mode(target)
            payload = {
                "status": "blocked",
                "iterations": iteration,
                "exit_code": BLOCKED_CODE,
                "log_path": runtime.rel_path(log_path, target),
                "cli_log_path": runtime.rel_path(cli_log_path, target),
                "runner_label": runner_label,
                "blocked_policy": blocked_policy,
                "stream_log_path": runtime.rel_path(stream_log_path, target) if stream_log_path else "",
                "stream_jsonl_path": runtime.rel_path(stream_jsonl_path, target) if stream_jsonl_path else "",
                "reason": reason,
                "reason_code": log_reason_code,
                "recoverable_blocked": recoverable_blocked,
                "retry_attempt": recoverable_retry_attempt,
                "recoverable_retry_budget": recoverable_retry_budget,
                "recovery_path": last_recovery_path,
                "runner_cmd": runner_effective,
                "scope_key": chosen_scope,
                "work_item_key": step_work_item or None,
                "active_stage_before": active_stage_before or None,
                "active_stage_after": active_stage_after or None,
                "active_stage_sync_applied": active_stage_sync_applied,
                "marker_signal_events": marker_signal_events,
                "report_noise_events": report_noise_events,
                "report_noise": report_noise,
                "step_log_path": step_command_log,
                "step_cli_log_path": step_cli_log_path,
                "stage_result_path": stage_result_path,
                "wrapper_logs": wrapper_logs,
                "step_stream_log_path": step_stream_log,
                "step_stream_jsonl_path": step_stream_jsonl,
                "stream_liveness": stream_liveness,
                "last_step": step_payload,
                "updated_at": utc_timestamp(),
            }
            append_log(cli_log_path, f"{utc_timestamp()} event=blocked iterations={iteration}")
            emit(args.format, payload)
            return BLOCKED_CODE
        if sleep_seconds:
            time.sleep(sleep_seconds)

    payload = {
        "status": "max-iterations",
        "iterations": max_iterations,
        "exit_code": MAX_ITERATIONS_CODE,
        "log_path": runtime.rel_path(log_path, target),
        "cli_log_path": runtime.rel_path(cli_log_path, target),
        "runner_label": runner_label,
        "blocked_policy": blocked_policy,
        "retry_attempt": recoverable_retry_attempt,
        "recoverable_retry_budget": recoverable_retry_budget,
        "last_recovery_path": last_recovery_path,
        "stream_log_path": runtime.rel_path(stream_log_path, target) if stream_log_path else "",
        "stream_jsonl_path": runtime.rel_path(stream_jsonl_path, target) if stream_jsonl_path else "",
        "last_step": last_payload,
        "updated_at": utc_timestamp(),
    }
    clear_active_mode(target)
    append_log(cli_log_path, f"{utc_timestamp()} event=max-iterations iterations={max_iterations}")
    emit(args.format, payload)
    return MAX_ITERATIONS_CODE


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
