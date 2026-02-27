#!/usr/bin/env python3
"""Run loop-step repeatedly until SHIP or limits reached."""

from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess
import shlex
import time
import sys
import datetime as dt
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from aidd_runtime import runtime
from aidd_runtime import stage_result_contract
from aidd_runtime import marker_semantics
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
DEFAULT_LOOP_STEP_TIMEOUT_SECONDS = 900
DEFAULT_SILENT_STALL_SECONDS = 1200
DEFAULT_STAGE_BUDGET_SECONDS = 3600
DEFAULT_BLOCKED_POLICY = "strict"
DEFAULT_RECOVERABLE_BLOCK_RETRIES = 2
DEFAULT_LOOP_RESEARCH_GATE_MODE = "auto"
BLOCKED_POLICY_VALUES = {"strict", "ralph"}
RESEARCH_GATE_MODE_VALUES = {"off", "on", "auto"}
STAGE_DEFAULT_BUDGET_SECONDS = {
    "implement": 3600,
    "review": 3600,
    "qa": 3600,
}
HARD_BLOCK_REASON_CODES = {
    "loop_runner_permissions",
    "user_approval_required",
    "diff_boundary_violation",
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
    "stage_chain_output_missing",
    "work_item_resolution_failed",
    "active_stage_sync_failed",
    "prompt_flow_blocker",
    "contract_mismatch_stage_result_shape",
    "contract_mismatch_actions_shape",
}
RECOVERABLE_BLOCK_REASON_CODES = {
    "",
    "stage_result_missing_or_invalid",
    "stage_result_blocked",
    "blocked_without_reason",
    "blocking_findings",
    "invalid_loop_step_payload",
    "stage_result_missing",
    "stage_chain_logs_missing",
    "preflight_missing",
    "qa_repair_missing_work_item",
    "qa_repair_no_handoff",
    "qa_repair_multiple_handoffs",
    "qa_repair_tasklist_missing",
    "unsupported_stage_result",
    "scope_drift_recoverable",
}
RECOVERABLE_RESEARCH_GATE_REASON_CODES = {
    "rlm_links_empty_warn",
    "rlm_status_pending",
}
DEFAULT_RESEARCH_GATE_PROBE_TIMEOUT_SECONDS = 180
LOOP_RESULT_SCHEMA = "aidd.loop_result.v1"


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


def _resolve_path_within_target(
    target: Path,
    value: str,
    *,
    label: str,
) -> tuple[Optional[Path], str]:
    raw = str(value or "").strip()
    if not raw:
        return None, ""
    candidate = Path(raw).expanduser()
    resolved = runtime.resolve_path_for_target(candidate, target)
    if not runtime.is_relative_to(resolved, target.resolve()):
        if candidate.is_absolute():
            remapped_raw = candidate.as_posix().lstrip("/")
            target_prefix = f"{target.name}/" if target.name else ""
            if target_prefix and remapped_raw.startswith(target_prefix):
                remapped = runtime.resolve_path_for_target(Path(remapped_raw), target)
                if runtime.is_relative_to(remapped, target.resolve()):
                    return remapped, ""
        return None, f"{label}:outside_target:{resolved.as_posix()}"
    return resolved, ""


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


def _truthy_flag(value: object) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


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


def _resolve_step_timeout_seconds(raw: object) -> int:
    if raw is None or str(raw).strip() == "":
        raw = os.environ.get("AIDD_LOOP_STEP_TIMEOUT_SECONDS", str(DEFAULT_LOOP_STEP_TIMEOUT_SECONDS))
    try:
        value = int(str(raw).strip())
    except (TypeError, ValueError):
        value = DEFAULT_LOOP_STEP_TIMEOUT_SECONDS
    return max(value, 0)


def _resolve_silent_stall_seconds(raw: object) -> int:
    if raw is None or str(raw).strip() == "":
        raw = os.environ.get("AIDD_LOOP_SILENT_STALL_SECONDS", str(DEFAULT_SILENT_STALL_SECONDS))
    try:
        value = int(str(raw).strip())
    except (TypeError, ValueError):
        value = DEFAULT_SILENT_STALL_SECONDS
    return max(value, 0)


def _resolve_stage_budget_seconds(raw: object, stage: str) -> int:
    stage_value = str(stage or "").strip().lower()
    env_key = f"AIDD_LOOP_STAGE_BUDGET_SECONDS_{stage_value.upper()}" if stage_value else ""
    stage_default = STAGE_DEFAULT_BUDGET_SECONDS.get(stage_value, DEFAULT_STAGE_BUDGET_SECONDS)
    candidate = raw
    if candidate is None or str(candidate).strip() == "":
        if env_key:
            candidate = os.environ.get(env_key, "")
    if candidate is None or str(candidate).strip() == "":
        candidate = os.environ.get("AIDD_LOOP_STAGE_BUDGET_SECONDS", str(stage_default))
    try:
        value = int(str(candidate).strip())
    except (TypeError, ValueError):
        value = stage_default
    return max(value, 0)


