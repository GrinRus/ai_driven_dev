from __future__ import annotations

import re
from typing import Tuple

from aidd_runtime import stage_lexicon

_WORK_ITEM_KEY_RE = re.compile(r"^(iteration_id|id)=[A-Za-z0-9_.:-]+$")
_ITERATION_WORK_ITEM_KEY_RE = re.compile(r"^iteration_id=[A-Za-z0-9_.:-]+$")
_SLUG_HINT_TOKEN_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,80}$")

_LOOP_STAGES = {"implement", "review"}


def normalize_stage_name(stage: str | None) -> str:
    return stage_lexicon.resolve_stage_name(stage)


def is_valid_work_item_key(value: str | None) -> bool:
    raw = str(value or "").strip()
    if not raw:
        return False
    return bool(_WORK_ITEM_KEY_RE.match(raw))


def is_iteration_work_item_key(value: str | None) -> bool:
    raw = str(value or "").strip()
    if not raw:
        return False
    return bool(_ITERATION_WORK_ITEM_KEY_RE.match(raw))


def normalize_slug_hint_token(value: str | None) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    token = raw.split()[0].strip().strip("\"'")
    if not token:
        return ""
    lowered = token.lower()
    for prefix in ("slug=", "slug:"):
        if lowered.startswith(prefix):
            token = token[len(prefix):]
            break
    token = token.strip().strip("\"'").strip(",;").lower()
    if not token:
        return ""
    if not _SLUG_HINT_TOKEN_RE.match(token):
        return ""
    return token


def normalize_work_item_for_stage(
    *,
    stage: str | None,
    requested_work_item: str | None,
    current_work_item: str | None = None,
) -> Tuple[str, str]:
    """
    Normalize work_item for active state updates.

    Returns (normalized_work_item, last_review_report_id).
    """
    stage_value = normalize_stage_name(stage)
    requested = str(requested_work_item or "").strip()
    current = str(current_work_item or "").strip()
    if not requested:
        return "", ""

    if not is_valid_work_item_key(requested):
        return "", ""

    if stage_value not in _LOOP_STAGES:
        return requested, ""

    if is_iteration_work_item_key(requested):
        return requested, ""

    if not requested.startswith("id="):
        return "", ""

    # Keep report/handoff id out of loop-stage work_item and persist it separately.
    report_id = requested[len("id="):].strip()
    if current and is_iteration_work_item_key(current):
        return current, report_id
    return "", report_id
