"""Append-only tests log (JSONL)."""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path
from typing import Any, Dict, List, Optional


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
        "ts": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
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
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False) + "\n")


def read_log(root: Path, ticket: str, *, limit: int = 5) -> List[Dict[str, Any]]:
    path = tests_log_path(root, ticket)
    if not path.exists():
        return []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    events: List[Dict[str, Any]] = []
    for raw in reversed(lines):
        if not raw.strip():
            continue
        try:
            events.append(json.loads(raw))
        except json.JSONDecodeError:
            continue
        if len(events) >= max(limit, 0):
            break
    return list(reversed(events))
