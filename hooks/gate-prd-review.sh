#!/usr/bin/env python3
from __future__ import annotations

import io
import os
import sys
from pathlib import Path
from contextlib import redirect_stdout


HOOK_PREFIX = "[gate-prd-review]"


def _bootstrap() -> None:
    raw = os.environ.get("CLAUDE_PLUGIN_ROOT")
    if not raw:
        print(f"{HOOK_PREFIX} CLAUDE_PLUGIN_ROOT is required to run hooks.", file=sys.stderr)
        raise SystemExit(2)
    plugin_root = Path(raw).expanduser().resolve()
    if str(plugin_root) not in sys.path:
        sys.path.insert(0, str(plugin_root))
    vendor_dir = Path(__file__).resolve().parent / "_vendor"
    if vendor_dir.exists():
        sys.path.insert(0, str(vendor_dir))


def _log_stdout(message: str) -> None:
    from hooks import hooklib

    if message:
        print(hooklib.prefix_lines(HOOK_PREFIX, message))


def _log_stderr(message: str) -> None:
    from hooks import hooklib

    if message:
        print(hooklib.prefix_lines(HOOK_PREFIX, message), file=sys.stderr)


def main() -> int:
    _bootstrap()
    from hooks import hooklib
    from tools import prd_review_gate

    ctx = hooklib.read_hook_context()
    root, used_workspace = hooklib.resolve_project_root(ctx)
    if used_workspace:
        _log_stdout(f"WARN: detected workspace root; using {root} as project root")

    if not (root / "docs").is_dir():
        _log_stderr(
            f"BLOCK: aidd/docs not found at {root / 'docs'}. "
            "Run '/feature-dev-aidd:aidd-init' or "
            "'${CLAUDE_PLUGIN_ROOT}/tools/init.sh' from the workspace root to bootstrap ./aidd."
        )
        return 2

    os.chdir(root)

    payload = ctx.raw
    file_path = hooklib.payload_file_path(payload) or ""

    ticket_path = root / "docs" / ".active.json"
    slug_path = root / "docs" / ".active.json"
    if not ticket_path.exists() and not slug_path.exists():
        return 0
    ticket = hooklib.read_ticket(ticket_path, slug_path)
    slug_hint = hooklib.read_slug(slug_path) if slug_path.exists() else None
    if not ticket:
        return 0

    event_status = "fail"
    event_should_log = True
    try:
        args = ["--ticket", ticket, "--file-path", file_path, "--skip-on-prd-edit"]
        branch = hooklib.git_current_branch(root)
        if branch:
            args.extend(["--branch", branch])
        if slug_hint:
            args.extend(["--slug-hint", slug_hint])
        parsed = prd_review_gate.parse_args(args)
        buf = io.StringIO()
        with redirect_stdout(buf):
            status = prd_review_gate.run_gate(parsed)
        output = buf.getvalue().strip()
        if status != 0:
            if output:
                _log_stderr(output)
            else:
                _log_stderr(f"BLOCK: PRD Review не готов → выполните /feature-dev-aidd:review-spec {ticket}")
            return 2
        event_status = "pass"
        return 0
    finally:
        if event_should_log:
            hooklib.append_event(root, "gate-prd-review", event_status, source="hook gate-prd-review")


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
