from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List

from aidd_runtime import runtime
from aidd_runtime.rlm_config import load_conventions

SCHEMA_SEMANTIC = "aidd.memory.semantic.v1"
SCHEMA_DECISION = "aidd.memory.decision.v1"
SCHEMA_DECISIONS_PACK = "aidd.memory.decisions.pack.v1"
SCHEMAS_SUPPORTED = (SCHEMA_DECISION, SCHEMA_DECISIONS_PACK, SCHEMA_SEMANTIC)

PACK_VERSION = "v1"

DEFAULT_SEMANTIC_MAX_CHARS = 8000
DEFAULT_SEMANTIC_MAX_LINES = 320
DEFAULT_SEMANTIC_MAX_ITEMS = 120
DEFAULT_SEMANTIC_TRIM_PRIORITY = ("invariants", "constraints", "defaults", "terms", "open_questions")

DEFAULT_DECISIONS_MAX_CHARS = 8000
DEFAULT_DECISIONS_MAX_LINES = 220
DEFAULT_DECISIONS_MAX_ACTIVE = 50
DEFAULT_DECISIONS_MAX_HISTORY = 150

DEFAULT_SLICE_MAX_HITS = 20
DEFAULT_SLICE_MAX_CHARS = 3000
DEFAULT_SLICE_POLICY_MODE = "warn"
DEFAULT_SLICE_ENFORCE_STAGES = ("research", "plan", "review-spec", "implement", "review", "qa")
DEFAULT_SLICE_MAX_AGE_MINUTES = 240
DEFAULT_RG_POLICY = "controlled_fallback"
DEFAULT_SLICE_MANIFEST_MAX_SLICES = 6
DEFAULT_SLICE_MANIFEST_MAX_CHARS = 12000

DEFAULT_STAGE_QUERIES: Dict[str, List[str]] = {
    "research": [
        "constraint|invariant|default",
        "open_questions|decision|risk",
    ],
    "plan": [
        "constraint|invariant|fallback|required",
        "decision|topic|status",
    ],
    "review-spec": [
        "acceptance|constraint|invariant",
        "decision|topic|conflict",
    ],
    "implement": [
        "decision|topic|active",
        "constraint|fallback|status",
    ],
    "review": [
        "decision|topic|active",
        "invariant|constraint|risk",
    ],
    "qa": [
        "decision|topic|active",
        "constraint|fallback|status",
    ],
}

_FILE_TOKEN_RE = re.compile(r"[^A-Za-z0-9_.-]+")


def stable_id(*parts: Any, length: int = 12) -> str:
    digest = hashlib.sha1()
    for part in parts:
        digest.update(str(part).encode("utf-8"))
        digest.update(b"|")
    return digest.hexdigest()[:length]


def normalize_text(value: Any) -> str:
    return " ".join(str(value or "").strip().split())


def load_memory_settings(project_root: Path) -> Dict[str, Any]:
    config = load_conventions(project_root)
    settings = config.get("memory")
    return settings if isinstance(settings, dict) else {}


def semantic_limits(settings: Dict[str, Any]) -> Dict[str, Any]:
    semantic = settings.get("semantic") if isinstance(settings.get("semantic"), dict) else {}
    trim_priority_raw = semantic.get("trim_priority")
    trim_priority = (
        [str(item).strip() for item in trim_priority_raw if str(item).strip()]
        if isinstance(trim_priority_raw, list)
        else list(DEFAULT_SEMANTIC_TRIM_PRIORITY)
    )
    return {
        "max_chars": int(semantic.get("max_chars") or DEFAULT_SEMANTIC_MAX_CHARS),
        "max_lines": int(semantic.get("max_lines") or DEFAULT_SEMANTIC_MAX_LINES),
        "max_items": int(semantic.get("max_items") or DEFAULT_SEMANTIC_MAX_ITEMS),
        "trim_priority": trim_priority or list(DEFAULT_SEMANTIC_TRIM_PRIORITY),
    }


def decisions_limits(settings: Dict[str, Any]) -> Dict[str, Any]:
    decisions = settings.get("decisions") if isinstance(settings.get("decisions"), dict) else {}
    return {
        "max_chars": int(decisions.get("max_chars") or DEFAULT_DECISIONS_MAX_CHARS),
        "max_lines": int(decisions.get("max_lines") or DEFAULT_DECISIONS_MAX_LINES),
        "max_active": int(decisions.get("max_active") or DEFAULT_DECISIONS_MAX_ACTIVE),
        "max_history": int(decisions.get("max_history") or DEFAULT_DECISIONS_MAX_HISTORY),
    }


def slice_limits(settings: Dict[str, Any]) -> Dict[str, Any]:
    slice_budget = settings.get("slice_budget") if isinstance(settings.get("slice_budget"), dict) else {}
    return {
        "max_hits": int(slice_budget.get("max_hits") or DEFAULT_SLICE_MAX_HITS),
        "max_chars": int(slice_budget.get("max_chars") or DEFAULT_SLICE_MAX_CHARS),
    }


