#!/usr/bin/env python3
from __future__ import annotations

from hooks.hooklib import (
    load_config,
    read_hook_context,
    resolve_aidd_root,
    resolve_context_gc_mode,
    resolve_project_dir,
    sessionstart_additional_context,
)
from .working_set_builder import build_working_set


def main() -> None:
    ctx = read_hook_context()
    if ctx.hook_event_name != "SessionStart":
        return

    project_dir = resolve_project_dir(ctx)
    aidd_root = resolve_aidd_root(project_dir)
    cfg = load_config(aidd_root)
    if not cfg.get("enabled", True) or not aidd_root:
        return
    if resolve_context_gc_mode(cfg) == "off":
        return

    ws = build_working_set(project_dir)
    if not ws.text.strip():
        return

    sessionstart_additional_context(ws.text)


if __name__ == "__main__":
    main()
