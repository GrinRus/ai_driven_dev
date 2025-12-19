#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional


DEFAULT_CONFIG: Dict[str, Any] = {
    "enabled": True,
    "working_set": {
        "max_chars": 6000,
        "max_tasks": 25,
        "max_open_questions": 15,
        "include_git_status": True,
        "max_git_status_lines": 60,
    },
    "transcript_limits": {
        "soft_bytes": 2_500_000,
        "hard_bytes": 4_500_000,
        "hard_behavior": "block_prompt",  # block_prompt | warn_only
    },
    "bash_output_guard": {
        "enabled": True,
        "tail_lines": 200,
        "log_dir": "aidd/reports/logs",
        "only_for_regex": r"(docker\s+logs|kubectl\s+logs|journalctl|gradlew|mvn|npm|pnpm|pytest|go\s+test|cat\s+)",
        "skip_if_regex": r"(--tail\s+|\|\s*tail\b|>\s*\S+|2>\s*\S+|--quiet\b|--silent\b)",
    },
    "read_guard": {
        "enabled": True,
        "max_bytes": 200_000,
        "ask_instead_of_deny": True,
    },
}


@dataclass(frozen=True)
class HookContext:
    hook_event_name: str
    session_id: str
    transcript_path: Optional[str]
    cwd: Optional[str]
    permission_mode: Optional[str]
    raw: Dict[str, Any]


def _read_stdin_json() -> Dict[str, Any]:
    raw = sys.stdin.read()
    if not raw.strip():
        return {}
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        print("Invalid JSON on stdin for hook", file=sys.stderr)
        return {}


def read_hook_context() -> HookContext:
    data = _read_stdin_json()
    return HookContext(
        hook_event_name=str(data.get("hook_event_name", "")),
        session_id=str(data.get("session_id", "")),
        transcript_path=data.get("transcript_path"),
        cwd=data.get("cwd"),
        permission_mode=data.get("permission_mode"),
        raw=data,
    )


def resolve_project_dir(ctx: HookContext) -> Path:
    env = os.environ.get("CLAUDE_PROJECT_DIR")
    if env:
        return Path(env).expanduser().resolve()
    if ctx.cwd:
        return Path(ctx.cwd).expanduser().resolve()
    return Path.cwd().resolve()


def resolve_aidd_root(project_dir: Path) -> Optional[Path]:
    candidates = [
        os.environ.get("AIDD_ROOT"),
        os.environ.get("CLAUDE_PLUGIN_ROOT"),
        str(project_dir / "aidd"),
        str(project_dir),
        str(project_dir.parent / "aidd"),
    ]
    for c in candidates:
        if not c:
            continue
        p = Path(c).expanduser().resolve()
        if (p / "docs").is_dir() and (p / "config").is_dir():
            return p
    return None


def load_config(aidd_root: Optional[Path]) -> Dict[str, Any]:
    cfg = json.loads(json.dumps(DEFAULT_CONFIG))
    if not aidd_root:
        return cfg

    path = aidd_root / "config" / "context_gc.json"
    if not path.exists():
        return cfg

    try:
        user_cfg = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"Failed to read {path}: {exc}", file=sys.stderr)
        return cfg

    def deep_merge(dst: Dict[str, Any], src: Dict[str, Any]) -> Dict[str, Any]:
        for key, value in src.items():
            if isinstance(value, dict) and isinstance(dst.get(key), dict):
                dst[key] = deep_merge(dict(dst[key]), value)
            else:
                dst[key] = value
        return dst

    return deep_merge(cfg, user_cfg)


def json_out(payload: Dict[str, Any]) -> None:
    sys.stdout.write(json.dumps(payload, ensure_ascii=False))
    sys.stdout.write("\n")


def sessionstart_additional_context(text: str, system_message: Optional[str] = None) -> None:
    payload: Dict[str, Any] = {
        "suppressOutput": True,
        "hookSpecificOutput": {
            "hookEventName": "SessionStart",
            "additionalContext": text,
        },
    }
    if system_message:
        payload["systemMessage"] = system_message
    json_out(payload)


def userprompt_block(reason: str, system_message: Optional[str] = None) -> None:
    payload: Dict[str, Any] = {
        "suppressOutput": True,
        "decision": "block",
        "reason": reason,
        "hookSpecificOutput": {
            "hookEventName": "UserPromptSubmit",
        },
    }
    if system_message:
        payload["systemMessage"] = system_message
    json_out(payload)


def pretooluse_decision(
    permission_decision: str,
    reason: str,
    updated_input: Optional[Dict[str, Any]] = None,
    system_message: Optional[str] = None,
) -> None:
    payload: Dict[str, Any] = {
        "suppressOutput": True,
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": permission_decision,
            "permissionDecisionReason": reason,
        },
    }
    if updated_input is not None:
        payload["hookSpecificOutput"]["updatedInput"] = updated_input
    if system_message:
        payload["systemMessage"] = system_message
    json_out(payload)


def stat_file_bytes(path_str: Optional[str]) -> Optional[int]:
    if not path_str:
        return None
    try:
        return Path(path_str).expanduser().stat().st_size
    except Exception:
        return None
