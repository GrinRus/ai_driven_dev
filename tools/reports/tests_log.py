"""Append-only tests log (JSONL)."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

from tools.io_utils import append_jsonl, read_jsonl, utc_timestamp

def tests_log_path(root: Path, ticket: str) -> Path:
    return root / "reports" / "tests" / f"{ticket}.jsonl"


def append_log(
    root: Path,
    *,
    ticket: str,
    slug_hint: Optional[str],
    status: str,
    details: Optional[Dict[str, Any]] = None,
    source: Optional[str] = None,
) -> None:
    if not ticket:
        return
    payload: Dict[str, Any] = {
        "ts": utc_timestamp(),
        "ticket": ticket,
        "slug_hint": slug_hint or ticket,
        "type": "tests",
        "status": status,
    }
    if details:
        payload["details"] = details
    if source:
        payload["source"] = source

    path = tests_log_path(root, ticket)
    append_jsonl(path, payload)


def read_log(root: Path, ticket: str, *, limit: int = 5) -> List[Dict[str, Any]]:
    path = tests_log_path(root, ticket)
    if not path.exists():
        return []
    events = read_jsonl(path)
    if not events:
        return []
    if limit <= 0:
        return []
    return events[-max(limit, 0):]
