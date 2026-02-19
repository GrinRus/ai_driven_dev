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
from aidd_runtime import stage_result_contract
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
    "fast_mode_warn",
    "output_contract_warn",
    "blocking_findings",
}
HARD_BLOCK_REASON_CODES = {
    "user_approval_required",
}
WRAPPER_SKIP_BLOCK_REASON_CODE = "wrappers_skipped_unsafe"
WRAPPER_SKIP_WARN_REASON_CODE = "wrappers_skipped_warn"
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
WRAPPER_REASON_CODE_RE = re.compile(r"\breason_code=([a-z0-9_:-]+)\b", re.IGNORECASE)
_APPROVAL_ALLOW_VALUES = {"1", "true", "yes", "on"}
_CLAUDE_COMMANDS = {"claude", "claude.exe"}
_APPROVAL_MARKERS = (
    "requires approval",
    "command requires approval",
    "manual approval",
)
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


def _approval_allowed() -> bool:
    raw = str(os.environ.get("AIDD_LOOP_ALLOW_APPROVAL") or "").strip().lower()
    return raw in _APPROVAL_ALLOW_VALUES


def _runner_is_claude(command: str) -> bool:
    text = str(command or "").strip()
    if not text:
        return False
    try:
        tokens = shlex.split(text)
    except ValueError:
        tokens = [text]
    if not tokens:
        return False
    return Path(tokens[0]).name.lower() in _CLAUDE_COMMANDS


def _file_head_tail_text(path: Optional[Path], *, head_lines: int = 80, tail_bytes: int = 131072) -> str:
    if path is None or not path.exists():
        return ""
    head_parts: List[str] = []
    try:
        with path.open("r", encoding="utf-8", errors="replace") as handle:
            for _ in range(head_lines):
                line = handle.readline()
                if not line:
                    break
                head_parts.append(line)
    except OSError:
        return ""
    tail_text = ""
    try:
        with path.open("rb") as handle:
            handle.seek(0, os.SEEK_END)
            size = handle.tell()
            start = max(size - tail_bytes, 0)
            handle.seek(start)
            tail_text = handle.read().decode("utf-8", errors="replace")
    except OSError:
        tail_text = ""
    return "".join(head_parts) + "\n" + tail_text


def _detect_runner_permission_mismatch(
    *,
    runner_effective: str,
    runner_notice: str,
    stream_jsonl_path: Optional[Path],
    stream_log_path: Optional[Path],
    raw_log_path: Path,
) -> Tuple[bool, str]:
    if _approval_allowed():
        return False, ""
    if not _runner_is_claude(runner_effective):
        return False, ""
    try:
        runner_tokens = shlex.split(str(runner_effective or "").strip())
    except ValueError:
        runner_tokens = [str(runner_effective or "").strip()]
    non_interactive_enabled = "--dangerously-skip-permissions" in runner_tokens
    stream_text = _file_head_tail_text(stream_jsonl_path)
    if stream_log_path is not None:
        stream_text += "\n" + _file_head_tail_text(stream_log_path)
    raw_text = _file_head_tail_text(raw_log_path)
    combined = (stream_text + "\n" + raw_text).lower()
    approval_hit = any(marker in combined for marker in _APPROVAL_MARKERS)
    has_default_mode = '"permissionmode":"default"' in combined or '"permissionmode": "default"' in combined
    notice_lower = str(runner_notice or "").strip().lower()
    notice_mismatch = "missing --dangerously-skip-permissions support" in notice_lower
    if notice_mismatch:
        reason = (
            "loop runner cannot enforce non-interactive permissions; "
            "runner missing --dangerously-skip-permissions support"
        )
        return True, reason
    if approval_hit and (has_default_mode or not non_interactive_enabled):
        reason = (
            "loop runner permission mismatch: approval required during loop execution; "
            f"permission_mode={'default' if has_default_mode else 'unknown'} "
            f"non_interactive_flag={'on' if non_interactive_enabled else 'off'}"
        )
        return True, reason
    return False, ""


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
    stripped = str(line or "").strip()
    line_lower = stripped.lower()
    if any(hint in line_lower for hint in _MARKER_NOISE_SECTION_HINTS):
        return True
    if any(token in line_lower for token in _MARKER_NOISE_PLACEHOLDERS):
        return True
    if stripped.startswith(">"):
        return True
    if (stripped.startswith("- `") or stripped.startswith("* `")) and (
        "id=review:" in line_lower or "id_review_" in line_lower
    ):
        return True
    if "`" in stripped and ("id=review:" in line_lower or "id_review_" in line_lower):
        return True
    if ("канонический формат" in line_lower or "canonical format" in line_lower) and (
        "id=review:" in line_lower or "id_review_" in line_lower
    ):
        return True
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


