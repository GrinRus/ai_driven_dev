#!/usr/bin/env python3
"""Run loop-step repeatedly until SHIP or limits reached."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import datetime as dt
import re
from pathlib import Path
from typing import Dict, List, Optional

from aidd_runtime import runtime
from aidd_runtime import loop_block_policy
from aidd_runtime.feature_ids import write_active_state
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
_MARKER_NOISE_SECTION_HINTS = ("aidd:how_to_update", "aidd:progress_log")
_MARKER_NOISE_PLACEHOLDERS = ("<title>", "<ticket>", "<scope_key>", "<commit/pr|report>")
_MARKER_INLINE_PATH_RE = re.compile(r"(?P<path>(?:aidd|docs|reports)/[^\s,;]+)", re.IGNORECASE)
_REASON_CODE_RE = re.compile(r"\breason_code=([a-z0-9_:-]+)\b", re.IGNORECASE)
_NEXT_ACTION_RE = re.compile(r"Next action:\s*`([^`]+)`", re.IGNORECASE)
_LEGACY_STAGE_ALIAS_TO_CANONICAL = {
    "/feature-dev-aidd:planner": "/feature-dev-aidd:plan-new",
    "/feature-dev-aidd:tasklist-refiner": "/feature-dev-aidd:tasks-new",
    "/feature-dev-aidd:implementer": "/feature-dev-aidd:implement",
    "/feature-dev-aidd:reviewer": "/feature-dev-aidd:review",
}
_NON_CANONICAL_LOOP_PACK_PATH_REPLACEMENTS = (
    (
        re.compile(r"(?i)\bskills/aidd-flow-state/runtime/loop_pack\.py\b"),
        "skills/aidd-loop/runtime/loop_pack.py",
    ),
    (
        re.compile(r"(?i)/skills/aidd-flow-state/runtime/loop_pack\.py"),
        "/skills/aidd-loop/runtime/loop_pack.py",
    ),
)
_SCOPE_STALE_HINT_RE = re.compile(
    r"\b(?:scope_fallback_stale_ignored|scope_shape_invalid)=([A-Za-z0-9_.:-]+)\b",
    re.IGNORECASE,
)
DEFAULT_LOOP_STEP_TIMEOUT_SECONDS = 3600
DEFAULT_SILENT_STALL_SECONDS = 1200
DEFAULT_STAGE_BUDGET_SECONDS = 3600
DEFAULT_RECOVERABLE_BLOCK_RETRIES = 2
DEFAULT_LOOP_RESEARCH_GATE_MODE = "auto"
RESEARCH_GATE_MODE_VALUES = {"off", "on", "auto"}
STAGE_DEFAULT_BUDGET_SECONDS = {
    "implement": 3600,
    "review": 3600,
    "qa": 3600,
}
DEFAULT_RESEARCH_GATE_PROBE_TIMEOUT_SECONDS = 180
LOOP_RESULT_SCHEMA = "aidd.loop_result.v1"
PROMPT_FLOW_DRIFT_REASON_FAMILY = "prompt_flow_drift_non_canonical_runtime_path"
LOOP_RESEARCH_SOFT_REASON_CODES = {
    "research_status_invalid",
    "rlm_links_empty_warn",
    "rlm_status_pending",
}

if not __package__:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    __package__ = "loop_run_parts"

from .helpers_preparse import (
    _apply_recoverable_block_recovery,
    _build_termination_attribution,
    _expand_next_action_command,
    _extract_next_action,
    _normalize_termination_attribution,
    _permission_mismatch_from_text,
    _promote_stage_result_reason,
    _research_gate_recovery_path,
    _resolve_loop_research_gate_mode,
    _resolve_path_within_target,
    _resolve_recoverable_retry_budget,
    _resolve_silent_stall_seconds,
    _resolve_stage_budget_seconds,
    _resolve_step_timeout_seconds,
    _run_research_gate_probe,
    _safe_mtime,
    _safe_size,
    _safe_updated_at,
    _scan_marker_semantics,
    _should_enforce_loop_research_gate,
    _truthy_flag,
    _validate_loop_research_gate,
    append_log,
    append_stream_file,
    clear_active_mode,
    resolve_runner_label,
    resolve_stream_mode,
    run_loop_step,
    select_next_work_item,
    write_active_stage,
)
__all__ = [
    "main",
    "_expand_next_action_command",
    "_extract_next_action",
]

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
        "--silent-stall-seconds",
        type=int,
        help="Silent stall watchdog window (seconds) when stream liveness is unavailable (default from env or 1200).",
    )
    parser.add_argument(
        "--stage-budget-seconds",
        type=int,
        help=(
            "Per-stage budget in seconds before terminal timeout classification "
            "(default: implement/review/qa=3600; override via env or this flag)."
        ),
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
    parser.add_argument(
        "--research-gate",
        choices=("off", "on", "auto"),
        help="Research/RLM gate mode before auto-loop (off|on|auto).",
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
    # Keep a machine-readable top-level result event in text mode so audit parsers
    # can reliably detect terminal loop outcomes in main logs.
    event = {
        "type": "result",
        "schema": LOOP_RESULT_SCHEMA,
        "status": payload.get("status"),
        "exit_code": payload.get("exit_code"),
        "reason_code": payload.get("reason_code", ""),
        "payload": payload,
    }
    print(json.dumps(event, ensure_ascii=False))


def _ralph_recoverable_semantics(
    *,
    blocked_policy: str,
    reason_code: str,
    reason_class: str,
    recoverable_blocked: bool,
    retry_attempt: int,
    recoverable_retry_budget: int,
) -> Dict[str, object]:
    if blocked_policy != "ralph":
        return {
            "ralph_policy_version": "",
            "ralph_reason_class": "n/a",
            "ralph_recoverable_reason_scope": "n/a",
            "ralph_recoverable_expected": False,
            "ralph_recoverable_exercised": False,
            "ralph_recoverable_not_exercised": False,
            "ralph_recoverable_not_exercised_reason": "",
        }
    normalized_reason = str(reason_code or "").strip() or "blocked_without_reason"
    normalized_class = str(reason_class or "").strip() or "not_recoverable"
    expected = normalized_class == "recoverable_retry"
    exercised = bool(expected and recoverable_blocked)
    not_exercised_reason = ""
    if not exercised:
        if expected:
            if int(retry_attempt) >= int(recoverable_retry_budget):
                not_exercised_reason = f"recoverable_budget_exhausted:{normalized_reason}"
            else:
                not_exercised_reason = f"recoverable_not_applied:{normalized_reason}"
        else:
            not_exercised_reason = f"reason_not_recoverable_by_policy:{normalized_reason}"
    return {
        "ralph_policy_version": loop_block_policy.RALPH_POLICY_VERSION,
        "ralph_reason_class": normalized_class,
        "ralph_recoverable_reason_scope": "policy_matrix_v2",
        "ralph_recoverable_expected": expected,
        "ralph_recoverable_exercised": exercised,
        "ralph_recoverable_not_exercised": not exercised,
        "ralph_recoverable_not_exercised_reason": not_exercised_reason,
    }


def main(argv: List[str] | None = None) -> int:
    args = parse_args(argv)
    workspace_root, target = runtime.require_workflow_root()
    context = runtime.resolve_feature_context(target, ticket=args.ticket, slug_hint=None)
    ticket = (context.resolved_ticket or "").strip()
    if not ticket:
        raise ValueError("feature ticket is required; pass --ticket or set docs/.active.json via /feature-dev-aidd:idea-new.")

    plugin_root = runtime.resolve_plugin_root_with_fallback(start_file=Path(__file__))
    log_path = target / "reports" / "loops" / ticket / "loop.run.log"
    max_iterations = max(1, int(args.max_iterations))
    sleep_seconds = max(0.0, float(args.sleep_seconds))
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%d-%H%M%S")
    cli_log_path = target / "reports" / "loops" / ticket / f"cli.loop-run.{stamp}.log"
    runner_label = resolve_runner_label(args.runner_label)
    stream_mode = resolve_stream_mode(getattr(args, "stream", None))
    step_timeout_seconds = _resolve_step_timeout_seconds(getattr(args, "step_timeout_seconds", None))
    silent_stall_seconds = _resolve_silent_stall_seconds(getattr(args, "silent_stall_seconds", None))
    blocked_policy = loop_block_policy.resolve_blocked_policy(
        getattr(args, "blocked_policy", None),
        target=target,
    )
    recoverable_retry_budget = _resolve_recoverable_retry_budget(getattr(args, "recoverable_block_retries", None))
    research_gate_mode = _resolve_loop_research_gate_mode(getattr(args, "research_gate", None))
    research_gate_softened = False
    research_gate_soft_reason = ""
    research_gate_soft_policy = "always"
    stage_budget_starts: Dict[str, float] = {}
    recoverable_retry_attempt = 0
    last_recovery_path = ""
    scope_drift_recovery_probe_used = False
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
            f"blocked_policy={blocked_policy} recoverable_retry_budget={recoverable_retry_budget} "
            f"research_gate={research_gate_mode} step_timeout_seconds={step_timeout_seconds} "
            f"silent_stall_seconds={silent_stall_seconds}"
        ),
    )

    def _attach_research_gate_telemetry(payload: Dict[str, object]) -> Dict[str, object]:
        payload["research_gate_softened"] = bool(research_gate_softened)
        payload["research_gate_soft_reason"] = research_gate_soft_reason
        payload["research_gate_soft_policy"] = research_gate_soft_policy
        return payload

    if args.work_item_key and not runtime.is_valid_work_item_key(args.work_item_key):
        clear_active_mode(target)
        payload = {
            "status": "blocked",
            "terminal_marker": 1,
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
        emit(args.format, _attach_research_gate_telemetry(payload))
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
                    "terminal_marker": 1,
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
                emit(args.format, _attach_research_gate_telemetry(payload))
                return BLOCKED_CODE

    if _should_enforce_loop_research_gate(target, ticket, research_gate_mode):
        research_ok, research_reason_code, research_reason, research_next_action = _validate_loop_research_gate(
            target,
            ticket,
        )
        if research_ok and str(research_reason_code or "").strip().lower() in LOOP_RESEARCH_SOFT_REASON_CODES:
            research_gate_softened = True
            research_gate_soft_reason = str(research_reason_code or "").strip().lower()
            append_log(
                log_path,
                (
                    f"{utc_timestamp()} event=research-gate-softened-by-guard "
                    f"reason_code={research_gate_soft_reason} policy={research_gate_soft_policy}"
                ),
            )
            append_log(
                cli_log_path,
                (
                    f"{utc_timestamp()} event=research-gate-softened-by-guard "
                    f"reason_code={research_gate_soft_reason}"
                ),
            )
        if not research_ok:
            research_reason_code = str(research_reason_code or "").strip().lower() or "research_gate_blocked"
            gate_classification = loop_block_policy.classify_block_reason(
                research_reason_code,
                blocked_policy,
                os.environ.get("AIDD_HOOKS_MODE"),
                target=target,
            )
            gate_reason_class = str(gate_classification.get("reason_class") or "not_recoverable")
            recoverable_gate = (
                blocked_policy == "ralph"
                and gate_reason_class == "recoverable_retry"
                and recoverable_retry_attempt < recoverable_retry_budget
            )
            if recoverable_gate:
                recoverable_retry_attempt += 1
                last_recovery_path = _research_gate_recovery_path(research_reason_code)
                probe_ok, probe_command, probe_detail, probe_exit_code = _run_research_gate_probe(
                    target=target,
                    plugin_root=plugin_root,
                    next_action=research_next_action,
                )
                append_log(
                    log_path,
                    (
                        f"{utc_timestamp()} event=research-gate-recovery-probe "
                        f"retry_attempt={recoverable_retry_attempt}/{recoverable_retry_budget} "
                        f"recovery_path={last_recovery_path} "
                        f"reason_code={research_reason_code} "
                        f"probe_ok={'1' if probe_ok else '0'} "
                        f"probe_exit_code={probe_exit_code} "
                        f"probe_command={probe_command or 'n/a'}"
                        + (f" probe_detail={probe_detail}" if probe_detail else "")
                    ),
                )
                append_log(
                    cli_log_path,
                    (
                        f"{utc_timestamp()} event=research-gate-recovery-probe "
                        f"retry_attempt={recoverable_retry_attempt}/{recoverable_retry_budget} "
                        f"recovery_path={last_recovery_path} probe_ok={'1' if probe_ok else '0'}"
                    ),
                )
                if probe_ok:
                    (
                        research_ok,
                        research_reason_code,
                        research_reason,
                        research_next_action,
                    ) = _validate_loop_research_gate(target, ticket)
                    research_reason_code = str(research_reason_code or "").strip().lower() or "research_gate_blocked"
                    if research_ok:
                        append_log(
                            log_path,
                            (
                                f"{utc_timestamp()} event=research-gate-recovered "
                                f"retry_attempt={recoverable_retry_attempt}/{recoverable_retry_budget} "
                                f"recovery_path={last_recovery_path}"
                            ),
                        )
                        append_log(
                            cli_log_path,
                            (
                                f"{utc_timestamp()} event=research-gate-recovered "
                                f"retry_attempt={recoverable_retry_attempt}/{recoverable_retry_budget}"
                            ),
                        )
                if not research_ok and probe_detail:
                    research_reason = (
                        f"{research_reason}; recovery_probe={probe_detail}"
                        if str(research_reason or "").strip()
                        else f"research gate blocked; recovery_probe={probe_detail}"
                    )
                    if probe_command:
                        research_next_action = probe_command
            soften_research_gate = research_reason_code in LOOP_RESEARCH_SOFT_REASON_CODES
            if research_ok:
                pass
            elif gate_reason_class == "warn_continue" or soften_research_gate:
                effective_reason_class = (
                    "warn_continue" if gate_reason_class == "warn_continue" else "soft_override"
                )
                research_gate_softened = True
                research_gate_soft_reason = research_reason_code
                append_log(
                    log_path,
                    (
                        f"{utc_timestamp()} event=research-gate-warn-continue "
                        f"reason_code={research_reason_code} blocked_policy={blocked_policy} "
                        f"reason_class={effective_reason_class}"
                    ),
                )
                append_log(
                    cli_log_path,
                    (
                        f"{utc_timestamp()} event=research-gate-warn-continue "
                        f"reason_code={research_reason_code} blocked_policy={blocked_policy} "
                        f"reason_class={effective_reason_class}"
                    ),
                )
            else:
                ralph_semantics = _ralph_recoverable_semantics(
                    blocked_policy=blocked_policy,
                    reason_code=research_reason_code,
                    reason_class=gate_reason_class,
                    recoverable_blocked=bool(recoverable_gate),
                    retry_attempt=recoverable_retry_attempt,
                    recoverable_retry_budget=recoverable_retry_budget,
                )
                payload = {
                    "status": "blocked",
                    "terminal_marker": 1,
                    "iterations": 0,
                    "exit_code": BLOCKED_CODE,
                    "log_path": runtime.rel_path(log_path, target),
                    "cli_log_path": runtime.rel_path(cli_log_path, target),
                    "runner_label": runner_label,
                    "blocked_policy": blocked_policy,
                    "reason": research_reason,
                    "reason_code": research_reason_code,
                    "ralph_reason_class": gate_reason_class,
                    "next_action": research_next_action or None,
                    "recoverable_blocked": bool(recoverable_gate),
                    "retry_attempt": recoverable_retry_attempt,
                    "recoverable_retry_budget": recoverable_retry_budget,
                    "recovery_path": last_recovery_path if recoverable_gate else "",
                    "updated_at": utc_timestamp(),
                    **ralph_semantics,
                }
                append_log(
                    log_path,
                    (
                        f"{utc_timestamp()} ticket={ticket} iteration=0 status=blocked "
                        f"reason_code={research_reason_code} research_gate={research_gate_mode}"
                        + (f" next_action={research_next_action}" if research_next_action else "")
                        + (
                            f" recoverable_blocked=1 retry_attempt={recoverable_retry_attempt}/{recoverable_retry_budget} "
                            f"recovery_path={last_recovery_path}"
                            if recoverable_gate
                            else " recoverable_blocked=0"
                        )
                    ),
                )
                append_log(
                    cli_log_path,
                    (
                        f"{utc_timestamp()} event=blocked iterations=0 reason_code={research_reason_code} "
                        "source=research_gate"
                        + (
                            f" recoverable_blocked=1 retry_attempt={recoverable_retry_attempt}/{recoverable_retry_budget} "
                            f"recovery_path={last_recovery_path}"
                            if recoverable_gate
                            else ""
                        )
                    ),
                )
                emit(args.format, _attach_research_gate_telemetry(payload))
                return BLOCKED_CODE

    last_payload: Dict[str, object] = {}
    for iteration in range(1, max_iterations + 1):
        active_stage_for_budget = str(runtime.read_active_stage(target) or "").strip().lower()
        if active_stage_for_budget not in {"implement", "review", "qa"}:
            active_stage_for_budget = "qa" if args.from_qa else "implement"
        stage_budget_seconds = _resolve_stage_budget_seconds(
            getattr(args, "stage_budget_seconds", None),
            active_stage_for_budget,
        )
        now_ts = time.time()
        stage_started_at = stage_budget_starts.get(active_stage_for_budget)
        if stage_started_at is None:
            stage_started_at = now_ts
            stage_budget_starts[active_stage_for_budget] = stage_started_at
        stage_elapsed_seconds = max(now_ts - stage_started_at, 0.0)
        stage_budget_remaining_seconds = (
            max(int(stage_budget_seconds - stage_elapsed_seconds), 0)
            if stage_budget_seconds > 0
            else 0
        )

        if stage_budget_seconds > 0 and stage_budget_remaining_seconds <= 0:
            reason_code = "seed_stage_budget_exhausted"
            reason = (
                f"{active_stage_for_budget} stage budget exhausted "
                f"({stage_budget_seconds}s, elapsed={int(stage_elapsed_seconds)}s)"
            )
            active_work_item = str(runtime.read_active_work_item(target) or "").strip()
            if active_stage_for_budget == "qa":
                budget_scope_key = runtime.resolve_scope_key("", ticket)
            else:
                budget_scope_key = runtime.resolve_scope_key(active_work_item, ticket)
            termination_attribution = _build_termination_attribution(
                exit_code=143,
                classification="watchdog_terminated",
                killed_flag=True,
                watchdog_marker=True,
            )
            stream_liveness = {
                "main_log_path": runtime.rel_path(log_path, target),
                "main_log_bytes": _safe_size(log_path),
                "main_log_updated_at": _safe_updated_at(log_path),
                "step_stream_log_bytes": 0,
                "step_stream_log_updated_at": "",
                "step_stream_jsonl_bytes": 0,
                "step_stream_jsonl_updated_at": "",
                "observability_degraded": False,
                "stream_path_invalid_count": 0,
                "stream_path_invalid": [],
                "active_source": "none",
            }
            payload = {
                "status": "blocked",
                "terminal_marker": 1,
                "iterations": iteration,
                "exit_code": BLOCKED_CODE,
                "log_path": runtime.rel_path(log_path, target),
                "cli_log_path": runtime.rel_path(cli_log_path, target),
                "runner_label": runner_label,
                "blocked_policy": blocked_policy,
                "stream_log_path": runtime.rel_path(stream_log_path, target) if stream_log_path else "",
                "stream_jsonl_path": runtime.rel_path(stream_jsonl_path, target) if stream_jsonl_path else "",
                "reason": reason,
                "reason_code": reason_code,
                "scope_key": budget_scope_key,
                "work_item_key": active_work_item or None,
                "recoverable_blocked": False,
                "retry_attempt": recoverable_retry_attempt,
                "recoverable_retry_budget": recoverable_retry_budget,
                "runner_cmd": str(args.runner or os.environ.get("AIDD_LOOP_RUNNER") or "claude").strip() or "claude",
                "stage": active_stage_for_budget,
                "stage_budget_seconds": stage_budget_seconds,
                "stage_budget_remaining_seconds": 0,
                "budget_exhausted": True,
                "watchdog_marker": 1,
                "termination_attribution": termination_attribution,
                "stream_liveness": stream_liveness,
                "updated_at": utc_timestamp(),
            }
            append_log(
                log_path,
                (
                    f"{utc_timestamp()} iteration={iteration} status=blocked stage={active_stage_for_budget} "
                    f"reason_code={reason_code} stage_budget_seconds={stage_budget_seconds} "
                    f"stage_elapsed_seconds={int(stage_elapsed_seconds)} watchdog_marker=1"
                ),
            )
            append_log(
                cli_log_path,
                (
                    f"{utc_timestamp()} event=blocked iteration={iteration} "
                    f"reason_code={reason_code} stage={active_stage_for_budget}"
                ),
            )
            clear_active_mode(target)
            emit(args.format, _attach_research_gate_telemetry(payload))
            return BLOCKED_CODE

        if stream_mode:
            watchdog_timeout_seconds = max(step_timeout_seconds, 1)
        else:
            watchdog_timeout_seconds = max(silent_stall_seconds or step_timeout_seconds, 1)

        if stage_budget_seconds > 0:
            budget_timeout_seconds = max(stage_budget_remaining_seconds, 1)
            timeout_seconds = min(watchdog_timeout_seconds, budget_timeout_seconds)
            budget_exhausted_on_timeout = stage_budget_remaining_seconds <= watchdog_timeout_seconds
        else:
            timeout_seconds = watchdog_timeout_seconds
            budget_exhausted_on_timeout = False

        iteration_started_at = time.time()
        result = run_loop_step(
            plugin_root,
            workspace_root,
            target,
            ticket,
            args.runner,
            blocked_policy,
            from_qa=args.from_qa,
            work_item_key=args.work_item_key,
            select_qa_handoff=args.select_qa_handoff,
            stream_mode=stream_mode,
            timeout_seconds=timeout_seconds,
            stage_budget_seconds=stage_budget_seconds,
            stage_budget_remaining_seconds=stage_budget_remaining_seconds,
            budget_exhausted_on_timeout=budget_exhausted_on_timeout,
            silent_stall_seconds=silent_stall_seconds,
        )
        if result.returncode not in {DONE_CODE, CONTINUE_CODE, BLOCKED_CODE}:
            unexpected_payload: Dict[str, object] = {}
            parse_error = ""
            try:
                unexpected_payload = json.loads(result.stdout)
            except json.JSONDecodeError as exc:
                parse_error = str(exc)
                unexpected_payload = {}
            nested_reason = str(unexpected_payload.get("reason") or "").strip()
            nested_reason_code = str(unexpected_payload.get("reason_code") or "").strip().lower()
            nested_stage = str(unexpected_payload.get("stage") or "").strip().lower()
            is_sigterm = result.returncode == 143 or "runner exited with 143" in nested_reason.lower()
            if is_sigterm:
                killed_flag = _truthy_flag(unexpected_payload.get("killed_flag")) or _truthy_flag(
                    unexpected_payload.get("killed")
                )
                watchdog_marker = _truthy_flag(unexpected_payload.get("watchdog_marker")) or (
                    "watchdog timeout" in nested_reason.lower()
                )
                initial_reason_code = (
                    "watchdog_terminated"
                    if killed_flag and watchdog_marker
                    else "parent_terminated_or_external_terminate"
                )
                status = "blocked"
                out_code = BLOCKED_CODE
                reason_text = nested_reason or f"loop-step runner exited with {result.returncode}"
                termination_attribution, _ = _normalize_termination_attribution(
                    attribution={
                        "killed_flag": 1 if killed_flag else 0,
                        "watchdog_marker": 1 if watchdog_marker else 0,
                    },
                    exit_code=result.returncode,
                    reason_code=initial_reason_code,
                    watchdog_hint=watchdog_marker,
                )
                reason_code = str(termination_attribution.get("classification") or initial_reason_code)
            else:
                status = "error"
                out_code = ERROR_CODE
                if result.returncode == 127:
                    reason_code = "launcher_tokenization_or_command_not_found"
                else:
                    reason_code = nested_reason_code or "loop_step_unexpected_exit"
                reason_text = nested_reason or f"loop-step failed ({result.returncode})"
                termination_attribution = _build_termination_attribution(
                    exit_code=result.returncode,
                    classification=reason_code,
                    killed_flag=False,
                    watchdog_marker=False,
                )
            payload = {
                "status": status,
                "terminal_marker": 1,
                "iterations": iteration,
                "exit_code": out_code,
                "log_path": runtime.rel_path(log_path, target),
                "cli_log_path": runtime.rel_path(cli_log_path, target),
                "runner_label": runner_label,
                "blocked_policy": blocked_policy,
                "retry_attempt": recoverable_retry_attempt,
                "recoverable_retry_budget": recoverable_retry_budget,
                "stream_log_path": runtime.rel_path(stream_log_path, target) if stream_log_path else "",
                "stream_jsonl_path": runtime.rel_path(stream_jsonl_path, target) if stream_jsonl_path else "",
                "stage": nested_stage or None,
                "reason": reason_text,
                "reason_code": reason_code,
                "watchdog_marker": int(termination_attribution.get("watchdog_marker") or 0),
                "budget_exhausted": False,
                "last_step": unexpected_payload if unexpected_payload else None,
                "parse_error": parse_error or None,
                "termination_attribution": termination_attribution,
                "updated_at": utc_timestamp(),
            }
            append_log(
                log_path,
                (
                    f"{utc_timestamp()} iteration={iteration} status={status} code={result.returncode} "
                    f"runner={runner_label} reason_code={reason_code}"
                    + (f" stage={nested_stage}" if nested_stage else "")
                    + (f" parse_error={parse_error}" if parse_error else "")
                ),
            )
            append_log(
                cli_log_path,
                (
                    f"{utc_timestamp()} event={status} iteration={iteration} "
                    f"exit_code={result.returncode} reason_code={reason_code}"
                ),
            )
            clear_active_mode(target)
            emit(args.format, _attach_research_gate_telemetry(payload))
            return out_code
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
        stage_chain_logs_raw = step_payload.get("stage_chain_logs")
        stage_chain_logs = (
            [str(item) for item in stage_chain_logs_raw if str(item).strip()]
            if isinstance(stage_chain_logs_raw, list)
            else []
        )
        runner_effective = step_payload.get("runner_effective") or ""
        if not str(runner_effective).strip():
            runner_effective = str(args.runner or os.environ.get("AIDD_LOOP_RUNNER") or "claude").strip() or "claude"
        step_stream_log = step_payload.get("stream_log_path") or ""
        step_stream_jsonl = step_payload.get("stream_jsonl_path") or ""
        budget_exhausted = _truthy_flag(step_payload.get("budget_exhausted"))
        step_watchdog_marker = _truthy_flag(step_payload.get("watchdog_marker"))
        try:
            stage_budget_seconds_payload = int(step_payload.get("stage_budget_seconds") or 0)
        except (TypeError, ValueError):
            stage_budget_seconds_payload = 0
        try:
            stage_budget_remaining_payload = int(step_payload.get("stage_budget_remaining_seconds") or 0)
        except (TypeError, ValueError):
            stage_budget_remaining_payload = 0
        step_termination_raw = step_payload.get("termination_attribution")
        step_termination_attribution = (
            step_termination_raw if isinstance(step_termination_raw, dict) else None
        )
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
        scope_drift_hint = ""
        if step_status == "blocked":
            promoted_reason_code, promoted_scope_hint = _promote_stage_result_reason(
                str(log_reason_code),
                str(reason),
                str(stage_diag),
            )
            log_reason_code = promoted_reason_code
            scope_drift_hint = promoted_scope_hint
        if not str(reason).strip() and step_status == "blocked":
            if parse_error:
                reason = f"loop-step returned invalid JSON payload: {parse_error}"
            else:
                reason = f"{step_stage or 'stage'} blocked"
        scope_mismatch_non_authoritative = bool(step_payload.get("scope_mismatch_non_authoritative"))
        expected_scope_key_payload = str(step_payload.get("expected_scope_key") or "").strip()
        selected_scope_key_payload = str(step_payload.get("selected_scope_key") or "").strip()
        chosen_scope = repair_scope or scope_key
        if mismatch_to and not scope_mismatch_non_authoritative:
            chosen_scope = mismatch_to
        if scope_mismatch_non_authoritative and expected_scope_key_payload:
            chosen_scope = expected_scope_key_payload
        if not str(chosen_scope).strip() and runtime.is_valid_work_item_key(step_work_item):
            chosen_scope = runtime.resolve_scope_key(step_work_item, ticket)
        if (
            mismatch_warn
            and scope_mismatch_non_authoritative
            and step_status == "blocked"
            and str(log_reason_code or "").strip().lower() not in {"scope_drift_recoverable", "stage_result_missing_or_invalid"}
        ):
            mismatch_warn = ""
            if isinstance(step_payload, dict):
                step_payload.pop("scope_key_mismatch_warn", None)
        reason_class = "not_recoverable"
        if step_status == "blocked":
            classification = loop_block_policy.classify_block_reason(
                str(log_reason_code),
                blocked_policy,
                os.environ.get("AIDD_HOOKS_MODE"),
                target=target,
            )
            reason_class = str(classification.get("reason_class") or "not_recoverable")
        recoverable_blocked = bool(step_status == "blocked" and reason_class == "recoverable_retry")
        strict_recoverable_reason_class = (
            reason_class if blocked_policy == "strict" and reason_class == "recoverable_retry" else ""
        )
        warn_continue_blocked = bool(step_status == "blocked" and reason_class == "warn_continue" and blocked_policy == "ralph")
        if step_status == "blocked":
            step_payload = dict(step_payload)
            step_payload["ralph_reason_class"] = reason_class
            step_payload["ralph_policy_version"] = (
                loop_block_policy.RALPH_POLICY_VERSION
                if blocked_policy == "ralph"
                else ""
            )
            step_payload["strict_recoverable_reason_class"] = strict_recoverable_reason_class
        if not stage_result_path and step_status == "blocked":
            step_stage = str(step_payload.get("stage") or "").strip().lower()
            fallback_scope = str(chosen_scope or runtime.resolve_scope_key("", ticket)).strip()
            if step_stage:
                stage_result_path = f"aidd/reports/loops/{ticket}/{fallback_scope}/stage.{step_stage}.result.json"
        stream_path_invalid: List[str] = []
        stream_path_stale: List[str] = []

        def _stale_stream(path: Optional[Path], _iteration_started_at: float = iteration_started_at) -> bool:
            if path is None or not path.exists():
                return False
            return _safe_mtime(path) + 1.0 < _iteration_started_at
        if stream_mode and stream_log_path and step_stream_log:
            step_stream_log_path, invalid_path = _resolve_path_within_target(
                target,
                step_stream_log,
                label="step_stream_log_path",
            )
            if invalid_path:
                stream_path_invalid.append(invalid_path)
            elif step_stream_log_path:
                if _stale_stream(step_stream_log_path):
                    stream_path_stale.append(f"step_stream_log_path:stale:{step_stream_log_path.as_posix()}")
                else:
                    append_stream_file(
                        stream_log_path,
                        step_stream_log_path,
                        header=(
                            f"==> loop-step iteration={iteration} stage={step_payload.get('stage')} "
                            f"stream_log={step_stream_log}"
                        ),
                    )
        if stream_mode and stream_jsonl_path and step_stream_jsonl:
            step_jsonl_path, invalid_path = _resolve_path_within_target(
                target,
                step_stream_jsonl,
                label="step_stream_jsonl_path",
            )
            if invalid_path:
                stream_path_invalid.append(invalid_path)
            elif step_jsonl_path:
                if _stale_stream(step_jsonl_path):
                    stream_path_stale.append(f"step_stream_jsonl_path:stale:{step_jsonl_path.as_posix()}")
                else:
                    append_stream_file(stream_jsonl_path, step_jsonl_path)
        step_main_log_abs, main_log_invalid = _resolve_path_within_target(
            target,
            step_command_log,
            label="step_main_log_path",
        )
        if main_log_invalid:
            stream_path_invalid.append(main_log_invalid)
        main_log_abs = step_main_log_abs if step_main_log_abs and step_main_log_abs.exists() else log_path
        step_stream_log_abs, step_stream_log_invalid = _resolve_path_within_target(
            target,
            step_stream_log,
            label="step_stream_log_path",
        )
        if step_stream_log_invalid:
            stream_path_invalid.append(step_stream_log_invalid)
        elif _stale_stream(step_stream_log_abs):
            stream_path_stale.append(f"step_stream_log_path:stale:{step_stream_log_abs.as_posix()}")
            step_stream_log_abs = None
        step_stream_jsonl_abs, step_stream_jsonl_invalid = _resolve_path_within_target(
            target,
            step_stream_jsonl,
            label="step_stream_jsonl_path",
        )
        if step_stream_jsonl_invalid:
            stream_path_invalid.append(step_stream_jsonl_invalid)
        elif _stale_stream(step_stream_jsonl_abs):
            stream_path_stale.append(f"step_stream_jsonl_path:stale:{step_stream_jsonl_abs.as_posix()}")
            step_stream_jsonl_abs = None
        if stream_path_invalid:
            stream_path_invalid = sorted(set(stream_path_invalid))
        if stream_path_stale:
            stream_path_stale = sorted(set(stream_path_stale))
        stream_liveness = {
            "main_log_path": runtime.rel_path(main_log_abs, target),
            "main_log_bytes": _safe_size(main_log_abs),
            "main_log_updated_at": _safe_updated_at(main_log_abs),
            "step_stream_log_bytes": _safe_size(step_stream_log_abs),
            "step_stream_log_updated_at": _safe_updated_at(step_stream_log_abs),
            "step_stream_jsonl_bytes": _safe_size(step_stream_jsonl_abs),
            "step_stream_jsonl_updated_at": _safe_updated_at(step_stream_jsonl_abs),
            "observability_degraded": False,
            "stream_path_invalid_count": len(stream_path_invalid),
            "stream_path_invalid": stream_path_invalid,
            "stream_path_stale_count": len(stream_path_stale),
            "stream_path_stale": stream_path_stale,
        }
        if stream_liveness["step_stream_jsonl_bytes"] > 0 or stream_liveness["step_stream_log_bytes"] > 0:
            stream_liveness["active_source"] = "stream"
        elif stream_liveness["main_log_bytes"] > 0:
            stream_liveness["active_source"] = "main_log"
        else:
            stream_liveness["active_source"] = "none"
        if stream_mode and stream_liveness["active_source"] == "main_log":
            stream_liveness["observability_degraded"] = True
            if stream_path_invalid:
                stream_liveness["degraded_reason"] = "stream_path_invalid"
            elif stream_path_stale:
                stream_liveness["degraded_reason"] = "stream_path_stale"
            elif step_stream_log or step_stream_jsonl:
                stream_liveness["degraded_reason"] = "stream_artifacts_missing_or_empty"
            else:
                stream_liveness["degraded_reason"] = "stream_paths_missing"
        if stream_mode and stream_liveness["active_source"] == "none" and (stream_path_invalid or stream_path_stale):
            stream_liveness["observability_degraded"] = True
            stream_liveness["degraded_reason"] = (
                "stream_path_invalid" if stream_path_invalid else "stream_path_stale"
            )

        if step_termination_attribution is not None or step_status == "blocked":
            watchdog_hint = bool(
                step_watchdog_marker
                or log_reason_code in {"seed_stage_silent_stall", "seed_stage_active_stream_timeout", "seed_stage_budget_exhausted"}
            )
            step_termination_attribution, normalized_watchdog_marker = _normalize_termination_attribution(
                attribution=step_termination_attribution,
                exit_code=(143 if watchdog_hint else int(step_exit_code)),
                reason_code=str(log_reason_code or "blocked_without_reason"),
                watchdog_hint=watchdog_hint,
            )
            step_watchdog_marker = normalized_watchdog_marker
        reason_family = str(step_payload.get("reason_family") or "").strip().lower()
        if not reason_family and str(log_reason_code).strip().lower() == "runtime_path_missing_or_drift":
            reason_family = PROMPT_FLOW_DRIFT_REASON_FAMILY

        append_log(
            log_path,
            (
                f"{utc_timestamp()} ticket={ticket} iteration={iteration} status={step_status} "
                f"result={step_status} stage={step_payload.get('stage')} scope_key={scope_key} "
                f"work_item_key={step_work_item or 'null'} "
                f"exit_code={step_exit_code} reason_code={log_reason_code} runner={runner_label} "
                f"runner_cmd={runner_effective} reason={reason} blocked_policy={blocked_policy} "
                f"recoverable_blocked={'1' if recoverable_blocked else '0'} "
                f"ralph_reason_class={reason_class}"
                + (f" strict_recoverable_reason_class={strict_recoverable_reason_class}" if strict_recoverable_reason_class else "")
                + (f" chosen_scope_key={chosen_scope}" if chosen_scope else "")
                + (f" expected_scope_key={expected_scope_key_payload}" if expected_scope_key_payload else "")
                + (f" selected_scope_key={selected_scope_key_payload}" if selected_scope_key_payload else "")
                + (
                    f" scope_mismatch_non_authoritative={'1' if scope_mismatch_non_authoritative else '0'}"
                    if mismatch_to or scope_mismatch_non_authoritative
                    else ""
                )
                + (f" scope_key_mismatch_warn={mismatch_warn}" if mismatch_warn else "")
                + (f" mismatch_from={mismatch_from} mismatch_to={mismatch_to}" if mismatch_to else "")
                + (f" reason_family={reason_family}" if reason_family else "")
                + (f" active_stage_before={active_stage_before}" if active_stage_before else "")
                + (f" active_stage_after={active_stage_after}" if active_stage_after else "")
                + (f" active_stage_sync_applied={'1' if active_stage_sync_applied else '0'}")
                + (f" log_path={step_command_log}" if step_command_log else "")
                + (f" step_cli_log_path={step_cli_log_path}" if step_cli_log_path else "")
                + (f" tests_log_path={tests_log_path}" if tests_log_path else "")
                + (f" stage_result_diagnostics={stage_diag}" if stage_diag else "")
                + (f" stage_result_path={stage_result_path}" if stage_result_path else "")
                + (f" stage_chain_logs={','.join(stage_chain_logs)}" if stage_chain_logs else "")
                + (
                    " stream_liveness="
                    f"main:{stream_liveness['main_log_bytes']},"
                    f"step_log:{stream_liveness['step_stream_log_bytes']},"
                    f"step_jsonl:{stream_liveness['step_stream_jsonl_bytes']},"
                    f"active:{stream_liveness['active_source']}"
                )
                + (f" budget_exhausted={'1' if budget_exhausted else '0'}")
                + (f" watchdog_marker={'1' if step_watchdog_marker else '0'}")
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
                + (f" stream_path_invalid={','.join(stream_path_invalid)}" if stream_path_invalid else "")
                + (f" stream_path_stale={','.join(stream_path_stale)}" if stream_path_stale else "")
            ),
        )
        append_log(
            cli_log_path,
            (
                f"{utc_timestamp()} event=step iteration={iteration} status={step_status} "
                f"stage={step_payload.get('stage')} scope_key={scope_key} exit_code={step_exit_code} "
                f"runner_cmd={runner_effective} blocked_policy={blocked_policy} "
                f"recoverable_blocked={'1' if recoverable_blocked else '0'} "
                f"ralph_reason_class={reason_class} "
                + (f"strict_recoverable_reason_class={strict_recoverable_reason_class} " if strict_recoverable_reason_class else "")
                + f"work_item_key={step_work_item or 'null'} "
                + f"active_stage_sync_applied={'1' if active_stage_sync_applied else '0'}"
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
                "terminal_marker": 1,
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
            emit(args.format, _attach_research_gate_telemetry(payload))
            return DONE_CODE
        if step_exit_code == BLOCKED_CODE:
            step_stage = str(step_payload.get("stage") or "").strip().lower()
            if log_reason_code == "seed_stage_active_stream_timeout" and not budget_exhausted:
                append_log(
                    log_path,
                    (
                        f"{utc_timestamp()} event=no-convergence-yet iteration={iteration} "
                        f"reason_code={log_reason_code} stage={step_stage or 'n/a'} "
                        "classification=prompt_exec_no_convergence_yet"
                    ),
                )
                append_log(
                    cli_log_path,
                    (
                        f"{utc_timestamp()} event=no-convergence-yet iteration={iteration} "
                        f"reason_code={log_reason_code} stage={step_stage or 'n/a'}"
                    ),
                )
                if sleep_seconds:
                    time.sleep(sleep_seconds)
                continue
            if warn_continue_blocked:
                step_payload = dict(step_payload)
                step_payload["status"] = "continue"
                step_payload["reason_code"] = log_reason_code
                step_payload["reason"] = reason
                step_payload["recoverable_blocked"] = False
                step_payload["retry_attempt"] = recoverable_retry_attempt
                step_payload["blocked_policy"] = blocked_policy
                step_payload["ralph_reason_class"] = reason_class
                last_payload = step_payload
                append_log(
                    log_path,
                    (
                        f"{utc_timestamp()} event=warn-continue iteration={iteration} "
                        f"reason_code={log_reason_code} ralph_reason_class={reason_class} "
                        "classification=policy_matrix_v2_warn_continue"
                    ),
                )
                append_log(
                    cli_log_path,
                    (
                        f"{utc_timestamp()} event=warn-continue iteration={iteration} "
                        f"reason_code={log_reason_code} ralph_reason_class={reason_class}"
                    ),
                )
                if sleep_seconds:
                    time.sleep(sleep_seconds)
                continue
            scope_drift_probe_allowed = True
            if log_reason_code == "scope_drift_recoverable":
                scope_drift_probe_allowed = not scope_drift_recovery_probe_used
            if (
                recoverable_blocked
                and recoverable_retry_attempt < recoverable_retry_budget
                and scope_drift_probe_allowed
            ):
                if log_reason_code == "scope_drift_recoverable":
                    scope_drift_recovery_probe_used = True
                recoverable_retry_attempt += 1
                recovery_path, recovery_work_item = _apply_recoverable_block_recovery(
                    target=target,
                    ticket=ticket,
                    stage=step_stage,
                    reason_code=str(log_reason_code or ""),
                    drift_scope_key=scope_drift_hint,
                    chosen_scope=str(chosen_scope or ""),
                )
                last_recovery_path = recovery_path
                step_payload = dict(step_payload)
                step_payload["recoverable_blocked"] = True
                step_payload["retry_attempt"] = recoverable_retry_attempt
                step_payload["recovery_path"] = recovery_path
                step_payload["blocked_policy"] = blocked_policy
                step_payload["recovery_work_item"] = recovery_work_item or None
                step_payload["ralph_policy_version"] = loop_block_policy.RALPH_POLICY_VERSION
                step_payload["ralph_reason_class"] = reason_class
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
            if log_reason_code == "scope_drift_recoverable" and not scope_drift_probe_allowed:
                append_log(
                    log_path,
                    (
                        f"{utc_timestamp()} event=scope-drift-recovery-exhausted iteration={iteration} "
                        f"reason_code={log_reason_code}"
                    ),
                )
                append_log(
                    cli_log_path,
                    (
                        f"{utc_timestamp()} event=scope-drift-recovery-exhausted iteration={iteration} "
                        f"reason_code={log_reason_code}"
                    ),
                )
            clear_active_mode(target)
            ralph_semantics = _ralph_recoverable_semantics(
                blocked_policy=blocked_policy,
                reason_code=str(log_reason_code or ""),
                reason_class=reason_class,
                recoverable_blocked=recoverable_blocked,
                retry_attempt=recoverable_retry_attempt,
                recoverable_retry_budget=recoverable_retry_budget,
            )
            payload = {
                "status": "blocked",
                "terminal_marker": 1,
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
                "reason_family": reason_family or None,
                "ralph_reason_class": reason_class,
                "strict_recoverable_reason_class": strict_recoverable_reason_class or None,
                "recoverable_blocked": recoverable_blocked,
                "retry_attempt": recoverable_retry_attempt,
                "recoverable_retry_budget": recoverable_retry_budget,
                "recovery_path": last_recovery_path,
                "runner_cmd": runner_effective,
                "scope_key": chosen_scope,
                "expected_scope_key": expected_scope_key_payload or None,
                "selected_scope_key": selected_scope_key_payload or None,
                "scope_mismatch_non_authoritative": bool(scope_mismatch_non_authoritative),
                "work_item_key": step_work_item or None,
                "stage_budget_seconds": (
                    stage_budget_seconds_payload
                    if "stage_budget_seconds" in step_payload
                    else stage_budget_seconds
                ),
                "stage_budget_remaining_seconds": (
                    stage_budget_remaining_payload
                    if "stage_budget_remaining_seconds" in step_payload
                    else stage_budget_remaining_seconds
                ),
                "silent_stall_seconds": silent_stall_seconds,
                "budget_exhausted": budget_exhausted,
                "watchdog_marker": 1 if step_watchdog_marker else 0,
                "termination_attribution": step_termination_attribution,
                "active_stage_before": active_stage_before or None,
                "active_stage_after": active_stage_after or None,
                "active_stage_sync_applied": active_stage_sync_applied,
                "marker_signal_events": marker_signal_events,
                "report_noise_events": report_noise_events,
                "report_noise": report_noise,
                "step_log_path": step_command_log,
                "step_cli_log_path": step_cli_log_path,
                "stage_result_path": stage_result_path,
                "stage_chain_logs": stage_chain_logs,
                "step_stream_log_path": step_stream_log,
                "step_stream_jsonl_path": step_stream_jsonl,
                "stream_liveness": stream_liveness,
                "last_step": step_payload,
                "updated_at": utc_timestamp(),
                **ralph_semantics,
            }
            append_log(cli_log_path, f"{utc_timestamp()} event=blocked iterations={iteration}")
            emit(args.format, _attach_research_gate_telemetry(payload))
            return BLOCKED_CODE
        if sleep_seconds:
            time.sleep(sleep_seconds)

    payload = {
        "status": "max-iterations",
        "terminal_marker": 1,
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
        "budget_exhausted": False,
        "watchdog_marker": 0,
        "termination_attribution": _build_termination_attribution(
            exit_code=MAX_ITERATIONS_CODE,
            classification="max_iterations_reached",
            killed_flag=False,
            watchdog_marker=False,
        ),
        "updated_at": utc_timestamp(),
    }
    if blocked_policy == "ralph":
        last_reason = str((last_payload or {}).get("reason_code") or "")
        last_reason_class = str((last_payload or {}).get("ralph_reason_class") or "not_recoverable")
        last_recoverable = bool((last_payload or {}).get("recoverable_blocked"))
        payload.update(
            _ralph_recoverable_semantics(
                blocked_policy=blocked_policy,
                reason_code=last_reason,
                reason_class=last_reason_class,
                recoverable_blocked=last_recoverable,
                retry_attempt=recoverable_retry_attempt,
                recoverable_retry_budget=recoverable_retry_budget,
            )
        )
    clear_active_mode(target)
    append_log(cli_log_path, f"{utc_timestamp()} event=max-iterations iterations={max_iterations}")
    emit(args.format, _attach_research_gate_telemetry(payload))
    return MAX_ITERATIONS_CODE


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
