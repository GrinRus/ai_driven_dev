#!/usr/bin/env python3
"""Guard runtime/hooks against silent `except ...: pass` handlers."""

from __future__ import annotations

import ast
import sys
from pathlib import Path
from typing import Dict, List, Tuple

ROOT = Path(__file__).resolve().parents[2]
TARGET_GLOBS = ("skills/*/runtime/**/*.py", "hooks/**/*.py", "hooks/*.py")
ALLOWLIST_PATH = ROOT / "tests" / "repo_tools" / "silent-except-allowlist.txt"


def _iter_target_files() -> List[Path]:
    files: List[Path] = []
    for pattern in TARGET_GLOBS:
        files.extend(path.resolve() for path in ROOT.glob(pattern) if path.is_file())
    unique: List[Path] = []
    seen = set()
    for path in sorted(files):
        if path in seen:
            continue
        seen.add(path)
        if path.name == "__init__.py":
            continue
        unique.append(path)
    return unique


def _handler_is_silent_pass(handler: ast.ExceptHandler) -> bool:
    body = list(handler.body)
    while body and isinstance(body[0], ast.Expr) and isinstance(getattr(body[0], "value", None), ast.Constant):
        value = getattr(body[0], "value", None)
        if isinstance(getattr(value, "value", None), str):
            body.pop(0)
            continue
        break
    return len(body) == 1 and isinstance(body[0], ast.Pass)


def _handler_label(handler: ast.ExceptHandler) -> str:
    if handler.type is None:
        return "bare"
    if isinstance(handler.type, ast.Name):
        return handler.type.id
    try:
        return ast.unparse(handler.type)
    except Exception:
        return handler.type.__class__.__name__


def _scan_file(path: Path) -> List[Tuple[int, str]]:
    try:
        source = path.read_text(encoding="utf-8")
    except OSError:
        return []

    try:
        tree = ast.parse(source, filename=str(path))
    except SyntaxError as exc:
        print(f"[silent-except-guard] ERROR: failed to parse {path.relative_to(ROOT).as_posix()}: {exc}", file=sys.stderr)
        return []

    findings: List[Tuple[int, str]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Try):
            continue
        for handler in node.handlers:
            if _handler_is_silent_pass(handler):
                findings.append((handler.lineno, _handler_label(handler)))
    return findings


def _load_allowlist(path: Path) -> tuple[Dict[str, str], List[str]]:
    allowlist: Dict[str, str] = {}
    errors: List[str] = []
    if not path.exists():
        return allowlist, errors

    for lineno, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "|" not in line:
            errors.append(f"{path.relative_to(ROOT).as_posix()}:{lineno}: invalid format (expected path:line|reason)")
            continue
        key, reason = line.split("|", 1)
        key = key.strip()
        reason = reason.strip()
        if not key or not reason:
            errors.append(f"{path.relative_to(ROOT).as_posix()}:{lineno}: empty key/reason")
            continue
        if ":" not in key:
            errors.append(f"{path.relative_to(ROOT).as_posix()}:{lineno}: key must be path:line")
            continue
        if key in allowlist:
            errors.append(f"{path.relative_to(ROOT).as_posix()}:{lineno}: duplicate allowlist key {key}")
            continue
        allowlist[key] = reason
    return allowlist, errors


def main() -> int:
    allowlist, parse_errors = _load_allowlist(ALLOWLIST_PATH)
    violations: Dict[str, str] = {}
    errors: List[str] = list(parse_errors)

    for path in _iter_target_files():
        rel = path.relative_to(ROOT).as_posix()
        for lineno, label in _scan_file(path):
            key = f"{rel}:{lineno}"
            violations[key] = label

    for key, label in sorted(violations.items()):
        if key in allowlist:
            continue
        errors.append(f"{key}: silent except handler (`except {label}: pass`) is forbidden")

    for key, reason in sorted(allowlist.items()):
        if key not in violations:
            errors.append(f"stale allowlist entry: {key} ({reason})")

    if errors:
        for message in errors:
            print(f"[silent-except-guard] ERROR: {message}", file=sys.stderr)
        return 2

    print(f"[silent-except-guard] OK (violations=0, allowlist={len(allowlist)})")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