def _log_excerpt(path: Path, *, max_bytes: int = 65536) -> str:
    if not path.exists():
        return ""
    try:
        content = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""
    if len(content) <= max_bytes:
        return content
    return content[-max_bytes:]


def _question_retry_material(
    *,
    payload: Dict[str, object] | None,
    reason: str,
    reason_code: str,
    diagnostics: str,
    log_path: Path,
) -> str:
    chunks: List[str] = []
    if reason:
        chunks.append(reason)
    if diagnostics:
        chunks.append(diagnostics)
    if reason_code:
        chunks.append(f"reason_code={reason_code}")
    if payload:
        for key in ("questions", "question", "details", "hint", "next_action", "nextAction"):
            value = payload.get(key)
            if not value:
                continue
            if isinstance(value, list):
                chunks.extend(str(item) for item in value if str(item).strip())
            else:
                chunks.append(str(value))
    log_excerpt = _log_excerpt(log_path)
    if log_excerpt:
        chunks.append(log_excerpt)
    return "\n".join(part for part in chunks if str(part).strip())


def _is_question_retry_candidate(*, reason: str, reason_code: str, material: str) -> bool:
    code = str(reason_code or "").strip().lower()
    if code in _QUESTION_REASON_CODES:
        return True
    merged = "\n".join(part for part in (reason, material) if str(part).strip())
    lower = merged.lower()
    if not lower:
        return False
    if not _QUESTION_PROMPT_RE.search(lower):
        return False
    if _QUESTION_REFERENCE_RE.search(merged):
        return True
    return "aidd:answers" in lower


def _write_question_retry_artifacts(
    target: Path,
    *,
    ticket: str,
    scope_key: str,
    stage: str,
    questions_text: str,
    answers_text: str,
) -> Tuple[str, str]:
    base_dir = target / "reports" / "loops" / ticket / scope_key
    base_dir.mkdir(parents=True, exist_ok=True)
    questions_path = base_dir / f"stage.{stage}.questions.txt"
    answers_path = base_dir / f"stage.{stage}.answers.txt"
    questions_path.write_text((questions_text or "").rstrip() + "\n", encoding="utf-8")
    answers_path.write_text((answers_text or "").rstrip() + "\n", encoding="utf-8")
    return runtime.rel_path(questions_path, target), runtime.rel_path(answers_path, target)


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


def _sync_active_stage_for_loop_step(root: Path, ticket: str, stage: str) -> tuple[str, str, bool]:
    current_stage = read_active_stage(root)
    applied = False
    if stage and current_stage != stage:
        write_active_ticket(root, ticket)
        write_active_stage(root, stage)
        applied = True
    synced_stage = read_active_stage(root)
    return current_stage, synced_stage, applied


def resolve_stage_scope(root: Path, ticket: str, stage: str) -> Tuple[str, str]:
    if stage in {"implement", "review"}:
        work_item_key = runtime.read_active_work_item(root)
        if not work_item_key:
            return "", ""
        if not runtime.is_valid_work_item_key(work_item_key):
            return work_item_key, ""
        return work_item_key, runtime.resolve_scope_key(work_item_key, ticket)
    if stage == "qa":
        work_item_key = runtime.read_active_work_item(root)
        if runtime.is_iteration_work_item_key(work_item_key):
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
    wrapper_logs: List[str] | None = None,
    stage_result_path: str = "",
) -> Tuple[bool, str, str]:
    from aidd_runtime import loop_step_wrappers as _wrappers

    return _wrappers.validate_stage_wrapper_contract(
        target=target,
        ticket=ticket,
        scope_key=scope_key,
        stage=stage,
        actions_log_rel=actions_log_rel,
        wrapper_logs=wrapper_logs,
        stage_result_path=stage_result_path,
    )


