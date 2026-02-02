#!/usr/bin/env python3
"""Run loop-step repeatedly until SHIP or limits reached."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import time
import datetime as dt
from pathlib import Path
from typing import Dict, List

from tools import runtime
from tools.io_utils import dump_yaml, utc_timestamp

DONE_CODE = 0
CONTINUE_CODE = 10
BLOCKED_CODE = 20
MAX_ITERATIONS_CODE = 11
ERROR_CODE = 30


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


def resolve_runner_label(raw: str | None) -> str:
    if raw:
        return raw.strip()
    env_value = (os.environ.get("AIDD_LOOP_RUNNER_LABEL") or os.environ.get("AIDD_RUNNER") or "").strip()
    if env_value:
        return env_value
    if os.environ.get("CI"):
        return "ci"
    return "local"


def run_loop_step(
    plugin_root: Path,
    workspace_root: Path,
    ticket: str,
    runner: str | None,
    *,
    from_qa: str | None,
    work_item_key: str | None,
    select_qa_handoff: bool,
) -> subprocess.CompletedProcess[str]:
    cmd = [str(plugin_root / "tools" / "loop-step.sh"), "--ticket", ticket, "--format", "json"]
    if runner:
        cmd.extend(["--runner", runner])
    if from_qa:
        cmd.extend(["--from-qa", from_qa])
    if work_item_key:
        cmd.extend(["--work-item-key", work_item_key])
    if select_qa_handoff:
        cmd.append("--select-qa-handoff")
    env = os.environ.copy()
    env["CLAUDE_PLUGIN_ROOT"] = str(plugin_root)
    return subprocess.run(cmd, text=True, capture_output=True, cwd=workspace_root, env=env)


def parse_args(argv: List[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run loop-step until SHIP.")
    parser.add_argument("--ticket", help="Ticket identifier (defaults to docs/.active_ticket).")
    parser.add_argument("--max-iterations", type=int, default=10, help="Maximum number of loop iterations.")
    parser.add_argument("--sleep-seconds", type=float, default=0.0, help="Sleep between iterations.")
    parser.add_argument("--runner", help="Runner command override.")
    parser.add_argument("--runner-label", help="Runner label for logs (claude_cli|ci|local).")
    parser.add_argument("--format", choices=("json", "yaml"), help="Emit structured output to stdout.")
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
        raise ValueError("feature ticket is required; pass --ticket or set docs/.active_ticket via /feature-dev-aidd:idea-new.")

    plugin_root = runtime.require_plugin_root()
    log_path = target / "reports" / "loops" / ticket / "loop.run.log"
    max_iterations = max(1, int(args.max_iterations))
    sleep_seconds = max(0.0, float(args.sleep_seconds))
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%d-%H%M%S")
    cli_log_path = target / "reports" / "loops" / ticket / f"cli.loop-run.{stamp}.log"
    runner_label = resolve_runner_label(args.runner_label)
    append_log(
        cli_log_path,
        f"{utc_timestamp()} event=start ticket={ticket} max_iterations={max_iterations} runner={runner_label}",
    )

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
        try:
            step_payload = json.loads(result.stdout)
        except json.JSONDecodeError:
            step_payload = {}
        last_payload = step_payload
        reason = step_payload.get("reason") or ""
        reason_code = step_payload.get("reason_code") or ""
        repair_code = step_payload.get("repair_reason_code") or ""
        repair_scope = step_payload.get("repair_scope_key") or ""
        scope_key = step_payload.get("scope_key") or ""
        runner_effective = step_payload.get("runner_effective") or ""
        step_status = step_payload.get("status")
        log_reason_code = repair_code or reason_code
        chosen_scope = repair_scope or scope_key
        append_log(
            log_path,
            (
                f"{utc_timestamp()} ticket={ticket} iteration={iteration} status={step_status} "
                f"result={step_status} stage={step_payload.get('stage')} scope_key={scope_key} "
                f"exit_code={result.returncode} reason_code={log_reason_code} runner={runner_label} "
                f"runner_cmd={runner_effective} reason={reason}"
                + (f" chosen_scope_key={chosen_scope}" if chosen_scope else "")
            ),
        )
        append_log(
            cli_log_path,
            f"{utc_timestamp()} event=step iteration={iteration} status={step_payload.get('status')} stage={step_payload.get('stage')} scope_key={scope_key} exit_code={result.returncode}",
        )
        if result.returncode == DONE_CODE:
            clear_active_mode(target)
            payload = {
                "status": "ship",
                "iterations": iteration,
                "exit_code": DONE_CODE,
                "log_path": runtime.rel_path(log_path, target),
                "cli_log_path": runtime.rel_path(cli_log_path, target),
                "runner_label": runner_label,
                "last_step": step_payload,
                "updated_at": utc_timestamp(),
            }
            append_log(cli_log_path, f"{utc_timestamp()} event=done iterations={iteration}")
            emit(args.format, payload)
            return DONE_CODE
        if result.returncode == BLOCKED_CODE:
            clear_active_mode(target)
            payload = {
                "status": "blocked",
                "iterations": iteration,
                "exit_code": BLOCKED_CODE,
                "log_path": runtime.rel_path(log_path, target),
                "cli_log_path": runtime.rel_path(cli_log_path, target),
                "runner_label": runner_label,
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
        "last_step": last_payload,
        "updated_at": utc_timestamp(),
    }
    clear_active_mode(target)
    append_log(cli_log_path, f"{utc_timestamp()} event=max-iterations iterations={max_iterations}")
    emit(args.format, payload)
    return MAX_ITERATIONS_CODE


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
