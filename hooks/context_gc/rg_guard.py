from __future__ import annotations

import datetime as dt
import json
import shlex
from pathlib import Path
from typing import Any, Dict, Optional

from aidd_runtime import context_quality
from aidd_runtime import memory_common
from aidd_runtime import stage_lexicon
from hooks.context_gc.bash_guard import is_rg_command
from hooks.context_gc.rw_policy import policy_state
from hooks.hooklib import resolve_hooks_mode


def _load_memory_gate(aidd_root: Path) -> Dict[str, Any]:
    gate_path = aidd_root / "config" / "gates.json"
    payload: Dict[str, Any] = {}
    try:
        parsed = json.loads(gate_path.read_text(encoding="utf-8"))
        if isinstance(parsed, dict):
            payload = parsed
    except Exception:
        payload = {}
    memory_cfg = payload.get("memory") if isinstance(payload.get("memory"), dict) else {}

    raw_mode = str(memory_cfg.get("slice_enforcement") or "warn").strip().lower()
    mode = raw_mode if raw_mode in {"off", "warn", "hard"} else "warn"

    raw_rg_policy = str(memory_cfg.get("rg_policy") or "controlled_fallback").strip().lower()
    rg_policy = raw_rg_policy if raw_rg_policy in {"free", "controlled_fallback", "deny"} else "controlled_fallback"

    raw_stages = memory_cfg.get("enforce_stages")
    if isinstance(raw_stages, list):
        stages = [
            stage_lexicon.resolve_stage_name(str(item).strip())
            for item in raw_stages
            if str(item).strip()
        ]
        stages = [stage for stage in stages if stage]
    else:
        stages = ["research", "plan", "review-spec", "implement", "review", "qa"]

    try:
        max_age = max(1, int(memory_cfg.get("max_slice_age_minutes") or 240))
    except (TypeError, ValueError):
        max_age = 240

    return {
        "mode": mode,
        "rg_policy": rg_policy,
        "enforce_stages": stages,
        "max_slice_age_minutes": max_age,
    }


def _parse_timestamp(raw: object) -> Optional[dt.datetime]:
    text = str(raw or "").strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = dt.datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt.timezone.utc)
    return parsed.astimezone(dt.timezone.utc)


def _is_safe_rg_command(command: str) -> bool:
    text = str(command or "").strip()
    if not text:
        return False
    # Prevent shell-chain/redirect/substitution bypass for rg allow-path.
    if _contains_shell_control_operator(text):
        return False
    try:
        tokens = shlex.split(text)
    except ValueError:
        return False
    if not tokens:
        return False
    idx = _resolve_command_binary_index(tokens)
    if idx < 0:
        return False
    binary = Path(tokens[idx]).name.lower()
    if binary not in {"rg", "rg.exe"}:
        return False
    tail_tokens = tokens[idx + 1 :]
    if any(Path(token).name == "tee" for token in tail_tokens):
        return False
    return True


def _resolve_command_binary_index(tokens: list[str]) -> int:
    if not tokens:
        return -1
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
                # `command -v/-V ...` only queries command path/version.
                return -1
            idx += 1
    if idx >= len(tokens):
        return -1
    return idx


def _contains_shell_control_operator(command: str) -> bool:
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
        if ch == "\n" and not in_single and not in_double:
            return True
        # Command substitution is active outside single quotes (also inside double quotes).
        if not in_single:
            if ch == "`":
                return True
            if text.startswith("$(", idx):
                return True
        if not in_single and not in_double:
            for op in operators:
                if text.startswith(op, idx):
                    return True
        idx += 1
    return False


def _manifest_age_minutes(path: Path) -> Optional[float]:
    if not path.exists():
        return None
    payload: Dict[str, Any] = {}
    try:
        parsed = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(parsed, dict):
            payload = parsed
    except Exception:
        payload = {}
    ts = _parse_timestamp(payload.get("updated_at") or payload.get("generated_at"))
    if ts is None:
        try:
            ts = dt.datetime.fromtimestamp(path.stat().st_mtime, tz=dt.timezone.utc)
        except OSError:
            return None
    return max(0.0, (dt.datetime.now(dt.timezone.utc) - ts).total_seconds() / 60.0)


def _manifest_is_valid(path: Path) -> bool:
    if not path.exists():
        return False
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return False
    if not isinstance(payload, dict):
        return False
    return str(payload.get("schema") or "").strip() == "aidd.memory.slices.manifest.v1"


def _autoslice_hint(ticket: str, stage: str, scope_key: str) -> str:
    return (
        "python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-memory/runtime/memory_autoslice.py "
        f"--ticket {ticket} --stage {stage} --scope-key {scope_key}"
    )


def _stage_rerun_hint(ticket: str, stage: str) -> str:
    normalized = stage_lexicon.resolve_stage_name(stage)
    if normalized in {"implement", "review", "qa"}:
        return f"/feature-dev-aidd:{normalized} {ticket}"
    return f"/feature-dev-aidd:status {ticket}"


