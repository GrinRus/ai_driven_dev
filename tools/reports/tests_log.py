"""Append-only tests log (JSONL)."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from tools import runtime
from tools.io_utils import append_jsonl, read_jsonl, utc_timestamp

def tests_log_dir(root: Path, ticket: str) -> Path:
    return root / "reports" / "tests" / ticket


def legacy_tests_log_path(root: Path, ticket: str) -> Path:
    return root / "reports" / "tests" / f"{ticket}.jsonl"


def tests_log_path(root: Path, ticket: str, scope_key: str) -> Path:
    scope = runtime.sanitize_scope_key(scope_key)
    if not scope:
        scope = runtime.sanitize_scope_key(ticket) or "ticket"
    return tests_log_dir(root, ticket) / f"{scope}.jsonl"


def append_log(
    root: Path,
    *,
    ticket: str,
    slug_hint: Optional[str],
    ticket_guess: Optional[str] = None,
    stage: str,
    scope_key: str,
    work_item_key: Optional[str] = None,
    profile: Optional[str] = None,
    tasks: Optional[Iterable[str]] = None,
    filters: Optional[Iterable[str]] = None,
    exit_code: Optional[int] = None,
    log_path: Optional[str] = None,
    status: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
    source: Optional[str] = None,
    cwd: Optional[str] = None,
    worktree: Optional[str] = None,
) -> None:
    if not ticket:
        return
    stage_value = str(stage or "").strip().lower()
    scope_value = runtime.sanitize_scope_key(scope_key) or runtime.sanitize_scope_key(ticket) or "ticket"
    status_value = str(status or "").strip().lower()
    if not status_value:
        if exit_code is None:
            status_value = "unknown"
        elif exit_code == 0:
            status_value = "pass"
        else:
            status_value = "fail"

    payload: Dict[str, Any] = {
        "schema": "aidd.tests_log.v1",
        "updated_at": utc_timestamp(),
        "ticket": ticket,
        "slug_hint": slug_hint or ticket,
        "stage": stage_value,
        "scope_key": scope_value,
        "status": status_value,
    }
    if ticket_guess:
        payload["ticket_guess"] = ticket_guess
    if work_item_key:
        payload["work_item_key"] = work_item_key
    if profile:
        payload["profile"] = profile
    if tasks:
        payload["tasks"] = list(tasks)
    if filters:
        payload["filters"] = list(filters)
    if exit_code is not None:
        payload["exit_code"] = exit_code
    if log_path:
        payload["log_path"] = str(log_path)
    if cwd:
        payload["cwd"] = cwd
    if worktree:
        payload["worktree"] = worktree
    if details:
        payload["details"] = details
    if source:
        payload["source"] = source

    path = tests_log_path(root, ticket, scope_value)
    append_jsonl(path, payload)


def _load_events(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    return read_jsonl(path) or []


def _entry_timestamp(entry: Dict[str, Any]) -> str:
    return str(entry.get("updated_at") or entry.get("ts") or "")


def read_log(
    root: Path,
    ticket: str,
    *,
    scope_key: Optional[str] = None,
    stage: Optional[str] = None,
    limit: int = 5,
) -> List[Dict[str, Any]]:
    if limit <= 0:
        return []
    stage_value = str(stage or "").strip().lower()
    events: List[Dict[str, Any]] = []

    if scope_key:
        events = _load_events(tests_log_path(root, ticket, scope_key))
    else:
        legacy_path = legacy_tests_log_path(root, ticket)
        if legacy_path.exists():
            events = _load_events(legacy_path)
        else:
            dir_path = tests_log_dir(root, ticket)
            if dir_path.exists():
                for path in sorted(dir_path.glob("*.jsonl")):
                    events.extend(_load_events(path))

    if stage_value:
        events = [entry for entry in events if str(entry.get("stage") or "").strip().lower() == stage_value]
    if not events:
        return []
    events.sort(key=_entry_timestamp)
    return events[-max(limit, 0):]


def latest_entry(
    root: Path,
    ticket: str,
    scope_key: str,
    *,
    stages: Optional[Iterable[str]] = None,
) -> Tuple[Optional[Dict[str, Any]], Optional[Path]]:
    path = tests_log_path(root, ticket, scope_key)
    events = _load_events(path)
    if not events:
        return None, path if path.exists() else None
    stage_set = {str(stage or "").strip().lower() for stage in (stages or []) if str(stage or "").strip()}
    for entry in reversed(events):
        if stage_set:
            entry_stage = str(entry.get("stage") or "").strip().lower()
            if entry_stage not in stage_set:
                continue
        return entry, path
    return None, path