def _signal_name_from_return_code(return_code: int) -> str:
    if int(return_code) == 143:
        return "SIGTERM"
    if int(return_code) < 0:
        signum = abs(int(return_code))
        try:
            return signal.Signals(signum).name
        except Exception:  # pragma: no cover - defensive mapping
            return f"SIG{signum}"
    return ""


def _build_termination_attribution(
    *,
    exit_code: int,
    classification: str,
    killed_flag: bool = False,
    watchdog_marker: bool = False,
) -> dict[str, object]:
    return {
        "exit_code": int(exit_code),
        "signal": _signal_name_from_return_code(int(exit_code)),
        "killed_flag": 1 if killed_flag else 0,
        "watchdog_marker": 1 if watchdog_marker else 0,
        "classification": str(classification or "").strip() or "unknown_non_zero_exit",
    }


def _normalize_termination_attribution(
    *,
    attribution: dict[str, object] | None,
    exit_code: int,
    reason_code: str,
    watchdog_hint: bool = False,
) -> tuple[dict[str, object], bool]:
    current = dict(attribution or {})
    raw_exit = current.get("exit_code", exit_code)
    try:
        normalized_exit = int(raw_exit)
    except (TypeError, ValueError):
        normalized_exit = int(exit_code)
    killed_flag = _truthy_flag(current.get("killed_flag")) or _truthy_flag(current.get("killed"))
    watchdog_marker = (
        _truthy_flag(current.get("watchdog_marker"))
        or bool(watchdog_hint)
        or str(reason_code or "").strip().lower() in {"seed_stage_budget_exhausted", "watchdog_terminated"}
    )

    if normalized_exit == 143:
        if killed_flag and watchdog_marker:
            classification = "watchdog_terminated"
        else:
            classification = "parent_terminated_or_external_terminate"
            watchdog_marker = False
    else:
        classification = str(current.get("classification") or "").strip() or str(reason_code or "").strip() or "unknown_non_zero_exit"

    normalized = {
        "exit_code": normalized_exit,
        "signal": _signal_name_from_return_code(normalized_exit),
        "killed_flag": 1 if killed_flag else 0,
        "watchdog_marker": 1 if watchdog_marker else 0,
        "classification": classification,
    }
    return normalized, watchdog_marker


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


def _extract_reason_code(text: str) -> str:
    match = _REASON_CODE_RE.search(str(text or ""))
    if not match:
        return ""
    return str(match.group(1) or "").strip().lower()


def _extract_next_action(text: str) -> str:
    match = _NEXT_ACTION_RE.search(str(text or ""))
    if not match:
        return ""
    raw = str(match.group(1) or "").strip()
    return _sanitize_next_action_aliases(raw)


def _sanitize_next_action_aliases(next_action: str) -> str:
    value = str(next_action or "").strip()
    if not value:
        return ""
    for legacy_alias in sorted(_LEGACY_STAGE_ALIAS_TO_CANONICAL, key=len, reverse=True):
        canonical_alias = _LEGACY_STAGE_ALIAS_TO_CANONICAL[legacy_alias]
        value = re.sub(re.escape(legacy_alias), canonical_alias, value, flags=re.IGNORECASE)
    for pattern, replacement in _NON_CANONICAL_LOOP_PACK_PATH_REPLACEMENTS:
        value = pattern.sub(replacement, value)
    return value.strip()


def _extract_scope_drift_hint(reason: str, diagnostics: str) -> str:
    joined = f"{reason}\n{diagnostics}"
    match = _SCOPE_STALE_HINT_RE.search(joined)
    if not match:
        return ""
    return runtime.sanitize_scope_key(match.group(1) or "")


def _promote_stage_result_reason(reason_code: str, reason: str, diagnostics: str) -> tuple[str, str]:
    code = str(reason_code or "").strip().lower()
    if code not in {"stage_result_missing_or_invalid", "stage_result_blocked", "blocked_without_reason", "actions_missing", ""}:
        return code, ""
    joined = f"{reason}\n{diagnostics}".lower()
    if "reason_code=contract_mismatch_actions_shape" in joined:
        return "contract_mismatch_actions_shape", ""
    if code == "actions_missing":
        contract_tokens = (
            "actions-validate",
            "schema_version must be one of",
            "missing field: allowed_action_types",
            "allowed_action_types must be list[str]",
            "unsupported type",
            "params must be object",
        )
        if any(token in joined for token in contract_tokens):
            return "contract_mismatch_actions_shape", ""
    if "invalid-schema" in joined:
        return "contract_mismatch_stage_result_shape", ""
    scope_hint = _extract_scope_drift_hint(reason, diagnostics)
    if scope_hint:
        return "scope_drift_recoverable", scope_hint
    return code, ""


