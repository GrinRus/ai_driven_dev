#!/usr/bin/env python3
"""Shared blocked-reason policy matrix for loop-step/loop-run."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Dict, Set

from aidd_runtime import runtime


DEFAULT_BLOCKED_POLICY = "strict"
BLOCKED_POLICY_VALUES = {"strict", "ralph"}
RALPH_POLICY_VERSION = "v2"

DEFAULT_HARD_BLOCK_REASONS: Set[str] = {
    "loop_runner_permissions",
    "user_approval_required",
    "diff_boundary_violation",
    "preflight_contract_mismatch",
    "plugin_root_missing",
    "command_unavailable",
    "invalid_work_item_key",
    "work_item_resolution_failed",
    "active_stage_sync_failed",
    "prompt_flow_blocker",
    "contract_mismatch_stage_result_shape",
    "contract_mismatch_actions_shape",
}

DEFAULT_RECOVERABLE_REASONS: Set[str] = {
    "stage_result_missing_or_invalid",
    "stage_result_blocked",
    "blocked_without_reason",
    "blocking_findings",
    "scope_drift_recoverable",
    "rlm_links_empty_warn",
    "rlm_worklist_missing",
    "rlm_status_pending",
    "no_tests_hard",
    "qa_tests_failed",
    "review_context_pack_missing",
    "qa_blocked",
    # Compatibility reasons from historical loop-run recoverable set.
    "invalid_loop_step_payload",
    "stage_result_missing",
    "stage_chain_logs_missing",
    "preflight_missing",
    "qa_repair_missing_work_item",
    "qa_repair_no_handoff",
    "qa_repair_multiple_handoffs",
    "qa_repair_tasklist_missing",
    "unsupported_stage_result",
}

DEFAULT_WARN_CONTINUE_REASONS: Set[str] = {
    "output_contract_warn",
    "no_tests_soft",
    "review_context_pack_placeholder_warn",
    "fast_mode_warn",
    "out_of_scope_warn",
    "no_boundaries_defined_warn",
    "auto_boundary_extend_warn",
}
DEFAULT_STRICT_RECOVERABLE_REASONS: Set[str] = {
    "no_tests_hard",
}

_ENV_REASON_KEYS = {
    "hard": "AIDD_LOOP_BLOCK_REASON_HARD",
    "recoverable": "AIDD_LOOP_BLOCK_REASON_RECOVERABLE",
    "warn": "AIDD_LOOP_BLOCK_REASON_WARN",
    "strict_recoverable": "AIDD_LOOP_BLOCK_REASON_STRICT_RECOVERABLE",
}


def normalize_reason_code(reason_code: str | None) -> str:
    return str(reason_code or "").strip().lower()


def _split_reason_codes(value: object) -> Set[str]:
    if value is None:
        return set()
    if isinstance(value, (list, tuple, set)):
        parts = [str(item) for item in value]
    else:
        text = str(value).replace(",", " ").replace(";", " ")
        parts = text.split()
    return {normalize_reason_code(item) for item in parts if normalize_reason_code(item)}


def _load_gates_policy(target: Path | None) -> Dict[str, Set[str]]:
    if target is None:
        return {"hard": set(), "recoverable": set(), "warn": set(), "strict_recoverable": set()}
    config = runtime.load_gates_config(target)
    if not isinstance(config, dict):
        return {"hard": set(), "recoverable": set(), "warn": set(), "strict_recoverable": set()}
    loop_cfg = config.get("loop")
    if not isinstance(loop_cfg, dict):
        return {"hard": set(), "recoverable": set(), "warn": set(), "strict_recoverable": set()}
    reason_cfg = loop_cfg.get("block_reason_policy")
    strict_recoverable = _split_reason_codes(loop_cfg.get("strict_recoverable_reason_codes"))
    if not isinstance(reason_cfg, dict):
        return {
            "hard": set(),
            "recoverable": set(),
            "warn": set(),
            "strict_recoverable": strict_recoverable,
        }
    return {
        "hard": _split_reason_codes(reason_cfg.get("hard")),
        "recoverable": _split_reason_codes(reason_cfg.get("recoverable")),
        "warn": _split_reason_codes(reason_cfg.get("warn")),
        "strict_recoverable": strict_recoverable,
    }


def resolve_reason_policy(target: Path | None = None) -> Dict[str, Set[str]]:
    policy = {
        "hard": set(DEFAULT_HARD_BLOCK_REASONS),
        "recoverable": set(DEFAULT_RECOVERABLE_REASONS),
        "warn": set(DEFAULT_WARN_CONTINUE_REASONS),
        "strict_recoverable": set(DEFAULT_STRICT_RECOVERABLE_REASONS),
    }
    gates_policy = _load_gates_policy(target)
    for key in ("hard", "recoverable", "warn", "strict_recoverable"):
        if gates_policy[key]:
            policy[key] = set(gates_policy[key])
    for key, env_name in _ENV_REASON_KEYS.items():
        env_value = os.environ.get(env_name)
        if env_value and env_value.strip():
            policy[key] = _split_reason_codes(env_value)
    return policy


def _gates_blocked_policy(target: Path | None) -> str:
    if target is None:
        return ""
    config = runtime.load_gates_config(target)
    if not isinstance(config, dict):
        return ""
    loop_cfg = config.get("loop")
    if not isinstance(loop_cfg, dict):
        return ""
    return normalize_reason_code(loop_cfg.get("blocked_policy"))


def resolve_blocked_policy(raw: str | None, *, target: Path | None = None) -> str:
    for candidate in (
        normalize_reason_code(raw),
        normalize_reason_code(os.environ.get("AIDD_LOOP_BLOCKED_POLICY")),
        _gates_blocked_policy(target),
        DEFAULT_BLOCKED_POLICY,
    ):
        if candidate in BLOCKED_POLICY_VALUES:
            return candidate
    return DEFAULT_BLOCKED_POLICY


def classify_block_reason(
    reason_code: str | None,
    blocked_policy: str | None,
    hooks_mode: str | None,
    *,
    target: Path | None = None,
) -> Dict[str, object]:
    resolved_policy = resolve_blocked_policy(blocked_policy, target=target)
    normalized = normalize_reason_code(reason_code) or "blocked_without_reason"
    hooks_value = str(hooks_mode or "").strip().lower()
    policy = resolve_reason_policy(target=target)

    reason_class = "not_recoverable"
    if normalized in policy["hard"]:
        reason_class = "hard_block"
    elif resolved_policy == "strict" and normalized in policy["strict_recoverable"]:
        reason_class = "recoverable_retry"
    elif resolved_policy == "ralph":
        if normalized in policy["recoverable"]:
            reason_class = "recoverable_retry"
        elif normalized in policy["warn"]:
            reason_class = "warn_continue"
        elif normalized.startswith("stage_result_") or normalized.startswith("qa_repair_"):
            reason_class = "recoverable_retry"
        elif normalized.endswith("_warn"):
            reason_class = "warn_continue"
    elif hooks_value != "strict" and normalized in policy["warn"]:
        # Strict policy remains fail-fast; this branch is for telemetry only.
        reason_class = "warn_continue"

    return {
        "reason_code": normalized,
        "blocked_policy": resolved_policy,
        "reason_class": reason_class,
        "is_hard_block": reason_class == "hard_block",
        "is_recoverable_retry": reason_class == "recoverable_retry",
        "is_warn_continue": reason_class == "warn_continue",
        "policy_version": RALPH_POLICY_VERSION if resolved_policy == "ralph" else "",
    }
