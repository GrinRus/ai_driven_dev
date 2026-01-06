#!/usr/bin/env python3
"""Show differences between RU and EN prompt files (EN optional)."""

from __future__ import annotations

import argparse
import difflib
import sys
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Diff RU vs EN prompt text")
    parser.add_argument("--name", required=True, help="Prompt name (e.g., implementer, plan-new)")
    parser.add_argument(
        "--kind",
        choices=("agent", "command"),
        required=True,
        help="Prompt type",
    )
    parser.add_argument(
        "--root",
        default=Path(__file__).resolve().parents[1],
        type=Path,
        help="Repository root",
    )
    parser.add_argument("--context", type=int, default=3, help="Number of context lines in diff")
    return parser.parse_args()


def load(path: Path) -> list[str]:
    if not path.exists():
        raise FileNotFoundError(path)
    return path.read_text(encoding="utf-8").splitlines(keepends=True)


def resolve_ru_base(root: Path, kind: str) -> Path:
    subdir = "agents" if kind == "agent" else "commands"
    candidates = [
        root / subdir,
        root / "aidd" / subdir,
        root / ".claude" / subdir,
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0]


def resolve_en_base(root: Path, kind: str) -> Path:
    subdir = "agents" if kind == "agent" else "commands"
    candidates = [
        root / "prompts" / "en" / subdir,
        root / "aidd" / "prompts" / "en" / subdir,
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0]


def main() -> int:
    args = parse_args()
    root = args.root
    ru_base = resolve_ru_base(root, args.kind)
    en_base = resolve_en_base(root, args.kind)
    ru_path = ru_base / f"{args.name}.md"
    en_path = en_base / f"{args.name}.md"

    try:
        ru_lines = load(ru_path)
    except FileNotFoundError:
        print(f"[prompt-diff] missing RU file: {ru_path}", file=sys.stderr)
        return 1
    if not en_path.exists():
        print(f"[prompt-diff] EN prompt missing; skipping diff ({en_path})")
        return 0
    en_lines = load(en_path)

    diff = list(
        difflib.unified_diff(
            ru_lines,
            en_lines,
            fromfile=str(ru_path),
            tofile=str(en_path),
            n=args.context,
        )
    )
    if not diff:
        print("[prompt-diff] no differences detected")
        return 0
    sys.stdout.writelines(diff)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
