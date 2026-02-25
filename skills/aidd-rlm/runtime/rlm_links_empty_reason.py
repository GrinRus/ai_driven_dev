from __future__ import annotations

from typing import Dict


def _safe_int(value: object) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def resolve_empty_reason(
    *,
    links_total: int,
    target_files_total: int,
    scope_stats: Dict[str, object],
    link_stats: Dict[str, object],
) -> str:
    if links_total > 0:
        return ""

    scope_label = str(scope_stats.get("target_files_scope") or "").strip().lower()
    scope_total = _safe_int(scope_stats.get("target_files_scope_total"))
    scope_input_total = _safe_int(scope_stats.get("target_files_scope_input_total"))
    if scope_label == "worklist" and scope_input_total > 0 and scope_total == 0:
        return "filtered_all"

    if target_files_total <= 0:
        return "no_targets"

    symbols_total = _safe_int(link_stats.get("symbols_total"))
    symbols_scanned = _safe_int(link_stats.get("symbols_scanned"))
    rg_timeouts = _safe_int(link_stats.get("rg_timeouts"))
    rg_errors = _safe_int(link_stats.get("rg_errors"))
    if rg_errors > 0 and rg_timeouts <= 0:
        return "rg_error"
    if rg_timeouts > 0:
        return "rg_timeout"
    if symbols_total <= 0 or symbols_scanned <= 0:
        return "no_symbols"
    return "no_matches"
