#!/usr/bin/env python3
"""Persist the active feature slug and refresh Researcher targets."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Optional, Sequence

try:
    from researcher_context import ResearcherContextBuilder, _parse_paths
except ImportError:  # pragma: no cover - fallback when module unavailable
    ResearcherContextBuilder = None  # type: ignore


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Write the provided slug to docs/.active_feature and update Researcher targets."
    )
    parser.add_argument("slug", help="Feature identifier to persist")
    parser.add_argument(
        "--target",
        default=".",
        help="Project root containing docs/.active_feature (default: current directory).",
    )
    parser.add_argument(
        "--paths",
        help="Optional colon-separated list of extra paths for Researcher scope.",
    )
    parser.add_argument(
        "--keywords",
        help="Optional comma-separated keywords to seed Researcher search.",
    )
    parser.add_argument(
        "--config",
        help="Path to conventions.json with researcher section (defaults to config/conventions.json).",
    )
    return parser.parse_args()


def _split_keywords(value: Optional[str]) -> Sequence[str]:
    if not value:
        return []
    return [chunk.strip().lower() for chunk in value.split(",") if chunk.strip()]


def main() -> None:
    args = parse_args()
    root = Path(args.target).resolve()
    docs_dir = root / "docs"
    docs_dir.mkdir(parents=True, exist_ok=True)
    (docs_dir / ".active_feature").write_text(args.slug, encoding="utf-8")
    print(f"active feature: {args.slug}")

    if ResearcherContextBuilder is None:
        print("[researcher] skip: researcher_context module not found", file=sys.stderr)
        return

    config_path = Path(args.config).resolve() if args.config else None
    builder = ResearcherContextBuilder(root, config_path=config_path)
    scope = builder.build_scope(args.slug)
    scope = builder.extend_scope(
        scope,
        extra_paths=_parse_paths(args.paths) if args.paths else None,
        extra_keywords=_split_keywords(args.keywords),
    )
    targets_path = builder.write_targets(scope)
    rel_targets = targets_path.relative_to(root).as_posix()
    print(f"[researcher] targets saved to {rel_targets} ({len(scope.paths)} paths, {len(scope.docs)} docs)")


if __name__ == "__main__":
    main()
