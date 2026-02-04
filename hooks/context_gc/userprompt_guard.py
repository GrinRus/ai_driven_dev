#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from hooks.hooklib import (
    json_out,
    load_config,
    read_hook_context,
    resolve_context_gc_mode,
    resolve_aidd_root,
    resolve_project_dir,
    stat_file_bytes,
    userprompt_block,
)

TAIL_BYTES = 1_000_000


def _read_tail(path: Path, max_bytes: int) -> str:
    try:
        size = path.stat().st_size
        with path.open("rb") as handle:
            if size > max_bytes:
                handle.seek(size - max_bytes)
            data = handle.read()
        return data.decode("utf-8", errors="replace")
    except Exception:
        return ""


def _extract_latest_mainchain_tokens(transcript_path: str) -> Optional[int]:
    path = Path(transcript_path).expanduser()
    if not path.exists():
        return None

    tail = _read_tail(path, TAIL_BYTES)
    if not tail.strip():
        return None

    lines = [line for line in tail.splitlines() if line.strip()]
    for line in reversed(lines):
        try:
            data = json.loads(line)
        except Exception:
            continue

        if data.get("isSidechain") is True:
            continue
        if data.get("isApiErrorMessage") is True:
            continue

        msg = data.get("message") or {}
        usage = msg.get("usage")
        if not isinstance(usage, dict):
            continue

        def _as_int(key: str) -> int:
            value = usage.get(key, 0)
            try:
                return int(value or 0)
            except Exception:
                return 0

        return (
            _as_int("input_tokens")
            + _as_int("cache_read_input_tokens")
            + _as_int("cache_creation_input_tokens")
        )

    return None


def _warn_message(tokens_used: int, usable: int, reserve: int) -> str:
    return (
        "Context GC: high context usage. "
        f"Used≈{tokens_used} tokens (usable≈{usable}, reserve={reserve}). "
        "Consider /compact soon."
    )


def _block_message(tokens_used: int, usable: int, reserve: int) -> str:
    return (
        "Context GC: too close to limit. "
        f"Used≈{tokens_used} tokens, reserve={reserve}, usable≈{usable}. "
        "Run /compact and retry."
    )


def main() -> None:
    ctx = read_hook_context()
    if ctx.hook_event_name != "UserPromptSubmit":
        return

    project_dir = resolve_project_dir(ctx)
    aidd_root = resolve_aidd_root(project_dir)
    cfg = load_config(aidd_root)
    if not cfg.get("enabled", True):
        return
    if resolve_context_gc_mode(cfg) == "off":
        return

    limits = cfg.get("context_limits", {})
    mode = str(limits.get("mode", "bytes")).lower()
    tokens_used = None

    if mode == "tokens":
        max_ctx = int(limits.get("max_context_tokens", 0) or 0)
        if max_ctx > 0 and ctx.transcript_path:
            tokens_used = _extract_latest_mainchain_tokens(ctx.transcript_path)
        if max_ctx > 0 and tokens_used is not None:
            buffer_tokens = int(limits.get("autocompact_buffer_tokens", 0) or 0)
            reserve = int(limits.get("reserve_next_turn_tokens", 0) or 0)
            warn_pct = float(limits.get("warn_pct_of_usable", 80) or 80)
            block_pct = float(limits.get("block_pct_of_usable", 92) or 92)

            usable = max(1, max_ctx - max(0, buffer_tokens))
            projected = tokens_used + max(0, reserve)
            warn_at = int(usable * (warn_pct / 100.0))
            block_at = int(usable * (block_pct / 100.0))

            if projected >= block_at:
                userprompt_block(reason=_block_message(tokens_used, usable, reserve))
                return

            if projected >= warn_at:
                json_out(
                    {
                        "suppressOutput": True,
                        "systemMessage": _warn_message(tokens_used, usable, reserve),
                    }
                )
                return

            return

    limits_b = cfg.get("transcript_limits", {})
    soft = int(limits_b.get("soft_bytes", 2_500_000))
    hard = int(limits_b.get("hard_bytes", 4_500_000))
    hard_behavior = str(limits_b.get("hard_behavior", "block_prompt"))

    size = stat_file_bytes(ctx.transcript_path) or 0

    if soft <= size < hard:
        json_out(
            {
                "suppressOutput": True,
                "systemMessage": (
                    f"Context GC(bytes): transcript is large ({size} bytes). "
                    "Consider /compact soon."
                ),
            }
        )
        return

    if size >= hard:
        if hard_behavior == "block_prompt":
            userprompt_block(reason="Context GC(bytes): transcript is too large. Run /compact and retry.")
        else:
            json_out(
                {
                    "suppressOutput": True,
                    "systemMessage": (
                        f"Context GC(bytes): transcript exceeded hard limit ({size} bytes). "
                        "Consider /compact."
                    ),
                }
            )


if __name__ == "__main__":
    main()
