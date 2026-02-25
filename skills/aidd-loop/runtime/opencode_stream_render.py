#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass
from typing import Any, Iterable, Optional, TextIO


MAX_ARG_CHARS = 200
HELP_EPILOG = """Examples:
  python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-loop/runtime/opencode_stream_render.py --help
  cat stream.jsonl | python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-loop/runtime/opencode_stream_render.py --mode text+tools

Outputs:
  stdout: rendered stream text (and optional tool markers).

Exit codes:
  0 - success.
  1 - strict-mode parse failure.
  2 - CLI usage error (argparse)."""


@dataclass
class RenderState:
    line_start: bool = True


def _shorten(value: Any, *, limit: int = MAX_ARG_CHARS) -> str:
    text = ""
    if value is None:
        text = ""
    elif isinstance(value, str):
        text = value
    else:
        try:
            text = json.dumps(value, ensure_ascii=False)
        except (TypeError, ValueError):
            text = str(value)
    cleaned = " ".join(text.splitlines()).strip()
    if len(cleaned) > limit:
        return cleaned[: limit - 3] + "..."
    return cleaned


def _write(writer: TextIO, state: RenderState, text: str) -> None:
    if not text:
        return
    writer.write(text)
    state.line_start = text.endswith("\n")


def _write_line(writer: TextIO, state: RenderState, text: str) -> None:
    if not text:
        return
    if not state.line_start:
        writer.write("\n")
    writer.write(text + "\n")
    state.line_start = True


def _extract_text(event: Any) -> Iterable[str]:
    if not isinstance(event, dict):
        return []
    for key in ("text", "delta", "content", "message"):
        value = event.get(key)
        if isinstance(value, str) and value:
            return [value]
    payload = event.get("payload")
    if isinstance(payload, dict):
        for key in ("text", "delta"):
            value = payload.get(key)
            if isinstance(value, str) and value:
                return [value]
        content = payload.get("content")
        if isinstance(content, list):
            texts: list[str] = []
            for item in content:
                if isinstance(item, dict):
                    text = item.get("text")
                    if isinstance(text, str) and text:
                        texts.append(text)
            if texts:
                return texts
    if isinstance(event.get("content"), list):
        texts = []
        for item in event.get("content"):
            if isinstance(item, dict) and isinstance(item.get("text"), str):
                texts.append(item.get("text"))
        if texts:
            return texts
    return []


def _extract_tool_start(event: Any) -> Optional[tuple[str, str]]:
    if not isinstance(event, dict):
        return None
    event_type = str(event.get("type") or "")
    payload = event.get("payload") if isinstance(event.get("payload"), dict) else event
    if event_type in {"tool_use", "tool_call", "tool.execute.before"}:
        name = payload.get("tool_name") or payload.get("name") or payload.get("tool") or "unknown"
        args = payload.get("args") or payload.get("input") or payload.get("arguments")
        return str(name), _shorten(args)
    return None


def _extract_tool_stop(event: Any) -> Optional[tuple[str, str, str]]:
    if not isinstance(event, dict):
        return None
    event_type = str(event.get("type") or "")
    payload = event.get("payload") if isinstance(event.get("payload"), dict) else event
    if event_type not in {"tool_result", "tool.execute.after"}:
        return None
    name = payload.get("tool_name") or payload.get("name") or payload.get("tool") or "unknown"
    exit_code = payload.get("exit_code") or payload.get("code") or ""
    status = str(payload.get("status") or "")
    if not status:
        status = "error" if payload.get("error") else "ok"
    return str(name), str(exit_code or ""), status


def render_event(event: Any, *, writer: TextIO, mode: str, state: RenderState) -> None:
    for fragment in _extract_text(event):
        _write(writer, state, fragment)
    if mode != "text+tools":
        return
    tool_start = _extract_tool_start(event)
    if tool_start:
        name, args = tool_start
        payload = f"[tool:start] {name}"
        if args:
            payload += f" {args}"
        _write_line(writer, state, payload)
        return
    tool_stop = _extract_tool_stop(event)
    if tool_stop:
        name, exit_code, status = tool_stop
        payload = f"[tool:stop] {name}"
        if exit_code:
            payload += f" exit_code={exit_code}"
        payload += f" status={status}"
        _write_line(writer, state, payload)


def render_line(
    line: str,
    *,
    writer: TextIO,
    mode: str,
    strict: bool,
    warn_stream: Optional[TextIO] = None,
    state: Optional[RenderState] = None,
) -> bool:
    raw = line.strip("\n")
    if not raw.strip():
        return True
    if state is None:
        state = RenderState()
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        if warn_stream:
            warn_stream.write(f"[stream] WARN: invalid json line ({exc})\n")
            warn_stream.flush()
        return not strict
    render_event(payload, writer=writer, mode=mode, state=state)
    writer.flush()
    return True


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Render OpenCode json events into text output.",
        epilog=HELP_EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--mode",
        choices=("text-only", "text+tools"),
        default="text-only",
        help="Render mode (default: text-only).",
    )
    return parser.parse_args(argv)


def _strict_enabled() -> bool:
    return os.getenv("AIDD_STREAM_STRICT", "").strip().lower() in {"1", "true", "yes"}


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    strict = _strict_enabled()
    state = RenderState()
    ok = True
    for line in sys.stdin:
        ok = render_line(
            line,
            writer=sys.stdout,
            mode=args.mode,
            strict=strict,
            warn_stream=sys.stderr,
            state=state,
        )
        if not ok and strict:
            return 1
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
