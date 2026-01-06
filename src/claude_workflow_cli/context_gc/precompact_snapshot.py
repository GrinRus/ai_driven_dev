#!/usr/bin/env python3
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from .hooklib import load_config, read_hook_context, resolve_aidd_root, resolve_project_dir, stat_file_bytes
from .working_set_builder import build_working_set


def _safe_mkdir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def _write_snapshot(
    session_dir: Path,
    ws_text: str,
    meta: dict,
    tail: str,
) -> None:
    _safe_mkdir(session_dir)
    (session_dir / "working_set.md").write_text(ws_text + "\n", encoding="utf-8")
    (session_dir / "precompact_meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    if tail.strip():
        (session_dir / "transcript_tail.jsonl").write_text(tail, encoding="utf-8")


def _tail_file(path: Path, max_bytes: int = 200_000) -> str:
    try:
        size = path.stat().st_size
        with path.open("rb") as handle:
            if size > max_bytes:
                handle.seek(size - max_bytes)
            data = handle.read()
        return data.decode("utf-8", errors="replace")
    except Exception:
        return ""


def main() -> None:
    ctx = read_hook_context()
    if ctx.hook_event_name != "PreCompact":
        return

    project_dir = resolve_project_dir(ctx)
    aidd_root = resolve_aidd_root(project_dir)
    cfg = load_config(aidd_root)
    if not cfg.get("enabled", True) or not aidd_root:
        return

    reports_dir = aidd_root / "reports" / "context"
    ws = build_working_set(project_dir)
    now = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")

    meta = {
        "generated_at": now,
        "hook": "PreCompact",
        "trigger": ctx.raw.get("trigger"),
        "custom_instructions": ctx.raw.get("custom_instructions"),
        "ticket": ws.ticket,
        "slug": ws.slug,
        "transcript_path": ctx.transcript_path,
        "transcript_bytes": stat_file_bytes(ctx.transcript_path),
    }
    tail = ""
    if ctx.transcript_path:
        tail = _tail_file(Path(ctx.transcript_path).expanduser())

    session_dir = reports_dir / (ctx.session_id or "unknown")
    _write_snapshot(session_dir, ws.text, meta, tail)
    (reports_dir / "latest_working_set.md").write_text(ws.text + "\n", encoding="utf-8")

    if ws.ticket:
        ticket_root = reports_dir / "by-ticket" / ws.ticket
        ticket_session_dir = ticket_root / (ctx.session_id or "unknown")
        _write_snapshot(ticket_session_dir, ws.text, meta, tail)
        (ticket_root / "latest_working_set.md").write_text(ws.text + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
