from __future__ import annotations

from typing import Dict, Tuple

from aidd_runtime import runtime


CANONICAL_STAGE_RESULT_SCHEMA = "aidd.stage_result.v1"
CANONICAL_STAGE_RESULTS = {"blocked", "continue", "done"}
SOFT_BLOCK_REASON_CODES = {
    "out_of_scope_warn",
    "no_boundaries_defined_warn",
    "auto_boundary_extend_warn",
    "review_context_pack_placeholder_warn",
    "fast_mode_warn",
    "output_contract_warn",
    "blocking_findings",
}


def normalize_requested_result(value: object) -> str:
    requested = str(value or "").strip().lower()
    if requested in CANONICAL_STAGE_RESULTS:
        return requested
    return ""


def effective_stage_result(payload: Dict[str, object]) -> str:
    result = str(payload.get("result") or "").strip().lower()
    if result not in CANONICAL_STAGE_RESULTS:
        return ""
    requested_result = normalize_requested_result(payload.get("requested_result"))
    reason_code = str(payload.get("reason_code") or "").strip().lower()
    # Stage-result may degrade requested continue/done into blocked on soft warnings.
    # Loop consumers use requested_result to avoid false hard-stop on this downgrade.
    if result == "blocked" and requested_result in {"continue", "done"} and reason_code in SOFT_BLOCK_REASON_CODES:
        return requested_result
    return result


def normalize_stage_result_payload(payload: Dict[str, object], stage: str) -> Tuple[Dict[str, object] | None, str]:
    if not isinstance(payload, dict):
        return None, "invalid-json"

    stage_value = (stage or "").strip().lower()
    normalized = dict(payload)
    schema = str(normalized.get("schema") or "").strip().lower()
    schema_version = str(normalized.get("schema_version") or "").strip().lower()
    if not schema and schema_version == CANONICAL_STAGE_RESULT_SCHEMA:
        schema = schema_version
        normalized["schema"] = schema_version
    if schema != CANONICAL_STAGE_RESULT_SCHEMA:
        return None, "invalid-schema"

    if str(normalized.get("stage") or "").strip().lower() != stage_value:
        return None, "wrong-stage"

    result = str(normalized.get("result") or "").strip().lower()
    if result not in CANONICAL_STAGE_RESULTS:
        return None, "invalid-result"

    normalized["result"] = result

    work_item_key = str(normalized.get("work_item_key") or "").strip()
    if work_item_key and not runtime.is_valid_work_item_key(work_item_key):
        return None, "invalid-work-item"

    return normalized, ""
