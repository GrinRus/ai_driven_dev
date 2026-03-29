#!/usr/bin/env python3
"""Execute a single loop step (implement/review)."""

from __future__ import annotations

import datetime as dt
import json
import os
import re
import sys
from pathlib import Path
from typing import Dict, List, Tuple, Optional

def _ensure_plugin_root_on_path() -> None:
    env_root = os.environ.get("CLAUDE_PLUGIN_ROOT", "").strip()
    if env_root:
        root = Path(env_root).resolve()
        if (root / "aidd_runtime").is_dir():
            if str(root) not in sys.path:
                sys.path.insert(0, str(root))
            return

    probe = Path(__file__).resolve()
    for parent in (probe.parent, *probe.parents):
        if (parent / "aidd_runtime").is_dir():
            os.environ.setdefault("CLAUDE_PLUGIN_ROOT", str(parent))
            if str(parent) not in sys.path:
                sys.path.insert(0, str(parent))
            return

_ensure_plugin_root_on_path()

from aidd_runtime import runtime
from aidd_runtime import stage_result_contract

DONE_CODE = 0
CONTINUE_CODE = 10
BLOCKED_CODE = 20
ERROR_CODE = 30
WARN_REASON_CODES = {
    "out_of_scope_warn",
    "no_boundaries_defined_warn",
    "auto_boundary_extend_warn",
    "review_context_pack_placeholder_warn",
    "fast_mode_warn",
    "output_contract_warn",
    "blocking_findings",
}
HARD_BLOCK_REASON_CODES = {"user_approval_required"}
OUTPUT_CONTRACT_WARN_REASON_CODE = "output_contract_warn"
LOOP_RUNNER_PERMISSIONS_REASON_CODE = "loop_runner_permissions"
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
STAGE_CHAIN_REASON_CODE_RE = re.compile(r"\breason_code=([a-z0-9_:-]+)\b", re.IGNORECASE)
_APPROVAL_ALLOW_VALUES = {"1", "true", "yes", "on"}
_CLAUDE_COMMANDS = {"claude", "claude.exe"}
_APPROVAL_MARKERS = ("requires approval", "command requires approval", "manual approval")
_MARKER_SEMANTIC_TOKENS = ("id=review:", "id_review_")
_MARKER_NOISE_SECTION_HINTS = ("aidd:how_to_update", "aidd:progress_log")
_MARKER_NOISE_PLACEHOLDERS = ("<title>", "<ticket>", "<scope_key>", "<commit/pr|report>")
_MARKER_INLINE_PATH_RE = re.compile(r"(?P<path>(?:aidd|docs|reports)/[^\s,;]+)", re.IGNORECASE)
_QUESTION_PROMPT_RE = re.compile(r"\b(?:question|вопрос|aidd:answers|answer|ответ)\b", re.IGNORECASE)
_QUESTION_REFERENCE_RE = re.compile(r"(?:^|\b)(?:q|question|вопрос)\s*\d+", re.IGNORECASE)
_QUESTION_REASON_CODES = {
    "answers_required",
    "missing_answers",
    "questions_pending",
    "missing_spec_answers",
    "spec_questions_unresolved",
}
_QUESTION_RETRY_REASON_CODE = "prompt_flow_blocker"
RUNTIME_PATH_DRIFT_REASON_CODE = "runtime_path_missing_or_drift"
PROMPT_FLOW_DRIFT_REASON_FAMILY = "prompt_flow_drift_non_canonical_runtime_path"
_CANT_OPEN_RUNTIME_RE = re.compile(
    r"can't open file [\"']?[^\"'\n]*?/skills/[^\"'\n]*/runtime/[^\"'\n]*",
    re.IGNORECASE,
)
_MANUAL_PREFLIGHT_PREPARE_CMD_RE = re.compile(
    r"python3\s+[^\n]*skills/aidd-loop/runtime/preflight_prepare\.py\b",
    re.IGNORECASE,
)
_NON_CANONICAL_STAGE_PREFLIGHT_CMD_RE = re.compile(
    r"python3\s+[^\n]*skills/(implement|review|qa)/runtime/preflight(?:_[a-z0-9]+)?\.py\b",
    re.IGNORECASE,
)
_JSON_COMMAND_RE = re.compile(r'"command"\s*:\s*"([^"]+)"')
if not __package__: sys.path.insert(0, str(Path(__file__).resolve().parents[1])); __package__ = "loop_step_parts"

