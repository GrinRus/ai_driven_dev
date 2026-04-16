from __future__ import annotations

import re

_SEPARATOR_RE = re.compile(r"[\s_]+")

PUBLIC_STAGES: tuple[str, ...] = (
    "idea",
    "research",
    "plan",
    "review-spec",
    "tasklist",
    "implement",
    "review",
    "qa",
    "status",
)

INTERNAL_STAGES: tuple[str, ...] = (
    "review-plan",
    "review-prd",
)

CANONICAL_STAGES: frozenset[str] = frozenset(PUBLIC_STAGES + INTERNAL_STAGES)

# Legacy aliases that still appear in historical artifacts.
STAGE_ALIASES: dict[str, str] = {
    "task": "tasklist",
    "tasks": "tasklist",
}

LOOP_STAGES: frozenset[str] = frozenset(
    {
        "implement",
        "review",
        "qa",
        "status",
    }
)

PLANNING_STAGES: frozenset[str] = frozenset(
    {
        "idea",
        "research",
        "plan",
        "review-spec",
        "review-plan",
        "review-prd",
        "tasklist",
    }
)


def normalize_stage_name(value: str | None) -> str:
    raw = str(value or "").strip().lower()
    if not raw:
        return ""
    normalized = _SEPARATOR_RE.sub("-", raw)
    normalized = normalized.strip("-")
    while "--" in normalized:
        normalized = normalized.replace("--", "-")
    return normalized


def resolve_stage_name(value: str | None) -> str:
    normalized = normalize_stage_name(value)
    if not normalized:
        return ""
    return STAGE_ALIASES.get(normalized, normalized)


def is_known_stage(value: str | None, *, include_aliases: bool = False) -> bool:
    normalized = normalize_stage_name(value)
    if not normalized:
        return False
    if include_aliases and normalized in STAGE_ALIASES:
        return True
    return resolve_stage_name(normalized) in CANONICAL_STAGES


def supported_stage_values(*, include_aliases: bool = False) -> tuple[str, ...]:
    values = sorted(CANONICAL_STAGES)
    if include_aliases:
        values.extend(sorted(STAGE_ALIASES))
    return tuple(values)


def is_loop_stage(value: str | None) -> bool:
    return resolve_stage_name(value) in LOOP_STAGES


def is_planning_stage(value: str | None) -> bool:
    return resolve_stage_name(value) in PLANNING_STAGES
