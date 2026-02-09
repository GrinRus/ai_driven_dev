#!/usr/bin/env python3
"""Guard oversized runtime modules and enforce explicit waivers."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Dict

ROOT = Path(__file__).resolve().parents[2]
RUNTIME_GLOB = "skills/*/runtime/*.py"
WAIVERS_PATH = ROOT / "tests" / "repo_tools" / "runtime-module-guard-waivers.txt"
DEFAULT_WARN = 600
DEFAULT_ERROR = 900


def _read_threshold(name: str, fallback: int) -> int:
    raw = os.getenv(name, "").strip()
    if not raw:
        return fallback
    try:
        value = int(raw)
    except ValueError:
        return fallback
    return value if value > 0 else fallback


def _line_count(path: Path) -> int:
    try:
        text = path.read_text(encoding="utf-8")
    except Exception:
        return 0
    if not text:
        return 0
    return text.count("\n") + (0 if text.endswith("\n") else 1)


def _load_waivers(path: Path) -> tuple[Dict[str, str], list[str]]:
    waivers: Dict[str, str] = {}
    errors: list[str] = []
    if not path.exists():
        return waivers, errors
    for lineno, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "|" not in line:
            errors.append(f"{path.relative_to(ROOT).as_posix()}:{lineno}: invalid format (expected path|reason)")
            continue
        rel, reason = line.split("|", 1)
        rel = rel.strip()
        reason = reason.strip()
        if not rel or not reason:
            errors.append(f"{path.relative_to(ROOT).as_posix()}:{lineno}: empty path/reason in waiver")
            continue
        if rel in waivers:
            errors.append(f"{path.relative_to(ROOT).as_posix()}:{lineno}: duplicate waiver for {rel}")
            continue
        waivers[rel] = reason
    return waivers, errors


def main() -> int:
    warn_limit = _read_threshold("AIDD_RUNTIME_MODULE_WARN_LINES", DEFAULT_WARN)
    error_limit = _read_threshold("AIDD_RUNTIME_MODULE_ERROR_LINES", DEFAULT_ERROR)
    if error_limit <= warn_limit:
        error_limit = warn_limit + 1

    waivers, parse_errors = _load_waivers(WAIVERS_PATH)
    errors: list[str] = list(parse_errors)
    warnings: list[str] = []

    runtime_paths = sorted(ROOT.glob(RUNTIME_GLOB))
    seen_runtime: Dict[str, int] = {}
    for path in runtime_paths:
        rel = path.relative_to(ROOT).as_posix()
        lines = _line_count(path)
        seen_runtime[rel] = lines
        if lines > warn_limit:
            warnings.append(f"{rel}: {lines} lines > warn threshold {warn_limit}")
        if lines > error_limit and rel not in waivers:
            errors.append(
                f"{rel}: {lines} lines > error threshold {error_limit} (add waiver in {WAIVERS_PATH.relative_to(ROOT).as_posix()})"
            )
        elif lines > error_limit and rel in waivers:
            warnings.append(f"{rel}: {lines} lines > error threshold {error_limit} (waived: {waivers[rel]})")

    for rel, reason in waivers.items():
        path = ROOT / rel
        if not path.exists():
            errors.append(f"waiver target missing: {rel} ({reason})")
            continue
        if not path.is_file():
            errors.append(f"waiver target is not file: {rel} ({reason})")
            continue
        if rel not in seen_runtime:
            errors.append(f"waiver target outside runtime glob: {rel} ({reason})")
            continue
        lines = seen_runtime[rel]
        if lines <= error_limit:
            errors.append(
                f"stale waiver: {rel} has {lines} lines <= error threshold {error_limit} ({reason}); remove waiver"
            )

    for message in warnings:
        print(f"[runtime-module-guard] WARN: {message}", file=sys.stderr)

    if errors:
        for message in errors:
            print(f"[runtime-module-guard] ERROR: {message}", file=sys.stderr)
        return 2

    print(
        f"[runtime-module-guard] OK (warn>{warn_limit}, error>{error_limit}, waivers={len(waivers)})"
    )
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
