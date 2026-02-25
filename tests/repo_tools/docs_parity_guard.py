#!/usr/bin/env python3
"""Guard documentation parity and migration consistency."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


RU_REQUIRED = (
    "## Что это",
    "## Быстрый старт",
    "## Скрипты и проверки",
    "## Слэш-команды",
    "## Документация",
)

EN_REQUIRED = (
    "## What it is",
    "## Get Started",
    "## Scripts and Checks",
    "## Slash Commands",
    "## Documentation",
)

LEGACY_HOOK_PATTERNS = (
    re.compile(r"hooks/[A-Za-z0-9_.-]+\\.sh"),
    re.compile(r"hooks/<hook>\\.sh"),
    re.compile(r"\\bgate-workflow\\.sh\\b"),
    re.compile(r"\\bgate-tests\\.sh\\b"),
    re.compile(r"\\bgate-qa\\.sh\\b"),
    re.compile(r"\\bformat-and-test\\.sh\\b"),
    re.compile(r"\\blint-deps\\.sh\\b"),
    re.compile(r"\\bcontext-gc-[a-z-]+\\.sh\\b"),
)

LOCAL_ABSOLUTE_PATH_PATTERNS = (
    re.compile(r"(?<![A-Za-z0-9_])/(Users|home)/[^\s)`\"']+"),
    re.compile(r"\b[A-Za-z]:\\[^\s)`\"']+"),
)

LEGACY_ALLOWED_DOCS = {
    "docs/runbooks/prod-like-breaking-migration.md",
}


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError as exc:
        raise RuntimeError(f"failed to read {path}: {exc}") from exc


def _require_sections(path: Path, sections: tuple[str, ...], errors: list[str]) -> None:
    text = _read(path)
    for section in sections:
        if section not in text:
            errors.append(f"{path.as_posix()}: missing section '{section}'")


def _check_legacy_hooks(path: Path, root: Path, errors: list[str]) -> None:
    rel = path.relative_to(root).as_posix()
    if rel in LEGACY_ALLOWED_DOCS:
        return
    text = _read(path)
    for pattern in LEGACY_HOOK_PATTERNS:
        if pattern.search(text):
            errors.append(f"{path.as_posix()}: legacy hook path reference found ({pattern.pattern})")


def _check_local_absolute_paths(path: Path, errors: list[str]) -> None:
    text = _read(path)
    for pattern in LOCAL_ABSOLUTE_PATH_PATTERNS:
        if pattern.search(text):
            errors.append(f"{path.as_posix()}: local absolute path reference found ({pattern.pattern})")


def _check_relative_links(path: Path, errors: list[str]) -> None:
    text = _read(path)
    for match in re.finditer(r"\[[^\]]+\]\(([^)]+)\)", text):
        target = match.group(1).strip()
        if not target or target.startswith(("http://", "https://", "#", "mailto:")):
            continue
        if target.startswith("/"):
            continue
        target_path = (path.parent / target).resolve()
        if not target_path.exists():
            errors.append(f"{path.as_posix()}: broken relative link -> {target}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate docs parity and migration references.")
    parser.add_argument("--root", default=".", help="Repository root")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    errors: list[str] = []

    ru = root / "README.md"
    en = root / "README.en.md"
    agents = root / "AGENTS.md"

    _require_sections(ru, RU_REQUIRED, errors)
    _require_sections(en, EN_REQUIRED, errors)

    docs_to_scan = [ru, en, agents]
    docs_to_scan.extend(sorted((root / "docs").rglob("*.md")))

    for path in docs_to_scan:
        _check_legacy_hooks(path, root, errors)
        _check_local_absolute_paths(path, errors)
        _check_relative_links(path, errors)

    if errors:
        for item in errors[:200]:
            print(f"[docs-parity] {item}", file=sys.stderr)
        if len(errors) > 200:
            print(f"[docs-parity] ... and {len(errors) - 200} more", file=sys.stderr)
        return 2

    print("[docs-parity] OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
