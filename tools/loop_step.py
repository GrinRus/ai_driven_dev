#!/usr/bin/env python3
"""Execute a single loop step (implement/review)."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import shlex
import subprocess
import sys
import threading
from pathlib import Path
from typing import Dict, List, Tuple, Optional, TextIO

from tools import claude_stream_render
from tools import runtime
from tools.feature_ids import write_active_state
from tools.io_utils import dump_yaml, parse_front_matter, utc_timestamp

DONE_CODE = 0
CONTINUE_CODE = 10
BLOCKED_CODE = 20
ERROR_CODE = 30
WARN_REASON_CODES = {
    "out_of_scope_warn",
    "no_boundaries_defined_warn",
    "auto_boundary_extend_warn",
    "review_context_pack_placeholder_warn",
}
HANDOFF_QA_START = "<!-- handoff:qa start -->"
HANDOFF_QA_END = "<!-- handoff:qa end -->"
CHECKBOX_RE = re.compile(r"^\s*-\s*\[(?P<state>[ xX])\]\s+(?P<body>.+)$")
BLOCKING_PAREN_RE = re.compile(r"\(Blocking:\s*(true|false)\)", re.IGNORECASE)
BLOCKING_LINE_RE = re.compile(r"^\s*-\s*Blocking:\s*(true|false)\b", re.IGNORECASE)
SCOPE_RE = re.compile(r"\bscope\s*:\s*([A-Za-z0-9_.:=-]+)", re.IGNORECASE)
ITEM_ID_RE = re.compile(r"\bid\s*:\s*([A-Za-z0-9_.:-]+)")
STREAM_MODE_ALIASES = {
    "text-only": "text",
    "text": "text",
    "tools": "tools",
    "text+tools": "tools",
    "raw": "raw",
    "1": "text",
    "true": "text",
    "yes": "text",
}


def read_active_stage(root: Path) -> str:
    return runtime.read_active_stage(root)


def write_active_mode(root: Path, mode: str = "loop") -> None:
    docs_dir = root / "docs"
    docs_dir.mkdir(parents=True, exist_ok=True)
    (docs_dir / ".active_mode").write_text(mode + "\n", encoding="utf-8")


def write_active_stage(root: Path, stage: str) -> None:
    write_active_state(root, stage=stage)


def write_active_work_item(root: Path, work_item_key: str) -> None:
    write_active_state(root, work_item=work_item_key)


def write_active_ticket(root: Path, ticket: str) -> None:
    write_active_state(root, ticket=ticket)


def resolve_stage_scope(root: Path, ticket: str, stage: str) -> Tuple[str, str]:
    if stage in {"implement", "review"}:
        work_item_key = runtime.read_active_work_item(root)
        if not work_item_key:
            return "", ""
        if not runtime.is_valid_work_item_key(work_item_key):
            return work_item_key, ""
        return work_item_key, runtime.resolve_scope_key(work_item_key, ticket)
    return "", runtime.resolve_scope_key("", ticket)


def stage_result_path(root: Path, ticket: str, scope_key: str, stage: str) -> Path:
    return root / "reports" / "loops" / ticket / scope_key / f"stage.{stage}.result.json"


def _parse_stage_result(path: Path, stage: str) -> Tuple[Dict[str, object] | None, str]:
    if not path.exists():
        return None, "missing"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None, "invalid-json"
    if str(payload.get("schema") or "") != "aidd.stage_result.v1":
        return None, "invalid-schema"
    if str(payload.get("stage") or "").strip().lower() != stage:
        return None, "wrong-stage"
    result = str(payload.get("result") or "").strip().lower()
    if result not in {"blocked", "continue", "done"}:
        return None, "invalid-result"
    work_item_key = str(payload.get("work_item_key") or "").strip()
    if work_item_key and not runtime.is_valid_work_item_key(work_item_key):
        return None, "invalid-work-item"
    return payload, ""


def _collect_stage_result_candidates(root: Path, ticket: str, stage: str) -> List[Path]:
    base = root / "reports" / "loops" / ticket
    if not base.exists():
        return []
    return sorted(
        base.rglob(f"stage.{stage}.result.json"),
        key=lambda candidate: candidate.stat().st_mtime if candidate.exists() else 0.0,
        reverse=True,
    )


def _in_window(path: Path, *, started_at: float | None, finished_at: float | None, tolerance_seconds: float = 5.0) -> bool:
    if started_at is None or finished_at is None:
        return True
    if not path.exists():
        return False
    mtime = path.stat().st_mtime
    return (started_at - tolerance_seconds) <= mtime <= (finished_at + tolerance_seconds)


def _stage_result_diagnostics(candidates: List[Tuple[Path, str]]) -> str:
    if not candidates:
        return "candidates=none"
    parts: List[str] = []
    for path, status in candidates[:5]:
        timestamp = "n/a"
        if path.exists():
            timestamp = dt.datetime.fromtimestamp(path.stat().st_mtime, tz=dt.timezone.utc).isoformat()
        parts.append(f"{path.as_posix()}:{status}@{timestamp}")
    return "candidates=" + ", ".join(parts)


def load_stage_result(
    root: Path,
    ticket: str,
    scope_key: str,
    stage: str,
    *,
    started_at: float | None = None,
    finished_at: float | None = None,
) -> Tuple[Dict[str, object] | None, Path, str, str, str, str]:
    preferred_path = stage_result_path(root, ticket, scope_key, stage)
    preferred_payload, preferred_error = _parse_stage_result(preferred_path, stage)
    if preferred_payload is not None:
        return preferred_payload, preferred_path, "", "", "", ""

    validated: List[Tuple[Path, Dict[str, object]]] = []
    diagnostics: List[Tuple[Path, str]] = [(preferred_path, preferred_error)]
    for candidate in _collect_stage_result_candidates(root, ticket, stage):
        if candidate == preferred_path:
            continue
        payload, status = _parse_stage_result(candidate, stage)
        diagnostics.append((candidate, status))
        if payload is None:
            continue
        validated.append((candidate, payload))

    fresh = [
        (path, payload)
        for path, payload in validated
        if _in_window(path, started_at=started_at, finished_at=finished_at)
    ]
    selected_pool = fresh or validated
    if not selected_pool:
        return (
            None,
            preferred_path,
            "stage_result_missing_or_invalid",
            "",
            "",
            _stage_result_diagnostics(diagnostics),
        )

    selected_path, selected_payload = selected_pool[0]
    selected_scope = str(selected_payload.get("scope_key") or "").strip() or selected_path.parent.name
    mismatch_from = scope_key or ""
    mismatch_to = ""
    if scope_key and selected_scope and selected_scope != scope_key:
        mismatch_to = selected_scope
    return selected_payload, selected_path, "", mismatch_from, mismatch_to, _stage_result_diagnostics(diagnostics)


def normalize_stage_result(result: str, reason_code: str) -> str:
    if result == "blocked" and reason_code in WARN_REASON_CODES:
        return "continue"
    return result


def runner_supports_flag(command: str, flag: str) -> bool:
    try:
        proc = subprocess.run(
            [command, "--help"],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
        )
    except OSError:
        return False
    if proc.returncode != 0:
        return False
    return flag in (proc.stdout or "")


def _strip_flag_with_value(tokens: List[str], flag: str) -> Tuple[List[str], bool]:
    cleaned: List[str] = []
    stripped = False
    skip_next = False
    for token in tokens:
        if skip_next:
            skip_next = False
            stripped = True
            continue
        if token == flag:
            skip_next = True
            stripped = True
            continue
        if token.startswith(flag + "="):
            stripped = True
            continue
        cleaned.append(token)
    return cleaned, stripped


def inject_plugin_flags(tokens: List[str], plugin_root: Path) -> Tuple[List[str], List[str]]:
    notices: List[str] = []
    updated, stripped_plugin = _strip_flag_with_value(tokens, "--plugin-dir")
    updated, stripped_add = _strip_flag_with_value(updated, "--add-dir")
    if stripped_plugin or stripped_add:
        notices.append("runner plugin flags replaced with CLAUDE_PLUGIN_ROOT")
    updated.extend(["--plugin-dir", str(plugin_root), "--add-dir", str(plugin_root)])
    return updated, notices


def validate_command_available(plugin_root: Path, stage: str) -> Tuple[bool, str, str]:
    if not plugin_root.exists():
        return False, f"plugin root not found: {plugin_root}", "plugin_root_missing"
    skill_path = plugin_root / "skills" / stage / "SKILL.md"
    if skill_path.exists():
        return True, "", ""
    command_path = plugin_root / "commands" / f"{stage}.md"
    if command_path.exists():
        return True, "", ""
    return False, f"command not found: /feature-dev-aidd:{stage}", "command_unavailable"
    return True, "", ""


def resolve_stream_mode(raw: Optional[str]) -> str:
    if raw is None:
        raw = os.environ.get("AIDD_AGENT_STREAM_MODE", "")
    value = str(raw or "").strip().lower()
    if not value:
        return ""
    return STREAM_MODE_ALIASES.get(value, "text")


def review_pack_v2_required(root: Path) -> bool:
    config = runtime.load_gates_config(root)
    if not isinstance(config, dict):
        return False
    raw = config.get("review_pack_v2_required")
    if raw is None:
        return False
    if isinstance(raw, str):
        return raw.strip().lower() in {"1", "true", "yes", "block", "strict"}
    return bool(raw)


def _parse_bool(value: str | None) -> bool | None:
    if value is None:
        return None
    raw = value.strip().lower()
    if raw in {"true", "yes", "1"}:
        return True
    if raw in {"false", "no", "0"}:
        return False
    return None


def _normalize_scope(value: str) -> str:
    cleaned = value.strip().strip(")").strip()
    return cleaned


def _is_valid_work_item_key(value: str) -> bool:
    return runtime.is_valid_work_item_key(value)


def _extract_work_item_key(lines: List[str]) -> str:
    scope = ""
    for line in lines:
        match = SCOPE_RE.search(line)
        if match:
            scope = _normalize_scope(match.group(1))
            if scope:
                break
    if not scope:
        return ""
    return scope if _is_valid_work_item_key(scope) else ""


def _extract_blocking_flag(lines: List[str]) -> bool | None:
    for line in lines:
        match = BLOCKING_PAREN_RE.search(line)
        if match:
            return _parse_bool(match.group(1))
        match = BLOCKING_LINE_RE.search(line)
        if match:
            return _parse_bool(match.group(1))
    return None


def _extract_item_id(lines: List[str]) -> str:
    for line in lines:
        match = ITEM_ID_RE.search(line)
        if match:
            return match.group(1).strip()
    return ""


def _extract_checkbox_state(line: str) -> str:
    match = CHECKBOX_RE.match(line)
    if not match:
        return ""
    return match.group("state").strip().lower()


def _parse_qa_handoff_candidates(lines: List[str]) -> List[Tuple[str, str]]:
    candidates: List[Tuple[str, str]] = []
    in_handoff = False
    current: List[str] = []

    def flush(block: List[str]) -> None:
        if not block:
            return
        state = _extract_checkbox_state(block[0])
        if state in {"x"}:
            return
        blocking = _extract_blocking_flag(block)
        if blocking is not True:
            return
        work_item_key = _extract_work_item_key(block)
        if not work_item_key:
            return
        item_id = _extract_item_id(block)
        label = item_id or work_item_key
        candidates.append((work_item_key, label))

    for raw in lines:
        stripped = raw.strip()
        if stripped == HANDOFF_QA_START:
            in_handoff = True
            current = []
            continue
        if stripped == HANDOFF_QA_END:
            flush(current)
            current = []
            in_handoff = False
            continue
        if not in_handoff:
            continue
        if CHECKBOX_RE.match(raw):
            flush(current)
            current = [raw]
            continue
        if current:
            current.append(raw)
    flush(current)
    return candidates


def _auto_repair_enabled(root: Path) -> bool:
    config = runtime.load_gates_config(root)
    if not isinstance(config, dict):
        return False
    loop_cfg = config.get("loop")
    if not isinstance(loop_cfg, dict):
        loop_cfg = {}
    raw = loop_cfg.get("auto_repair_from_qa")
    if isinstance(raw, str):
        return raw.strip().lower() in {"1", "true", "yes"}
    return bool(raw)


def _resolve_qa_repair_mode(requested: str | None, root: Path) -> Tuple[str, bool]:
    if requested:
        return requested, True
    if _auto_repair_enabled(root):
        return "auto", False
    return "", False


def _select_qa_repair_work_item(
    *,
    tasklist_lines: List[str],
    explicit: str,
    select_handoff: bool,
    mode: str,
) -> Tuple[str, str, str, List[str]]:
    if explicit:
        if not _is_valid_work_item_key(explicit):
            return "", "qa_repair_invalid_work_item", "work_item_key must start with iteration_id= or id=", []
        return explicit, "", "", []
    use_auto = select_handoff or mode == "auto"
    if not use_auto:
        return "", "qa_repair_missing_work_item", "work_item_key required for qa repair", []
    candidates = _parse_qa_handoff_candidates(tasklist_lines)
    if not candidates:
        return "", "qa_repair_no_handoff", "no blocking QA handoff candidates", []
    if len(candidates) > 1:
        labels = [label for _, label in candidates]
        return (
            "",
            "qa_repair_multiple_handoffs",
            "multiple blocking QA handoff candidates",
            labels,
        )
    work_item_key, label = candidates[0]
    return work_item_key, "", "", [label]


def _maybe_append_qa_repair_event(
    root: Path,
    *,
    ticket: str,
    slug_hint: str,
    work_item_key: str,
    mode: str,
) -> None:
    from tools.reports import events as _events

    path = _events.events_path(root, ticket)
    if not path.exists():
        return
    _events.append_event(
        root,
        ticket=ticket,
        slug_hint=slug_hint,
        event_type="qa_repair_requested",
        status="blocked",
        details={"work_item_key": work_item_key, "mode": mode},
        source="loop-step",
    )


def parse_timestamp(value: str) -> dt.datetime | None:
    if not value:
        return None
    raw = value.strip()
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    try:
        return dt.datetime.fromisoformat(raw)
    except ValueError:
        return None


def resolve_review_report_path(root: Path, ticket: str, slug_hint: str, scope_key: str) -> Path:
    template = runtime.review_report_template(root)
    rel_text = (
        str(template)
        .replace("{ticket}", ticket)
        .replace("{slug}", slug_hint or ticket)
        .replace("{scope_key}", scope_key)
    )
    return runtime.resolve_path_for_target(Path(rel_text), root)


def _maybe_regen_review_pack(
    root: Path,
    *,
    ticket: str,
    slug_hint: str,
    scope_key: str,
) -> Tuple[bool, str]:
    report_path = resolve_review_report_path(root, ticket, slug_hint, scope_key)
    if not report_path.exists():
        return False, "review report missing"
    loop_pack_path = root / "reports" / "loops" / ticket / f"{scope_key}.loop.pack.md"
    if not loop_pack_path.exists():
        return False, "loop pack missing"
    try:
        from tools import review_pack as review_pack_module

        args = ["--ticket", ticket]
        if slug_hint:
            args.extend(["--slug-hint", slug_hint])
        import io
        from contextlib import redirect_stderr, redirect_stdout

        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            review_pack_module.main(args)
    except Exception as exc:
        return False, f"review pack regen failed: {exc}"
    pack_path = root / "reports" / "loops" / ticket / scope_key / "review.latest.pack.md"
    if not pack_path.exists():
        return False, "review pack missing"
    return True, ""


def validate_review_pack(
    root: Path,
    *,
    ticket: str,
    slug_hint: str,
    scope_key: str,
) -> Tuple[bool, str, str]:
    pack_path = root / "reports" / "loops" / ticket / scope_key / "review.latest.pack.md"
    if not pack_path.exists():
        ok, regen_message = _maybe_regen_review_pack(
            root,
            ticket=ticket,
            slug_hint=slug_hint,
            scope_key=scope_key,
        )
        if ok:
            pack_path = root / "reports" / "loops" / ticket / scope_key / "review.latest.pack.md"
        else:
            reason = regen_message or "review pack missing"
            missing_reasons = {
                "review report missing",
                "loop pack missing",
                "review pack missing",
            }
            code = "review_pack_missing" if reason in missing_reasons else "review_pack_regen_failed"
            return False, reason, code
    lines = pack_path.read_text(encoding="utf-8").splitlines()
    front = parse_front_matter(lines)
    schema = str(front.get("schema") or "").strip()
    if schema not in {"aidd.review_pack.v1", "aidd.review_pack.v2"}:
        return False, "review pack schema invalid", "review_pack_invalid_schema"
    if schema == "aidd.review_pack.v1" and review_pack_v2_required(root):
        return False, "review pack v2 required", "review_pack_v2_required"
    if schema == "aidd.review_pack.v1":
        rel_path = runtime.rel_path(pack_path, root)
        print(f"[loop-step] WARN: review pack v1 in use ({rel_path})", file=sys.stderr)
    verdict = str(front.get("verdict") or "").strip().upper()
    if verdict == "REVISE":
        fix_plan_path = root / "reports" / "loops" / ticket / scope_key / "review.fix_plan.json"
        if not fix_plan_path.exists():
            return False, "review fix plan missing", "review_fix_plan_missing"
    report_path = resolve_review_report_path(root, ticket, slug_hint, scope_key)
    if report_path.exists():
        try:
            report = json.loads(report_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            report = {}
        pack_updated = parse_timestamp(str(front.get("updated_at") or ""))
        report_updated = parse_timestamp(str(report.get("updated_at") or report.get("generated_at") or ""))
        if pack_updated and report_updated and pack_updated < report_updated:
            ok, regen_message = _maybe_regen_review_pack(
                root,
                ticket=ticket,
                slug_hint=slug_hint,
                scope_key=scope_key,
            )
            if not ok:
                return False, regen_message or "review pack stale", "review_pack_stale"
            try:
                refreshed = pack_path.read_text(encoding="utf-8").splitlines()
                front = parse_front_matter(refreshed)
            except OSError:
                front = front
            pack_updated = parse_timestamp(str(front.get("updated_at") or ""))
            if pack_updated and report_updated and pack_updated < report_updated:
                return False, "review pack stale", "review_pack_stale"
    return True, "", ""


def resolve_runner(args_runner: str | None, plugin_root: Path) -> Tuple[List[str], str, str]:
    raw = args_runner or os.environ.get("AIDD_LOOP_RUNNER") or "claude"
    tokens = shlex.split(raw) if raw.strip() else ["claude"]
    notices: List[str] = []
    if "-p" in tokens:
        tokens = [token for token in tokens if token != "-p"]
        notices.append("runner flag -p dropped; loop-step adds -p with slash command")
    if "--no-session-persistence" in tokens:
        if not runner_supports_flag(tokens[0], "--no-session-persistence"):
            tokens = [token for token in tokens if token != "--no-session-persistence"]
            notices.append("runner flag --no-session-persistence unsupported; dropped")
    tokens, flag_notices = inject_plugin_flags(tokens, plugin_root)
    notices.extend(flag_notices)
    return tokens, raw, "; ".join(notices)


def is_skill_first(plugin_root: Path) -> bool:
    core = plugin_root / "skills" / "aidd-core" / "SKILL.md"
    if not core.exists():
        return False
    for stage in ("implement", "review", "qa"):
        if (plugin_root / "skills" / stage / "SKILL.md").exists():
            return True
    return False


def resolve_wrapper_plugin_root(plugin_root: Path) -> Path:
    for env_name in ("AIDD_STAGE_WRAPPERS_ROOT", "AIDD_WRAPPER_PLUGIN_ROOT"):
        raw = os.environ.get(env_name, "").strip()
        if not raw:
            continue
        candidate = Path(raw).expanduser().resolve()
        if (candidate / "skills").exists():
            return candidate
        print(
            f"[loop-step] WARN: {env_name}={candidate} has no skills/; using {plugin_root}",
            file=sys.stderr,
        )
    return plugin_root


def should_run_wrappers(stage: str, runner_raw: str, plugin_root: Path) -> bool:
    if stage not in {"implement", "review", "qa"}:
        return False
    if os.environ.get("AIDD_SKIP_STAGE_WRAPPERS", "").strip() == "1":
        return False
    if not is_skill_first(plugin_root):
        return False
    if os.environ.get("AIDD_FORCE_STAGE_WRAPPERS", "").strip() == "1":
        return True
    raw = (runner_raw or "").strip()
    if not raw:
        return True
    tokens = shlex.split(raw)
    if not tokens:
        return True
    return Path(tokens[0]).name == "claude"


def _parse_wrapper_output(stdout: str) -> Dict[str, str]:
    payload: Dict[str, str] = {}
    for raw in stdout.splitlines():
        line = raw.strip()
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not key or not value:
            continue
        payload[key] = value
    return payload


def run_stage_wrapper(
    *,
    plugin_root: Path,
    workspace_root: Path,
    stage: str,
    kind: str,
    ticket: str,
    scope_key: str,
    work_item_key: str,
    actions_path: str = "",
    result: str = "",
    verdict: str = "",
) -> Tuple[bool, Dict[str, str], str]:
    script = plugin_root / "skills" / stage / "scripts" / f"{kind}.sh"
    if not script.exists():
        return False, {}, f"wrapper script missing: {script}"
    cmd = [
        str(script),
        "--ticket",
        ticket,
        "--scope-key",
        scope_key,
        "--work-item-key",
        work_item_key,
        "--stage",
        stage,
    ]
    if actions_path:
        cmd.extend(["--actions", actions_path])
    if kind == "postflight" and result:
        cmd.extend(["--result", result])
    if kind == "postflight" and verdict:
        cmd.extend(["--verdict", verdict])
    proc = subprocess.run(
        cmd,
        cwd=workspace_root,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    parsed = _parse_wrapper_output(proc.stdout or "")
    if proc.returncode != 0:
        stderr = (proc.stderr or "").strip()
        stdout = (proc.stdout or "").strip()
        details = stderr or stdout or f"exit={proc.returncode}"
        return False, parsed, f"{kind} wrapper failed: {details}"
    return True, parsed, ""


def build_command(stage: str, ticket: str) -> List[str]:
    command = f"/feature-dev-aidd:{stage} {ticket}"
    return ["-p", command]


class MultiWriter:
    def __init__(self, *streams: Optional[TextIO]) -> None:
        self._streams: List[TextIO] = [stream for stream in streams if stream is not None]

    def write(self, data: str) -> None:
        for stream in self._streams:
            stream.write(data)

    def flush(self) -> None:
        for stream in self._streams:
            stream.flush()


def _drain_stream(pipe: Optional[TextIO], writer: MultiWriter, raw_log: TextIO) -> None:
    if pipe is None:
        return
    for line in pipe:
        raw_log.write(line)
        writer.write(line)
        raw_log.flush()
        writer.flush()


def run_command(command: List[str], cwd: Path, log_path: Path) -> int:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("w", encoding="utf-8") as handle:
        result = subprocess.run(
            command,
            cwd=cwd,
            text=True,
            stdout=handle,
            stderr=subprocess.STDOUT,
        )
    return result.returncode


def run_stream_command(
    *,
    command: List[str],
    cwd: Path,
    log_path: Path,
    stream_mode: str,
    stream_jsonl_path: Path,
    stream_log_path: Path,
    output_stream: TextIO,
    header_lines: Optional[List[str]] = None,
) -> int:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    stream_jsonl_path.parent.mkdir(parents=True, exist_ok=True)
    stream_log_path.parent.mkdir(parents=True, exist_ok=True)

    with (
        log_path.open("w", encoding="utf-8") as raw_log,
        stream_jsonl_path.open("w", encoding="utf-8") as stream_jsonl,
        stream_log_path.open("w", encoding="utf-8") as stream_log,
    ):
        writer = MultiWriter(stream_log, output_stream)
        if header_lines:
            for line in header_lines:
                writer.write(line + "\n")
            writer.flush()
        if stream_mode == "raw":
            writer.write("[stream] WARN: raw mode enabled; JSON events will be printed.\n")
            writer.flush()
        proc = subprocess.Popen(
            command,
            cwd=cwd,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            bufsize=1,
        )
        drain_thread = threading.Thread(
            target=_drain_stream,
            args=(proc.stderr, writer, raw_log),
            daemon=True,
        )
        drain_thread.start()
        for line in proc.stdout or []:
            raw_log.write(line)
            stream_jsonl.write(line)
            raw_log.flush()
            stream_jsonl.flush()
            if stream_mode == "raw":
                writer.write(line)
                writer.flush()
                continue
            claude_stream_render.render_line(
                line,
                writer=writer,
                mode="text+tools" if stream_mode == "tools" else "text-only",
                strict=False,
                warn_stream=writer,
            )
        if proc.stdout:
            proc.stdout.close()
        returncode = proc.wait()
        drain_thread.join(timeout=1)
        return returncode


def append_cli_log(log_path: Path, payload: Dict[str, object]) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False) + "\n")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Execute a single loop step (implement/review).")
    parser.add_argument("--ticket", help="Ticket identifier (defaults to docs/.active.json).")
    parser.add_argument("--runner", help="Runner command override (default: claude).")
    parser.add_argument("--format", choices=("json", "yaml"), help="Emit structured output to stdout.")
    parser.add_argument(
        "--from-qa",
        nargs="?",
        const="manual",
        choices=("manual", "auto"),
        help="Allow repair from QA blocked stage (manual|auto).",
    )
    parser.add_argument(
        "--repair-from-qa",
        dest="from_qa",
        nargs="?",
        const="manual",
        choices=("manual", "auto"),
        help=argparse.SUPPRESS,
    )
    parser.add_argument("--work-item-key", help="Explicit work item key (iteration_id=... or id=...).")
    parser.add_argument(
        "--select-qa-handoff",
        action="store_true",
        help="Auto-select blocking QA handoff item when repairing from QA.",
    )
    parser.add_argument(
        "--stream",
        nargs="?",
        const="text",
        help="Enable agent streaming output (text|tools|raw).",
    )
    parser.add_argument(
        "--agent-stream",
        dest="stream",
        nargs="?",
        const="text",
        help=argparse.SUPPRESS,
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    workspace_root, target = runtime.require_workflow_root()
    context = runtime.resolve_feature_context(target, ticket=args.ticket, slug_hint=None)
    ticket = (context.resolved_ticket or "").strip()
    slug_hint = (context.slug_hint or ticket or "").strip()
    if not ticket:
        raise ValueError("feature ticket is required; pass --ticket or set docs/.active.json via /feature-dev-aidd:idea-new.")
    plugin_root = runtime.require_plugin_root()
    wrapper_plugin_root = resolve_wrapper_plugin_root(plugin_root)

    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%d-%H%M%S")
    cli_log_path = target / "reports" / "loops" / ticket / f"cli.loop-step.{stamp}.log"

    stage = read_active_stage(target)
    stream_mode = resolve_stream_mode(getattr(args, "stream", None))
    from_qa_mode, from_qa_requested = _resolve_qa_repair_mode(args.from_qa, target)
    reason = ""
    reason_code = ""
    scope_key = ""
    stage_result_rel = ""
    repair_reason_code = ""
    repair_scope_key = ""
    scope_key_mismatch_warn = ""
    scope_key_mismatch_from = ""
    scope_key_mismatch_to = ""
    stage_result_diag = ""

    if from_qa_requested and stage != "qa":
        reason = f"qa repair requested but active stage is '{stage or 'unset'}'"
        reason_code = "qa_repair_invalid_stage"
        return emit_result(
            args.format,
            ticket,
            stage or "unknown",
            "blocked",
            BLOCKED_CODE,
            "",
            reason,
            reason_code,
            cli_log_path=cli_log_path,
        )

    if not stage:
        next_stage = "implement"
    else:
        work_item_key, scope_key = resolve_stage_scope(target, ticket, stage)
        if stage in {"implement", "review"}:
            if not work_item_key:
                reason = "active work item missing"
                reason_code = "stage_result_missing_or_invalid"
                return emit_result(
                    args.format,
                    ticket,
                    stage,
                    "blocked",
                    BLOCKED_CODE,
                    "",
                    reason,
                    reason_code,
                    cli_log_path=cli_log_path,
                )
            if not runtime.is_valid_work_item_key(work_item_key):
                reason = f"invalid active work item key: {work_item_key}"
                reason_code = "invalid_work_item_key"
                return emit_result(
                    args.format,
                    ticket,
                    stage,
                    "blocked",
                    BLOCKED_CODE,
                    "",
                    reason,
                    reason_code,
                    cli_log_path=cli_log_path,
                )
            if not runtime.is_iteration_work_item_key(work_item_key):
                reason = (
                    f"invalid active work item key for loop stage: {work_item_key}; "
                    "expected iteration_id=<id>. Update tasklist/active work item."
                )
                reason_code = "invalid_work_item_key"
                return emit_result(
                    args.format,
                    ticket,
                    stage,
                    "blocked",
                    BLOCKED_CODE,
                    "",
                    reason,
                    reason_code,
                    cli_log_path=cli_log_path,
                )
        payload, result_path, error, mismatch_from, mismatch_to, diag = load_stage_result(
            target, ticket, scope_key, stage
        )
        if error:
            reason = f"{error}; {diag}" if diag else error
            reason_code = error
            return emit_result(
                args.format,
                ticket,
                stage,
                "blocked",
                BLOCKED_CODE,
                "",
                reason,
                reason_code,
                scope_key=scope_key,
                stage_result_diag=diag,
                cli_log_path=cli_log_path,
            )
        if mismatch_to:
            scope_key_mismatch_warn = "1"
            scope_key_mismatch_from = mismatch_from
            scope_key_mismatch_to = mismatch_to
            print(
                f"[loop-step] WARN: scope_key_mismatch_warn from={mismatch_from} to={mismatch_to}",
                file=sys.stderr,
            )
            scope_key = mismatch_to
        result = str(payload.get("result") or "").strip().lower()
        reason = str(payload.get("reason") or "").strip()
        reason_code = str(payload.get("reason_code") or "").strip().lower()
        result = normalize_stage_result(result, reason_code)
        stage_result_rel = runtime.rel_path(result_path, target)
        if result == "blocked" and stage != "qa":
            return emit_result(
                args.format,
                ticket,
                stage,
                "blocked",
                BLOCKED_CODE,
                "",
                reason,
                reason_code,
                scope_key=scope_key,
                stage_result_path=stage_result_rel,
                cli_log_path=cli_log_path,
            )
        if stage == "review":
            if result == "done":
                ok, message, code = validate_review_pack(
                    target,
                    ticket=ticket,
                    slug_hint=slug_hint,
                    scope_key=scope_key,
                )
                if not ok:
                    return emit_result(
                        args.format,
                        ticket,
                        stage,
                        "blocked",
                        BLOCKED_CODE,
                        "",
                        message,
                        code,
                        scope_key=scope_key,
                        stage_result_path=stage_result_rel,
                        cli_log_path=cli_log_path,
                    )
                return emit_result(
                    args.format,
                    ticket,
                    stage,
                    "done",
                    DONE_CODE,
                    "",
                    reason,
                    reason_code,
                    scope_key=scope_key,
                    stage_result_path=stage_result_rel,
                    cli_log_path=cli_log_path,
                )
            if result == "continue":
                ok, message, code = validate_review_pack(
                    target,
                    ticket=ticket,
                    slug_hint=slug_hint,
                    scope_key=scope_key,
                )
                if not ok:
                    return emit_result(
                        args.format,
                        ticket,
                        stage,
                        "blocked",
                        BLOCKED_CODE,
                        "",
                        message,
                        code,
                        scope_key=scope_key,
                        stage_result_path=stage_result_rel,
                        cli_log_path=cli_log_path,
                    )
                next_stage = "implement"
            else:
                reason = f"review result={result or 'unknown'}"
                reason_code = reason_code or "unsupported_stage_result"
                return emit_result(
                    args.format,
                    ticket,
                    stage,
                    "blocked",
                    BLOCKED_CODE,
                    "",
                    reason,
                    reason_code,
                    scope_key=scope_key,
                    stage_result_path=stage_result_rel,
                    cli_log_path=cli_log_path,
                )
        elif stage == "implement":
            if result in {"continue", "done"}:
                next_stage = "review"
            else:
                reason = f"implement result={result or 'unknown'}"
                reason_code = reason_code or "unsupported_stage_result"
                return emit_result(
                    args.format,
                    ticket,
                    stage,
                    "blocked",
                    BLOCKED_CODE,
                    "",
                    reason,
                    reason_code,
                    scope_key=scope_key,
                    stage_result_path=stage_result_rel,
                    cli_log_path=cli_log_path,
                )
        elif stage == "qa":
            if result == "done":
                if from_qa_requested:
                    reason = "qa repair requested but stage result is not blocked"
                    reason_code = "qa_repair_not_blocked"
                    return emit_result(
                        args.format,
                        ticket,
                        stage,
                        "blocked",
                        BLOCKED_CODE,
                        "",
                        reason,
                        reason_code,
                        scope_key=scope_key,
                        stage_result_path=stage_result_rel,
                        cli_log_path=cli_log_path,
                    )
                return emit_result(
                    args.format,
                    ticket,
                    stage,
                    "done",
                    DONE_CODE,
                    "",
                    reason,
                    reason_code,
                    scope_key=scope_key,
                    stage_result_path=stage_result_rel,
                    cli_log_path=cli_log_path,
                )
            if result == "blocked":
                if from_qa_mode:
                    tasklist_path = target / "docs" / "tasklist" / f"{ticket}.md"
                    if args.work_item_key:
                        tasklist_lines: List[str] = []
                    else:
                        if not tasklist_path.exists():
                            reason = "tasklist missing; cannot select qa handoff"
                            reason_code = "qa_repair_tasklist_missing"
                            return emit_result(
                                args.format,
                                ticket,
                                stage,
                                "blocked",
                                BLOCKED_CODE,
                                "",
                                reason,
                                reason_code,
                                scope_key=scope_key,
                                stage_result_path=stage_result_rel,
                                cli_log_path=cli_log_path,
                            )
                        tasklist_lines = tasklist_path.read_text(encoding="utf-8").splitlines()

                    work_item_key, select_code, select_reason, labels = _select_qa_repair_work_item(
                        tasklist_lines=tasklist_lines,
                        explicit=(args.work_item_key or "").strip(),
                        select_handoff=args.select_qa_handoff,
                        mode=from_qa_mode,
                    )
                    if select_code:
                        reason = select_reason
                        if labels:
                            reason = f"{select_reason}: {', '.join(labels)}"
                        reason_code = select_code
                        return emit_result(
                            args.format,
                            ticket,
                            stage,
                            "blocked",
                            BLOCKED_CODE,
                            "",
                            reason,
                            reason_code,
                            scope_key=scope_key,
                            stage_result_path=stage_result_rel,
                            cli_log_path=cli_log_path,
                        )

                    write_active_ticket(target, ticket)
                    write_active_work_item(target, work_item_key)
                    write_active_stage(target, "implement")
                    _maybe_append_qa_repair_event(
                        target,
                        ticket=ticket,
                        slug_hint=slug_hint,
                        work_item_key=work_item_key,
                        mode=from_qa_mode,
                    )
                    repair_reason_code = "qa_repair"
                    repair_scope_key = runtime.resolve_scope_key(work_item_key, ticket)
                    reason = "qa blocked; switching to implement"
                    reason_code = repair_reason_code
                    next_stage = "implement"
                    # fall through to runner execution
                else:
                    return emit_result(
                        args.format,
                        ticket,
                        stage,
                        "blocked",
                        BLOCKED_CODE,
                        "",
                        reason,
                        reason_code,
                        scope_key=scope_key,
                        stage_result_path=stage_result_rel,
                        cli_log_path=cli_log_path,
                    )
                # from-qa repair path continues to runner
            else:
                reason = f"qa result={result or 'unknown'}"
                reason_code = reason_code or "unsupported_stage_result"
                return emit_result(
                    args.format,
                    ticket,
                    stage,
                    "blocked",
                    BLOCKED_CODE,
                    "",
                    reason,
                    reason_code,
                    scope_key=scope_key,
                    stage_result_path=stage_result_rel,
                    cli_log_path=cli_log_path,
                )
        else:
            reason = f"unsupported stage={stage}"
            reason_code = reason_code or "unsupported_stage"
            return emit_result(
                args.format,
                ticket,
                stage,
                "blocked",
                BLOCKED_CODE,
                "",
                reason,
                reason_code,
                cli_log_path=cli_log_path,
            )

    write_active_mode(target, "loop")
    ok, message, code = validate_command_available(plugin_root, next_stage)
    if not ok:
        return emit_result(
            args.format,
            ticket,
            next_stage,
            "blocked",
            BLOCKED_CODE,
            "",
            message,
            code,
            repair_reason_code=repair_reason_code,
            repair_scope_key=repair_scope_key,
            cli_log_path=cli_log_path,
        )
    runner_tokens, runner_raw, runner_notice = resolve_runner(args.runner, plugin_root)
    wrapper_enabled = should_run_wrappers(next_stage, runner_raw, wrapper_plugin_root)
    wrapper_logs: List[str] = []
    actions_log_rel = ""
    wrapper_scope_key = runtime.resolve_scope_key(runtime.read_active_work_item(target), ticket)
    wrapper_work_item_key = runtime.read_active_work_item(target)
    if next_stage == "qa":
        wrapper_scope_key = runtime.resolve_scope_key("", ticket)
        wrapper_work_item_key = wrapper_work_item_key or ""
    if wrapper_enabled:
        ok_wrapper, preflight_payload, wrapper_error = run_stage_wrapper(
            plugin_root=wrapper_plugin_root,
            workspace_root=workspace_root,
            stage=next_stage,
            kind="preflight",
            ticket=ticket,
            scope_key=wrapper_scope_key,
            work_item_key=wrapper_work_item_key,
        )
        if not ok_wrapper:
            return emit_result(
                args.format,
                ticket,
                next_stage,
                "blocked",
                BLOCKED_CODE,
                "",
                wrapper_error,
                "preflight_missing",
                scope_key=wrapper_scope_key,
                cli_log_path=cli_log_path,
            )
        if preflight_payload.get("log_path"):
            wrapper_logs.append(preflight_payload["log_path"])
        actions_log_rel = preflight_payload.get("actions_path", actions_log_rel)

    command = list(runner_tokens)
    if stream_mode:
        command.extend(["--output-format", "stream-json", "--include-partial-messages", "--verbose"])
    command.extend(build_command(next_stage, ticket))
    runner_effective = " ".join(command)
    run_stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%d-%H%M%S")
    log_path = target / "reports" / "loops" / ticket / f"cli.{next_stage}.{run_stamp}.log"

    stream_log_rel = ""
    stream_jsonl_rel = ""
    run_started_at = dt.datetime.now(dt.timezone.utc).timestamp()
    if stream_mode:
        stream_log_path = target / "reports" / "loops" / ticket / f"cli.loop-step.{stamp}.stream.log"
        stream_jsonl_path = target / "reports" / "loops" / ticket / f"cli.loop-step.{stamp}.stream.jsonl"
        stream_log_rel = runtime.rel_path(stream_log_path, target)
        stream_jsonl_rel = runtime.rel_path(stream_jsonl_path, target)
        active_work_item = runtime.read_active_work_item(target)
        stream_scope_key = runtime.resolve_scope_key(active_work_item, ticket) if active_work_item else "n/a"
        header_lines = [
            f"==> loop-step: stage={next_stage} ticket={ticket} scope_key={stream_scope_key}",
            f"==> streaming enabled: writing stream={stream_jsonl_rel} log={stream_log_rel}",
        ]
        returncode = run_stream_command(
            command=command,
            cwd=workspace_root,
            log_path=log_path,
            stream_mode=stream_mode,
            stream_jsonl_path=stream_jsonl_path,
            stream_log_path=stream_log_path,
            output_stream=sys.stderr,
            header_lines=header_lines,
        )
    else:
        returncode = run_command(command, workspace_root, log_path)
    run_finished_at = dt.datetime.now(dt.timezone.utc).timestamp()
    if returncode != 0:
        status = "error"
        code = ERROR_CODE
        reason = f"runner exited with {returncode}"
        return emit_result(
            args.format,
            ticket,
            next_stage,
            status,
            code,
            log_path,
            reason,
            "",
            scope_key="",
            stage_result_path="",
            runner=runner_raw,
            runner_effective=runner_effective,
            runner_notice=runner_notice,
            repair_reason_code=repair_reason_code,
            repair_scope_key=repair_scope_key,
            stream_log_path=stream_log_rel,
            stream_jsonl_path=stream_jsonl_rel,
            cli_log_path=cli_log_path,
        )

    next_work_item_key, next_scope_key = resolve_stage_scope(target, ticket, next_stage)
    if next_stage in {"implement", "review"} and next_work_item_key and not runtime.is_iteration_work_item_key(next_work_item_key):
        reason = (
            f"invalid active work item key for loop stage: {next_work_item_key}; "
            "expected iteration_id=<id>. Update tasklist/active work item."
        )
        return emit_result(
            args.format,
            ticket,
            next_stage,
            "blocked",
            BLOCKED_CODE,
            log_path,
            reason,
            "invalid_work_item_key",
            runner=runner_raw,
            runner_effective=runner_effective,
            runner_notice=runner_notice,
            repair_reason_code=repair_reason_code,
            repair_scope_key=repair_scope_key,
            stream_log_path=stream_log_rel,
            stream_jsonl_path=stream_jsonl_rel,
            cli_log_path=cli_log_path,
        )

    if wrapper_enabled:
        ok_wrapper, run_payload, wrapper_error = run_stage_wrapper(
            plugin_root=wrapper_plugin_root,
            workspace_root=workspace_root,
            stage=next_stage,
            kind="run",
            ticket=ticket,
            scope_key=wrapper_scope_key,
            work_item_key=wrapper_work_item_key,
            actions_path=actions_log_rel,
        )
        if not ok_wrapper:
            return emit_result(
                args.format,
                ticket,
                next_stage,
                "blocked",
                BLOCKED_CODE,
                log_path,
                wrapper_error,
                "actions_missing",
                scope_key=wrapper_scope_key,
                runner=runner_raw,
                runner_effective=runner_effective,
                runner_notice=runner_notice,
                repair_reason_code=repair_reason_code,
                repair_scope_key=repair_scope_key,
                stream_log_path=stream_log_rel,
                stream_jsonl_path=stream_jsonl_rel,
                cli_log_path=cli_log_path,
            )
        if run_payload.get("log_path"):
            wrapper_logs.append(run_payload["log_path"])
        actions_log_rel = run_payload.get("actions_path", actions_log_rel)

    payload, result_path, error, mismatch_from, mismatch_to, diag = load_stage_result(
        target,
        ticket,
        next_scope_key,
        next_stage,
        started_at=run_started_at,
        finished_at=run_finished_at,
    )
    preliminary_result = str(payload.get("result") or "").strip().lower() if payload else "continue"
    preliminary_verdict = str(payload.get("verdict") or "").strip().upper() if payload else ""

    if wrapper_enabled:
        ok_wrapper, post_payload, wrapper_error = run_stage_wrapper(
            plugin_root=wrapper_plugin_root,
            workspace_root=workspace_root,
            stage=next_stage,
            kind="postflight",
            ticket=ticket,
            scope_key=wrapper_scope_key,
            work_item_key=wrapper_work_item_key,
            actions_path=actions_log_rel,
            result=preliminary_result or "continue",
            verdict=preliminary_verdict,
        )
        if not ok_wrapper:
            return emit_result(
                args.format,
                ticket,
                next_stage,
                "blocked",
                BLOCKED_CODE,
                log_path,
                wrapper_error,
                "postflight_missing",
                scope_key=wrapper_scope_key,
                runner=runner_raw,
                runner_effective=runner_effective,
                runner_notice=runner_notice,
                repair_reason_code=repair_reason_code,
                repair_scope_key=repair_scope_key,
                stream_log_path=stream_log_rel,
                stream_jsonl_path=stream_jsonl_rel,
                cli_log_path=cli_log_path,
            )
        if post_payload.get("log_path"):
            wrapper_logs.append(post_payload["log_path"])
        if post_payload.get("apply_log"):
            wrapper_logs.append(post_payload["apply_log"])
        actions_log_rel = post_payload.get("actions_path", actions_log_rel)
        run_finished_at = dt.datetime.now(dt.timezone.utc).timestamp()
        payload, result_path, error, mismatch_from, mismatch_to, diag = load_stage_result(
            target,
            ticket,
            next_scope_key,
            next_stage,
            started_at=run_started_at,
            finished_at=run_finished_at,
        )

    if mismatch_to:
        scope_key_mismatch_warn = "1"
        scope_key_mismatch_from = mismatch_from
        scope_key_mismatch_to = mismatch_to
        next_scope_key = mismatch_to
        print(
            f"[loop-step] WARN: scope_key_mismatch_warn from={mismatch_from} to={mismatch_to}",
            file=sys.stderr,
        )

    if error:
        return emit_result(
            args.format,
            ticket,
            next_stage,
            "blocked",
            BLOCKED_CODE,
            log_path,
            f"{error}; {diag}" if diag else error,
            error,
            scope_key=next_scope_key,
            stage_result_path=runtime.rel_path(result_path, target),
            runner=runner_raw,
            runner_effective=runner_effective,
            runner_notice=runner_notice,
            repair_reason_code=repair_reason_code,
            repair_scope_key=repair_scope_key,
            stream_log_path=stream_log_rel,
            stream_jsonl_path=stream_jsonl_rel,
            stage_result_diag=diag,
            scope_key_mismatch_warn=scope_key_mismatch_warn,
            scope_key_mismatch_from=scope_key_mismatch_from,
            scope_key_mismatch_to=scope_key_mismatch_to,
            cli_log_path=cli_log_path,
        )
    next_scope_key = str(payload.get("scope_key") or next_scope_key or "").strip() or next_scope_key
    next_work_item_key = str(payload.get("work_item_key") or next_work_item_key or "").strip() or next_work_item_key
    result = str(payload.get("result") or "").strip().lower()
    reason = str(payload.get("reason") or "").strip()
    reason_code = str(payload.get("reason_code") or "").strip().lower()
    result = normalize_stage_result(result, reason_code)
    evidence_links = payload.get("evidence_links") if isinstance(payload, dict) else {}
    tests_log_path = ""
    if isinstance(evidence_links, dict):
        tests_log_path = str(evidence_links.get("tests_log") or "").strip()
    if not actions_log_rel and next_stage in {"implement", "review", "qa"}:
        default_actions = target / "reports" / "actions" / ticket / next_scope_key / f"{next_stage}.actions.json"
        if default_actions.exists():
            actions_log_rel = runtime.rel_path(default_actions, target)
    if next_stage in {"implement", "review", "qa"} and actions_log_rel:
        with log_path.open("a", encoding="utf-8") as handle:
            handle.write(f"\nAIDD:ACTIONS_LOG: {actions_log_rel}\n")
    if next_stage == "review" and result in {"continue", "done"}:
        ok, message, code = validate_review_pack(
            target,
            ticket=ticket,
            slug_hint=slug_hint,
            scope_key=next_scope_key,
        )
        if not ok:
            return emit_result(
                args.format,
                ticket,
                next_stage,
                "blocked",
                BLOCKED_CODE,
                log_path,
                message,
                code,
                scope_key=next_scope_key,
                stage_result_path=runtime.rel_path(result_path, target),
                runner=runner_raw,
                runner_effective=runner_effective,
                runner_notice=runner_notice,
                repair_reason_code=repair_reason_code,
                repair_scope_key=repair_scope_key,
                stream_log_path=stream_log_rel,
                stream_jsonl_path=stream_jsonl_rel,
                scope_key_mismatch_warn=scope_key_mismatch_warn,
                scope_key_mismatch_from=scope_key_mismatch_from,
                scope_key_mismatch_to=scope_key_mismatch_to,
                actions_log_path=actions_log_rel,
                tests_log_path=tests_log_path,
                wrapper_logs=wrapper_logs,
                cli_log_path=cli_log_path,
            )
    output_contract_path = ""
    output_contract_status = ""
    try:
        from tools import output_contract as _output_contract

        report = _output_contract.check_output_contract(
            target=target,
            ticket=ticket,
            stage=next_stage,
            scope_key=next_scope_key,
            work_item_key=next_work_item_key,
            log_path=log_path,
            stage_result_path=result_path,
            max_read_items=3,
        )
        output_contract_status = str(report.get("status") or "")
        output_dir = target / "reports" / "loops" / ticket / next_scope_key
        output_dir.mkdir(parents=True, exist_ok=True)
        report_path = output_dir / "output.contract.json"
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        output_contract_path = runtime.rel_path(report_path, target)
    except Exception as exc:
        print(f"[loop-step] WARN: output contract check failed: {exc}", file=sys.stderr)
    status = result if result in {"blocked", "continue", "done"} else "blocked"
    code = DONE_CODE if status == "done" else BLOCKED_CODE if status == "blocked" else CONTINUE_CODE
    return emit_result(
        args.format,
        ticket,
        next_stage,
        status,
        code,
        log_path,
        reason,
        reason_code,
        scope_key=next_scope_key,
        stage_result_path=runtime.rel_path(result_path, target),
        runner=runner_raw,
        runner_effective=runner_effective,
        runner_notice=runner_notice,
        repair_reason_code=repair_reason_code,
        repair_scope_key=repair_scope_key,
        stream_log_path=stream_log_rel,
        stream_jsonl_path=stream_jsonl_rel,
        scope_key_mismatch_warn=scope_key_mismatch_warn,
        scope_key_mismatch_from=scope_key_mismatch_from,
        scope_key_mismatch_to=scope_key_mismatch_to,
        actions_log_path=actions_log_rel,
        tests_log_path=tests_log_path,
        wrapper_logs=wrapper_logs,
        cli_log_path=cli_log_path,
        output_contract_path=output_contract_path,
        output_contract_status=output_contract_status,
    )


def emit_result(
    fmt: str | None,
    ticket: str,
    stage: str,
    status: str,
    code: int,
    log_path: Path | str,
    reason: str,
    reason_code: str = "",
    *,
    scope_key: str = "",
    stage_result_path: str = "",
    runner: str = "",
    runner_effective: str = "",
    runner_notice: str = "",
    repair_reason_code: str = "",
    repair_scope_key: str = "",
    stream_log_path: str = "",
    stream_jsonl_path: str = "",
    cli_log_path: Path | None = None,
    output_contract_path: str = "",
    output_contract_status: str = "",
    scope_key_mismatch_warn: str = "",
    scope_key_mismatch_from: str = "",
    scope_key_mismatch_to: str = "",
    stage_result_diag: str = "",
    actions_log_path: str = "",
    tests_log_path: str = "",
    wrapper_logs: List[str] | None = None,
) -> int:
    log_value = str(log_path) if log_path else ""
    payload = {
        "ticket": ticket,
        "stage": stage,
        "status": status,
        "exit_code": code,
        "scope_key": scope_key,
        "log_path": log_value,
        "stage_result_path": stage_result_path,
        "runner": runner,
        "runner_effective": runner_effective,
        "runner_notice": runner_notice,
        "repair_reason_code": repair_reason_code,
        "repair_scope_key": repair_scope_key,
        "stream_log_path": stream_log_path,
        "stream_jsonl_path": stream_jsonl_path,
        "output_contract_path": output_contract_path,
        "output_contract_status": output_contract_status,
        "scope_key_mismatch_warn": scope_key_mismatch_warn,
        "scope_key_mismatch_from": scope_key_mismatch_from,
        "scope_key_mismatch_to": scope_key_mismatch_to,
        "stage_result_diagnostics": stage_result_diag,
        "actions_log_path": actions_log_path,
        "tests_log_path": tests_log_path,
        "wrapper_logs": wrapper_logs or [],
        "updated_at": utc_timestamp(),
        "reason": reason,
        "reason_code": reason_code,
    }
    if fmt:
        output = json.dumps(payload, ensure_ascii=False, indent=2) if fmt == "json" else "\n".join(dump_yaml(payload))
        print(output)
        print(f"[loop-step] {status} stage={stage} log={log_value}", file=sys.stderr)
    else:
        summary = f"[loop-step] {status} stage={stage}"
        if log_value:
            summary += f" log={log_value}"
        if reason:
            summary += f" reason={reason}"
        print(summary)
    if cli_log_path:
        append_cli_log(cli_log_path, payload)
    return code


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