from .helpers_preparse import (
    _approval_allowed,
    _build_loop_runner_env,
    _detect_runner_permission_mismatch,
    _detect_runtime_path_tripwire,
    _extract_stage_chain_reason_code,
    _is_question_retry_candidate,
    _maybe_append_qa_repair_event,
    _question_retry_material,
    _resolve_qa_repair_mode,
    _runner_is_claude,
    _scan_marker_semantics,
    _select_qa_repair_work_item,
    _sync_active_stage_for_loop_step,
    _validate_stage_chain_contract,
    _write_question_retry_artifacts,
    build_command,
    emit_result,
    evaluate_output_contract_policy,
    load_stage_result,
    normalize_stage_result,
    parse_args,
    read_active_stage,
    resolve_blocked_policy,
    resolve_runner,
    resolve_stage_chain_plugin_root,
    resolve_stage_scope,
    resolve_stream_mode,
    run_command,
    run_stage_chain,
    run_stream_command,
    should_run_stage_chain,
    validate_command_available,
    validate_review_pack,
    write_active_mode,
    write_active_stage,
    write_active_ticket,
    write_active_work_item,
)
__all__ = ["main", "_scan_marker_semantics"]

def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    runner_hint = str(args.runner or os.environ.get("AIDD_LOOP_RUNNER") or "claude").strip() or "claude"
    os.environ["AIDD_LOOP_RUNNER_HINT"] = runner_hint
    if str(args.runner or "").strip():
        os.environ["AIDD_LOOP_RUNNER_SOURCE_HINT"] = "cli_arg"
    elif str(os.environ.get("AIDD_LOOP_RUNNER") or "").strip():
        os.environ["AIDD_LOOP_RUNNER_SOURCE_HINT"] = "env_AIDD_LOOP_RUNNER"
    else:
        os.environ["AIDD_LOOP_RUNNER_SOURCE_HINT"] = "default"
    workspace_root, target = runtime.require_workflow_root()
    context = runtime.resolve_feature_context(target, ticket=args.ticket, slug_hint=None)
    ticket = (context.resolved_ticket or "").strip()
    slug_hint = (context.slug_hint or ticket or "").strip()
    if not ticket:
        raise ValueError("feature ticket is required; pass --ticket or set docs/.active.json via /feature-dev-aidd:idea-new.")
    plugin_root = runtime.resolve_plugin_root_with_fallback(start_file=Path(__file__))
    stage_chain_plugin_root = resolve_stage_chain_plugin_root(plugin_root)

    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%d-%H%M%S")
    cli_log_path = target / "reports" / "loops" / ticket / f"cli.loop-step.{stamp}.log"

    stage = read_active_stage(target)
    blocked_policy = resolve_blocked_policy(getattr(args, "blocked_policy", None), target)
    os.environ["AIDD_LOOP_BLOCKED_POLICY"] = blocked_policy
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
    scope_mismatch_non_authoritative = False
    expected_scope_key = ""
    selected_scope_key = ""
    stage_result_diag = ""
    stage_requested_result = ""
    active_stage_before_sync = stage or ""
    active_stage_after_sync = stage or ""
    active_stage_sync_applied = False

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

    if stage and stage not in {"implement", "review", "qa"}:
        active_work_item = runtime.read_active_work_item(target)
        if not active_work_item:
            reason = (
                f"cannot recover from active stage '{stage}': active work item missing; "
                "expected iteration_id=<id>."
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
        if not runtime.is_valid_work_item_key(active_work_item):
            reason = (
                f"cannot recover from active stage '{stage}': invalid active work item key "
                f"'{active_work_item}'; expected iteration_id=<id>."
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
        if not runtime.is_iteration_work_item_key(active_work_item):
            reason = (
                f"cannot recover from active stage '{stage}': invalid active work item key "
                f"'{active_work_item}'; expected iteration_id=<id>."
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
        write_active_ticket(target, ticket)
        write_active_work_item(target, active_work_item)
        write_active_stage(target, "implement")
        repair_reason_code = "non_loop_stage_recovered"
        repair_scope_key = runtime.resolve_scope_key(active_work_item, ticket)
        reason = f"active stage '{stage}' recovered to implement using work item {active_work_item}"
        reason_code = repair_reason_code
        print(
            f"[loop-step] WARN: {reason} (reason_code={repair_reason_code})",
            file=sys.stderr,
        )
        stage = ""

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
            expected_scope_key = mismatch_from or scope_key
            selected_scope_key = mismatch_to
            scope_mismatch_non_authoritative = True
            print(
                f"[loop-step] WARN: scope_key_mismatch_warn from={mismatch_from} to={mismatch_to}",
                file=sys.stderr,
            )
        result = str(payload.get("result") or "").strip().lower()
        reason = str(payload.get("reason") or "").strip()
        reason_code = str(payload.get("reason_code") or "").strip().lower()
        stage_requested_result = stage_result_contract.normalize_requested_result(payload.get("requested_result"))
        result = normalize_stage_result(result, reason_code)
        if (
            result == "continue"
            and stage_requested_result == "done"
            and reason_code in WARN_REASON_CODES
        ):
            result = "done"
        diag_parts: List[str] = []
        if diag:
            diag_parts.append(diag)
        if stage_requested_result:
            diag_parts.append(f"requested_result={stage_requested_result}")
        effective_result = stage_result_contract.effective_stage_result(payload)
        if effective_result and effective_result != str(payload.get("result") or "").strip().lower():
            diag_parts.append(f"effective_result={effective_result}")
        stage_result_diag = "; ".join(diag_parts)
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
                stage_result_diag=stage_result_diag,
                stage_requested_result=stage_requested_result,
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
                        stage_result_diag=stage_result_diag,
                        stage_requested_result=stage_requested_result,
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
                    stage_result_diag=stage_result_diag,
                    stage_requested_result=stage_requested_result,
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
                        stage_result_diag=stage_result_diag,
                        stage_requested_result=stage_requested_result,
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
                    stage_result_diag=stage_result_diag,
                    stage_requested_result=stage_requested_result,
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
                    stage_result_diag=stage_result_diag,
                    stage_requested_result=stage_requested_result,
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
                        stage_result_diag=stage_result_diag,
                        stage_requested_result=stage_requested_result,
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
                    stage_result_diag=stage_result_diag,
                    stage_requested_result=stage_requested_result,
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
                                stage_result_diag=stage_result_diag,
                                stage_requested_result=stage_requested_result,
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
                            stage_result_diag=stage_result_diag,
                            stage_requested_result=stage_requested_result,
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
                        stage_result_diag=stage_result_diag,
                        stage_requested_result=stage_requested_result,
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
                    stage_result_diag=stage_result_diag,
                    stage_requested_result=stage_requested_result,
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
    if next_stage in {"implement", "review"}:
        staged_work_item = str(runtime.read_active_work_item(target) or "").strip()
        if not runtime.is_iteration_work_item_key(staged_work_item):
            reason = (
                f"{next_stage} requires iteration work item; "
                f"got '{staged_work_item or 'null'}'."
            )
            return emit_result(
                args.format,
                ticket,
                next_stage,
                "blocked",
                BLOCKED_CODE,
                "",
                reason,
                "work_item_resolution_failed",
                scope_key=runtime.resolve_scope_key(staged_work_item, ticket),
                runner=runner_raw,
                runner_effective=" ".join(runner_tokens),
                runner_notice=runner_notice,
                repair_reason_code=repair_reason_code,
                repair_scope_key=repair_scope_key,
                cli_log_path=cli_log_path,
            )
    if next_stage in {"implement", "review", "qa"}:
        (
            active_stage_before_sync,
            active_stage_after_sync,
            active_stage_sync_applied,
        ) = _sync_active_stage_for_loop_step(target, ticket, next_stage)
        if active_stage_after_sync != next_stage:
            reason = (
                f"active stage sync failed: expected '{next_stage}', "
                f"got '{active_stage_after_sync or 'unset'}'"
            )
            return emit_result(
                args.format,
                ticket,
                next_stage,
                "blocked",
                BLOCKED_CODE,
                "",
                reason,
                "active_stage_sync_failed",
                scope_key=runtime.resolve_scope_key(runtime.read_active_work_item(target), ticket),
                runner=runner_raw,
                runner_effective=" ".join(runner_tokens),
                runner_notice=runner_notice,
                repair_reason_code=repair_reason_code,
                repair_scope_key=repair_scope_key,
                cli_log_path=cli_log_path,
                active_stage_before=active_stage_before_sync,
                active_stage_after=active_stage_after_sync,
                active_stage_sync_applied=active_stage_sync_applied,
            )
        if active_stage_sync_applied:
            sync_notice = (
                f"active stage sync applied before={active_stage_before_sync or 'unset'} "
                f"after={active_stage_after_sync or 'unset'}"
            )
            runner_notice = f"{runner_notice}; {sync_notice}" if runner_notice else sync_notice
    stage_sync_kwargs = {
        "active_stage_before": active_stage_before_sync,
        "active_stage_after": active_stage_after_sync,
        "active_stage_sync_applied": active_stage_sync_applied,
    }
    if not _approval_allowed() and _runner_is_claude(" ".join(runner_tokens)):
        if "--dangerously-skip-permissions" not in runner_tokens:
            reason = (
                "loop runner requires non-interactive permissions; "
                "--dangerously-skip-permissions is missing. "
                "Set AIDD_LOOP_RUNNER with this flag or allow approvals explicitly."
            )
            return emit_result(
                args.format,
                ticket,
                next_stage,
                "blocked",
                BLOCKED_CODE,
                "",
                reason,
                LOOP_RUNNER_PERMISSIONS_REASON_CODE,
                scope_key=runtime.resolve_scope_key(runtime.read_active_work_item(target), ticket),
                runner=runner_raw,
                runner_effective=" ".join(runner_tokens),
                runner_notice=runner_notice,
                repair_reason_code=repair_reason_code,
                repair_scope_key=repair_scope_key,
                cli_log_path=cli_log_path,
                **stage_sync_kwargs,
            )
    stage_chain_enabled = should_run_stage_chain(next_stage, runner_raw, stage_chain_plugin_root)
    stage_chain_logs: List[str] = []
    actions_log_rel = ""
    preflight_payload: Dict[str, str] = {}
    stage_chain_scope_key = runtime.resolve_scope_key(runtime.read_active_work_item(target), ticket)
    stage_chain_work_item_key = runtime.read_active_work_item(target)
    if next_stage == "qa":
        stage_chain_scope_key = runtime.resolve_scope_key("", ticket)
        stage_chain_work_item_key = stage_chain_work_item_key or ""
    if stage_chain_enabled:
        ok_stage_chain, preflight_payload, stage_chain_error = run_stage_chain(
            plugin_root=stage_chain_plugin_root,
            workspace_root=workspace_root,
            stage=next_stage,
            kind="preflight",
            ticket=ticket,
            scope_key=stage_chain_scope_key,
            work_item_key=stage_chain_work_item_key,
        )
        if not ok_stage_chain:
            stage_chain_reason_code = _extract_stage_chain_reason_code(stage_chain_error, "preflight_missing")
            return emit_result(
                args.format,
                ticket,
                next_stage,
                "blocked",
                BLOCKED_CODE,
                "",
                stage_chain_error,
                stage_chain_reason_code,
                scope_key=stage_chain_scope_key,
                cli_log_path=cli_log_path,
                **stage_sync_kwargs,
            )
        if preflight_payload.get("log_path"):
            stage_chain_logs.append(preflight_payload["log_path"])
        actions_log_rel = preflight_payload.get("actions_path", actions_log_rel)

    runner_env: Dict[str, str] = {}
    if stage_chain_enabled:
        runner_env, env_notices = _build_loop_runner_env(
            target=target,
            stage=next_stage,
            preflight_payload=preflight_payload,
        )
        if env_notices:
            notice_text = "; ".join(env_notices)
            runner_notice = f"{runner_notice}; {notice_text}" if runner_notice else notice_text
    command_env: Optional[Dict[str, str]] = None
    if runner_env:
        command_env = os.environ.copy()
        command_env.update(runner_env)
    question_retry_attempt = 0
    question_retry_applied = False
    question_answers_compact = ""
    question_questions_path = ""
    question_answers_path = ""

    def _execute_stage_command(
        compact_answers: str,
        *,
        retry_attempt: int = 0,
    ) -> Tuple[int, List[str], Path, str, str, Optional[Path], Optional[Path], float, float]:
        command = list(runner_tokens)
        if stream_mode:
            command.extend(["--output-format", "stream-json", "--include-partial-messages", "--verbose"])
        command.extend(build_command(next_stage, ticket, compact_answers))
        effective = " ".join(command)
        run_stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%d-%H%M%S")
        retry_suffix = f".retry{retry_attempt}" if retry_attempt else ""
        current_log_path = target / "reports" / "loops" / ticket / f"cli.{next_stage}.{run_stamp}{retry_suffix}.log"

        current_stream_log_rel = ""
        current_stream_jsonl_rel = ""
        current_stream_log_path: Optional[Path] = None
        current_stream_jsonl_path: Optional[Path] = None
        started_at = dt.datetime.now(dt.timezone.utc).timestamp()
        if stream_mode:
            if retry_attempt:
                stream_stamp = f"{stamp}.retry{retry_attempt}"
            else:
                stream_stamp = stamp
            current_stream_log_path = target / "reports" / "loops" / ticket / f"cli.loop-step.{stream_stamp}.stream.log"
            current_stream_jsonl_path = target / "reports" / "loops" / ticket / f"cli.loop-step.{stream_stamp}.stream.jsonl"
            current_stream_log_rel = runtime.rel_path(current_stream_log_path, target)
            current_stream_jsonl_rel = runtime.rel_path(current_stream_jsonl_path, target)
            active_work_item = runtime.read_active_work_item(target)
            stream_scope_key = runtime.resolve_scope_key(active_work_item, ticket) if active_work_item else "n/a"
            header_lines = [
                f"==> loop-step: stage={next_stage} ticket={ticket} scope_key={stream_scope_key}",
                f"==> streaming enabled: writing stream={current_stream_jsonl_rel} log={current_stream_log_rel}",
            ]
            if retry_attempt:
                header_lines.append(f"==> question-retry attempt={retry_attempt}")
            returncode = run_stream_command(
                command=command,
                cwd=workspace_root,
                log_path=current_log_path,
                stream_mode=stream_mode,
                stream_jsonl_path=current_stream_jsonl_path,
                stream_log_path=current_stream_log_path,
                output_stream=sys.stderr,
                header_lines=header_lines,
                env=command_env,
            )
        else:
            returncode = run_command(command, workspace_root, current_log_path, env=command_env)
        finished_at = dt.datetime.now(dt.timezone.utc).timestamp()
        return (
            returncode,
            command,
            current_log_path,
            effective,
            current_stream_log_rel,
            current_stream_jsonl_rel,
            current_stream_log_path,
            current_stream_jsonl_path,
            started_at,
            finished_at,
        )

    (
        returncode,
        command,
        log_path,
        runner_effective,
        stream_log_rel,
        stream_jsonl_rel,
        stream_log_path,
        stream_jsonl_path,
        run_started_at,
        run_finished_at,
    ) = _execute_stage_command("", retry_attempt=0)
    permissions_mismatch, permissions_reason = _detect_runner_permission_mismatch(
        runner_effective=runner_effective,
        runner_notice=runner_notice,
        stream_jsonl_path=stream_jsonl_path,
        stream_log_path=stream_log_path,
        raw_log_path=log_path,
    )
    if permissions_mismatch:
        return emit_result(
            args.format,
            ticket,
            next_stage,
            "blocked",
            BLOCKED_CODE,
            log_path,
            permissions_reason,
            LOOP_RUNNER_PERMISSIONS_REASON_CODE,
            scope_key=runtime.resolve_scope_key(runtime.read_active_work_item(target), ticket),
            stage_result_path="",
            runner=runner_raw,
            runner_effective=runner_effective,
            runner_notice=runner_notice,
            repair_reason_code=repair_reason_code,
            repair_scope_key=repair_scope_key,
            stream_log_path=stream_log_rel,
            stream_jsonl_path=stream_jsonl_rel,
            cli_log_path=cli_log_path,
            question_retry_attempt=question_retry_attempt,
            question_retry_applied=question_retry_applied,
            question_answers=question_answers_compact,
            question_questions_path=question_questions_path,
            question_answers_path=question_answers_path,
            **stage_sync_kwargs,
        )
    drift_hit, drift_reason_code, drift_reason, drift_telemetry_events = _detect_runtime_path_tripwire(
        raw_log_path=log_path,
        stream_jsonl_path=stream_jsonl_path,
        stream_log_path=stream_log_path,
    )
    if drift_hit:
        return emit_result(
            args.format,
            ticket,
            next_stage,
            "blocked",
            BLOCKED_CODE,
            log_path,
            drift_reason,
            drift_reason_code,
            scope_key=runtime.resolve_scope_key(runtime.read_active_work_item(target), ticket),
            stage_result_path="",
            runner=runner_raw,
            runner_effective=runner_effective,
            runner_notice=runner_notice,
            repair_reason_code=repair_reason_code,
            repair_scope_key=repair_scope_key,
            stream_log_path=stream_log_rel,
            stream_jsonl_path=stream_jsonl_rel,
            cli_log_path=cli_log_path,
            question_retry_attempt=question_retry_attempt,
            question_retry_applied=question_retry_applied,
            question_answers=question_answers_compact,
            question_questions_path=question_questions_path,
            question_answers_path=question_answers_path,
            drift_tripwire_hit=True,
            drift_telemetry_events=drift_telemetry_events,
            **stage_sync_kwargs,
        )
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
            question_retry_attempt=question_retry_attempt,
            question_retry_applied=question_retry_applied,
            question_answers=question_answers_compact,
            question_questions_path=question_questions_path,
            question_answers_path=question_answers_path,
            drift_telemetry_events=drift_telemetry_events,
            **stage_sync_kwargs,
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
            **stage_sync_kwargs,
        )

    if stage_chain_enabled:
        ok_stage_chain, run_payload, stage_chain_error = run_stage_chain(
            plugin_root=stage_chain_plugin_root,
            workspace_root=workspace_root,
            stage=next_stage,
            kind="run",
            ticket=ticket,
            scope_key=stage_chain_scope_key,
            work_item_key=stage_chain_work_item_key,
            actions_path=actions_log_rel,
        )
        if not ok_stage_chain:
            return emit_result(
                args.format,
                ticket,
                next_stage,
                "blocked",
                BLOCKED_CODE,
                log_path,
                stage_chain_error,
                "actions_missing",
                scope_key=stage_chain_scope_key,
                runner=runner_raw,
                runner_effective=runner_effective,
                runner_notice=runner_notice,
                repair_reason_code=repair_reason_code,
                repair_scope_key=repair_scope_key,
                stream_log_path=stream_log_rel,
                stream_jsonl_path=stream_jsonl_rel,
                cli_log_path=cli_log_path,
                question_retry_attempt=question_retry_attempt,
                question_retry_applied=question_retry_applied,
                question_answers=question_answers_compact,
                question_questions_path=question_questions_path,
                question_answers_path=question_answers_path,
                **stage_sync_kwargs,
            )
        if run_payload.get("log_path"):
            stage_chain_logs.append(run_payload["log_path"])
        actions_log_rel = run_payload.get("actions_path", actions_log_rel)

    payload, result_path, error, mismatch_from, mismatch_to, diag = load_stage_result(
        target,
        ticket,
        next_scope_key,
        next_stage,
        started_at=run_started_at,
        finished_at=run_finished_at,
    )
    if not error and payload and not mismatch_to:
        initial_result = normalize_stage_result(
            str(payload.get("result") or "").strip().lower(),
            str(payload.get("reason_code") or "").strip().lower(),
        )
        initial_reason = str(payload.get("reason") or "").strip()
        initial_reason_code = str(payload.get("reason_code") or "").strip().lower()
        question_material = _question_retry_material(
            payload=payload,
            reason=initial_reason,
            reason_code=initial_reason_code,
            diagnostics=diag,
            log_path=log_path,
        )
        if initial_result == "blocked" and _is_question_retry_candidate(
            reason=initial_reason,
            reason_code=initial_reason_code,
            material=question_material,
        ):
            from aidd_runtime import tasklist_parser as _tasklist_parser

            question_retry_attempt = 1
            question_answers_compact = _tasklist_parser.build_compact_answers(question_material)
            if not question_answers_compact:
                blocker_reason = (
                    "stage requested compact AIDD:ANSWERS but question extraction failed; "
                    "manual clarification is required"
                )
                return emit_result(
                    args.format,
                    ticket,
                    next_stage,
                    "blocked",
                    BLOCKED_CODE,
                    log_path,
                    blocker_reason,
                    _QUESTION_RETRY_REASON_CODE,
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
                    cli_log_path=cli_log_path,
                    question_retry_attempt=question_retry_attempt,
                    question_retry_applied=False,
                    question_answers=question_answers_compact,
                    **stage_sync_kwargs,
                )
            question_retry_applied = True
            question_questions_path, question_answers_path = _write_question_retry_artifacts(
                target,
                ticket=ticket,
                scope_key=next_scope_key,
                stage=next_stage,
                questions_text=question_material,
                answers_text=question_answers_compact,
            )
            retry_notice = "auto question-retry applied with compact AIDD:ANSWERS"
            runner_notice = f"{runner_notice}; {retry_notice}" if runner_notice else retry_notice
            (
                returncode,
                command,
                log_path,
                runner_effective,
                stream_log_rel,
                stream_jsonl_rel,
                stream_log_path,
                stream_jsonl_path,
                run_started_at,
                run_finished_at,
            ) = _execute_stage_command(question_answers_compact, retry_attempt=question_retry_attempt)
            permissions_mismatch, permissions_reason = _detect_runner_permission_mismatch(
                runner_effective=runner_effective,
                runner_notice=runner_notice,
                stream_jsonl_path=stream_jsonl_path,
                stream_log_path=stream_log_path,
                raw_log_path=log_path,
            )
            if permissions_mismatch:
                return emit_result(
                    args.format,
                    ticket,
                    next_stage,
                    "blocked",
                    BLOCKED_CODE,
                    log_path,
                    permissions_reason,
                    LOOP_RUNNER_PERMISSIONS_REASON_CODE,
                    scope_key=runtime.resolve_scope_key(runtime.read_active_work_item(target), ticket),
                    stage_result_path="",
                    runner=runner_raw,
                    runner_effective=runner_effective,
                    runner_notice=runner_notice,
                    repair_reason_code=repair_reason_code,
                    repair_scope_key=repair_scope_key,
                    stream_log_path=stream_log_rel,
                    stream_jsonl_path=stream_jsonl_rel,
                    cli_log_path=cli_log_path,
                    question_retry_attempt=question_retry_attempt,
                    question_retry_applied=question_retry_applied,
                    question_answers=question_answers_compact,
                    question_questions_path=question_questions_path,
                    question_answers_path=question_answers_path,
                    **stage_sync_kwargs,
                )
            if returncode != 0:
                return emit_result(
                    args.format,
                    ticket,
                    next_stage,
                    "error",
                    ERROR_CODE,
                    log_path,
                    f"runner exited with {returncode}",
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
                    question_retry_attempt=question_retry_attempt,
                    question_retry_applied=question_retry_applied,
                    question_answers=question_answers_compact,
                    question_questions_path=question_questions_path,
                    question_answers_path=question_answers_path,
                    **stage_sync_kwargs,
                )
            payload, result_path, error, mismatch_from, mismatch_to, diag = load_stage_result(
                target,
                ticket,
                next_scope_key,
                next_stage,
                started_at=run_started_at,
                finished_at=run_finished_at,
            )
            if not error and payload:
                retry_result = normalize_stage_result(
                    str(payload.get("result") or "").strip().lower(),
                    str(payload.get("reason_code") or "").strip().lower(),
                )
                retry_reason = str(payload.get("reason") or "").strip()
                retry_reason_code = str(payload.get("reason_code") or "").strip().lower()
                retry_material = _question_retry_material(
                    payload=payload,
                    reason=retry_reason,
                    reason_code=retry_reason_code,
                    diagnostics=diag,
                    log_path=log_path,
                )
                if retry_result == "blocked" and _is_question_retry_candidate(
                    reason=retry_reason,
                    reason_code=retry_reason_code,
                    material=retry_material,
                ):
                    blocker_reason = (
                        "stage remained blocked after one automatic compact-answer retry; "
                        "manual clarification is required"
                    )
                    return emit_result(
                        args.format,
                        ticket,
                        next_stage,
                        "blocked",
                        BLOCKED_CODE,
                        log_path,
                        blocker_reason,
                        _QUESTION_RETRY_REASON_CODE,
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
                        cli_log_path=cli_log_path,
                        question_retry_attempt=question_retry_attempt,
                        question_retry_applied=question_retry_applied,
                        question_answers=question_answers_compact,
                        question_questions_path=question_questions_path,
                        question_answers_path=question_answers_path,
                        **stage_sync_kwargs,
                    )
    preliminary_result = str(payload.get("result") or "").strip().lower() if payload else "continue"
    preliminary_verdict = str(payload.get("verdict") or "").strip().upper() if payload else ""
    question_retry_kwargs = {
        "question_retry_attempt": question_retry_attempt,
        "question_retry_applied": question_retry_applied,
        "question_answers": question_answers_compact,
        "question_questions_path": question_questions_path,
        "question_answers_path": question_answers_path,
    }
    if mismatch_to:
        if not scope_key_mismatch_warn:
            scope_key_mismatch_warn = "1"
            scope_key_mismatch_from = mismatch_from
            scope_key_mismatch_to = mismatch_to
            expected_scope_key = mismatch_from or next_scope_key
            selected_scope_key = mismatch_to
            scope_mismatch_non_authoritative = True
            print(
                f"[loop-step] WARN: scope_key_mismatch_warn from={mismatch_from} to={mismatch_to}",
                file=sys.stderr,
            )

    if stage_chain_enabled:
        ok_stage_chain, post_payload, stage_chain_error = run_stage_chain(
            plugin_root=stage_chain_plugin_root,
            workspace_root=workspace_root,
            stage=next_stage,
            kind="postflight",
            ticket=ticket,
            scope_key=next_scope_key or stage_chain_scope_key,
            work_item_key=stage_chain_work_item_key,
            actions_path=actions_log_rel,
            result=preliminary_result or "continue",
            verdict=preliminary_verdict,
        )
        if not ok_stage_chain:
            stage_chain_reason_code = _extract_stage_chain_reason_code(stage_chain_error, "postflight_missing")
            return emit_result(
                args.format,
                ticket,
                next_stage,
                "blocked",
                BLOCKED_CODE,
                log_path,
                stage_chain_error,
                stage_chain_reason_code,
                scope_key=stage_chain_scope_key,
                runner=runner_raw,
                runner_effective=runner_effective,
                runner_notice=runner_notice,
                repair_reason_code=repair_reason_code,
                repair_scope_key=repair_scope_key,
                stream_log_path=stream_log_rel,
                stream_jsonl_path=stream_jsonl_rel,
                cli_log_path=cli_log_path,
                **stage_sync_kwargs,
            )
        if post_payload.get("log_path"):
            stage_chain_logs.append(post_payload["log_path"])
        if post_payload.get("apply_log"):
            stage_chain_logs.append(post_payload["apply_log"])
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
            expected_scope_key = mismatch_from or next_scope_key
            selected_scope_key = mismatch_to
            scope_mismatch_non_authoritative = True
            print(
                f"[loop-step] WARN: scope_key_mismatch_warn from={mismatch_from} to={mismatch_to}",
                file=sys.stderr,
            )
    if error:
        error_reason = f"{error}; {diag}" if diag else error
        error_reason_code = error
        if stage_chain_enabled and error == "stage_result_missing_or_invalid":
            error_reason_code = "stage_chain_output_missing"
            error_reason = (
                "stage-chain run completed without canonical stage-result emission; "
                f"{error_reason}"
            )
        return emit_result(
            args.format,
            ticket,
            next_stage,
            "blocked",
            BLOCKED_CODE,
            log_path,
            error_reason,
            error_reason_code,
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
            **question_retry_kwargs,
            **stage_sync_kwargs,
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
    artifact_scope_key = stage_chain_scope_key or next_scope_key
    if stage_chain_enabled and next_stage in {"implement", "review", "qa"}:
        ok_contract, contract_message, contract_reason_code = _validate_stage_chain_contract(
            target=target,
            ticket=ticket,
            scope_key=artifact_scope_key,
            stage=next_stage,
            actions_log_rel=actions_log_rel,
            stage_chain_logs=stage_chain_logs,
            stage_result_path=runtime.rel_path(result_path, target) if scope_key_mismatch_warn else "",
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
                scope_mismatch_non_authoritative=scope_mismatch_non_authoritative,
                expected_scope_key=expected_scope_key,
                selected_scope_key=selected_scope_key,
                actions_log_path=actions_log_rel,
                tests_log_path=tests_log_path,
                stage_chain_logs=stage_chain_logs,
                cli_log_path=cli_log_path,
                **question_retry_kwargs,
                **stage_sync_kwargs,
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
                scope_mismatch_non_authoritative=scope_mismatch_non_authoritative,
                expected_scope_key=expected_scope_key,
                selected_scope_key=selected_scope_key,
                actions_log_path=actions_log_rel,
                tests_log_path=tests_log_path,
                stage_chain_logs=stage_chain_logs,
                cli_log_path=cli_log_path,
                **question_retry_kwargs,
                **stage_sync_kwargs,
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
    contract_policy, contract_reason_code = evaluate_output_contract_policy(
        output_contract_status,
        blocked_policy=blocked_policy,
        target=target,
    )
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
                scope_mismatch_non_authoritative=scope_mismatch_non_authoritative,
                expected_scope_key=expected_scope_key,
                selected_scope_key=selected_scope_key,
                actions_log_path=actions_log_rel,
                tests_log_path=tests_log_path,
                stage_chain_logs=stage_chain_logs,
                cli_log_path=cli_log_path,
                output_contract_path=output_contract_path,
                output_contract_status=output_contract_status,
                **question_retry_kwargs,
                **stage_sync_kwargs,
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
        scope_mismatch_non_authoritative=scope_mismatch_non_authoritative,
        expected_scope_key=expected_scope_key,
        selected_scope_key=selected_scope_key,
        actions_log_path=actions_log_rel,
        tests_log_path=tests_log_path,
        stage_chain_logs=stage_chain_logs,
        cli_log_path=cli_log_path,
        output_contract_path=output_contract_path,
        output_contract_status=output_contract_status,
        stage_result_diag=stage_result_diag,
        stage_requested_result=stage_requested_result,
        drift_telemetry_events=drift_telemetry_events,
        **question_retry_kwargs,
        **stage_sync_kwargs,
    )
if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
