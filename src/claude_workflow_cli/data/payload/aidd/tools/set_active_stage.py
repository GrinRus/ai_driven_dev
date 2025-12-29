#!/usr/bin/env python3
"""Persist the active workflow stage in docs/.active_stage."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Iterable

VALID_STAGES = {
    "idea",
    "research",
    "plan",
    "tasklist",
    "implement",
    "review",
    "qa",
}


def parse_args(argv: Iterable[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Write the provided stage to docs/.active_stage (under aidd/)."
    )
    parser.add_argument("stage", help="Stage name (idea/research/plan/tasklist/implement/review/qa).")
    parser.add_argument(
        "--target",
        default="aidd",
        help="Project root containing docs/.active_stage (default: aidd/ under the workspace).",
    )
    parser.add_argument(
        "--allow-custom",
        action="store_true",
        help="Allow arbitrary stage values (skip validation).",
    )
    return parser.parse_args(list(argv) if argv is not None else None)


def _resolve_root(target: str) -> Path:
    root = Path(target).resolve()
    env_root = os.getenv("CLAUDE_PLUGIN_ROOT")
    project_dir = os.getenv("CLAUDE_PROJECT_DIR")
    if env_root:
        return Path(env_root).expanduser().resolve()
    if (root / "docs").is_dir():
        return root
    for candidate in (root / "aidd", root.parent / "aidd"):
        if (candidate / "docs").is_dir():
            return candidate.resolve()
    if project_dir:
        project_candidate = Path(project_dir).expanduser().resolve()
        if (project_candidate / "docs").is_dir():
            return project_candidate
    return root


def _normalize_stage(value: str) -> str:
    return value.strip().lower().replace(" ", "-")


def _is_valid(stage: str, allow_custom: bool) -> bool:
    return allow_custom or stage in VALID_STAGES


def main(argv: Iterable[str] | None = None) -> int:
    args = parse_args(argv)
    root = _resolve_root(args.target)
    stage = _normalize_stage(args.stage)
    if not _is_valid(stage, args.allow_custom):
        valid = ", ".join(sorted(VALID_STAGES))
        print(f"[stage] invalid stage '{stage}'. Allowed: {valid}.", file=sys.stderr)
        return 2
    docs_dir = root / "docs"
    docs_dir.mkdir(parents=True, exist_ok=True)
    stage_path = docs_dir / ".active_stage"
    stage_path.write_text(stage + "\n", encoding="utf-8")
    print(f"active stage: {stage}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
