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
from pathlib import Path
from typing import Dict, List

from aidd_runtime import runtime
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


def run_loop_step(
    plugin_root: Path,
    workspace_root: Path,
    ticket: str,
    runner: str | None,
    *,
    from_qa: str | None,
    work_item_key: str | None,
    select_qa_handoff: bool,
    stream_mode: str | None,
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
    if stream_mode:
        return subprocess.run(cmd, text=True, stdout=subprocess.PIPE, stderr=None, cwd=workspace_root, env=env)
    return subprocess.run(cmd, text=True, capture_output=True, cwd=workspace_root, env=env)


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
        f"{utc_timestamp()} event=start ticket={ticket} max_iterations={max_iterations} runner={runner_label}",
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
            ticket,
            args.runner,
            from_qa=args.from_qa,
            work_item_key=args.work_item_key,
            select_qa_handoff=args.select_qa_handoff,
            stream_mode=stream_mode,
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
        scope_key = step_payload.get("scope_key") or ""
        mismatch_warn = step_payload.get("scope_key_mismatch_warn") or ""
        mismatch_from = step_payload.get("scope_key_mismatch_from") or ""
        mismatch_to = step_payload.get("scope_key_mismatch_to") or ""
        step_command_log = step_payload.get("log_path") or ""
        step_cli_log_path = step_payload.get("cli_log_path") or ""
        tests_log_path = step_payload.get("tests_log_path") or ""
        stage_diag = step_payload.get("stage_result_diagnostics") or ""
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
        if not str(reason).strip() and step_status == "blocked":
            step_stage = str(step_payload.get("stage") or "").strip().lower()
            if parse_error:
                reason = f"loop-step returned invalid JSON payload: {parse_error}"
            else:
                reason = f"{step_stage or 'stage'} blocked"
        chosen_scope = repair_scope or scope_key
        if mismatch_to:
            chosen_scope = mismatch_to
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
        append_log(
            log_path,
            (
                f"{utc_timestamp()} ticket={ticket} iteration={iteration} status={step_status} "
                f"result={step_status} stage={step_payload.get('stage')} scope_key={scope_key} "
                f"exit_code={step_exit_code} reason_code={log_reason_code} runner={runner_label} "
                f"runner_cmd={runner_effective} reason={reason}"
                + (f" chosen_scope_key={chosen_scope}" if chosen_scope else "")
                + (f" scope_key_mismatch_warn={mismatch_warn}" if mismatch_warn else "")
                + (f" mismatch_from={mismatch_from} mismatch_to={mismatch_to}" if mismatch_to else "")
                + (f" log_path={step_command_log}" if step_command_log else "")
                + (f" step_cli_log_path={step_cli_log_path}" if step_cli_log_path else "")
                + (f" tests_log_path={tests_log_path}" if tests_log_path else "")
                + (f" stage_result_diagnostics={stage_diag}" if stage_diag else "")
                + (f" stage_result_path={stage_result_path}" if stage_result_path else "")
                + (f" wrapper_logs={','.join(wrapper_logs)}" if wrapper_logs else "")
            ),
        )
        append_log(
            cli_log_path,
            (
                f"{utc_timestamp()} event=step iteration={iteration} status={step_status} "
                f"stage={step_payload.get('stage')} scope_key={scope_key} exit_code={step_exit_code} "
                f"runner_cmd={runner_effective}"
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
                "stream_log_path": runtime.rel_path(stream_log_path, target) if stream_log_path else "",
                "stream_jsonl_path": runtime.rel_path(stream_jsonl_path, target) if stream_jsonl_path else "",
                "last_step": step_payload,
                "updated_at": utc_timestamp(),
            }
            append_log(cli_log_path, f"{utc_timestamp()} event=done iterations={iteration}")
            emit(args.format, payload)
            return DONE_CODE
        if step_exit_code == BLOCKED_CODE:
            clear_active_mode(target)
            payload = {
                "status": "blocked",
                "iterations": iteration,
                "exit_code": BLOCKED_CODE,
                "log_path": runtime.rel_path(log_path, target),
                "cli_log_path": runtime.rel_path(cli_log_path, target),
                "runner_label": runner_label,
                "stream_log_path": runtime.rel_path(stream_log_path, target) if stream_log_path else "",
                "stream_jsonl_path": runtime.rel_path(stream_jsonl_path, target) if stream_jsonl_path else "",
                "reason": reason,
                "reason_code": log_reason_code,
                "runner_cmd": runner_effective,
                "scope_key": chosen_scope,
                "step_log_path": step_command_log,
                "step_cli_log_path": step_cli_log_path,
                "stage_result_path": stage_result_path,
                "wrapper_logs": wrapper_logs,
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
