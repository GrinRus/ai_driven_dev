"""Event logging for workflow status."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from aidd_runtime import ast_index
from aidd_runtime.io_utils import append_jsonl, read_jsonl, utc_timestamp


_REASON_TOKEN_RE = re.compile(r"[^a-z0-9_:]+")
_AST_REASON_CODES = {
    ast_index.REASON_BINARY_MISSING,
    ast_index.REASON_INDEX_MISSING,
    ast_index.REASON_TIMEOUT,
    ast_index.REASON_JSON_INVALID,
    ast_index.REASON_FALLBACK_RG,
}


def _normalize_reason_code(value: Any) -> str:
    text = str(value or "").strip().lower()
    if not text:
        return ""
    text = text.replace("-", "_").replace(" ", "_")
    return _REASON_TOKEN_RE.sub("", text)


def _normalize_details(details: Dict[str, Any]) -> Dict[str, Any]:
    normalized: Dict[str, Any] = {}
    for key, value in details.items():
        if key.endswith("reason_code"):
            reason = _normalize_reason_code(value)
            normalized[key] = reason or ""
            continue
        if key.endswith("reason_codes") and isinstance(value, list):
            normalized[key] = [
                item
                for item in (_normalize_reason_code(raw) for raw in value)
                if item
            ]
            continue
        normalized[key] = value
    return normalized


def _first_reason_code(details: Optional[Dict[str, Any]]) -> str:
    if not details:
        return ""
    for key in ("reason_code", "ast_reason_code", "pending_reason_code", "memory_reason_code"):
        token = _normalize_reason_code(details.get(key))
        if token:
            return token
    for key, value in details.items():
        if not key.endswith("reason_code"):
            continue
        token = _normalize_reason_code(value)
        if token:
            return token
    return ""


def _ast_policy(details: Optional[Dict[str, Any]]) -> tuple[str, str]:
    if not details:
        return "", ""
    reason_code = _normalize_reason_code(details.get("ast_reason_code"))
    if reason_code not in _AST_REASON_CODES:
        return "", reason_code
    required = bool(details.get("ast_required"))
    return ("blocked" if required else "warn"), reason_code


def events_path(root: Path, ticket: str) -> Path:
    return root / "reports" / "events" / f"{ticket}.jsonl"


def append_event(
    root: Path,
    *,
    ticket: str,
    slug_hint: Optional[str],
    event_type: str,
    status: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
    report_path: Optional[Path] = None,
    source: Optional[str] = None,
) -> None:
    if not ticket:
        return
    normalized_details = _normalize_details(details) if details else None
    effective_status = str(status or "").strip().lower()
    ast_policy, ast_reason_code = _ast_policy(normalized_details)
    if ast_policy == "blocked":
        effective_status = "blocked"
    elif ast_policy == "warn" and effective_status in {"", "ok"}:
        effective_status = "warn"
    primary_reason = _first_reason_code(normalized_details)
    if ast_policy and normalized_details is not None:
        normalized_details.setdefault("ast_fallback_policy", ast_policy)
    if primary_reason and normalized_details is not None:
        normalized_details.setdefault("reason_code", primary_reason)
    if ast_policy == "blocked" and normalized_details is not None:
        next_action = str(normalized_details.get("ast_next_action") or "").strip()
        if next_action:
            normalized_details.setdefault("next_action", next_action)

    payload: Dict[str, Any] = {
        "ts": utc_timestamp(),
        "ticket": ticket,
        "slug_hint": slug_hint,
        "type": event_type,
    }
    if effective_status:
        payload["status"] = effective_status
    elif status:
        payload["status"] = str(status)
    if primary_reason:
        payload["reason_code"] = primary_reason
    if ast_reason_code and primary_reason != ast_reason_code and payload.get("reason_code"):
        payload["ast_reason_code"] = ast_reason_code
    if normalized_details:
        payload["details"] = normalized_details
    if report_path:
        payload["report"] = report_path.as_posix()
    if source:
        payload["source"] = source

    path = events_path(root, ticket)
    append_jsonl(path, payload)


def read_events(root: Path, ticket: str, *, limit: int = 5) -> List[Dict[str, Any]]:
    path = events_path(root, ticket)
    if not path.exists():
        return []
    events = read_jsonl(path)
    if not events:
        return []
    if limit <= 0:
        return []
    return events[-max(limit, 0):]