def build_command(stage: str, ticket: str, answers: str = "") -> List[str]:
    from aidd_runtime import loop_step_wrappers as _wrappers

    return _wrappers.build_command(stage, ticket, answers)


def run_command(
    command: List[str],
    cwd: Path,
    log_path: Path,
    env: Optional[Dict[str, str]] = None,
) -> int:
    from aidd_runtime import loop_step_wrappers as _wrappers

    return _wrappers.run_command(command, cwd, log_path, env=env)


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
    env: Optional[Dict[str, str]] = None,
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
        env=env,
    )


def append_cli_log(log_path: Path, payload: Dict[str, object]) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False) + "\n")


def _extract_wrapper_reason_code(message: str, default: str) -> str:
    match = WRAPPER_REASON_CODE_RE.search(str(message or ""))
    if not match:
        return default
    value = match.group(1).strip().lower()
    return value or default


def _true_env(value: str | None) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def _load_writemap_scope_paths(target: Path, writemap_path: str) -> List[str]:
    raw = str(writemap_path or "").strip()
    if not raw:
        return []
    resolved = runtime.resolve_path_for_target(Path(raw), target)
    if not resolved.exists():
        return []
    try:
        payload = json.loads(resolved.read_text(encoding="utf-8"))
    except Exception:
        return []
    if not isinstance(payload, dict):
        return []
    values: List[str] = []
    for key in ("loop_allowed_paths", "allowed_paths"):
        raw_items = payload.get(key)
        if not isinstance(raw_items, list):
            continue
        for item in raw_items:
            text = str(item or "").strip()
            if text and text not in values:
                values.append(text)
    return values


