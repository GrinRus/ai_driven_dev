#!/usr/bin/env python3
from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path


HOOK_PREFIX = "[lint-deps]"


def _bootstrap() -> Path:
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
    return plugin_root


def _log_stdout(message: str) -> None:
    from hooks import hooklib

    if message:
        print(hooklib.prefix_lines(HOOK_PREFIX, message))


def _run_git(root: Path, args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=str(root),
        text=True,
        capture_output=True,
    )


def main() -> int:
    _bootstrap()
    from hooks import hooklib

    root, _ = hooklib.resolve_project_root()
    if not (root / "docs").is_dir():
        return 0

    if os.environ.get("CLAUDE_SKIP_STAGE_CHECKS") != "1":
        stage = hooklib.resolve_stage(root / "docs" / ".active_stage")
        if stage != "implement":
            return 0

    config_path = root / "config" / "gates.json"
    if not hooklib.config_get_bool(config_path, "deps_allowlist", False):
        return 0

    allow_path = root / "config" / "allowed-deps.txt"
    if not allow_path.is_file():
        return 0

    allowed: set[str] = set()
    for raw in allow_path.read_text(encoding="utf-8").splitlines():
        stripped = raw.split("#", 1)[0].strip()
        stripped = "".join(stripped.split())
        if stripped:
            allowed.add(stripped)

    if not allowed:
        return 0

    added_lines: list[str] = []
    if hooklib.git_has_head(root):
        result = _run_git(
            root,
            [
                "diff",
                "--unified=0",
                "--no-color",
                "HEAD",
                "--",
                "**/build.gradle*",
                "gradle/libs.versions.toml",
            ],
        )
        if result.returncode == 0:
            for line in result.stdout.splitlines():
                if not line.startswith("+") or line.startswith("+++"):
                    continue
                added_lines.append(line[1:])

    dep_pattern = re.compile(r"(implementation|api|compileOnly|runtimeOnly)\\([\"']([^:\"'\\)]+:[^:\"'\\)]+)")
    for line in added_lines:
        match = dep_pattern.search(line)
        if not match:
            continue
        ga = match.group(2)
        if ga not in allowed:
            _log_stdout(f"WARN: dependency '{ga}' не в allowlist (config/allowed-deps.txt)")

    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
