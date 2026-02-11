#!/usr/bin/env python3
"""Execute a single loop step (implement/review)."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import shutil
import shlex
import subprocess
import sys
import threading
from pathlib import Path
from typing import Dict, List, Tuple, Optional, TextIO

from aidd_runtime import claude_stream_render
from aidd_runtime import runtime
from aidd_runtime.feature_ids import write_active_state
from aidd_runtime.io_utils import dump_yaml, parse_front_matter, utc_timestamp

DONE_CODE = 0
CONTINUE_CODE = 10
BLOCKED_CODE = 20
ERROR_CODE = 30
WARN_REASON_CODES = {
    "out_of_scope_warn",
    "no_boundaries_defined_warn",
    "auto_boundary_extend_warn",
    "review_context_pack_placeholder_warn",
}
HARD_BLOCK_REASON_CODES = {
    "user_approval_required",
}
WRAPPER_SKIP_BLOCK_REASON_CODE = "wrappers_skipped_unsafe"
WRAPPER_SKIP_WARN_REASON_CODE = "wrappers_skipped_warn"
OUTPUT_CONTRACT_WARN_REASON_CODE = "output_contract_warn"
HANDOFF_QA_START = "<!-- handoff:qa start -->"
HANDOFF_QA_END = "<!-- handoff:qa end -->"
CHECKBOX_RE = re.compile(r"^\s*-\s*\[(?P<state>[ xX])\]\s+(?P<body>.+)$")
BLOCKING_PAREN_RE = re.compile(r"\(Blocking:\s*(true|false)\)", re.IGNORECASE)
BLOCKING_LINE_RE = re.compile(r"^\s*-\s*Blocking:\s*(true|false)\b", re.IGNORECASE)
SCOPE_RE = re.compile(r"\bscope\s*:\s*([A-Za-z0-9_.:=-]+)", re.IGNORECASE)
ITEM_ID_RE = re.compile(r"\bid\s*:\s*([A-Za-z0-9_.:-]+)")
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


def read_active_stage(root: Path) -> str:
    return runtime.read_active_stage(root)


def write_active_mode(root: Path, mode: str = "loop") -> None:
    docs_dir = root / "docs"
    docs_dir.mkdir(parents=True, exist_ok=True)
    (docs_dir / ".active_mode").write_text(mode + "\n", encoding="utf-8")


def write_active_stage(root: Path, stage: str) -> None:
    write_active_state(root, stage=stage)


def write_active_work_item(root: Path, work_item_key: str) -> None:
    write_active_state(root, work_item=work_item_key)


def write_active_ticket(root: Path, ticket: str) -> None:
    write_active_state(root, ticket=ticket)


def resolve_stage_scope(root: Path, ticket: str, stage: str) -> Tuple[str, str]:
    if stage in {"implement", "review"}:
        work_item_key = runtime.read_active_work_item(root)
        if not work_item_key:
            return "", ""
        if not runtime.is_valid_work_item_key(work_item_key):
            return work_item_key, ""
        return work_item_key, runtime.resolve_scope_key(work_item_key, ticket)
    return "", runtime.resolve_scope_key("", ticket)


def stage_result_path(root: Path, ticket: str, scope_key: str, stage: str) -> Path:
    from aidd_runtime import loop_step_stage_result as _stage_result

    return _stage_result.stage_result_path(root, ticket, scope_key, stage)


def _parse_stage_result(path: Path, stage: str) -> Tuple[Dict[str, object] | None, str]:
    from aidd_runtime import loop_step_stage_result as _stage_result

    return _stage_result._parse_stage_result(path, stage)


def _collect_stage_result_candidates(root: Path, ticket: str, stage: str) -> List[Path]:
    from aidd_runtime import loop_step_stage_result as _stage_result

    return _stage_result._collect_stage_result_candidates(root, ticket, stage)


def _in_window(path: Path, *, started_at: float | None, finished_at: float | None, tolerance_seconds: float = 5.0) -> bool:
    from aidd_runtime import loop_step_stage_result as _stage_result

    return _stage_result._in_window(
        path,
        started_at=started_at,
        finished_at=finished_at,
        tolerance_seconds=tolerance_seconds,
    )


def _stage_result_diagnostics(candidates: List[Tuple[Path, str]]) -> str:
    from aidd_runtime import loop_step_stage_result as _stage_result

    return _stage_result._stage_result_diagnostics(candidates)


def load_stage_result(
    root: Path,
    ticket: str,
    scope_key: str,
    stage: str,
    *,
    started_at: float | None = None,
    finished_at: float | None = None,
) -> Tuple[Dict[str, object] | None, Path, str, str, str, str]:
    from aidd_runtime import loop_step_stage_result as _stage_result

    return _stage_result.load_stage_result(
        root,
        ticket,
        scope_key,
        stage,
        started_at=started_at,
        finished_at=finished_at,
    )


def normalize_stage_result(result: str, reason_code: str) -> str:
    from aidd_runtime import loop_step_stage_result as _stage_result

    return _stage_result.normalize_stage_result(result, reason_code)


def runner_supports_flag(command: str, flag: str) -> bool:
    from aidd_runtime import loop_step_wrappers as _wrappers

    return _wrappers.runner_supports_flag(command, flag)


def _strip_flag_with_value(tokens: List[str], flag: str) -> Tuple[List[str], bool]:
    from aidd_runtime import loop_step_wrappers as _wrappers

    return _wrappers._strip_flag_with_value(tokens, flag)


def inject_plugin_flags(tokens: List[str], plugin_root: Path) -> Tuple[List[str], List[str]]:
    from aidd_runtime import loop_step_wrappers as _wrappers

    return _wrappers.inject_plugin_flags(tokens, plugin_root)


def validate_command_available(plugin_root: Path, stage: str) -> Tuple[bool, str, str]:
    from aidd_runtime import loop_step_wrappers as _wrappers

    return _wrappers.validate_command_available(plugin_root, stage)


def resolve_stream_mode(raw: Optional[str]) -> str:
    from aidd_runtime import loop_step_policy as _policy

    return _policy.resolve_stream_mode(raw)


def review_pack_v2_required(root: Path) -> bool:
    from aidd_runtime import loop_step_stage_result as _stage_result

    return _stage_result.review_pack_v2_required(root)


def _parse_bool(value: str | None) -> bool | None:
    from aidd_runtime import loop_step_policy as _policy

    return _policy._parse_bool(value)


def _normalize_scope(value: str) -> str:
    from aidd_runtime import loop_step_policy as _policy

    return _policy._normalize_scope(value)


def _is_valid_work_item_key(value: str) -> bool:
    from aidd_runtime import loop_step_policy as _policy

    return _policy._is_valid_work_item_key(value)


def _extract_work_item_key(lines: List[str]) -> str:
    from aidd_runtime import loop_step_policy as _policy

    return _policy._extract_work_item_key(lines)


def _extract_blocking_flag(lines: List[str]) -> bool | None:
    from aidd_runtime import loop_step_policy as _policy

    return _policy._extract_blocking_flag(lines)


def _extract_item_id(lines: List[str]) -> str:
    from aidd_runtime import loop_step_policy as _policy

    return _policy._extract_item_id(lines)


def _extract_checkbox_state(line: str) -> str:
    from aidd_runtime import loop_step_policy as _policy

    return _policy._extract_checkbox_state(line)


def _parse_qa_handoff_candidates(lines: List[str]) -> List[Tuple[str, str]]:
    from aidd_runtime import loop_step_policy as _policy

    return _policy._parse_qa_handoff_candidates(lines)


def _auto_repair_enabled(root: Path) -> bool:
    from aidd_runtime import loop_step_policy as _policy

    return _policy._auto_repair_enabled(root)


def _resolve_qa_repair_mode(requested: str | None, root: Path) -> Tuple[str, bool]:
    from aidd_runtime import loop_step_policy as _policy

    return _policy._resolve_qa_repair_mode(requested, root)


def _select_qa_repair_work_item(
    *,
    tasklist_lines: List[str],
    explicit: str,
    select_handoff: bool,
    mode: str,
) -> Tuple[str, str, str, List[str]]:
    from aidd_runtime import loop_step_policy as _policy

    return _policy._select_qa_repair_work_item(
        tasklist_lines=tasklist_lines,
        explicit=explicit,
        select_handoff=select_handoff,
        mode=mode,
    )


def _maybe_append_qa_repair_event(
    root: Path,
    *,
    ticket: str,
    slug_hint: str,
    work_item_key: str,
    mode: str,
) -> None:
    from aidd_runtime import loop_step_policy as _policy

    _policy._maybe_append_qa_repair_event(
        root,
        ticket=ticket,
        slug_hint=slug_hint,
        work_item_key=work_item_key,
        mode=mode,
    )


def parse_timestamp(value: str) -> dt.datetime | None:
    from aidd_runtime import loop_step_stage_result as _stage_result

    return _stage_result.parse_timestamp(value)


def resolve_review_report_path(root: Path, ticket: str, slug_hint: str, scope_key: str) -> Path:
    from aidd_runtime import loop_step_stage_result as _stage_result

    return _stage_result.resolve_review_report_path(root, ticket, slug_hint, scope_key)


def _maybe_regen_review_pack(
    root: Path,
    *,
    ticket: str,
    slug_hint: str,
    scope_key: str,
) -> Tuple[bool, str]:
    from aidd_runtime import loop_step_stage_result as _stage_result

    return _stage_result._maybe_regen_review_pack(
        root,
        ticket=ticket,
        slug_hint=slug_hint,
        scope_key=scope_key,
    )


def validate_review_pack(
    root: Path,
    *,
    ticket: str,
    slug_hint: str,
    scope_key: str,
) -> Tuple[bool, str, str]:
    from aidd_runtime import loop_step_stage_result as _stage_result

    return _stage_result.validate_review_pack(
        root,
        ticket=ticket,
        slug_hint=slug_hint,
        scope_key=scope_key,
    )


def resolve_runner(args_runner: str | None, plugin_root: Path) -> Tuple[List[str], str, str]:
    from aidd_runtime import loop_step_wrappers as _wrappers

    return _wrappers.resolve_runner(args_runner, plugin_root)


def is_skill_first(plugin_root: Path) -> bool:
    from aidd_runtime import loop_step_policy as _policy

    return _policy.is_skill_first(plugin_root)


def resolve_wrapper_plugin_root(plugin_root: Path) -> Path:
    from aidd_runtime import loop_step_policy as _policy

    return _policy.resolve_wrapper_plugin_root(plugin_root)


def should_run_wrappers(stage: str, runner_raw: str, plugin_root: Path) -> bool:
    from aidd_runtime import loop_step_policy as _policy

    return _policy.should_run_wrappers(stage, runner_raw, plugin_root)


def resolve_hooks_mode() -> str:
    from aidd_runtime import loop_step_policy as _policy

    return _policy.resolve_hooks_mode()


def evaluate_wrapper_skip_policy(stage: str, plugin_root: Path) -> Tuple[str, str, str]:
    from aidd_runtime import loop_step_policy as _policy

    return _policy.evaluate_wrapper_skip_policy(stage, plugin_root)


def evaluate_output_contract_policy(status: str) -> Tuple[str, str]:
    from aidd_runtime import loop_step_policy as _policy

    return _policy.evaluate_output_contract_policy(status)


def _parse_wrapper_output(stdout: str) -> Dict[str, str]:
    from aidd_runtime import loop_step_wrappers as _wrappers

    return _wrappers._parse_wrapper_output(stdout)


def _runtime_env(plugin_root: Path) -> Dict[str, str]:
    from aidd_runtime import loop_step_wrappers as _wrappers

    return _wrappers._runtime_env(plugin_root)


def _stage_wrapper_log_path(target: Path, stage: str, ticket: str, scope_key: str, kind: str) -> Path:
    from aidd_runtime import loop_step_wrappers as _wrappers

    return _wrappers._stage_wrapper_log_path(target, stage, ticket, scope_key, kind)


def _append_stage_wrapper_log(log_path: Path, command: List[str], stdout: str, stderr: str) -> None:
    from aidd_runtime import loop_step_wrappers as _wrappers

    _wrappers._append_stage_wrapper_log(log_path, command, stdout, stderr)


def _run_runtime_command(
    *,
    command: List[str],
    cwd: Path,
    env: Dict[str, str],
    log_path: Path,
) -> Tuple[int, str, str]:
    from aidd_runtime import loop_step_wrappers as _wrappers

    return _wrappers._run_runtime_command(
        command=command,
        cwd=cwd,
        env=env,
        log_path=log_path,
    )


def _resolve_stage_paths(target: Path, ticket: str, scope_key: str, stage: str) -> Dict[str, Path]:
    from aidd_runtime import loop_step_wrappers as _wrappers

    return _wrappers._resolve_stage_paths(target, ticket, scope_key, stage)


def _copy_optional_preflight_fallback(paths: Dict[str, Path]) -> None:
    from aidd_runtime import loop_step_wrappers as _wrappers

    _wrappers._copy_optional_preflight_fallback(paths)


def run_stage_wrapper(
    *,
    plugin_root: Path,
    workspace_root: Path,
    stage: str,
    kind: str,
    ticket: str,
    scope_key: str,
    work_item_key: str,
    actions_path: str = "",
    result: str = "",
    verdict: str = "",
) -> Tuple[bool, Dict[str, str], str]:
    from aidd_runtime import loop_step_wrappers as _wrappers

    return _wrappers.run_stage_wrapper(
        plugin_root=plugin_root,
        workspace_root=workspace_root,
        stage=stage,
        kind=kind,
        ticket=ticket,
        scope_key=scope_key,
        work_item_key=work_item_key,
        actions_path=actions_path,
        result=result,
        verdict=verdict,
    )


def _canonical_actions_log_rel(ticket: str, scope_key: str, stage: str) -> str:
    from aidd_runtime import loop_step_policy as _policy

    return _policy.canonical_actions_log_rel(ticket, scope_key, stage)


def _align_actions_log_scope(
    *,
    actions_log_rel: str,
    ticket: str,
    stage: str,
    mismatch_from: str,
    mismatch_to: str,
    target: Path,
) -> str:
    from aidd_runtime import loop_step_policy as _policy

    return _policy.align_actions_log_scope(
        actions_log_rel=actions_log_rel,
        ticket=ticket,
        stage=stage,
        mismatch_from=mismatch_from,
        mismatch_to=mismatch_to,
        target=target,
    )


def _validate_stage_wrapper_contract(
    *,
    target: Path,
    ticket: str,
    scope_key: str,
    stage: str,
    actions_log_rel: str,
) -> Tuple[bool, str, str]:
    from aidd_runtime import loop_step_wrappers as _wrappers

    return _wrappers.validate_stage_wrapper_contract(
        target=target,
        ticket=ticket,
        scope_key=scope_key,
        stage=stage,
        actions_log_rel=actions_log_rel,
    )


def build_command(stage: str, ticket: str) -> List[str]:
    from aidd_runtime import loop_step_wrappers as _wrappers

    return _wrappers.build_command(stage, ticket)


def run_command(command: List[str], cwd: Path, log_path: Path) -> int:
    from aidd_runtime import loop_step_wrappers as _wrappers

    return _wrappers.run_command(command, cwd, log_path)


def run_stream_command(
    *,
    command: List[str],
    cwd: Path,
    log_path: Path,
    stream_mode: str,
    stream_jsonl_path: Path,
    stream_log_path: Path,
    output_stream: TextIO,
    header_lines: Optional[List[str]] = None,
) -> int:
    from aidd_runtime import loop_step_wrappers as _wrappers

    return _wrappers.run_stream_command(
        command=command,
        cwd=cwd,
        log_path=log_path,
        stream_mode=stream_mode,
        stream_jsonl_path=stream_jsonl_path,
        stream_log_path=stream_log_path,
        output_stream=output_stream,
        header_lines=header_lines,
    )


def append_cli_log(log_path: Path, payload: Dict[str, object]) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False) + "\n")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Execute a single loop step (implement/review).")
    parser.add_argument("--ticket", help="Ticket identifier (defaults to docs/.active.json).")
    parser.add_argument("--runner", help="Runner command override (default: claude).")
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
    parser.add_argument("--work-item-key", help="Explicit work item key (iteration_id=... or id=...).")
    parser.add_argument(
        "--select-qa-handoff",
        action="store_true",
        help="Auto-select blocking QA handoff item when repairing from QA.",
    )
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
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    runner_hint = str(args.runner or os.environ.get("AIDD_LOOP_RUNNER") or "claude").strip() or "claude"
    os.environ["AIDD_LOOP_RUNNER_HINT"] = runner_hint
    workspace_root, target = runtime.require_workflow_root()
    context = runtime.resolve_feature_context(target, ticket=args.ticket, slug_hint=None)
    ticket = (context.resolved_ticket or "").strip()
    slug_hint = (context.slug_hint or ticket or "").strip()
    if not ticket:
        raise ValueError("feature ticket is required; pass --ticket or set docs/.active.json via /feature-dev-aidd:idea-new.")
    plugin_root = runtime.require_plugin_root()
    wrapper_plugin_root = resolve_wrapper_plugin_root(plugin_root)

    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%d-%H%M%S")
    cli_log_path = target / "reports" / "loops" / ticket / f"cli.loop-step.{stamp}.log"

    stage = read_active_stage(target)
    stream_mode = resolve_stream_mode(getattr(args, "stream", None))
    from_qa_mode, from_qa_requested = _resolve_qa_repair_mode(args.from_qa, target)
    reason = ""
    reason_code = ""
    scope_key = ""
    stage_result_rel = ""
    repair_reason_code = ""
    repair_scope_key = ""
    scope_key_mismatch_warn = ""
    scope_key_mismatch_from = ""
    scope_key_mismatch_to = ""
    stage_result_diag = ""

    if from_qa_requested and stage != "qa":
        reason = f"qa repair requested but active stage is '{stage or 'unset'}'"
        reason_code = "qa_repair_invalid_stage"
        return emit_result(
            args.format,
            ticket,
            stage or "unknown",
            "blocked",
            BLOCKED_CODE,
            "",
            reason,
            reason_code,
            cli_log_path=cli_log_path,
        )

    if not stage:
        next_stage = "implement"
    else:
        work_item_key, scope_key = resolve_stage_scope(target, ticket, stage)
        if stage in {"implement", "review"}:
            if not work_item_key:
                reason = "active work item missing"
                reason_code = "stage_result_missing_or_invalid"
                return emit_result(
                    args.format,
                    ticket,
                    stage,
                    "blocked",
                    BLOCKED_CODE,
                    "",
                    reason,
                    reason_code,
                    cli_log_path=cli_log_path,
                )
            if not runtime.is_valid_work_item_key(work_item_key):
                reason = f"invalid active work item key: {work_item_key}"
                reason_code = "invalid_work_item_key"
                return emit_result(
                    args.format,
                    ticket,
                    stage,
                    "blocked",
                    BLOCKED_CODE,
                    "",
                    reason,
                    reason_code,
                    cli_log_path=cli_log_path,
                )
            if not runtime.is_iteration_work_item_key(work_item_key):
                reason = (
                    f"invalid active work item key for loop stage: {work_item_key}; "
                    "expected iteration_id=<id>. Update tasklist/active work item."
                )
                reason_code = "invalid_work_item_key"
                return emit_result(
                    args.format,
                    ticket,
                    stage,
                    "blocked",
                    BLOCKED_CODE,
                    "",
                    reason,
                    reason_code,
                    cli_log_path=cli_log_path,
                )
        payload, result_path, error, mismatch_from, mismatch_to, diag = load_stage_result(
            target, ticket, scope_key, stage
        )
        if error:
            reason = f"{error}; {diag}" if diag else error
            reason_code = error
            return emit_result(
                args.format,
                ticket,
                stage,
                "blocked",
                BLOCKED_CODE,
                "",
                reason,
                reason_code,
                scope_key=scope_key,
                stage_result_diag=diag,
                cli_log_path=cli_log_path,
            )
        if mismatch_to:
            scope_key_mismatch_warn = "1"
            scope_key_mismatch_from = mismatch_from
            scope_key_mismatch_to = mismatch_to
            print(
                f"[loop-step] WARN: scope_key_mismatch_warn from={mismatch_from} to={mismatch_to}",
                file=sys.stderr,
            )
            scope_key = mismatch_to
        result = str(payload.get("result") or "").strip().lower()
        reason = str(payload.get("reason") or "").strip()
        reason_code = str(payload.get("reason_code") or "").strip().lower()
        result = normalize_stage_result(result, reason_code)
        stage_result_rel = runtime.rel_path(result_path, target)
        if result == "blocked" and stage != "qa":
            return emit_result(
                args.format,
                ticket,
                stage,
                "blocked",
                BLOCKED_CODE,
                "",
                reason,
                reason_code,
                scope_key=scope_key,
                stage_result_path=stage_result_rel,
                cli_log_path=cli_log_path,
            )
        if stage == "review":
            if result == "done":
                ok, message, code = validate_review_pack(
                    target,
                    ticket=ticket,
                    slug_hint=slug_hint,
                    scope_key=scope_key,
                )
                if not ok:
                    return emit_result(
                        args.format,
                        ticket,
                        stage,
                        "blocked",
                        BLOCKED_CODE,
                        "",
                        message,
                        code,
                        scope_key=scope_key,
                        stage_result_path=stage_result_rel,
                        cli_log_path=cli_log_path,
                    )
                return emit_result(
                    args.format,
                    ticket,
                    stage,
                    "done",
                    DONE_CODE,
                    "",
                    reason,
                    reason_code,
                    scope_key=scope_key,
                    stage_result_path=stage_result_rel,
                    cli_log_path=cli_log_path,
                )
            if result == "continue":
                ok, message, code = validate_review_pack(
                    target,
                    ticket=ticket,
                    slug_hint=slug_hint,
                    scope_key=scope_key,
                )
                if not ok:
                    return emit_result(
                        args.format,
                        ticket,
                        stage,
                        "blocked",
                        BLOCKED_CODE,
                        "",
                        message,
                        code,
                        scope_key=scope_key,
                        stage_result_path=stage_result_rel,
                        cli_log_path=cli_log_path,
                    )
                next_stage = "implement"
            else:
                reason = f"review result={result or 'unknown'}"
                reason_code = reason_code or "unsupported_stage_result"
                return emit_result(
                    args.format,
                    ticket,
                    stage,
                    "blocked",
                    BLOCKED_CODE,
                    "",
                    reason,
                    reason_code,
                    scope_key=scope_key,
                    stage_result_path=stage_result_rel,
                    cli_log_path=cli_log_path,
                )
        elif stage == "implement":
            if result in {"continue", "done"}:
                next_stage = "review"
            else:
                reason = f"implement result={result or 'unknown'}"
                reason_code = reason_code or "unsupported_stage_result"
                return emit_result(
                    args.format,
                    ticket,
                    stage,
                    "blocked",
                    BLOCKED_CODE,
                    "",
                    reason,
                    reason_code,
                    scope_key=scope_key,
                    stage_result_path=stage_result_rel,
                    cli_log_path=cli_log_path,
                )
        elif stage == "qa":
            if result == "done":
                if from_qa_requested:
                    reason = "qa repair requested but stage result is not blocked"
                    reason_code = "qa_repair_not_blocked"
                    return emit_result(
                        args.format,
                        ticket,
                        stage,
                        "blocked",
                        BLOCKED_CODE,
                        "",
                        reason,
                        reason_code,
                        scope_key=scope_key,
                        stage_result_path=stage_result_rel,
                        cli_log_path=cli_log_path,
                    )
                return emit_result(
                    args.format,
                    ticket,
                    stage,
                    "done",
                    DONE_CODE,
                    "",
                    reason,
                    reason_code,
                    scope_key=scope_key,
                    stage_result_path=stage_result_rel,
                    cli_log_path=cli_log_path,
                )
            if result == "blocked":
                if from_qa_mode:
                    tasklist_path = target / "docs" / "tasklist" / f"{ticket}.md"
                    if args.work_item_key:
                        tasklist_lines: List[str] = []
                    else:
                        if not tasklist_path.exists():
                            reason = "tasklist missing; cannot select qa handoff"
                            reason_code = "qa_repair_tasklist_missing"
                            return emit_result(
                                args.format,
                                ticket,
                                stage,
                                "blocked",
                                BLOCKED_CODE,
                                "",
                                reason,
                                reason_code,
                                scope_key=scope_key,
                                stage_result_path=stage_result_rel,
                                cli_log_path=cli_log_path,
                            )
                        tasklist_lines = tasklist_path.read_text(encoding="utf-8").splitlines()

                    work_item_key, select_code, select_reason, labels = _select_qa_repair_work_item(
                        tasklist_lines=tasklist_lines,
                        explicit=(args.work_item_key or "").strip(),
                        select_handoff=args.select_qa_handoff,
                        mode=from_qa_mode,
                    )
                    if select_code:
                        reason = select_reason
                        if labels:
                            reason = f"{select_reason}: {', '.join(labels)}"
                        reason_code = select_code
                        return emit_result(
                            args.format,
                            ticket,
                            stage,
                            "blocked",
                            BLOCKED_CODE,
                            "",
                            reason,
                            reason_code,
                            scope_key=scope_key,
                            stage_result_path=stage_result_rel,
                            cli_log_path=cli_log_path,
                        )

                    write_active_ticket(target, ticket)
                    write_active_work_item(target, work_item_key)
                    write_active_stage(target, "implement")
                    _maybe_append_qa_repair_event(
                        target,
                        ticket=ticket,
                        slug_hint=slug_hint,
                        work_item_key=work_item_key,
                        mode=from_qa_mode,
                    )
                    repair_reason_code = "qa_repair"
                    repair_scope_key = runtime.resolve_scope_key(work_item_key, ticket)
                    reason = "qa blocked; switching to implement"
                    reason_code = repair_reason_code
                    next_stage = "implement"
                    # fall through to runner execution
                else:
                    return emit_result(
                        args.format,
                        ticket,
                        stage,
                        "blocked",
                        BLOCKED_CODE,
                        "",
                        reason,
                        reason_code,
                        scope_key=scope_key,
                        stage_result_path=stage_result_rel,
                        cli_log_path=cli_log_path,
                    )
                # from-qa repair path continues to runner
            else:
                reason = f"qa result={result or 'unknown'}"
                reason_code = reason_code or "unsupported_stage_result"
                return emit_result(
                    args.format,
                    ticket,
                    stage,
                    "blocked",
                    BLOCKED_CODE,
                    "",
                    reason,
                    reason_code,
                    scope_key=scope_key,
                    stage_result_path=stage_result_rel,
                    cli_log_path=cli_log_path,
                )
        else:
            reason = f"unsupported stage={stage}"
            reason_code = reason_code or "unsupported_stage"
            return emit_result(
                args.format,
                ticket,
                stage,
                "blocked",
                BLOCKED_CODE,
                "",
                reason,
                reason_code,
                cli_log_path=cli_log_path,
            )

    write_active_mode(target, "loop")
    ok, message, code = validate_command_available(plugin_root, next_stage)
    if not ok:
        return emit_result(
            args.format,
            ticket,
            next_stage,
            "blocked",
            BLOCKED_CODE,
            "",
            message,
            code,
            repair_reason_code=repair_reason_code,
            repair_scope_key=repair_scope_key,
            cli_log_path=cli_log_path,
        )
    runner_tokens, runner_raw, runner_notice = resolve_runner(args.runner, plugin_root)
    wrapper_enabled = should_run_wrappers(next_stage, runner_raw, wrapper_plugin_root)
    wrapper_logs: List[str] = []
    actions_log_rel = ""
    wrapper_scope_key = runtime.resolve_scope_key(runtime.read_active_work_item(target), ticket)
    wrapper_work_item_key = runtime.read_active_work_item(target)
    if next_stage == "qa":
        wrapper_scope_key = runtime.resolve_scope_key("", ticket)
        wrapper_work_item_key = wrapper_work_item_key or ""
    wrapper_skip_policy, wrapper_skip_reason, wrapper_skip_code = evaluate_wrapper_skip_policy(
        next_stage,
        wrapper_plugin_root,
    )
    if wrapper_skip_policy == "blocked":
        return emit_result(
            args.format,
            ticket,
            next_stage,
            "blocked",
            BLOCKED_CODE,
            "",
            wrapper_skip_reason,
            wrapper_skip_code,
            scope_key=wrapper_scope_key,
            runner=runner_raw,
            repair_reason_code=repair_reason_code,
            repair_scope_key=repair_scope_key,
            cli_log_path=cli_log_path,
        )
    if wrapper_skip_policy == "warn":
        wrapper_skip_message = f"{wrapper_skip_reason} (reason_code={wrapper_skip_code})"
        print(f"[loop-step] WARN: {wrapper_skip_message}", file=sys.stderr)
        runner_notice = f"{runner_notice}; {wrapper_skip_message}" if runner_notice else wrapper_skip_message
    if wrapper_enabled:
        ok_wrapper, preflight_payload, wrapper_error = run_stage_wrapper(
            plugin_root=wrapper_plugin_root,
            workspace_root=workspace_root,
            stage=next_stage,
            kind="preflight",
            ticket=ticket,
            scope_key=wrapper_scope_key,
            work_item_key=wrapper_work_item_key,
        )
        if not ok_wrapper:
            return emit_result(
                args.format,
                ticket,
                next_stage,
                "blocked",
                BLOCKED_CODE,
                "",
                wrapper_error,
                "preflight_missing",
                scope_key=wrapper_scope_key,
                cli_log_path=cli_log_path,
            )
        if preflight_payload.get("log_path"):
            wrapper_logs.append(preflight_payload["log_path"])
        actions_log_rel = preflight_payload.get("actions_path", actions_log_rel)

    command = list(runner_tokens)
    if stream_mode:
        command.extend(["--output-format", "stream-json", "--include-partial-messages", "--verbose"])
    command.extend(build_command(next_stage, ticket))
    runner_effective = " ".join(command)
    run_stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%d-%H%M%S")
    log_path = target / "reports" / "loops" / ticket / f"cli.{next_stage}.{run_stamp}.log"

    stream_log_rel = ""
    stream_jsonl_rel = ""
    run_started_at = dt.datetime.now(dt.timezone.utc).timestamp()
    if stream_mode:
        stream_log_path = target / "reports" / "loops" / ticket / f"cli.loop-step.{stamp}.stream.log"
        stream_jsonl_path = target / "reports" / "loops" / ticket / f"cli.loop-step.{stamp}.stream.jsonl"
        stream_log_rel = runtime.rel_path(stream_log_path, target)
        stream_jsonl_rel = runtime.rel_path(stream_jsonl_path, target)
        active_work_item = runtime.read_active_work_item(target)
        stream_scope_key = runtime.resolve_scope_key(active_work_item, ticket) if active_work_item else "n/a"
        header_lines = [
            f"==> loop-step: stage={next_stage} ticket={ticket} scope_key={stream_scope_key}",
            f"==> streaming enabled: writing stream={stream_jsonl_rel} log={stream_log_rel}",
        ]
        returncode = run_stream_command(
            command=command,
            cwd=workspace_root,
            log_path=log_path,
            stream_mode=stream_mode,
            stream_jsonl_path=stream_jsonl_path,
            stream_log_path=stream_log_path,
            output_stream=sys.stderr,
            header_lines=header_lines,
        )
    else:
        returncode = run_command(command, workspace_root, log_path)
    run_finished_at = dt.datetime.now(dt.timezone.utc).timestamp()
    if returncode != 0:
        status = "error"
        code = ERROR_CODE
        reason = f"runner exited with {returncode}"
        return emit_result(
            args.format,
            ticket,
            next_stage,
            status,
            code,
            log_path,
            reason,
            "",
            scope_key="",
            stage_result_path="",
            runner=runner_raw,
            runner_effective=runner_effective,
            runner_notice=runner_notice,
            repair_reason_code=repair_reason_code,
            repair_scope_key=repair_scope_key,
            stream_log_path=stream_log_rel,
            stream_jsonl_path=stream_jsonl_rel,
            cli_log_path=cli_log_path,
        )

    next_work_item_key, next_scope_key = resolve_stage_scope(target, ticket, next_stage)
    if next_stage in {"implement", "review"} and next_work_item_key and not runtime.is_iteration_work_item_key(next_work_item_key):
        reason = (
            f"invalid active work item key for loop stage: {next_work_item_key}; "
            "expected iteration_id=<id>. Update tasklist/active work item."
        )
        return emit_result(
            args.format,
            ticket,
            next_stage,
            "blocked",
            BLOCKED_CODE,
            log_path,
            reason,
            "invalid_work_item_key",
            runner=runner_raw,
            runner_effective=runner_effective,
            runner_notice=runner_notice,
            repair_reason_code=repair_reason_code,
            repair_scope_key=repair_scope_key,
            stream_log_path=stream_log_rel,
            stream_jsonl_path=stream_jsonl_rel,
            cli_log_path=cli_log_path,
        )

    if wrapper_enabled:
        ok_wrapper, run_payload, wrapper_error = run_stage_wrapper(
            plugin_root=wrapper_plugin_root,
            workspace_root=workspace_root,
            stage=next_stage,
            kind="run",
            ticket=ticket,
            scope_key=wrapper_scope_key,
            work_item_key=wrapper_work_item_key,
            actions_path=actions_log_rel,
        )
        if not ok_wrapper:
            return emit_result(
                args.format,
                ticket,
                next_stage,
                "blocked",
                BLOCKED_CODE,
                log_path,
                wrapper_error,
                "actions_missing",
                scope_key=wrapper_scope_key,
                runner=runner_raw,
                runner_effective=runner_effective,
                runner_notice=runner_notice,
                repair_reason_code=repair_reason_code,
                repair_scope_key=repair_scope_key,
                stream_log_path=stream_log_rel,
                stream_jsonl_path=stream_jsonl_rel,
                cli_log_path=cli_log_path,
            )
        if run_payload.get("log_path"):
            wrapper_logs.append(run_payload["log_path"])
        actions_log_rel = run_payload.get("actions_path", actions_log_rel)

    payload, result_path, error, mismatch_from, mismatch_to, diag = load_stage_result(
        target,
        ticket,
        next_scope_key,
        next_stage,
        started_at=run_started_at,
        finished_at=run_finished_at,
    )
    preliminary_result = str(payload.get("result") or "").strip().lower() if payload else "continue"
    preliminary_verdict = str(payload.get("verdict") or "").strip().upper() if payload else ""
    if mismatch_to:
        if not scope_key_mismatch_warn:
            scope_key_mismatch_warn = "1"
            scope_key_mismatch_from = mismatch_from
            scope_key_mismatch_to = mismatch_to
            print(
                f"[loop-step] WARN: scope_key_mismatch_warn from={mismatch_from} to={mismatch_to}",
                file=sys.stderr,
            )
        next_scope_key = mismatch_to
        aligned_actions_log_rel = _align_actions_log_scope(
            actions_log_rel=actions_log_rel,
            ticket=ticket,
            stage=next_stage,
            mismatch_from=mismatch_from,
            mismatch_to=mismatch_to,
            target=target,
        )
        if aligned_actions_log_rel != actions_log_rel:
            print(
                "[loop-step] WARN: actions_log_scope_realigned "
                f"from={actions_log_rel or 'n/a'} to={aligned_actions_log_rel}",
                file=sys.stderr,
            )
            actions_log_rel = aligned_actions_log_rel

    if wrapper_enabled:
        ok_wrapper, post_payload, wrapper_error = run_stage_wrapper(
            plugin_root=wrapper_plugin_root,
            workspace_root=workspace_root,
            stage=next_stage,
            kind="postflight",
            ticket=ticket,
            scope_key=next_scope_key or wrapper_scope_key,
            work_item_key=wrapper_work_item_key,
            actions_path=actions_log_rel,
            result=preliminary_result or "continue",
            verdict=preliminary_verdict,
        )
        if not ok_wrapper:
            return emit_result(
                args.format,
                ticket,
                next_stage,
                "blocked",
                BLOCKED_CODE,
                log_path,
                wrapper_error,
                "postflight_missing",
                scope_key=wrapper_scope_key,
                runner=runner_raw,
                runner_effective=runner_effective,
                runner_notice=runner_notice,
                repair_reason_code=repair_reason_code,
                repair_scope_key=repair_scope_key,
                stream_log_path=stream_log_rel,
                stream_jsonl_path=stream_jsonl_rel,
                cli_log_path=cli_log_path,
            )
        if post_payload.get("log_path"):
            wrapper_logs.append(post_payload["log_path"])
        if post_payload.get("apply_log"):
            wrapper_logs.append(post_payload["apply_log"])
        actions_log_rel = post_payload.get("actions_path", actions_log_rel)
        run_finished_at = dt.datetime.now(dt.timezone.utc).timestamp()
        payload, result_path, error, mismatch_from, mismatch_to, diag = load_stage_result(
            target,
            ticket,
            next_scope_key,
            next_stage,
            started_at=run_started_at,
            finished_at=run_finished_at,
        )

    if mismatch_to:
        if not scope_key_mismatch_warn:
            scope_key_mismatch_warn = "1"
            scope_key_mismatch_from = mismatch_from
            scope_key_mismatch_to = mismatch_to
            print(
                f"[loop-step] WARN: scope_key_mismatch_warn from={mismatch_from} to={mismatch_to}",
                file=sys.stderr,
            )
        next_scope_key = mismatch_to
        aligned_actions_log_rel = _align_actions_log_scope(
            actions_log_rel=actions_log_rel,
            ticket=ticket,
            stage=next_stage,
            mismatch_from=mismatch_from,
            mismatch_to=mismatch_to,
            target=target,
        )
        if aligned_actions_log_rel != actions_log_rel:
            print(
                "[loop-step] WARN: actions_log_scope_realigned "
                f"from={actions_log_rel or 'n/a'} to={aligned_actions_log_rel}",
                file=sys.stderr,
            )
            actions_log_rel = aligned_actions_log_rel

    if error:
        return emit_result(
            args.format,
            ticket,
            next_stage,
            "blocked",
            BLOCKED_CODE,
            log_path,
            f"{error}; {diag}" if diag else error,
            error,
            scope_key=next_scope_key,
            stage_result_path=runtime.rel_path(result_path, target),
            runner=runner_raw,
            runner_effective=runner_effective,
            runner_notice=runner_notice,
            repair_reason_code=repair_reason_code,
            repair_scope_key=repair_scope_key,
            stream_log_path=stream_log_rel,
            stream_jsonl_path=stream_jsonl_rel,
            stage_result_diag=diag,
            scope_key_mismatch_warn=scope_key_mismatch_warn,
            scope_key_mismatch_from=scope_key_mismatch_from,
            scope_key_mismatch_to=scope_key_mismatch_to,
            cli_log_path=cli_log_path,
        )
    next_scope_key = str(payload.get("scope_key") or next_scope_key or "").strip() or next_scope_key
    next_work_item_key = str(payload.get("work_item_key") or next_work_item_key or "").strip() or next_work_item_key
    result = str(payload.get("result") or "").strip().lower()
    reason = str(payload.get("reason") or "").strip()
    reason_code = str(payload.get("reason_code") or "").strip().lower()
    result = normalize_stage_result(result, reason_code)
    evidence_links = payload.get("evidence_links") if isinstance(payload, dict) else {}
    tests_log_path = ""
    if isinstance(evidence_links, dict):
        tests_log_path = str(evidence_links.get("tests_log") or "").strip()
    if not actions_log_rel and next_stage in {"implement", "review", "qa"}:
        default_actions = target / "reports" / "actions" / ticket / next_scope_key / f"{next_stage}.actions.json"
        if default_actions.exists():
            actions_log_rel = runtime.rel_path(default_actions, target)
    artifact_scope_key = wrapper_scope_key or next_scope_key
    if wrapper_enabled and next_stage in {"implement", "review", "qa"}:
        ok_contract, contract_message, contract_reason_code = _validate_stage_wrapper_contract(
            target=target,
            ticket=ticket,
            scope_key=artifact_scope_key,
            stage=next_stage,
            actions_log_rel=actions_log_rel,
        )
        if not ok_contract:
            return emit_result(
                args.format,
                ticket,
                next_stage,
                "blocked",
                BLOCKED_CODE,
                log_path,
                contract_message,
                contract_reason_code,
                scope_key=artifact_scope_key,
                stage_result_path=runtime.rel_path(result_path, target),
                runner=runner_raw,
                runner_effective=runner_effective,
                runner_notice=runner_notice,
                repair_reason_code=repair_reason_code,
                repair_scope_key=repair_scope_key,
                stream_log_path=stream_log_rel,
                stream_jsonl_path=stream_jsonl_rel,
                scope_key_mismatch_warn=scope_key_mismatch_warn,
                scope_key_mismatch_from=scope_key_mismatch_from,
                scope_key_mismatch_to=scope_key_mismatch_to,
                actions_log_path=actions_log_rel,
                tests_log_path=tests_log_path,
                wrapper_logs=wrapper_logs,
                cli_log_path=cli_log_path,
            )
    if next_stage in {"implement", "review", "qa"} and actions_log_rel:
        with log_path.open("a", encoding="utf-8") as handle:
            handle.write(f"\nAIDD:ACTIONS_LOG: {actions_log_rel}\n")
    if next_stage == "review" and result in {"continue", "done"}:
        ok, message, code = validate_review_pack(
            target,
            ticket=ticket,
            slug_hint=slug_hint,
            scope_key=next_scope_key,
        )
        if not ok:
            return emit_result(
                args.format,
                ticket,
                next_stage,
                "blocked",
                BLOCKED_CODE,
                log_path,
                message,
                code,
                scope_key=next_scope_key,
                stage_result_path=runtime.rel_path(result_path, target),
                runner=runner_raw,
                runner_effective=runner_effective,
                runner_notice=runner_notice,
                repair_reason_code=repair_reason_code,
                repair_scope_key=repair_scope_key,
                stream_log_path=stream_log_rel,
                stream_jsonl_path=stream_jsonl_rel,
                scope_key_mismatch_warn=scope_key_mismatch_warn,
                scope_key_mismatch_from=scope_key_mismatch_from,
                scope_key_mismatch_to=scope_key_mismatch_to,
                actions_log_path=actions_log_rel,
                tests_log_path=tests_log_path,
                wrapper_logs=wrapper_logs,
                cli_log_path=cli_log_path,
            )
    output_contract_path = ""
    output_contract_status = ""
    output_contract_warnings: list[str] = []
    try:
        from aidd_runtime import output_contract as _output_contract

        report = _output_contract.check_output_contract(
            target=target,
            ticket=ticket,
            stage=next_stage,
            scope_key=next_scope_key,
            work_item_key=next_work_item_key,
            log_path=log_path,
            stage_result_path=result_path,
            max_read_items=3,
        )
        output_contract_status = str(report.get("status") or "")
        output_contract_warnings = [
            str(item).strip()
            for item in (report.get("warnings") if isinstance(report.get("warnings"), list) else [])
            if str(item).strip()
        ]
        output_dir = target / "reports" / "loops" / ticket / next_scope_key
        output_dir.mkdir(parents=True, exist_ok=True)
        report_path = output_dir / "output.contract.json"
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        output_contract_path = runtime.rel_path(report_path, target)
    except Exception as exc:
        print(f"[loop-step] WARN: output contract check failed: {exc}", file=sys.stderr)
    contract_policy, contract_reason_code = evaluate_output_contract_policy(output_contract_status)
    if contract_policy:
        contract_reason = (
            f"output contract warnings ({', '.join(output_contract_warnings)})"
            if output_contract_warnings
            else "output contract warnings"
        )
        contract_reason = (
            f"{contract_reason} (path={output_contract_path})"
            if output_contract_path
            else contract_reason
        )
        if contract_policy == "blocked":
            return emit_result(
                args.format,
                ticket,
                next_stage,
                "blocked",
                BLOCKED_CODE,
                log_path,
                contract_reason,
                contract_reason_code,
                scope_key=next_scope_key,
                stage_result_path=runtime.rel_path(result_path, target),
                runner=runner_raw,
                runner_effective=runner_effective,
                runner_notice=runner_notice,
                repair_reason_code=repair_reason_code,
                repair_scope_key=repair_scope_key,
                stream_log_path=stream_log_rel,
                stream_jsonl_path=stream_jsonl_rel,
                scope_key_mismatch_warn=scope_key_mismatch_warn,
                scope_key_mismatch_from=scope_key_mismatch_from,
                scope_key_mismatch_to=scope_key_mismatch_to,
                actions_log_path=actions_log_rel,
                tests_log_path=tests_log_path,
                wrapper_logs=wrapper_logs,
                cli_log_path=cli_log_path,
                output_contract_path=output_contract_path,
                output_contract_status=output_contract_status,
            )
        print(f"[loop-step] WARN: {contract_reason} (reason_code={contract_reason_code})", file=sys.stderr)
        runner_notice = (
            f"{runner_notice}; {contract_reason} (reason_code={contract_reason_code})"
            if runner_notice
            else f"{contract_reason} (reason_code={contract_reason_code})"
        )
    status = result if result in {"blocked", "continue", "done"} else "blocked"
    code = DONE_CODE if status == "done" else BLOCKED_CODE if status == "blocked" else CONTINUE_CODE
    return emit_result(
        args.format,
        ticket,
        next_stage,
        status,
        code,
        log_path,
        reason,
        reason_code,
        scope_key=next_scope_key,
        stage_result_path=runtime.rel_path(result_path, target),
        runner=runner_raw,
        runner_effective=runner_effective,
        runner_notice=runner_notice,
        repair_reason_code=repair_reason_code,
        repair_scope_key=repair_scope_key,
        stream_log_path=stream_log_rel,
        stream_jsonl_path=stream_jsonl_rel,
        scope_key_mismatch_warn=scope_key_mismatch_warn,
        scope_key_mismatch_from=scope_key_mismatch_from,
        scope_key_mismatch_to=scope_key_mismatch_to,
        actions_log_path=actions_log_rel,
        tests_log_path=tests_log_path,
        wrapper_logs=wrapper_logs,
        cli_log_path=cli_log_path,
        output_contract_path=output_contract_path,
        output_contract_status=output_contract_status,
    )


def emit_result(
    fmt: str | None,
    ticket: str,
    stage: str,
    status: str,
    code: int,
    log_path: Path | str,
    reason: str,
    reason_code: str = "",
    *,
    scope_key: str = "",
    stage_result_path: str = "",
    runner: str = "",
    runner_effective: str = "",
    runner_notice: str = "",
    repair_reason_code: str = "",
    repair_scope_key: str = "",
    stream_log_path: str = "",
    stream_jsonl_path: str = "",
    cli_log_path: Path | None = None,
    output_contract_path: str = "",
    output_contract_status: str = "",
    scope_key_mismatch_warn: str = "",
    scope_key_mismatch_from: str = "",
    scope_key_mismatch_to: str = "",
    stage_result_diag: str = "",
    actions_log_path: str = "",
    tests_log_path: str = "",
    wrapper_logs: List[str] | None = None,
) -> int:
    status_value = status if status in {"blocked", "continue", "done"} else "blocked"
    scope_value = str(scope_key or "").strip()
    if not scope_value:
        scope_value = runtime.resolve_scope_key("", ticket)

    runner_value = str(runner or "").strip()
    if not runner_value:
        runner_value = (
            os.environ.get("AIDD_LOOP_RUNNER_HINT")
            or os.environ.get("AIDD_LOOP_RUNNER")
            or "claude"
        ).strip() or "claude"
    runner_effective_value = str(runner_effective or "").strip() or runner_value

    cli_log_value = str(cli_log_path) if cli_log_path else ""
    log_value = str(log_path) if log_path else ""
    if not log_value and cli_log_value:
        log_value = cli_log_value

    stage_result_input = str(stage_result_path or "").strip()
    stage_result_value = stage_result_input
    if not stage_result_value and stage in {"implement", "review", "qa"}:
        stage_result_value = f"aidd/reports/loops/{ticket}/{scope_value}/stage.{stage}.result.json"

    reason_value = str(reason or "").strip()
    reason_code_value = str(reason_code or "").strip().lower()
    if status_value == "blocked":
        if not reason_code_value:
            reason_code_value = "stage_result_blocked" if stage_result_input else "blocked_without_reason"
        if not reason_value:
            reason_value = f"{stage} blocked" if stage else "blocked"

    payload = {
        "ticket": ticket,
        "stage": stage,
        "status": status_value,
        "exit_code": code,
        "scope_key": scope_value,
        "log_path": log_value,
        "stage_result_path": stage_result_value,
        "runner": runner_value,
        "runner_effective": runner_effective_value,
        "runner_notice": runner_notice,
        "repair_reason_code": repair_reason_code,
        "repair_scope_key": repair_scope_key,
        "stream_log_path": stream_log_path,
        "stream_jsonl_path": stream_jsonl_path,
        "cli_log_path": cli_log_value,
        "output_contract_path": output_contract_path,
        "output_contract_status": output_contract_status,
        "scope_key_mismatch_warn": scope_key_mismatch_warn,
        "scope_key_mismatch_from": scope_key_mismatch_from,
        "scope_key_mismatch_to": scope_key_mismatch_to,
        "stage_result_diagnostics": stage_result_diag,
        "actions_log_path": actions_log_path,
        "tests_log_path": tests_log_path,
        "wrapper_logs": wrapper_logs or [],
        "updated_at": utc_timestamp(),
        "reason": reason_value,
        "reason_code": reason_code_value,
    }
    if fmt:
        output = json.dumps(payload, ensure_ascii=False, indent=2) if fmt == "json" else "\n".join(dump_yaml(payload))
        print(output)
        print(f"[loop-step] {status} stage={stage} log={log_value}", file=sys.stderr)
    else:
        summary = f"[loop-step] {status} stage={stage}"
        if log_value:
            summary += f" log={log_value}"
        if reason:
            summary += f" reason={reason}"
        print(summary)
    if cli_log_path:
        append_cli_log(cli_log_path, payload)
    return code


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
