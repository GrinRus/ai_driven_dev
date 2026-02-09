from __future__ import annotations

import io
import os
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from aidd_runtime import runtime


STDOUT_MAX_LINES = 200
STDOUT_MAX_BYTES = 50 * 1024
STDERR_MAX_LINES = 50
OUTPUT_LIMIT_EXIT_CODE = 2
RUNTIME_FAILURE_EXIT_CODE = 1


@dataclass(frozen=True)
class LaunchContext:
    root: Path
    ticket: str
    scope_key: str
    work_item_key: str
    stage: str


@dataclass(frozen=True)
class LaunchResult:
    exit_code: int
    wrapped_exit_code: int
    stdout: str
    stderr: str
    log_path: Path
    output_limited: bool
    stdout_lines: int
    stdout_bytes: int
    stderr_lines: int


def resolve_workflow_root_or_fallback(cwd: Path | None = None) -> Path:
    target = (cwd or Path.cwd()).resolve()
    try:
        _, root = runtime.resolve_roots(target, create=False)
    except Exception:
        fallback = Path(os.environ.get("AIDD_WRAPPER_LOG_ROOT") or "/tmp/aidd-wrapper")
        fallback.mkdir(parents=True, exist_ok=True)
        return fallback.resolve()
    return root


def resolve_context(
    *,
    ticket: str | None = None,
    scope_key: str | None = None,
    work_item_key: str | None = None,
    stage: str | None = None,
    default_stage: str | None = None,
    cwd: Path | None = None,
) -> LaunchContext:
    target = (cwd or Path.cwd()).resolve()
    _, root = runtime.require_workflow_root(target)
    resolved_ticket, _context = runtime.require_ticket(root, ticket=ticket)
    resolved_work_item = (work_item_key or runtime.read_active_work_item(root) or "").strip()
    resolved_scope = (scope_key or runtime.resolve_scope_key(resolved_work_item, resolved_ticket)).strip()
    resolved_stage = (
        (stage or "").strip()
        or (default_stage or "").strip()
        or runtime.read_active_stage(root)
    )
    return LaunchContext(
        root=root,
        ticket=resolved_ticket,
        scope_key=resolved_scope,
        work_item_key=resolved_work_item,
        stage=resolved_stage,
    )


def actions_paths(context: LaunchContext) -> dict[str, Path]:
    actions_base = context.root / "reports" / "actions" / context.ticket / context.scope_key
    context_base = context.root / "reports" / "context" / context.ticket
    loops_base = context.root / "reports" / "loops" / context.ticket / context.scope_key
    return {
        "actions_template": actions_base / f"{context.stage}.actions.template.json",
        "actions_path": actions_base / f"{context.stage}.actions.json",
        "apply_log": actions_base / f"{context.stage}.apply.jsonl",
        "readmap_json": context_base / f"{context.scope_key}.readmap.json",
        "readmap_md": context_base / f"{context.scope_key}.readmap.md",
        "writemap_json": context_base / f"{context.scope_key}.writemap.json",
        "writemap_md": context_base / f"{context.scope_key}.writemap.md",
        "preflight_result": loops_base / "stage.preflight.result.json",
        "readmap_json_fallback": actions_base / "readmap.json",
        "readmap_md_fallback": actions_base / "readmap.md",
        "writemap_json_fallback": actions_base / "writemap.json",
        "writemap_md_fallback": actions_base / "writemap.md",
        "preflight_result_fallback": actions_base / "stage.preflight.result.json",
    }


def log_path(
    root: Path,
    stage: str,
    ticket: str,
    scope_key: str,
    name: str,
    *,
    now: datetime | None = None,
) -> Path:
    ts = (now or datetime.now(timezone.utc)).strftime("%Y%m%dT%H%M%SZ")
    log_dir = root / "reports" / "logs" / stage / ticket / scope_key
    log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir / f"wrapper.{name}.{ts}.log"


def _append_log(log_path_value: Path, stdout_text: str, stderr_text: str) -> None:
    log_path_value.parent.mkdir(parents=True, exist_ok=True)
    with log_path_value.open("a", encoding="utf-8") as handle:
        handle.write("[stdout]\n")
        handle.write(stdout_text)
        handle.write("\n[stderr]\n")
        handle.write(stderr_text)
        handle.write("\n")


def run_guarded(
    runner: Callable[[], int | None],
    *,
    log_path_value: Path,
    stdout_max_lines: int = STDOUT_MAX_LINES,
    stdout_max_bytes: int = STDOUT_MAX_BYTES,
    stderr_max_lines: int = STDERR_MAX_LINES,
) -> LaunchResult:
    out_buf = io.StringIO()
    err_buf = io.StringIO()
    wrapped_exit_code = 0
    try:
        with redirect_stdout(out_buf), redirect_stderr(err_buf):
            result = runner()
        wrapped_exit_code = int(result or 0)
    except SystemExit as exc:
        wrapped_exit_code = int(exc.code or 0) if isinstance(exc.code, int) else RUNTIME_FAILURE_EXIT_CODE
    except Exception as exc:  # pragma: no cover - defensive fallback
        wrapped_exit_code = RUNTIME_FAILURE_EXIT_CODE
        err_buf.write(f"[aidd] ERROR: {exc}\n")

    stdout_text = out_buf.getvalue()
    stderr_text = err_buf.getvalue()
    _append_log(log_path_value, stdout_text, stderr_text)

    stdout_lines = len(stdout_text.splitlines())
    stdout_bytes = len(stdout_text.encode("utf-8"))
    stderr_lines = len(stderr_text.splitlines())
    output_limited = (
        stdout_lines > stdout_max_lines
        or stdout_bytes > stdout_max_bytes
        or stderr_lines > stderr_max_lines
    )
    if output_limited:
        limited_stderr = (
            "[aidd] ERROR: output exceeded limits "
            f"(stdout lines={stdout_lines} bytes={stdout_bytes}, stderr lines={stderr_lines}). "
            f"See {log_path_value}\n"
        )
        return LaunchResult(
            exit_code=OUTPUT_LIMIT_EXIT_CODE,
            wrapped_exit_code=wrapped_exit_code,
            stdout="",
            stderr=limited_stderr,
            log_path=log_path_value,
            output_limited=True,
            stdout_lines=stdout_lines,
            stdout_bytes=stdout_bytes,
            stderr_lines=stderr_lines,
        )
    return LaunchResult(
        exit_code=wrapped_exit_code,
        wrapped_exit_code=wrapped_exit_code,
        stdout=stdout_text,
        stderr=stderr_text,
        log_path=log_path_value,
        output_limited=False,
        stdout_lines=stdout_lines,
        stdout_bytes=stdout_bytes,
        stderr_lines=stderr_lines,
    )