def _record_rg_metrics(aidd_root: Path, *, ticket: str, rg_without_slice: bool) -> None:
    if not ticket:
        return
    try:
        context_quality.update_from_rg_policy(
            aidd_root,
            ticket=ticket,
            rg_without_slice=rg_without_slice,
        )
    except Exception:
        return


def rg_fallback_decision(
    project_dir: Path,
    aidd_root: Optional[Path],
    tool_input: Dict[str, Any],
) -> Optional[Dict[str, str]]:
    if aidd_root is None:
        return None
    command = str(tool_input.get("command") or "").strip()
    if not command or not is_rg_command(command):
        return None
    if not _is_safe_rg_command(command):
        decision = "ask"
        # Complex shell command should be explicitly approved, especially in strict/hard modes.
        if resolve_hooks_mode() == "strict":
            decision = "deny"
        return {
            "decision": decision,
            "reason": "Context GC: complex rg shell command requires review (reason_code=rg_complex_command).",
            "system_message": (
                "Context GC: `rg` command includes shell chaining/redirects or `tee`. "
                "Run a simple `rg ...` command first, then execute follow-up steps separately."
            ),
        }

    state = policy_state(project_dir, aidd_root)
    if not state:
        return None
    ticket = str(state.get("ticket") or "").strip()
    stage = stage_lexicon.resolve_stage_name(str(state.get("stage") or "").strip())
    scope_key = str(state.get("scope_key") or "").strip()
    if not ticket or not stage:
        return None
    if not scope_key:
        scope_key = ticket

    gate = _load_memory_gate(aidd_root)
    mode = str(gate.get("mode") or "warn")
    rg_policy = str(gate.get("rg_policy") or "controlled_fallback")
    enforce_stages = {
        stage_lexicon.resolve_stage_name(str(item).strip())
        for item in (gate.get("enforce_stages") or [])
        if str(item).strip()
    }
    if mode == "off" or stage not in enforce_stages or rg_policy == "free":
        return None
    if rg_policy == "deny":
        _record_rg_metrics(aidd_root, ticket=ticket, rg_without_slice=False)
        return {
            "decision": "deny",
            "reason": "Context GC: rg is disabled by memory policy (reason_code=rg_policy_deny).",
            "system_message": (
                "Context GC: `rg` fallback is disabled (`memory.rg_policy=deny`). "
                "Use memory/pack/slice artifacts or switch policy to `controlled_fallback`."
            ),
        }
    readmap_exists = bool(state.get("readmap_exists"))
    if stage_lexicon.is_loop_stage(stage) and not readmap_exists:
        _record_rg_metrics(aidd_root, ticket=ticket, rg_without_slice=True)
        decision = "ask"
        if mode == "hard" or resolve_hooks_mode() == "strict":
            decision = "deny"
        return {
            "decision": decision,
            "reason": "Context GC: rg requires preflight readmap first (reason_code=readmap_missing).",
            "system_message": (
                "Context GC: `rg` is blocked because readmap for current loop scope is missing. "
                f"Re-run canonical stage command `{_stage_rerun_hint(ticket, stage)}` to regenerate preflight artifacts."
            ),
        }

    manifest_path = memory_common.memory_slices_manifest_path(aidd_root, ticket, stage, scope_key)
    manifest_rel = memory_common.rel_path(manifest_path, aidd_root)
    manifest_valid = _manifest_is_valid(manifest_path)
    manifest_age = _manifest_age_minutes(manifest_path) if manifest_valid else None
    max_age = int(gate.get("max_slice_age_minutes") or 240)
    manifest_fresh = manifest_valid and (manifest_age is None or manifest_age <= max_age)

    if manifest_fresh:
        _record_rg_metrics(aidd_root, ticket=ticket, rg_without_slice=False)
        return {
            "decision": "allow",
            "reason": (
                "Context GC: rg fallback allowed after fresh memory slice "
                "(reason_code=ast_index_fallback_rg)."
            ),
            "system_message": (
                f"Context GC: rg fallback allowed; fresh memory slice manifest found at `{manifest_rel}`."
            ),
        }

    _record_rg_metrics(aidd_root, ticket=ticket, rg_without_slice=True)
    decision = "ask"
    if rg_policy == "deny" or mode == "hard" or resolve_hooks_mode() == "strict":
        decision = "deny"
    stale_note = ""
    if manifest_path.exists() and not manifest_valid:
        stale_note = " Manifest is invalid."
    elif manifest_age is not None and manifest_age > max_age:
        stale_note = f" Stale manifest age={manifest_age:.1f}m max={max_age}m."
    elif not manifest_path.exists():
        stale_note = " Manifest is missing."
    return {
        "decision": decision,
        "reason": "Context GC: rg requires fresh memory slice first (reason_code=rg_without_slice).",
        "system_message": (
            "Context GC: `rg` is controlled fallback and requires a fresh memory slice manifest "
            f"for stage `{stage}` / scope `{scope_key}` at `{manifest_rel}`.{stale_note} "
            f"Next action: `{_autoslice_hint(ticket, stage, scope_key)}`."
        ),
    }
