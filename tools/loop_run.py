#!/usr/bin/env python3
"""Run loop-step repeatedly until SHIP or limits reached."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import time
from pathlib import Path
from typing import Dict, List

from tools import runtime
from tools.io_utils import dump_yaml, utc_timestamp

DONE_CODE = 0
CONTINUE_CODE = 10
BLOCKED_CODE = 20
MAX_ITERATIONS_CODE = 11
ERROR_CODE = 30


def clear_active_state(root: Path) -> None:
    for name in (".active_stage", ".active_work_item", ".active_mode", ".active_ticket"):
        path = root / "docs" / name
        try:
            path.unlink()
        except OSError:
            continue


def append_log(log_path: Path, message: str) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(message + "\n")


def run_loop_step(plugin_root: Path, workspace_root: Path, ticket: str, runner: str | None) -> subprocess.CompletedProcess[str]:
    cmd = [str(plugin_root / "tools" / "loop-step.sh"), "--ticket", ticket, "--format", "json"]
    if runner:
        cmd.extend(["--runner", runner])
    env = os.environ.copy()
    env["CLAUDE_PLUGIN_ROOT"] = str(plugin_root)
    return subprocess.run(cmd, text=True, capture_output=True, cwd=workspace_root, env=env)


def parse_args(argv: List[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run loop-step until SHIP.")
    parser.add_argument("--ticket", help="Ticket identifier (defaults to docs/.active_ticket).")
    parser.add_argument("--max-iterations", type=int, default=10, help="Maximum number of loop iterations.")
    parser.add_argument("--sleep-seconds", type=float, default=0.0, help="Sleep between iterations.")
    parser.add_argument("--runner", help="Runner command override.")
    parser.add_argument("--format", choices=("json", "yaml"), help="Emit structured output to stdout.")
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

    last_payload: Dict[str, object] = {}
    for iteration in range(1, max_iterations + 1):
        result = run_loop_step(plugin_root, workspace_root, ticket, args.runner)
        if result.returncode not in {DONE_CODE, CONTINUE_CODE, BLOCKED_CODE}:
            status = "error"
            payload = {
                "status": status,
                "iterations": iteration,
                "exit_code": ERROR_CODE,
                "log_path": runtime.rel_path(log_path, target),
                "reason": f"loop-step failed ({result.returncode})",
                "updated_at": utc_timestamp(),
            }
            append_log(log_path, f"{utc_timestamp()} iteration={iteration} status=error code={result.returncode}")
            emit(args.format, payload)
            return ERROR_CODE
        try:
            step_payload = json.loads(result.stdout)
        except json.JSONDecodeError:
            step_payload = {}
        last_payload = step_payload
        append_log(
            log_path,
            f"{utc_timestamp()} iteration={iteration} status={step_payload.get('status')} stage={step_payload.get('stage')} verdict={step_payload.get('verdict')}",
        )
        if result.returncode == DONE_CODE:
            clear_active_state(target)
            payload = {
                "status": "ship",
                "iterations": iteration,
                "exit_code": DONE_CODE,
                "log_path": runtime.rel_path(log_path, target),
                "last_step": step_payload,
                "updated_at": utc_timestamp(),
            }
            emit(args.format, payload)
            return DONE_CODE
        if result.returncode == BLOCKED_CODE:
            payload = {
                "status": "blocked",
                "iterations": iteration,
                "exit_code": BLOCKED_CODE,
                "log_path": runtime.rel_path(log_path, target),
                "last_step": step_payload,
                "updated_at": utc_timestamp(),
            }
            emit(args.format, payload)
            return BLOCKED_CODE
        if sleep_seconds:
            time.sleep(sleep_seconds)

    payload = {
        "status": "max-iterations",
        "iterations": max_iterations,
        "exit_code": MAX_ITERATIONS_CODE,
        "log_path": runtime.rel_path(log_path, target),
        "last_step": last_payload,
        "updated_at": utc_timestamp(),
    }
    emit(args.format, payload)
    return MAX_ITERATIONS_CODE


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
