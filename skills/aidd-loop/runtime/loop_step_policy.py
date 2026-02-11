#!/usr/bin/env python3
"""Policy helpers for loop-step orchestration."""

from __future__ import annotations

import os
from pathlib import Path
from typing import List, Tuple

from aidd_runtime import runtime
from aidd_runtime import loop_step as core


def resolve_stream_mode(raw: str | None) -> str:
    if raw is None:
        raw = os.environ.get("AIDD_AGENT_STREAM_MODE", "")
    value = str(raw or "").strip().lower()
    if not value:
        return ""
    return core.STREAM_MODE_ALIASES.get(value, "text")


def _parse_bool(value: str | None) -> bool | None:
    if value is None:
        return None
    raw = value.strip().lower()
    if raw in {"true", "yes", "1"}:
        return True
    if raw in {"false", "no", "0"}:
        return False
    return None


def _normalize_scope(value: str) -> str:
    cleaned = value.strip().strip(")").strip()
    return cleaned


def _is_valid_work_item_key(value: str) -> bool:
    return runtime.is_valid_work_item_key(value)


def _extract_work_item_key(lines: List[str]) -> str:
    scope = ""
    for line in lines:
        match = core.SCOPE_RE.search(line)
        if match:
            scope = _normalize_scope(match.group(1))
            if scope:
                break
    if not scope:
        return ""
    return scope if _is_valid_work_item_key(scope) else ""


def _extract_blocking_flag(lines: List[str]) -> bool | None:
    for line in lines:
        match = core.BLOCKING_PAREN_RE.search(line)
        if match:
            return _parse_bool(match.group(1))
        match = core.BLOCKING_LINE_RE.search(line)
        if match:
            return _parse_bool(match.group(1))
    return None


def _extract_item_id(lines: List[str]) -> str:
    for line in lines:
        match = core.ITEM_ID_RE.search(line)
        if match:
            return match.group(1).strip()
    return ""


def _extract_checkbox_state(line: str) -> str:
    match = core.CHECKBOX_RE.match(line)
    if not match:
        return ""
    return match.group("state").strip().lower()


def _parse_qa_handoff_candidates(lines: List[str]) -> List[Tuple[str, str]]:
    candidates: List[Tuple[str, str]] = []
    in_handoff = False
    current: List[str] = []

    def flush(block: List[str]) -> None:
        if not block:
            return
        state = _extract_checkbox_state(block[0])
        if state in {"x"}:
            return
        blocking = _extract_blocking_flag(block)
        if blocking is not True:
            return
        work_item_key = _extract_work_item_key(block)
        if not work_item_key:
            return
        item_id = _extract_item_id(block)
        label = item_id or work_item_key
        candidates.append((work_item_key, label))

    for raw in lines:
        stripped = raw.strip()
        if stripped == core.HANDOFF_QA_START:
            in_handoff = True
            current = []
            continue
        if stripped == core.HANDOFF_QA_END:
            flush(current)
            current = []
            in_handoff = False
            continue
        if not in_handoff:
            continue
        if core.CHECKBOX_RE.match(raw):
            flush(current)
            current = [raw]
            continue
        if current:
            current.append(raw)
    flush(current)
    return candidates


def _auto_repair_enabled(root: Path) -> bool:
    config = runtime.load_gates_config(root)
    if not isinstance(config, dict):
        return False
    loop_cfg = config.get("loop")
    if not isinstance(loop_cfg, dict):
        loop_cfg = {}
    raw = loop_cfg.get("auto_repair_from_qa")
    if isinstance(raw, str):
        return raw.strip().lower() in {"1", "true", "yes"}
    return bool(raw)


def _resolve_qa_repair_mode(requested: str | None, root: Path) -> Tuple[str, bool]:
    if requested:
        return requested, True
    if _auto_repair_enabled(root):
        return "auto", False
    return "", False


def _select_qa_repair_work_item(
    *,
    tasklist_lines: List[str],
    explicit: str,
    select_handoff: bool,
    mode: str,
) -> Tuple[str, str, str, List[str]]:
    if explicit:
        if not _is_valid_work_item_key(explicit):
            return "", "qa_repair_invalid_work_item", "work_item_key must start with iteration_id= or id=", []
        return explicit, "", "", []
    use_auto = select_handoff or mode == "auto"
    if not use_auto:
        return "", "qa_repair_missing_work_item", "work_item_key required for qa repair", []
    candidates = _parse_qa_handoff_candidates(tasklist_lines)
    if not candidates:
        return "", "qa_repair_no_handoff", "no blocking QA handoff candidates", []
    if len(candidates) > 1:
        labels = [label for _, label in candidates]
        return (
            "",
            "qa_repair_multiple_handoffs",
            "multiple blocking QA handoff candidates",
            labels,
        )
    work_item_key, label = candidates[0]
    return work_item_key, "", "", [label]