def _build_loop_runner_env(
    *,
    target: Path,
    stage: str,
    preflight_payload: Dict[str, str],
) -> tuple[Dict[str, str], List[str]]:
    if stage != "implement":
        return {}, []
    env: Dict[str, str] = {}
    notices: List[str] = []

    writemap_path = str(preflight_payload.get("writemap_path") or "").strip()
    scope_paths = _load_writemap_scope_paths(target, writemap_path)
    if scope_paths:
        scope_csv = ",".join(scope_paths)
        env["TEST_SCOPE"] = scope_csv
        env["AIDD_LOOP_SCOPE_PATHS"] = scope_csv
        notices.append(f"loop scope propagated to TEST_SCOPE ({len(scope_paths)} path(s))")

    allow_format = _true_env(os.environ.get("AIDD_LOOP_ALLOW_FORMAT"))
    if not allow_format:
        if os.environ.get("SKIP_FORMAT", "").strip() != "1":
            env["SKIP_FORMAT"] = "1"
            notices.append("SKIP_FORMAT=1 enforced for loop implement scope safety")
    return env, notices


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
            print(
                f"[loop-step] WARN: scope_key_mismatch_warn from={mismatch_from} to={mismatch_to}",
                file=sys.stderr,
            )
            scope_key = mismatch_to
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
    wrapper_enabled = should_run_wrappers(next_stage, runner_raw, wrapper_plugin_root)
    wrapper_logs: List[str] = []
    actions_log_rel = ""
    preflight_payload: Dict[str, str] = {}
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
            **stage_sync_kwargs,
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
            wrapper_reason_code = _extract_wrapper_reason_code(wrapper_error, "preflight_missing")
            return emit_result(
                args.format,
                ticket,
                next_stage,
                "blocked",
                BLOCKED_CODE,
                "",
                wrapper_error,
                wrapper_reason_code,
                scope_key=wrapper_scope_key,
                cli_log_path=cli_log_path,
                **stage_sync_kwargs,
            )
        if preflight_payload.get("log_path"):
            wrapper_logs.append(preflight_payload["log_path"])
        actions_log_rel = preflight_payload.get("actions_path", actions_log_rel)

    runner_env: Dict[str, str] = {}
    if wrapper_enabled:
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
                question_retry_attempt=question_retry_attempt,
                question_retry_applied=question_retry_applied,
                question_answers=question_answers_compact,
                question_questions_path=question_questions_path,
                question_answers_path=question_answers_path,
                **stage_sync_kwargs,
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
            wrapper_reason_code = _extract_wrapper_reason_code(wrapper_error, "postflight_missing")
            return emit_result(
                args.format,
                ticket,
                next_stage,
                "blocked",
                BLOCKED_CODE,
                log_path,
                wrapper_error,
                wrapper_reason_code,
                scope_key=wrapper_scope_key,
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
        error_reason = f"{error}; {diag}" if diag else error
        error_reason_code = error
        if wrapper_enabled and error == "stage_result_missing_or_invalid":
            error_reason_code = "wrapper_output_missing"
            error_reason = (
                "wrapper run completed without canonical stage-result emission; "
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
    artifact_scope_key = wrapper_scope_key or next_scope_key
    if wrapper_enabled and next_stage in {"implement", "review", "qa"}:
        ok_contract, contract_message, contract_reason_code = _validate_stage_wrapper_contract(
            target=target,
            ticket=ticket,
            scope_key=artifact_scope_key,
            stage=next_stage,
            actions_log_rel=actions_log_rel,
            wrapper_logs=wrapper_logs,
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
                actions_log_path=actions_log_rel,
                tests_log_path=tests_log_path,
                wrapper_logs=wrapper_logs,
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
                actions_log_path=actions_log_rel,
                tests_log_path=tests_log_path,
                wrapper_logs=wrapper_logs,
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
        actions_log_path=actions_log_rel,
        tests_log_path=tests_log_path,
        wrapper_logs=wrapper_logs,
        cli_log_path=cli_log_path,
        output_contract_path=output_contract_path,
        output_contract_status=output_contract_status,
        stage_result_diag=stage_result_diag,
        stage_requested_result=stage_requested_result,
        **question_retry_kwargs,
        **stage_sync_kwargs,
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
    work_item_key: str = "",
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
    stage_requested_result: str = "",
    actions_log_path: str = "",
    tests_log_path: str = "",
    wrapper_logs: List[str] | None = None,
    active_stage_before: str = "",
    active_stage_after: str = "",
    active_stage_sync_applied: bool = False,
    question_retry_attempt: int = 0,
    question_retry_applied: bool = False,
    question_answers: str = "",
    question_questions_path: str = "",
    question_answers_path: str = "",
) -> int:
    status_value = status if status in {"blocked", "continue", "done"} else "blocked"
    work_item_value = str(work_item_key or "").strip()
    scope_value = str(scope_key or "").strip()
    if not scope_value:
        scope_value = runtime.resolve_scope_key(work_item_value, ticket)
    if not work_item_value and stage in {"implement", "review"} and scope_value.startswith("iteration_id_"):
        suffix = scope_value[len("iteration_id_"):].strip()
        if suffix:
            work_item_value = f"iteration_id={suffix}"

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
    marker_signal_events, report_noise_events = _scan_marker_semantics(
        [
            ("reason", reason_value),
            ("stage_result_diagnostics", stage_result_diag),
        ]
    )

    payload = {
        "ticket": ticket,
        "stage": stage,
        "status": status_value,
        "exit_code": code,
        "scope_key": scope_value,
        "work_item_key": work_item_value or None,
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
        "stage_requested_result": stage_requested_result or None,
        "actions_log_path": actions_log_path,
        "tests_log_path": tests_log_path,
        "wrapper_logs": wrapper_logs or [],
        "active_stage_before": str(active_stage_before or "").strip() or None,
        "active_stage_after": str(active_stage_after or "").strip() or None,
        "active_stage_sync_applied": bool(active_stage_sync_applied),
        "question_retry_attempt": int(question_retry_attempt),
        "question_retry_applied": bool(question_retry_applied),
        "question_answers": str(question_answers or "").strip() or None,
        "question_questions_path": str(question_questions_path or "").strip() or None,
        "question_answers_path": str(question_answers_path or "").strip() or None,
        "marker_signal_events": marker_signal_events,
        "report_noise_events": report_noise_events,
        "report_noise": "marker_semantics_noise_only" if report_noise_events and not marker_signal_events else "",
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
