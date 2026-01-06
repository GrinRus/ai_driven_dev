#!/usr/bin/env python3
from __future__ import annotations

import re
import shlex
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from .hooklib import load_config, pretooluse_decision, read_hook_context, resolve_aidd_root, resolve_project_dir


def _resolve_log_dir(project_dir: Path, aidd_root: Optional[Path], rel_log_dir: str) -> Path:
    candidate = Path(rel_log_dir)
    if candidate.is_absolute():
        return candidate
    if rel_log_dir.startswith("aidd/"):
        if aidd_root and aidd_root.name == "aidd":
            return aidd_root.parent / candidate
        return project_dir / candidate
    if aidd_root:
        return aidd_root / candidate
    return project_dir / candidate


def _wrap_with_log_and_tail(log_dir: Path, tail_lines: int, original_cmd: str) -> str:
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    log_path = log_dir / f"bash-{ts}.log"

    wrapped = (
        f"mkdir -p {shlex.quote(str(log_dir))}; "
        f"LOG_FILE={shlex.quote(str(log_path))}; "
        f"({original_cmd}) >\"$LOG_FILE\" 2>&1; status=$?; "
        f"echo \"\"; echo \"[Context GC] Full output saved to: $LOG_FILE\"; "
        f"echo \"[Context GC] Showing last {int(tail_lines)} lines:\"; "
        f"tail -n {int(tail_lines)} \"$LOG_FILE\"; "
        f"exit $status"
    )
    return f"bash -lc {shlex.quote(wrapped)}"


def _handle_dangerous_bash(cmd: str, guard: Dict[str, Any]) -> bool:
    if not guard.get("enabled", True):
        return False

    patterns = guard.get("patterns") or []
    if isinstance(patterns, str):
        patterns = [patterns]
    if not isinstance(patterns, (list, tuple)):
        return False

    for raw in patterns:
        pattern = str(raw).strip()
        if not pattern:
            continue
        try:
            if not re.search(pattern, cmd):
                continue
        except re.error:
            continue

        mode = str(guard.get("mode", "ask")).strip().lower()
        decision = "deny" if mode == "deny" else "ask"
        pretooluse_decision(
            permission_decision=decision,
            reason="Context GC: detected potentially destructive Bash command.",
            system_message=(
                "Context GC: detected potentially destructive Bash command. "
                "Confirm explicitly if this is intended."
            ),
        )
        return True

    return False


def _should_rate_limit(
    guard: Dict[str, Any],
    project_dir: Path,
    aidd_root: Optional[Path],
    guard_name: str,
) -> bool:
    min_interval = guard.get("min_interval_seconds", 0)
    try:
        min_interval = int(min_interval)
    except (TypeError, ValueError):
        min_interval = 0
    if min_interval <= 0:
        return False

    log_dir_raw = str(guard.get("log_dir", "aidd/reports/logs"))
    log_dir = _resolve_log_dir(project_dir, aidd_root, log_dir_raw)
    stamp_path = log_dir / f".context-gc-{guard_name}.stamp"

    try:
        last_seen = float(stamp_path.read_text(encoding="utf-8").strip() or 0)
    except Exception:
        last_seen = 0.0

    now = time.time()
    if last_seen and (now - last_seen) < min_interval:
        return True

    try:
        log_dir.mkdir(parents=True, exist_ok=True)
        stamp_path.write_text(str(now), encoding="utf-8")
    except Exception:
        # If we can't persist the stamp, keep running the guard.
        return False

    return False


def handle_bash(project_dir: Path, aidd_root: Optional[Path], cfg: Dict[str, Any], tool_input: Dict[str, Any]) -> None:
    cmd = tool_input.get("command")
    if not isinstance(cmd, str) or not cmd.strip():
        return

    dangerous_guard = cfg.get("dangerous_bash_guard", {})
    if _handle_dangerous_bash(cmd, dangerous_guard):
        return

    guard = cfg.get("bash_output_guard", {})
    if not guard.get("enabled", True):
        return

    only_for = re.compile(str(guard.get("only_for_regex", ""))) if guard.get("only_for_regex") else None
    skip_if = re.compile(str(guard.get("skip_if_regex", ""))) if guard.get("skip_if_regex") else None

    if only_for and not only_for.search(cmd):
        return
    if skip_if and skip_if.search(cmd):
        return

    if _should_rate_limit(guard, project_dir, aidd_root, "bash_output"):
        return

    tail_lines = int(guard.get("tail_lines", 200))
    log_dir_raw = str(guard.get("log_dir", "aidd/reports/logs"))
    log_dir = _resolve_log_dir(project_dir, aidd_root, log_dir_raw)
    updated_cmd = _wrap_with_log_and_tail(log_dir, tail_lines, cmd)

    pretooluse_decision(
        permission_decision="allow",
        reason="Context GC: wrap to store full output + keep only tail in chat.",
        updated_input={"command": updated_cmd},
        system_message=(
            "Context GC applied: large-output command wrapped "
            f"(full output saved under {log_dir_raw})."
        ),
    )


def handle_read(project_dir: Path, aidd_root: Optional[Path], cfg: Dict[str, Any], tool_input: Dict[str, Any]) -> None:
    guard = cfg.get("read_guard", {})
    if not guard.get("enabled", True):
        return

    file_path = tool_input.get("file_path") or tool_input.get("path") or tool_input.get("filename")
    if not isinstance(file_path, str) or not file_path:
        return

    path = Path(file_path)
    if not path.is_absolute():
        candidates: list[Path] = []
        if path.as_posix().startswith("aidd/"):
            if aidd_root and aidd_root.name == "aidd":
                candidates.append(aidd_root.parent / path)
            else:
                candidates.append(project_dir / path)
        else:
            candidates.append(project_dir / path)
            if aidd_root:
                candidates.append(aidd_root / path)
        resolved = None
        for candidate in candidates:
            try:
                if candidate.exists():
                    resolved = candidate
                    break
            except Exception:
                continue
        path = (resolved or candidates[0]).resolve()

    try:
        size = path.stat().st_size
    except Exception:
        return

    max_bytes = int(guard.get("max_bytes", 200_000))
    if size <= max_bytes:
        return
    if _should_rate_limit(guard, project_dir, aidd_root, "read_guard"):
        return

    ask = bool(guard.get("ask_instead_of_deny", True))
    decision = "ask" if ask else "deny"

    pretooluse_decision(
        permission_decision=decision,
        reason=(
            f"Context GC: file is large ({size} bytes). "
            "Reading it fully may bloat the context. Prefer search/snippets."
        ),
        system_message=f"Context GC: {path.name} is large ({size} bytes). Prefer searching/snippets over full Read.",
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
        handle_bash(project_dir, aidd_root, cfg, tool_input)
    elif tool_name == "Read":
        handle_read(project_dir, aidd_root, cfg, tool_input)


if __name__ == "__main__":
    main()