def _resolve_loop_research_gate_mode(raw: str | None) -> str:
    value = str(raw or os.environ.get("AIDD_LOOP_RESEARCH_GATE", DEFAULT_LOOP_RESEARCH_GATE_MODE)).strip().lower()
    if value in {"0", "off", "false", "no", "disabled"}:
        return "off"
    if value in {"1", "on", "true", "yes", "strict"}:
        return "on"
    if value in RESEARCH_GATE_MODE_VALUES:
        return value
    return DEFAULT_LOOP_RESEARCH_GATE_MODE


def _should_enforce_loop_research_gate(target: Path, ticket: str, mode: str) -> bool:
    if mode == "off":
        return False
    if mode == "on":
        return True
    if mode != "auto":
        return False
    research_report = target / "docs" / "research" / f"{ticket}.md"
    if research_report.exists():
        return True
    research_base = target / "reports" / "research"
    candidates = (
        research_base / f"{ticket}-rlm-targets.json",
        research_base / f"{ticket}-rlm-manifest.json",
        research_base / f"{ticket}-rlm.worklist.pack.json",
        research_base / f"{ticket}-rlm.pack.json",
    )
    return any(path.exists() for path in candidates)


def _validate_loop_research_gate(target: Path, ticket: str) -> tuple[bool, str, str, str]:
    from aidd_runtime import research_guard

    try:
        settings = research_guard.load_settings(target)
        research_guard.validate_research(
            target,
            ticket,
            settings=settings,
            expected_stage="review",
        )
    except research_guard.ResearchValidationError as exc:
        message = str(exc)
        reason_code = _extract_reason_code(message) or "research_gate_blocked"
        next_action = _extract_next_action(message)
        return False, reason_code, message, next_action
    return True, "", "", ""


def _resolve_research_probe_timeout_seconds() -> int:
    raw = str(os.environ.get("AIDD_LOOP_RESEARCH_GATE_PROBE_TIMEOUT_SECONDS") or "").strip()
    try:
        value = int(raw) if raw else DEFAULT_RESEARCH_GATE_PROBE_TIMEOUT_SECONDS
    except (TypeError, ValueError):
        value = DEFAULT_RESEARCH_GATE_PROBE_TIMEOUT_SECONDS
    return max(value, 1)


def _expand_next_action_command(next_action: str, plugin_root: Path) -> tuple[list[str], str]:
    raw = _sanitize_next_action_aliases(next_action)
    if not raw:
        return [], ""
    expanded = raw
    plugin_root_text = str(plugin_root)
    expanded = expanded.replace("${CLAUDE_PLUGIN_ROOT}", plugin_root_text)
    expanded = expanded.replace("$CLAUDE_PLUGIN_ROOT", plugin_root_text)
    expanded = expanded.replace("${claude_plugin_root}", plugin_root_text)
    expanded = expanded.replace("$claude_plugin_root", plugin_root_text)
    try:
        tokens = shlex.split(expanded)
    except ValueError:
        return [], expanded
    if not tokens:
        return [], expanded
    first = str(tokens[0] or "").strip().lower()
    if first.startswith("/feature-dev-aidd:") or first.startswith("feature-dev-aidd:"):
        return [], expanded
    if any(token in {";", "&&", "||", "|"} for token in tokens):
        return [], expanded
    return tokens, expanded


