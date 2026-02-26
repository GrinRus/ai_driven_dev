from __future__ import annotations

import re
import shlex
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from hooks.context_gc.prompt_injection import prompt_injection_guard_message
from hooks.context_gc.rate_limit import resolve_log_dir, should_rate_limit
from hooks.hooklib import pretooluse_decision

_RG_COMMAND_RE = re.compile(r"(?<![A-Za-z0-9_./-])rg(?:\s|$)")
_SHELL_OPERATOR_TOKENS = {";", "&&", "||", "|", "|&", ">", ">>", "<", "<<"}


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


def is_aidd_scoped(path_value: str, project_dir: Path, aidd_root: Optional[Path]) -> bool:
    if not path_value:
        return False
    try:
        raw_path = Path(path_value)
    except Exception:
        return False
    if not raw_path.is_absolute():
        raw_path = (project_dir / raw_path).resolve()
    if aidd_root:
        try:
            rel = raw_path.resolve().relative_to(aidd_root.resolve()).as_posix()
        except Exception:
            rel = ""
        if rel:
            return rel.startswith(("docs/", "reports/", "config/", ".cache/"))
    text = raw_path.as_posix()
    return "/aidd/" in text or text.endswith("/aidd") or text.startswith("aidd/")


def command_targets_aidd(command: str) -> bool:
    lowered = command.lower()
    return any(token in lowered for token in ("aidd/", "docs/", "reports/", "config/", ".cache/"))


def _resolve_command_binary(command: str) -> str:
    text = str(command or "").strip()
    if not text:
        return ""
    try:
        tokens = shlex.split(text)
    except ValueError:
        return ""
    if not tokens:
        return ""
    idx = 0
    # Prefix assignments: VAR=value rg ...
    while idx < len(tokens) and "=" in tokens[idx] and not tokens[idx].startswith("-"):
        idx += 1
    # env wrapper: env VAR=value rg ...
    if idx < len(tokens) and Path(tokens[idx]).name.lower() == "env":
        idx += 1
        while idx < len(tokens) and tokens[idx].startswith("-"):
            idx += 1
        while idx < len(tokens) and "=" in tokens[idx] and not tokens[idx].startswith("-"):
            idx += 1
    # command wrapper: command rg ...
    if idx < len(tokens) and Path(tokens[idx]).name.lower() == "command":
        idx += 1
        while idx < len(tokens) and tokens[idx].startswith("-"):
            if tokens[idx] == "--":
                idx += 1
                break
            option = tokens[idx]
            option_chars = option[1:] if option.startswith("-") else ""
            if "v" in option_chars or "V" in option_chars:
                # `command -v/-V ...` is lookup mode, not command execution.
                return ""
            idx += 1
    if idx >= len(tokens):
        return ""
    return Path(tokens[idx]).name.lower()


def _contains_unquoted_shell_operator(command: str) -> bool:
    text = str(command or "")
    if not text:
        return False
    in_single = False
    in_double = False
    escaped = False
    idx = 0
    operators = ("&&", "||", "|&", ">>", "<<", ";", "|", ">", "<")
    while idx < len(text):
        ch = text[idx]
        if escaped:
            escaped = False
            idx += 1
            continue
        if ch == "\\" and not in_single:
            escaped = True
            idx += 1
            continue
        if ch == "'" and not in_double:
            in_single = not in_single
            idx += 1
            continue
        if ch == '"' and not in_single:
            in_double = not in_double
            idx += 1
            continue
        if not in_single and not in_double:
            if ch == "\n":
                return True
            for op in operators:
                if text.startswith(op, idx):
                    return True
        idx += 1
    return False


def is_rg_command(command: str) -> bool:
    text = str(command or "").strip()
    if not text:
        return False
    binary = _resolve_command_binary(text)
    if binary in {"rg", "rg.exe"}:
        return True
    try:
        tokens = shlex.split(text)
    except ValueError:
        # Fall back to regex only when shell parsing fails.
        return bool(_RG_COMMAND_RE.search(text))
    # For shell-chains like `... | rg ...`, route to rg guard.
    if _contains_unquoted_shell_operator(text):
        return bool(_RG_COMMAND_RE.search(text))
    if any(token in _SHELL_OPERATOR_TOKENS for token in tokens):
        return bool(_RG_COMMAND_RE.search(text))
    return False


def handle_bash(project_dir: Path, aidd_root: Optional[Path], cfg: Dict[str, Any], tool_input: Dict[str, Any]) -> None:
    cmd = tool_input.get("command")
    if not isinstance(cmd, str) or not cmd.strip():
        return

    injection_message = prompt_injection_guard_message(
        cfg,
        project_dir,
        aidd_root,
        command=cmd,
    )

    dangerous_guard = cfg.get("dangerous_bash_guard", {})
    if _handle_dangerous_bash(cmd, dangerous_guard):
        return

    guard = cfg.get("bash_output_guard", {})
    if not guard.get("enabled", True):
        if injection_message:
            pretooluse_decision(
                permission_decision="allow",
                reason="Context GC: prompt-injection guard for dependency command.",
                system_message=injection_message,
            )
        return

    only_for = re.compile(str(guard.get("only_for_regex", ""))) if guard.get("only_for_regex") else None
    skip_if = re.compile(str(guard.get("skip_if_regex", ""))) if guard.get("skip_if_regex") else None

    if only_for and not only_for.search(cmd):
        if injection_message:
            pretooluse_decision(
                permission_decision="allow",
                reason="Context GC: prompt-injection guard for dependency command.",
                system_message=injection_message,
            )
        return
    if skip_if and skip_if.search(cmd):
        if injection_message:
            pretooluse_decision(
                permission_decision="allow",
                reason="Context GC: prompt-injection guard for dependency command.",
                system_message=injection_message,
            )
        return

    if should_rate_limit(guard, project_dir, aidd_root, "bash_output"):
        if injection_message:
            pretooluse_decision(
                permission_decision="allow",
                reason="Context GC: prompt-injection guard for dependency command.",
                system_message=injection_message,
            )
        return

    tail_lines = int(guard.get("tail_lines", 200))
    log_dir_raw = str(guard.get("log_dir", "aidd/reports/logs"))
    log_dir = resolve_log_dir(project_dir, aidd_root, log_dir_raw)
    updated_cmd = _wrap_with_log_and_tail(log_dir, tail_lines, cmd)

    system_message = (
        "Context GC applied: large-output command wrapped "
        f"(full output saved under {log_dir_raw})."
    )
    if injection_message:
        system_message = f"{system_message}\n{injection_message}"

    pretooluse_decision(
        permission_decision="allow",
        reason="Context GC: wrap to store full output + keep only tail in chat.",
        updated_input={"command": updated_cmd},
        system_message=system_message,
    )
