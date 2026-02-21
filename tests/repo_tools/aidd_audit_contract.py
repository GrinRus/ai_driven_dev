from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping


CLASSIFICATION_PRIORITY = (
    "ENV_BLOCKER",
    "ENV_MISCONFIG",
    "PROMPT_EXEC_ISSUE",
    "CONTRACT_MISMATCH",
    "FLOW_BUG",
)


@dataclass(frozen=True)
class Classification:
    classification: str
    subtype: str
    source: str
    label: str


def _truthy(value: object) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def _as_text(values: Mapping[str, object]) -> str:
    return "\n".join(f"{key}={value}" for key, value in values.items())


def classify_incident(
    *,
    summary: Mapping[str, object],
    termination: Mapping[str, object] | None = None,
    log_text: str = "",
    top_level_status: str = "",
    preflight: Mapping[str, object] | None = None,
    diagnostics_text: str = "",
) -> Classification:
    term = termination or {}
    pre = preflight or {}
    summary_text = _as_text(summary).lower()
    term_text = _as_text(term).lower()
    pre_text = _as_text(pre).lower()
    merged_text = "\n".join(
        part for part in [summary_text, term_text, pre_text, diagnostics_text.lower(), log_text.lower()] if part
    )
    top_level = str(top_level_status or "").strip().lower()

    if _truthy(summary.get("unknown_skill_hit")) or "unknown skill: feature-dev-aidd" in merged_text:
        return Classification(
            classification="ENV_BLOCKER",
            subtype="plugin_not_loaded",
            source="summary" if _truthy(summary.get("unknown_skill_hit")) else "run_log",
            label="ENV_BLOCKER(plugin_not_loaded)",
        )

    enospc_markers = (
        "no_space_left_on_device",
        "no space left on device",
        "launcher_io_enospc",
    )
    enospc_hit = any(marker in merged_text for marker in enospc_markers)
    if _truthy(pre.get("disk_low")) or enospc_hit:
        if _truthy(pre.get("disk_low")):
            source = "runner_preflight"
        elif any(marker in summary_text for marker in enospc_markers):
            source = "summary"
        else:
            source = "run_log"
        return Classification(
            classification="ENV_MISCONFIG",
            subtype="no_space_left_on_device",
            source=source,
            label="ENV_MISCONFIG(no_space_left_on_device)",
        )

    if "claude_plugin_root (or aidd_plugin_dir) is required" in merged_text:
        return Classification(
            classification="ENV_MISCONFIG",
            subtype="loop_runner_env_missing",
            source="run_log",
            label="ENV_MISCONFIG(loop_runner_env_missing)",
        )

    exit_code = str(term.get("exit_code") or summary.get("effective_exit_code") or summary.get("exit_code") or "").strip()
    killed_flag = _truthy(term.get("killed_flag") or summary.get("killed_flag"))
    watchdog_marker = _truthy(term.get("watchdog_marker") or summary.get("watchdog_marker"))

    if exit_code == "143" and not killed_flag:
        return Classification(
            classification="ENV_MISCONFIG",
            subtype="parent_terminated_or_external_terminate",
            source="termination_attribution",
            label="ENV_MISCONFIG(parent_terminated_or_external_terminate)",
        )

    if exit_code == "143" and killed_flag and watchdog_marker:
        return Classification(
            classification="PROMPT_EXEC_ISSUE",
            subtype="watchdog_terminated",
            source="termination_attribution",
            label="NOT_VERIFIED(killed)+PROMPT_EXEC_ISSUE(watchdog_terminated)",
        )

    if "invalid-schema" in merged_text and "stage_result_missing_or_invalid" in merged_text:
        return Classification(
            classification="CONTRACT_MISMATCH",
            subtype="stage_result_shape",
            source="diagnostics",
            label="CONTRACT_MISMATCH(stage_result_shape)",
        )

    if "launcher_tokenization_or_command_not_found" in merged_text or str(summary.get("exit_code") or "").strip() == "127":
        return Classification(
            classification="PROMPT_EXEC_ISSUE",
            subtype="launcher_tokenization_or_command_not_found",
            source="summary",
            label="PROMPT_EXEC_ISSUE(launcher_tokenization_or_command_not_found)",
        )

    if top_level in {"blocked", "done", "ship", "success", "error", "continue"}:
        return Classification(
            classification="TELEMETRY_ONLY",
            subtype=f"top_level_{top_level}",
            source="top_level_payload",
            label=f"TELEMETRY_ONLY(top_level_{top_level})",
        )

    return Classification(
        classification="FLOW_BUG",
        subtype="unclassified_terminal_state",
        source="fallback",
        label="FLOW_BUG(unclassified_terminal_state)",
    )