def _run_research_gate_probe(
    *,
    target: Path,
    plugin_root: Path,
    next_action: str,
) -> tuple[bool, str, str, int]:
    tokens, expanded = _expand_next_action_command(next_action, plugin_root)
    if not tokens:
        return False, expanded, "invalid_or_unsafe_probe_command", 0
    env = os.environ.copy()
    env["CLAUDE_PLUGIN_ROOT"] = str(plugin_root)
    timeout_seconds = _resolve_research_probe_timeout_seconds()
    try:
        result = subprocess.run(
            tokens,
            cwd=target.parent,
            env=env,
            text=True,
            capture_output=True,
            timeout=timeout_seconds,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return False, expanded, f"probe_timeout_{timeout_seconds}s", timeout_seconds
    if result.returncode != 0:
        tail = (result.stderr or result.stdout or "").strip()
        tail = tail[-400:] if tail else ""
        detail = f"probe_exit={result.returncode}" + (f" tail={tail}" if tail else "")
        return False, expanded, detail, result.returncode
    return True, expanded, "", result.returncode


def _apply_recoverable_block_recovery(
    *,
    target: Path,
    ticket: str,
    stage: str,
    reason_code: str,
    drift_scope_key: str,
    chosen_scope: str,
) -> Tuple[str, str]:
    active_work_item = str(runtime.read_active_work_item(target) or "").strip()
    reason_value = str(reason_code or "").strip().lower()
    if reason_value == "scope_drift_recoverable":
        scope_hint = runtime.sanitize_scope_key(drift_scope_key or chosen_scope)
        hinted_work_item = _scope_to_work_item_key(scope_hint)
        if runtime.is_iteration_work_item_key(hinted_work_item):
            active_work_item = hinted_work_item
            write_active_state(target, ticket=ticket, work_item=active_work_item)
        if runtime.is_iteration_work_item_key(active_work_item):
            write_active_stage(target, "")
            return "scope_drift_reconcile_probe", active_work_item
    if not runtime.is_valid_work_item_key(active_work_item):
        from_scope = _scope_to_work_item_key(chosen_scope)
        if from_scope:
            active_work_item = from_scope
            write_active_state(target, ticket=ticket, work_item=active_work_item)
    if stage in {"review", "qa"} and runtime.is_iteration_work_item_key(active_work_item):
        write_active_stage(target, "implement")
        return "handoff_to_implement", active_work_item
    if stage == "implement" and runtime.is_iteration_work_item_key(active_work_item):
        if reason_value == "stage_result_missing_or_invalid":
            # Clear active stage so the next loop-step re-enters canonical implement orchestration.
            write_active_stage(target, "")
            return "retry_implement", active_work_item
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
    stage_budget_seconds: int = 0,
    stage_budget_remaining_seconds: int = 0,
    budget_exhausted_on_timeout: bool = False,
    silent_stall_seconds: int = 0,
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
        stream_active = bool(
            stream_liveness["step_stream_jsonl_bytes"] > 0 or stream_liveness["step_stream_log_bytes"] > 0
        )
        budget_exhausted = bool(budget_exhausted_on_timeout)
        if stream_active:
            stream_liveness["active_source"] = "stream"
            if budget_exhausted:
                reason_code = "seed_stage_budget_exhausted"
                reason = (
                    f"loop-step reached stage budget after {timeout_seconds}s while stream artifacts remained active"
                )
            else:
                reason_code = "seed_stage_active_stream_timeout"
                reason = (
                    f"loop-step watchdog timeout after {timeout_seconds}s while stream artifacts remain active"
                )
        else:
            stream_liveness["active_source"] = "none"
            if budget_exhausted:
                reason_code = "seed_stage_budget_exhausted"
                reason = f"loop-step reached stage budget after {timeout_seconds}s without completion"
            else:
                reason_code = "seed_stage_silent_stall"
                reason = f"loop-step watchdog timeout after {timeout_seconds}s without completion"
        diagnostics["stream_log_path"] = stream_log_rel or None
        diagnostics["stream_jsonl_path"] = stream_jsonl_rel or None
        diagnostics["stream_liveness"] = stream_liveness
        diagnostics["budget_exhausted"] = budget_exhausted
        diagnostics["stage_budget_seconds"] = stage_budget_seconds or None
        diagnostics["stage_budget_remaining_seconds"] = stage_budget_remaining_seconds or None
        diagnostics["silent_stall_seconds"] = silent_stall_seconds or None
        watchdog_marker = True
        termination_attribution = _build_termination_attribution(
            exit_code=143,
            classification=(
                "watchdog_terminated"
                if watchdog_marker and budget_exhausted
                else "watchdog_no_convergence_yet"
            ),
            killed_flag=True,
            watchdog_marker=watchdog_marker,
        )
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
            "silent_stall_seconds": silent_stall_seconds or timeout_seconds,
            "stage_budget_seconds": stage_budget_seconds or None,
            "stage_budget_remaining_seconds": stage_budget_remaining_seconds or None,
            "budget_exhausted": budget_exhausted,
            "killed_flag": 1,
            "watchdog_marker": 1,
            "termination_attribution": termination_attribution,
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
    recoverable_blocked: bool,
) -> Dict[str, object]:
    if blocked_policy != "ralph":
        return {
            "ralph_recoverable_reason_scope": "n/a",
            "ralph_recoverable_expected": False,
            "ralph_recoverable_exercised": False,
            "ralph_recoverable_not_exercised": False,
            "ralph_recoverable_not_exercised_reason": "",
        }
    normalized_reason = str(reason_code or "").strip()
    expected = normalized_reason == "blocking_findings"
    return {
        "ralph_recoverable_reason_scope": "blocking_findings_only",
        "ralph_recoverable_expected": expected,
        "ralph_recoverable_exercised": bool(expected and recoverable_blocked),
        "ralph_recoverable_not_exercised": not expected,
        "ralph_recoverable_not_exercised_reason": (
            f"reason_code_not_blocking_findings:{normalized_reason or 'blocked_without_reason'}"
            if not expected
            else ""
        ),
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
    blocked_policy = _resolve_blocked_policy(getattr(args, "blocked_policy", None))
    recoverable_retry_budget = _resolve_recoverable_retry_budget(getattr(args, "recoverable_block_retries", None))
    research_gate_mode = _resolve_loop_research_gate_mode(getattr(args, "research_gate", None))
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

    if _should_enforce_loop_research_gate(target, ticket, research_gate_mode):
        research_ok, research_reason_code, research_reason, research_next_action = _validate_loop_research_gate(
            target,
            ticket,
        )
        if not research_ok:
            research_reason_code = str(research_reason_code or "").strip().lower() or "research_gate_blocked"
            recoverable_gate = (
                blocked_policy == "ralph"
                and research_reason_code in RECOVERABLE_RESEARCH_GATE_REASON_CODES
                and recoverable_retry_attempt < recoverable_retry_budget
            )
            if recoverable_gate:
                recoverable_retry_attempt += 1
                last_recovery_path = "research_gate_links_build_probe"
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
            if research_ok:
                pass
            else:
                payload = {
                    "status": "blocked",
                    "iterations": 0,
                    "exit_code": BLOCKED_CODE,
                    "log_path": runtime.rel_path(log_path, target),
                    "cli_log_path": runtime.rel_path(cli_log_path, target),
                    "runner_label": runner_label,
                    "blocked_policy": blocked_policy,
                    "reason": research_reason,
                    "reason_code": research_reason_code,
                    "next_action": research_next_action or None,
                    "recoverable_blocked": bool(recoverable_gate),
                    "retry_attempt": recoverable_retry_attempt,
                    "recoverable_retry_budget": recoverable_retry_budget,
                    "recovery_path": last_recovery_path if recoverable_gate else "",
                    "updated_at": utc_timestamp(),
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
                emit(args.format, payload)
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
            emit(args.format, payload)
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
            emit(args.format, payload)
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
        stream_path_invalid: List[str] = []
        if stream_mode and stream_log_path and step_stream_log:
            step_stream_log_path, invalid_path = _resolve_path_within_target(
                target,
                step_stream_log,
                label="step_stream_log_path",
            )
            if invalid_path:
                stream_path_invalid.append(invalid_path)
            elif step_stream_log_path:
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
        step_stream_jsonl_abs, step_stream_jsonl_invalid = _resolve_path_within_target(
            target,
            step_stream_jsonl,
            label="step_stream_jsonl_path",
        )
        if step_stream_jsonl_invalid:
            stream_path_invalid.append(step_stream_jsonl_invalid)
        if stream_path_invalid:
            stream_path_invalid = sorted(set(stream_path_invalid))
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
            elif step_stream_log or step_stream_jsonl:
                stream_liveness["degraded_reason"] = "stream_artifacts_missing_or_empty"
            else:
                stream_liveness["degraded_reason"] = "stream_paths_missing"
        if stream_mode and stream_liveness["active_source"] == "none" and stream_path_invalid:
            stream_liveness["observability_degraded"] = True
            stream_liveness["degraded_reason"] = "stream_path_invalid"

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
            scope_drift_probe_allowed = True
            if log_reason_code == "scope_drift_recoverable":
                scope_drift_probe_allowed = not scope_drift_recovery_probe_used
            if (
                blocked_policy == "ralph"
                and recoverable_blocked
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
                recoverable_blocked=recoverable_blocked,
            )
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
        last_recoverable = bool((last_payload or {}).get("recoverable_blocked"))
        payload.update(
            _ralph_recoverable_semantics(
                blocked_policy=blocked_policy,
                reason_code=last_reason,
                recoverable_blocked=last_recoverable,
            )
        )
    clear_active_mode(target)
    append_log(cli_log_path, f"{utc_timestamp()} event=max-iterations iterations={max_iterations}")
    emit(args.format, payload)
    return MAX_ITERATIONS_CODE


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
