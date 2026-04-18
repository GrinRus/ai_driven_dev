#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import List, Tuple


NORMALIZE_DROP = re.compile(r"^(prompt_version|source_version|generated_at|updated_at)\s*:\s*.+$", re.IGNORECASE)


def _normalize(text: str) -> str:
    lines = []
    for line in text.splitlines():
        if NORMALIZE_DROP.match(line.strip()):
            continue
        lines.append(line.rstrip())
    return "\n".join(lines).strip()

def _compare_file(src: Path, dst: Path) -> Tuple[bool, str]:
    if not dst.exists():
        return False, f"missing target: {dst}"
    src_text = _normalize(src.read_text(encoding="utf-8"))
    dst_text = _normalize(dst.read_text(encoding="utf-8"))
    if src_text != dst_text:
        return False, f"content mismatch: {src} vs {dst}"
    return True, ""


def parse_args(argv: List[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Verify prompt/template sync across payload roots.")
    parser.add_argument("--root", default=".", help="Repository root (default: .).")
    parser.add_argument(
        "--payload-root",
        action="append",
        default=[],
        help="Optional payload root to compare against (can be repeated).",
    )
    return parser.parse_args(argv)


def main(argv: List[str] | None = None) -> int:
    args = parse_args(argv)
    repo_root = Path(args.root).resolve()
    payload_roots = [Path(raw).resolve() for raw in args.payload_root]

    file_pairs = [
        (repo_root / "skills" / "aidd-core" / "templates" / "workspace-agents.md", repo_root / "aidd" / "AGENTS.md"),
    ]

    issues: List[str] = []
    for src, dst in file_pairs:
        if src.exists() and dst.exists():
            ok, msg = _compare_file(src, dst)
            if not ok:
                issues.append(msg)

    for payload_root in payload_roots:
        for src, _ in file_pairs:
            rel = src.relative_to(repo_root)
            dst = payload_root / rel
            if src.exists() and dst.exists():
                ok, msg = _compare_file(src, dst)
                if not ok:
                    issues.append(msg)

    if issues:
        for issue in issues:
            print(f"[prompt-sync] {issue}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
