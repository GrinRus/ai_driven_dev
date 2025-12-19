#!/usr/bin/env python3
from __future__ import annotations

from hooklib import (
    json_out,
    load_config,
    read_hook_context,
    resolve_aidd_root,
    resolve_project_dir,
    stat_file_bytes,
    userprompt_block,
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

    limits = cfg.get("transcript_limits", {})
    soft = int(limits.get("soft_bytes", 2_500_000))
    hard = int(limits.get("hard_bytes", 4_500_000))
    hard_behavior = str(limits.get("hard_behavior", "block_prompt"))

    size = stat_file_bytes(ctx.transcript_path) or 0

    if soft <= size < hard:
        json_out(
            {
                "suppressOutput": True,
                "systemMessage": (
                    f"Context GC: transcript is large ({size} bytes). "
                    "Consider running /compact soon."
                ),
            }
        )
        return

    if size >= hard:
        if hard_behavior == "block_prompt":
            userprompt_block(
                reason="Context GC: context window is close to full. Run /compact and retry."
            )
        else:
            json_out(
                {
                    "suppressOutput": True,
                    "systemMessage": (
                        f"Context GC: transcript exceeded hard limit ({size} bytes). "
                        "Consider running /compact."
                    ),
                }
            )


if __name__ == "__main__":
    main()
