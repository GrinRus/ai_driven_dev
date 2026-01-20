#!/usr/bin/env python3
from __future__ import annotations

import os
import sys
from fnmatch import fnmatch
from pathlib import Path
from typing import Iterable, List

HOOK_PREFIX = "[gate-stage-writes]"

ALLOWLIST = {
    "review": [
        "docs/tasklist/**",
        "reports/**",
        "docs/.active_*",
    ],
    "qa": [
        "docs/tasklist/**",
        "reports/**",
        "docs/.active_*",
    ],
    "spec-interview": [
        "docs/spec/**",
        "reports/**",
        "docs/.active_*",
    ],
    "tasklist": [
        "docs/tasklist/**",
        "reports/**",
        "docs/.active_*",
    ],
}


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


def _log_stderr(message: str) -> None:
    from hooks import hooklib

    if message:
        print(hooklib.prefix_lines(HOOK_PREFIX, message), file=sys.stderr)


def _normalize_path(root: Path, path_str: str) -> str:
    raw = Path(path_str)
    if raw.is_absolute():
        try:
            rel = raw.relative_to(root)
            return rel.as_posix().lstrip("./")
        except ValueError:
            return raw.as_posix().lstrip("./")
    parts = raw.parts
    if parts and parts[0] == "aidd" and root.name == "aidd":
        raw = Path(*parts[1:])
    return raw.as_posix().lstrip("./")


def _is_allowed(path: str, allowlist: Iterable[str]) -> bool:
    for pattern in allowlist:
        if fnmatch(path, pattern):
            return True
    return False


def main() -> int:
    _bootstrap()
    from hooks import hooklib

    ctx = hooklib.read_hook_context()
    root, used_workspace = hooklib.resolve_project_root(ctx)
    if used_workspace:
        _log_stderr(f"WARN: detected workspace root; using {root} as project root")
    if not (root / "docs").exists():
        return 0

    stage = hooklib.resolve_stage(root / "docs" / ".active_stage") or ""
    if stage not in ALLOWLIST:
        return 0

    payload = ctx.raw
    file_path = hooklib.payload_file_path(payload) or ""
    changed_files = hooklib.collect_changed_files(root)
    if file_path:
        changed_files.insert(0, file_path)
    changed_files = list(dict.fromkeys(changed_files))
    if not changed_files:
        return 0

    allowlist = ALLOWLIST.get(stage, [])
    violations: List[str] = []
    for raw_path in changed_files:
        path = _normalize_path(root, raw_path)
        if _is_allowed(path, allowlist):
            continue
        violations.append(path)

    if violations:
        allowed = ", ".join(sorted(allowlist))
        blocked = ", ".join(sorted(set(violations)))
        _log_stderr(
            f"BLOCK: стадия '{stage}' запрещает правки вне allowlist. "
            f"Нарушения: {blocked}. Разрешено: {allowed}."
        )
        return 2
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
