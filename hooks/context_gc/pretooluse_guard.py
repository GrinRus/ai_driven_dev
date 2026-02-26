#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional

from hooks.context_gc.bash_guard import command_targets_aidd, handle_bash, is_aidd_scoped
from hooks.context_gc.prompt_injection import prompt_injection_guard_message
from hooks.context_gc.rate_limit import should_rate_limit
from hooks.context_gc.rg_guard import rg_fallback_decision
from hooks.context_gc.rw_policy import enforce_rw_policy, manual_preflight_bash_decision, resolve_tool_path
from hooks.hooklib import (
    load_config,
    pretooluse_decision,
    read_hook_context,
    resolve_aidd_root,
    resolve_context_gc_mode,
    resolve_project_dir,
)


def handle_read(project_dir: Path, aidd_root: Optional[Path], cfg: Dict[str, Any], tool_input: Dict[str, Any]) -> None:
    file_path = tool_input.get("file_path") or tool_input.get("path") or tool_input.get("filename")
    if not isinstance(file_path, str) or not file_path:
        return

    path = resolve_tool_path(file_path, project_dir, aidd_root)
    injection_message = prompt_injection_guard_message(
        cfg,
        project_dir,
        aidd_root,
        path=path,
    )

    guard = cfg.get("read_guard", {})
    if not guard.get("enabled", True):
        if injection_message:
            pretooluse_decision(
                permission_decision="allow",
                reason="Context GC: prompt-injection guard for dependency read.",
                system_message=injection_message,
            )
        return

    try:
        size = path.stat().st_size
    except Exception:
        if injection_message:
            pretooluse_decision(
                permission_decision="allow",
                reason="Context GC: prompt-injection guard for dependency read.",
                system_message=injection_message,
            )
        return

    max_bytes = int(guard.get("max_bytes", 200_000))
    if size <= max_bytes:
        if injection_message:
            pretooluse_decision(
                permission_decision="allow",
                reason="Context GC: prompt-injection guard for dependency read.",
                system_message=injection_message,
            )
        return
    if should_rate_limit(guard, project_dir, aidd_root, "read_guard"):
        return

    ask = bool(guard.get("ask_instead_of_deny", True))
    decision = "ask" if ask else "deny"

    system_message = f"Context GC: {path.name} is large ({size} bytes). Prefer searching/snippets over full Read."
    if injection_message:
        system_message = f"{system_message}\n{injection_message}"

    pretooluse_decision(
        permission_decision=decision,
        reason=(
            f"Context GC: file is large ({size} bytes). "
            "Reading it fully may bloat the context. Prefer search/snippets."
        ),
        system_message=system_message,
    )


def main() -> None:
    ctx = read_hook_context()
    if ctx.hook_event_name != "PreToolUse":
        return

    project_dir = resolve_project_dir(ctx)
    aidd_root = resolve_aidd_root(project_dir)
    cfg = load_config(aidd_root)
    if not cfg.get("enabled", True):
        return

    tool_name = str(ctx.raw.get("tool_name", ""))
    tool_input = ctx.raw.get("tool_input") or {}
    if not isinstance(tool_input, dict):
        return

    if tool_name == "Bash":
        cmd = tool_input.get("command")
        if isinstance(cmd, str) and cmd.strip():
            manual_preflight_decision = manual_preflight_bash_decision(
                command=cmd,
                project_dir=project_dir,
                aidd_root=aidd_root,
            )
            if manual_preflight_decision:
                pretooluse_decision(
                    permission_decision=manual_preflight_decision["decision"],
                    reason=manual_preflight_decision["reason"],
                    system_message=manual_preflight_decision["system_message"],
                )
                return
            rg_decision = rg_fallback_decision(project_dir, aidd_root, tool_input)
            if rg_decision:
                pretooluse_decision(
                    permission_decision=rg_decision["decision"],
                    reason=rg_decision["reason"],
                    system_message=rg_decision["system_message"],
                )
                return

    policy_decision = enforce_rw_policy(
        tool_name=tool_name,
        tool_input=tool_input,
        project_dir=project_dir,
        aidd_root=aidd_root,
    )
    if policy_decision:
        pretooluse_decision(
            permission_decision=policy_decision["decision"],
            reason=policy_decision["reason"],
            system_message=policy_decision["system_message"],
        )
        return

    mode = resolve_context_gc_mode(cfg)
    if mode == "off":
        return

    if mode == "light":
        if tool_name == "Bash":
            cmd = str(tool_input.get("command") or "")
            if not command_targets_aidd(cmd):
                return
        else:
            path_value = str(tool_input.get("file_path") or tool_input.get("path") or "")
            if not is_aidd_scoped(path_value, project_dir, aidd_root):
                return

    if tool_name == "Bash":
        handle_bash(project_dir, aidd_root, cfg, tool_input)
    elif tool_name == "Read":
        handle_read(project_dir, aidd_root, cfg, tool_input)


if __name__ == "__main__":
    main()
