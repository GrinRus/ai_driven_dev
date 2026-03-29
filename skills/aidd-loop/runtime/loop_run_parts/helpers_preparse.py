#!/usr/bin/env python3
"""Helper functions for loop_run_parts.core."""

from __future__ import annotations

import datetime as dt
import json
import os
import re
import shlex
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import List, Optional, Tuple

from aidd_runtime import marker_semantics
from aidd_runtime import runtime
from aidd_runtime import stage_result_contract
from aidd_runtime import tasklist_parser
from aidd_runtime.feature_ids import write_active_state
from aidd_runtime.loop_pack import (
    is_open_item,
    parse_iteration_items,
    parse_next3_refs,
    parse_sections,
    select_first_open,
)

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
BLOCKED_CODE = 20
RESEARCH_GATE_MODE_VALUES = {"off", "on", "auto"}
STAGE_DEFAULT_BUDGET_SECONDS = {
    "implement": 3600,
    "review": 3600,
    "qa": 3600,
}
DEFAULT_RESEARCH_GATE_PROBE_TIMEOUT_SECONDS = 180
PROMPT_FLOW_DRIFT_REASON_FAMILY = "prompt_flow_drift_non_canonical_runtime_path"
LOOP_RESEARCH_SOFT_REASON_CODES = {
    "research_status_invalid",
    "rlm_links_empty_warn",
    "rlm_status_pending",
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


def _has_executable_test_entries(target: Path, ticket: str) -> bool:
    tasklist_path = target / "docs" / "tasklist" / f"{ticket}.md"
    if not tasklist_path.exists():
        return False
    try:
        lines = tasklist_path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return False
    section_lines = tasklist_parser.extract_section(lines, "AIDD:TEST_EXECUTION")
    if not section_lines:
        return False
    parsed = tasklist_parser.parse_test_execution(section_lines)
    if parsed.get("tasks"):
        return True
    extra_commands: list[str] = []
    for field in ("command", "commands"):
        scalar = tasklist_parser.extract_scalar_field(section_lines, field)
        if scalar:
            extra_commands.append(scalar)
        extra_commands.extend(tasklist_parser.extract_list_field(section_lines, field))
    for raw in extra_commands:
        normalized = tasklist_parser.normalize_test_execution_task(str(raw))
        if normalized:
            return True
    return False


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


def _safe_mtime(path: Optional[Path]) -> float:
    if path is None or not path.exists():
        return 0.0
    try:
        return float(path.stat().st_mtime)
    except OSError:
        return 0.0


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


def _resolve_recoverable_retry_budget(raw: object) -> int:
    if raw is None or str(raw).strip() == "":
        raw = os.environ.get("AIDD_LOOP_RECOVERABLE_BLOCK_RETRIES", str(DEFAULT_RECOVERABLE_BLOCK_RETRIES))
    try:
        value = int(str(raw).strip())
    except (TypeError, ValueError):
        value = DEFAULT_RECOVERABLE_BLOCK_RETRIES
    return max(value, 0)


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
        summary = research_guard.validate_research(
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
    warnings = [str(item).strip().lower() for item in (summary.warnings or []) if str(item).strip()]
    if "rlm_links_empty_warn_non_blocking" in warnings:
        return True, "rlm_links_empty_warn", "", ""
    if "rlm_status_pending_softened" in warnings or "research_status_pending_softened" in warnings:
        return True, "rlm_status_pending", "", ""
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


def _research_gate_recovery_path(reason_code: str) -> str:
    normalized = str(reason_code or "").strip().lower()
    if normalized == "rlm_worklist_missing":
        return "research_gate_worklist_rebuild_probe"
    return "research_gate_links_build_probe"


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
    if (
        stage == "review"
        and reason_value in {"review_pack_missing", "review_pack_stale"}
        and runtime.is_iteration_work_item_key(active_work_item)
    ):
        # Keep review stage active for a bounded retry when review-pack artifacts lag.
        write_active_stage(target, "review")
        return "retry_review_pack", active_work_item
    if (
        stage == "review"
        and reason_value == "no_tests_hard"
        and runtime.is_iteration_work_item_key(active_work_item)
    ):
        if _has_executable_test_entries(target, ticket):
            write_active_stage(target, "review")
            return "derive_tests_then_retry_review", active_work_item
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
    blocked_policy: str | None = None,
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
    if blocked_policy:
        cmd.extend(["--blocked-policy", blocked_policy])
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
    if blocked_policy:
        env["AIDD_LOOP_BLOCKED_POLICY"] = str(blocked_policy)
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
            "terminal_marker": 1,
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
