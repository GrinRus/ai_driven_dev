#!/usr/bin/env python3
"""
Materialise the bundled payload into a local workspace for dogfooding.

By default the payload is copied into `.dev/.claude-example/`. Use `--force`
to overwrite the target directory if it already exists.
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path


def copy_payload(src: Path, dest: Path) -> None:
    for path in src.rglob("*"):
        relative = path.relative_to(src)
        target = dest / relative
        if path.is_dir():
            target.mkdir(parents=True, exist_ok=True)
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Copy the packaged payload into a local workspace for testing."
    )
    parser.add_argument(
        "--target",
        default=".dev/.claude-example",
        help="Relative path where the payload should be materialised "
             "(default: .dev/.claude-example).",
    )
    parser.add_argument(
        "--payload",
        help="Override payload source directory (defaults to src/claude_workflow_cli/data/payload).",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite the target directory if it already exists.",
    )
    args = parser.parse_args(argv)

    script_dir = Path(__file__).resolve().parent
    repo_root = script_dir.parent

    payload_root = Path(args.payload) if args.payload else repo_root / "src" / "claude_workflow_cli" / "data" / "payload"
    if not payload_root.exists():
        parser.error(f"payload directory not found: {payload_root}")

    target_dir = (repo_root / args.target).resolve()
    if not target_dir.is_relative_to(repo_root):
        parser.error("target must be inside the repository")

    if target_dir.exists():
        if not args.force:
            parser.error(f"{target_dir} already exists; rerun with --force to overwrite")
        shutil.rmtree(target_dir)

    target_dir.mkdir(parents=True, exist_ok=True)
    copy_payload(payload_root, target_dir)
    print(f"[bootstrap-local] payload copied to {target_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