def _maybe_append_qa_repair_event(
    root: Path,
    *,
    ticket: str,
    slug_hint: str,
    work_item_key: str,
    mode: str,
) -> None:
    from aidd_runtime.reports import events as _events

    path = _events.events_path(root, ticket)
    if not path.exists():
        return
    _events.append_event(
        root,
        ticket=ticket,
        slug_hint=slug_hint,
        event_type="qa_repair_requested",
        status="blocked",
        details={"work_item_key": work_item_key, "mode": mode},
        source="loop-step",
    )


def is_skill_first(plugin_root: Path) -> bool:
    core_skill = plugin_root / "skills" / "aidd-core" / "SKILL.md"
    if not core_skill.exists():
        return False
    for stage in ("implement", "review", "qa"):
        if (plugin_root / "skills" / stage / "SKILL.md").exists():
            return True
    return False


def resolve_wrapper_plugin_root(plugin_root: Path) -> Path:
    for env_name in ("AIDD_STAGE_WRAPPERS_ROOT", "AIDD_WRAPPER_PLUGIN_ROOT"):
        raw = os.environ.get(env_name, "").strip()
        if not raw:
            continue
        print(
            f"[loop-step] WARN: {env_name} is deprecated in python-only mode and will be ignored",
            file=core.sys.stderr,
        )
    return plugin_root


def should_run_wrappers(stage: str, runner_raw: str, plugin_root: Path) -> bool:
    _ = runner_raw
    if stage not in {"implement", "review", "qa"}:
        return False
    if os.environ.get("AIDD_SKIP_STAGE_WRAPPERS", "").strip() == "1":
        return False
    if not is_skill_first(plugin_root):
        return False
    return True


def resolve_hooks_mode() -> str:
    raw = (os.environ.get("AIDD_HOOKS_MODE") or "").strip().lower()
    return "strict" if raw == "strict" else "fast"


def evaluate_wrapper_skip_policy(stage: str, plugin_root: Path) -> Tuple[str, str, str]:
    if stage not in {"implement", "review", "qa"}:
        return "", "", ""
    if os.environ.get("AIDD_SKIP_STAGE_WRAPPERS", "").strip() != "1":
        return "", "", ""
    if not is_skill_first(plugin_root):
        return "", "", ""
    message = "stage wrappers disabled via AIDD_SKIP_STAGE_WRAPPERS=1"
    hooks_mode = resolve_hooks_mode()
    if hooks_mode == "strict" or stage in {"review", "qa"}:
        return "blocked", message, core.WRAPPER_SKIP_BLOCK_REASON_CODE
    return "warn", message, core.WRAPPER_SKIP_WARN_REASON_CODE


def evaluate_output_contract_policy(status: str) -> Tuple[str, str]:
    if str(status).strip().lower() != "warn":
        return "", ""
    hooks_mode = resolve_hooks_mode()
    if hooks_mode == "strict":
        return "blocked", core.OUTPUT_CONTRACT_WARN_REASON_CODE
    return "warn", core.OUTPUT_CONTRACT_WARN_REASON_CODE


def canonical_actions_log_rel(ticket: str, scope_key: str, stage: str) -> str:
    return f"aidd/reports/actions/{ticket}/{scope_key}/{stage}.actions.json"


def align_actions_log_scope(
    *,
    actions_log_rel: str,
    ticket: str,
    stage: str,
    mismatch_from: str,
    mismatch_to: str,
    target: Path,
) -> str:
    if not mismatch_to or stage not in {"implement", "review", "qa"}:
        return actions_log_rel
    canonical_rel = canonical_actions_log_rel(ticket, mismatch_to, stage)
    if actions_log_rel and f"/{mismatch_to}/" in actions_log_rel:
        return actions_log_rel
    canonical_path = runtime.resolve_path_for_target(Path(canonical_rel), target)
    if canonical_path.exists():
        return runtime.rel_path(canonical_path, target)
    if not actions_log_rel:
        return canonical_rel
    current_path = runtime.resolve_path_for_target(Path(actions_log_rel), target)
    if current_path.exists():
        return runtime.rel_path(current_path, target)
    if mismatch_from and f"/{mismatch_from}/" in actions_log_rel:
        return actions_log_rel
    return actions_log_rel
