from __future__ import annotations

import re
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
}
_LEGACY_STAGE_RESULT_SCHEMA_RE = re.compile(r"^aidd\.stage_result\.([a-z0-9_-]+)\.v1$")
_LEGACY_STATUS_TO_RESULT = {
    "ok": "continue",
    "pass": "continue",
    "passed": "continue",
    "success": "continue",
    "ready": "continue",
    "done": "done",
    "complete": "done",
    "completed": "done",
    "blocked": "blocked",
    "block": "blocked",
    "error": "blocked",
    "fail": "blocked",
    "failed": "blocked",
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
    legacy_schema = False

    if schema == CANONICAL_STAGE_RESULT_SCHEMA:
        pass
    else:
        legacy_match = _LEGACY_STAGE_RESULT_SCHEMA_RE.match(schema)
        if not legacy_match:
            return None, "invalid-schema"
        schema_stage = legacy_match.group(1).strip().lower()
        if schema_stage != stage_value:
            return None, "wrong-stage"
        legacy_schema = True
        normalized["schema"] = CANONICAL_STAGE_RESULT_SCHEMA
        if not str(normalized.get("stage") or "").strip():
            normalized["stage"] = stage_value

    if str(normalized.get("stage") or "").strip().lower() != stage_value:
        return None, "wrong-stage"

    result = str(normalized.get("result") or "").strip().lower()
    if result not in CANONICAL_STAGE_RESULTS:
        if not legacy_schema:
            return None, "invalid-result"
        status = str(normalized.get("status") or "").strip().lower()
        mapped = _LEGACY_STATUS_TO_RESULT.get(status, "")
        if mapped not in CANONICAL_STAGE_RESULTS:
            return None, "invalid-result"
        result = mapped

    normalized["result"] = result

    work_item_key = str(normalized.get("work_item_key") or "").strip()
    if work_item_key and not runtime.is_valid_work_item_key(work_item_key):
        return None, "invalid-work-item"

    return normalized, ""