def _normalize_file_token(value: str, *, fallback: str) -> str:
    text = str(value or "").strip()
    if not text:
        return fallback
    cleaned = _FILE_TOKEN_RE.sub("_", text).strip("._-")
    return cleaned or fallback


def slice_policy(settings: Dict[str, Any]) -> Dict[str, Any]:
    policy = settings.get("slice_policy") if isinstance(settings.get("slice_policy"), dict) else {}
    raw_mode = str(policy.get("mode") or DEFAULT_SLICE_POLICY_MODE).strip().lower()
    mode = raw_mode if raw_mode in {"off", "warn", "hard"} else DEFAULT_SLICE_POLICY_MODE
    raw_rg_policy = str(policy.get("rg_policy") or DEFAULT_RG_POLICY).strip().lower()
    rg_policy = raw_rg_policy if raw_rg_policy in {"free", "controlled_fallback", "deny"} else DEFAULT_RG_POLICY
    raw_stages = policy.get("enforce_stages")
    if isinstance(raw_stages, list):
        enforce_stages = [str(item).strip().lower() for item in raw_stages if str(item).strip()]
    else:
        enforce_stages = list(DEFAULT_SLICE_ENFORCE_STAGES)
    raw_stage_queries = policy.get("stage_queries")
    stage_queries: Dict[str, List[str]] = {
        key: list(values)
        for key, values in DEFAULT_STAGE_QUERIES.items()
    }
    if isinstance(raw_stage_queries, dict):
        for key, values in raw_stage_queries.items():
            stage = str(key).strip().lower()
            if not stage:
                continue
            if isinstance(values, list):
                normalized = [str(item).strip() for item in values if str(item).strip()]
                if normalized:
                    stage_queries[stage] = normalized
    manifest_budget = policy.get("manifest_budget") if isinstance(policy.get("manifest_budget"), dict) else {}
    return {
        "mode": mode,
        "enforce_stages": enforce_stages or list(DEFAULT_SLICE_ENFORCE_STAGES),
        "max_slice_age_minutes": max(1, int(policy.get("max_slice_age_minutes") or DEFAULT_SLICE_MAX_AGE_MINUTES)),
        "rg_policy": rg_policy,
        "manifest_budget": {
            "max_slices": max(1, int(manifest_budget.get("max_slices") or DEFAULT_SLICE_MANIFEST_MAX_SLICES)),
            "max_chars": max(2000, int(manifest_budget.get("max_chars") or DEFAULT_SLICE_MANIFEST_MAX_CHARS)),
        },
        "stage_queries": stage_queries,
    }


def semantic_pack_path(project_root: Path, ticket: str) -> Path:
    return project_root / "reports" / "memory" / f"{ticket}.semantic.pack.json"


def decision_log_path(project_root: Path, ticket: str) -> Path:
    return project_root / "reports" / "memory" / f"{ticket}.decisions.jsonl"


def decisions_pack_path(project_root: Path, ticket: str) -> Path:
    return project_root / "reports" / "memory" / f"{ticket}.decisions.pack.json"


def memory_slice_path(project_root: Path, ticket: str, query: str) -> Path:
    digest = stable_id(ticket, query, length=10)
    return project_root / "reports" / "context" / f"{ticket}-memory-slice-{digest}.pack.json"


def memory_slice_latest_path(project_root: Path, ticket: str) -> Path:
    return project_root / "reports" / "context" / f"{ticket}-memory-slice.latest.pack.json"


def memory_slice_stage_latest_path(project_root: Path, ticket: str, stage: str, scope_key: str) -> Path:
    stage_token = _normalize_file_token(stage, fallback="stage")
    scope_token = _normalize_file_token(scope_key, fallback="ticket")
    return project_root / "reports" / "context" / f"{ticket}-memory-slice.{stage_token}.{scope_token}.latest.pack.json"


def memory_slices_manifest_path(project_root: Path, ticket: str, stage: str, scope_key: str) -> Path:
    stage_token = _normalize_file_token(stage, fallback="stage")
    scope_token = _normalize_file_token(scope_key, fallback="ticket")
    return project_root / "reports" / "context" / f"{ticket}-memory-slices.{stage_token}.{scope_token}.pack.json"


def canonical_json(payload: Dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def payload_size(payload: Dict[str, Any]) -> Dict[str, int]:
    text = canonical_json(payload)
    return {
        "chars": len(text),
        "lines": text.count("\n"),
    }


def budget_exceeded(payload: Dict[str, Any], *, max_chars: int, max_lines: int) -> bool:
    size = payload_size(payload)
    return size["chars"] > max_chars or size["lines"] > max_lines


def columnar(cols: List[str], rows: List[List[Any]]) -> Dict[str, Any]:
    return {
        "cols": cols,
        "rows": rows,
    }


def rel_path(path: Path, project_root: Path) -> str:
    return runtime.rel_path(path.resolve(), project_root)


def dedupe_preserve_order(items: Iterable[str]) -> List[str]:
    seen: set[str] = set()
    output: List[str] = []
    for raw in items:
        value = normalize_text(raw)
        if not value or value in seen:
            continue
        seen.add(value)
        output.append(value)
    return output
