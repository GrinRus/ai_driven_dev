#!/usr/bin/env python3
"""Helper functions for loop_step_parts.core."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import shlex
import sys
from pathlib import Path
from typing import Dict, List, Optional, TextIO, Tuple

from aidd_runtime import marker_semantics
from aidd_runtime import runtime
from aidd_runtime.feature_ids import write_active_state
from aidd_runtime.io_utils import dump_yaml, utc_timestamp

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
RUNTIME_PATH_DRIFT_REASON_CODE = "runtime_path_missing_or_drift"
PROMPT_FLOW_DRIFT_REASON_FAMILY = "prompt_flow_drift_non_canonical_runtime_path"
_CANT_OPEN_RUNTIME_RE = re.compile(
    r"can't open file [\"']?[^\"'\n]*?/skills/[^\"'\n]*/runtime/[^\"'\n]*",
    re.IGNORECASE,
)
_NON_CANONICAL_REL_RUNTIME_CMD_RE = re.compile(
    r"python3\s+(?:\./)?skills/[^\s]*/runtime/[^\s`]+",
    re.IGNORECASE,
)
_DEPRECATED_SET_STAGE_CMD_RE = re.compile(
    r"python3\s+[^\n]*skills/aidd-flow-state/runtime/(?:set_stage|stage_set)\.py\b",
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
_MALFORMED_STAGE_ALIAS_RE = re.compile(
    r"(?:unknown skill|command not found):\s*:(?!status\b)([a-z0-9_-]+)",
    re.IGNORECASE,
)


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


def _iter_python_command_lines(text: str) -> List[str]:
    commands: List[str] = []
    for raw_line in str(text or "").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("$ "):
            command = line[2:].strip()
            if command:
                commands.append(command)
            continue
        if '"command"' in line and "python3" in line:
            match = _JSON_COMMAND_RE.search(line)
            if match:
                command = str(match.group(1) or "").strip()
                if command:
                    commands.append(command)
    return commands


def _detect_runtime_path_tripwire(
    *,
    raw_log_path: Path,
    stream_jsonl_path: Optional[Path],
    stream_log_path: Optional[Path],
) -> Tuple[bool, str, str, List[str]]:
    text_chunks: List[str] = [
        _file_head_tail_text(raw_log_path),
        _file_head_tail_text(stream_jsonl_path),
        _file_head_tail_text(stream_log_path),
    ]
    combined = "\n".join(chunk for chunk in text_chunks if chunk)
    if not combined:
        return False, "", "", []

    missing_match = _CANT_OPEN_RUNTIME_RE.search(combined)
    if missing_match:
        evidence = missing_match.group(0).strip()
        reason = f"runtime path drift detected: {evidence}"
        return True, RUNTIME_PATH_DRIFT_REASON_CODE, reason, []

    malformed_alias_match = _MALFORMED_STAGE_ALIAS_RE.search(combined)
    if malformed_alias_match:
        evidence = malformed_alias_match.group(0).strip()
        reason = f"prompt alias drift detected: {evidence}"
        return True, RUNTIME_PATH_DRIFT_REASON_CODE, reason, []

    telemetry_events: List[str] = []
    for command_line in _iter_python_command_lines(combined):
        normalized = command_line.strip()
        if _MANUAL_PREFLIGHT_PREPARE_CMD_RE.search(normalized):
            telemetry_events.append(f"manual_preflight_runtime_call={normalized}")
            reason = f"non-canonical stage orchestration drift detected: {normalized}"
            return True, RUNTIME_PATH_DRIFT_REASON_CODE, reason, telemetry_events
        if _NON_CANONICAL_STAGE_PREFLIGHT_CMD_RE.search(normalized):
            telemetry_events.append(f"non_canonical_stage_preflight_runtime_call={normalized}")
            reason = f"non-canonical stage preflight runtime detected: {normalized}"
            return True, RUNTIME_PATH_DRIFT_REASON_CODE, reason, telemetry_events
        if _DEPRECATED_SET_STAGE_CMD_RE.search(normalized):
            telemetry_events.append(f"deprecated_set_stage_runtime_call={normalized}")
            reason = f"deprecated stage alias runtime detected: {normalized}"
            return True, RUNTIME_PATH_DRIFT_REASON_CODE, reason, telemetry_events
        if _NON_CANONICAL_REL_RUNTIME_CMD_RE.search(normalized):
            telemetry_events.append(f"non_canonical_relative_runtime_call={normalized}")
            reason = f"non-canonical runtime path detected: {normalized}"
            return True, RUNTIME_PATH_DRIFT_REASON_CODE, reason, telemetry_events
    return False, "", "", telemetry_events


def _extract_marker_source(line: str) -> str:
    return marker_semantics.extract_marker_source(line, inline_path_re=_MARKER_INLINE_PATH_RE)


def _is_marker_noise_source(source: str, line: str) -> bool:
    return marker_semantics.is_marker_noise_source(
        source,
        line,
        noise_section_hints=_MARKER_NOISE_SECTION_HINTS,
        noise_placeholders=_MARKER_NOISE_PLACEHOLDERS,
    )


def _scan_marker_semantics(entries: List[Tuple[str, str]]) -> Tuple[List[str], List[str]]:
    return marker_semantics.scan_marker_semantics(
        entries,
        semantic_tokens=_MARKER_SEMANTIC_TOKENS,
        inline_path_re=_MARKER_INLINE_PATH_RE,
        noise_section_hints=_MARKER_NOISE_SECTION_HINTS,
        noise_placeholders=_MARKER_NOISE_PLACEHOLDERS,
    )


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
    from aidd_runtime import loop_step_stage_chain as _stage_chain

    return _stage_chain.runner_supports_flag(command, flag)


def _strip_flag_with_value(tokens: List[str], flag: str) -> Tuple[List[str], bool]:
    from aidd_runtime import loop_step_stage_chain as _stage_chain

    return _stage_chain._strip_flag_with_value(tokens, flag)


def inject_plugin_flags(tokens: List[str], plugin_root: Path) -> Tuple[List[str], List[str]]:
    from aidd_runtime import loop_step_stage_chain as _stage_chain

    return _stage_chain.inject_plugin_flags(tokens, plugin_root)


def validate_command_available(plugin_root: Path, stage: str) -> Tuple[bool, str, str]:
    from aidd_runtime import loop_step_stage_chain as _stage_chain

    return _stage_chain.validate_command_available(plugin_root, stage)


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
    from aidd_runtime import loop_step_stage_chain as _stage_chain

    return _stage_chain.resolve_runner(args_runner, plugin_root)


def is_skill_first(plugin_root: Path) -> bool:
    from aidd_runtime import loop_step_policy as _policy

    return _policy.is_skill_first(plugin_root)


def resolve_stage_chain_plugin_root(plugin_root: Path) -> Path:
    from aidd_runtime import loop_step_policy as _policy

    return _policy.resolve_stage_chain_plugin_root(plugin_root)


def should_run_stage_chain(stage: str, runner_raw: str, plugin_root: Path) -> bool:
    from aidd_runtime import loop_step_policy as _policy

    return _policy.should_run_stage_chain(stage, runner_raw, plugin_root)


def resolve_hooks_mode() -> str:
    from aidd_runtime import loop_step_policy as _policy

    return _policy.resolve_hooks_mode()


def resolve_blocked_policy(raw: str | None, target: Path) -> str:
    from aidd_runtime import loop_step_policy as _policy

    return _policy.resolve_blocked_policy(raw, target)


def evaluate_output_contract_policy(
    status: str,
    *,
    blocked_policy: str | None = None,
    target: Path | None = None,
) -> Tuple[str, str]:
    from aidd_runtime import loop_step_policy as _policy

    return _policy.evaluate_output_contract_policy(
        status,
        blocked_policy=blocked_policy,
        root=target,
    )


def _parse_stage_chain_output(stdout: str) -> Dict[str, str]:
    from aidd_runtime import loop_step_stage_chain as _stage_chain

    return _stage_chain._parse_stage_chain_output(stdout)


def _runtime_env(plugin_root: Path) -> Dict[str, str]:
    from aidd_runtime import loop_step_stage_chain as _stage_chain

    return _stage_chain._runtime_env(plugin_root)


def _stage_chain_log_path(target: Path, stage: str, ticket: str, scope_key: str, kind: str) -> Path:
    from aidd_runtime import loop_step_stage_chain as _stage_chain

    return _stage_chain._stage_chain_log_path(target, stage, ticket, scope_key, kind)


def _append_stage_chain_log(log_path: Path, command: List[str], stdout: str, stderr: str) -> None:
    from aidd_runtime import loop_step_stage_chain as _stage_chain

    _stage_chain._append_stage_chain_log(log_path, command, stdout, stderr)


def _run_runtime_command(
    *,
    command: List[str],
    cwd: Path,
    env: Dict[str, str],
    log_path: Path,
) -> Tuple[int, str, str]:
    from aidd_runtime import loop_step_stage_chain as _stage_chain

    return _stage_chain._run_runtime_command(
        command=command,
        cwd=cwd,
        env=env,
        log_path=log_path,
    )


def _resolve_stage_paths(target: Path, ticket: str, scope_key: str, stage: str) -> Dict[str, Path]:
    from aidd_runtime import loop_step_stage_chain as _stage_chain

    return _stage_chain._resolve_stage_paths(target, ticket, scope_key, stage)


def run_stage_chain(
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
    from aidd_runtime import loop_step_stage_chain as _stage_chain

    return _stage_chain.run_stage_chain(
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


def _validate_stage_chain_contract(
    *,
    target: Path,
    ticket: str,
    scope_key: str,
    stage: str,
    actions_log_rel: str,
    stage_chain_logs: List[str] | None = None,
    stage_result_path: str = "",
) -> Tuple[bool, str, str]:
    from aidd_runtime import loop_step_stage_chain as _stage_chain

    return _stage_chain.validate_stage_chain_contract(
        target=target,
        ticket=ticket,
        scope_key=scope_key,
        stage=stage,
        actions_log_rel=actions_log_rel,
        stage_chain_logs=stage_chain_logs,
        stage_result_path=stage_result_path,
    )


def build_command(stage: str, ticket: str, answers: str = "") -> List[str]:
    from aidd_runtime import loop_step_stage_chain as _stage_chain

    return _stage_chain.build_command(stage, ticket, answers)


def run_command(
    command: List[str],
    cwd: Path,
    log_path: Path,
    env: Optional[Dict[str, str]] = None,
) -> int:
    from aidd_runtime import loop_step_stage_chain as _stage_chain

    return _stage_chain.run_command(command, cwd, log_path, env=env)


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
    from aidd_runtime import loop_step_stage_chain as _stage_chain

    return _stage_chain.run_stream_command(
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


def _extract_stage_chain_reason_code(message: str, default: str) -> str:
    text = str(message or "")
    match = STAGE_CHAIN_REASON_CODE_RE.search(text)
    if not match:
        lowered = text.lower()
        if "[actions-apply] error:" in lowered:
            return "actions_apply_failed"
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
    parser.add_argument(
        "--blocked-policy",
        choices=("strict", "ralph"),
        help="Blocked outcome policy (strict|ralph).",
    )
    return parser.parse_args(argv)


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
    scope_mismatch_non_authoritative: bool = False,
    expected_scope_key: str = "",
    selected_scope_key: str = "",
    stage_result_diag: str = "",
    stage_requested_result: str = "",
    actions_log_path: str = "",
    tests_log_path: str = "",
    stage_chain_logs: List[str] | None = None,
    active_stage_before: str = "",
    active_stage_after: str = "",
    active_stage_sync_applied: bool = False,
    question_retry_attempt: int = 0,
    question_retry_applied: bool = False,
    question_answers: str = "",
    question_questions_path: str = "",
    question_answers_path: str = "",
    runner_source: str = "",
    blocked_policy: str = "",
    drift_tripwire_hit: bool = False,
    drift_telemetry_events: List[str] | None = None,
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
    runner_source_value = str(runner_source or "").strip()
    if not runner_source_value:
        runner_source_value = (
            str(os.environ.get("AIDD_LOOP_RUNNER_SOURCE_HINT") or "").strip()
            or "unknown"
        )
    blocked_policy_value = str(
        blocked_policy
        or os.environ.get("AIDD_LOOP_BLOCKED_POLICY")
        or "strict"
    ).strip().lower()
    if blocked_policy_value not in {"strict", "ralph"}:
        blocked_policy_value = "strict"

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
    reason_family_value = ""
    if reason_code_value == RUNTIME_PATH_DRIFT_REASON_CODE:
        reason_family_value = PROMPT_FLOW_DRIFT_REASON_FAMILY
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
        "terminal_marker": 1,
        "exit_code": code,
        "scope_key": scope_value,
        "work_item_key": work_item_value or None,
        "log_path": log_value,
        "stage_result_path": stage_result_value,
        "runner": runner_value,
        "runner_effective": runner_effective_value,
        "runner_source": runner_source_value,
        "blocked_policy": blocked_policy_value,
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
        "scope_mismatch_non_authoritative": bool(scope_mismatch_non_authoritative),
        "expected_scope_key": str(expected_scope_key or "").strip() or None,
        "selected_scope_key": str(selected_scope_key or "").strip() or None,
        "stage_result_diagnostics": stage_result_diag,
        "stage_requested_result": stage_requested_result or None,
        "actions_log_path": actions_log_path,
        "tests_log_path": tests_log_path,
        "stage_chain_logs": stage_chain_logs or [],
        "active_stage_before": str(active_stage_before or "").strip() or None,
        "active_stage_after": str(active_stage_after or "").strip() or None,
        "active_stage_sync_applied": bool(active_stage_sync_applied),
        "question_retry_attempt": int(question_retry_attempt),
        "question_retry_applied": bool(question_retry_applied),
        "question_answers": str(question_answers or "").strip() or None,
        "question_questions_path": str(question_questions_path or "").strip() or None,
        "question_answers_path": str(question_answers_path or "").strip() or None,
        "drift_tripwire_hit": bool(drift_tripwire_hit),
        "drift_telemetry_events": [str(item) for item in (drift_telemetry_events or []) if str(item).strip()],
        "marker_signal_events": marker_signal_events,
        "report_noise_events": report_noise_events,
        "report_noise": "marker_semantics_noise_only" if report_noise_events and not marker_signal_events else "",
        "updated_at": utc_timestamp(),
        "reason": reason_value,
        "reason_code": reason_code_value,
        "reason_family": reason_family_value or None,
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
