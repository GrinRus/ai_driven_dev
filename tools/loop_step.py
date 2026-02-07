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
        return work_item_key, runtime.resolve_scope_key(work_item_key, ticket)
    return "", runtime.resolve_scope_key("", ticket)


def stage_result_path(root: Path, ticket: str, scope_key: str, stage: str) -> Path:
    return root / "reports" / "loops" / ticket / scope_key / f"stage.{stage}.result.json"


def load_stage_result(root: Path, ticket: str, scope_key: str, stage: str) -> Tuple[Dict[str, object] | None, Path, str]:
    path = stage_result_path(root, ticket, scope_key, stage)
    if not path.exists():
        return None, path, "stage_result_missing_or_invalid"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None, path, "stage_result_missing_or_invalid"
    if str(payload.get("schema") or "") != "aidd.stage_result.v1":
        return None, path, "stage_result_missing_or_invalid"
    if str(payload.get("stage") or "").strip().lower() != stage:
        return None, path, "stage_result_missing_or_invalid"
    result = str(payload.get("result") or "").strip().lower()
    if result not in {"blocked", "continue", "done"}:
        return None, path, "stage_result_missing_or_invalid"
    work_item_key = str(payload.get("work_item_key") or "").strip()
    if work_item_key and not runtime.is_valid_work_item_key(work_item_key):
        return None, path, "stage_result_invalid_work_item"
    return payload, path, ""


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
    command_path = plugin_root / "commands" / f"{stage}.md"
    if not command_path.exists():
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
        if stage in {"implement", "review"} and not scope_key:
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
        payload, result_path, error = load_stage_result(target, ticket, scope_key, stage)
        if error:
            reason = error
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
                cli_log_path=cli_log_path,
            )
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
    command = list(runner_tokens)
    if stream_mode:
        command.extend(["--output-format", "stream-json", "--include-partial-messages", "--verbose"])
    command.extend(build_command(next_stage, ticket))
    runner_effective = " ".join(command)
    run_stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%d-%H%M%S")
    log_path = target / "reports" / "loops" / ticket / f"cli.{next_stage}.{run_stamp}.log"

    stream_log_rel = ""
    stream_jsonl_rel = ""
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
    if next_stage in {"implement", "review"} and not next_scope_key:
        reason = "stage_result_missing_or_invalid"
        return emit_result(
            args.format,
            ticket,
            next_stage,
            "blocked",
            BLOCKED_CODE,
            log_path,
            reason,
            "stage_result_missing_or_invalid",
            runner=runner_raw,
            runner_effective=runner_effective,
            runner_notice=runner_notice,
            repair_reason_code=repair_reason_code,
            repair_scope_key=repair_scope_key,
            stream_log_path=stream_log_rel,
            stream_jsonl_path=stream_jsonl_rel,
            cli_log_path=cli_log_path,
        )
    payload, result_path, error = load_stage_result(target, ticket, next_scope_key, next_stage)
    if error:
        return emit_result(
            args.format,
            ticket,
            next_stage,
            "blocked",
            BLOCKED_CODE,
            log_path,
            error,
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
            cli_log_path=cli_log_path,
        )
    result = str(payload.get("result") or "").strip().lower()
    reason = str(payload.get("reason") or "").strip()
    reason_code = str(payload.get("reason_code") or "").strip().lower()
    result = normalize_stage_result(result, reason_code)
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
