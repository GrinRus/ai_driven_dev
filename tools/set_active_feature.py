#!/usr/bin/env python3
"""Persist the active feature slug and refresh Researcher targets."""

from __future__ import annotations

import argparse
import datetime as dt
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


def _slug_to_title(slug: str) -> str:
    parts = [chunk for chunk in slug.replace("_", "-").split("-") if chunk]
    if not parts:
        return slug
    return " ".join(part.capitalize() for part in parts)


def _render_body_with_heading(original: str, title: str) -> str:
    lines = original.splitlines()
    idx = next((i for i, line in enumerate(lines) if line.strip()), None)
    if idx is None:
        return f"# Tasklist — {title}\n"
    first = lines[idx].strip()
    if first.lower().startswith("# tasklist"):
        lines[idx] = f"# Tasklist — {title}"
    else:
        lines.insert(idx, f"# Tasklist — {title}")
    return "\n".join(lines).rstrip() + "\n"


def _maybe_migrate_tasklist(root: Path, slug: str) -> None:
    legacy = root / "tasklist.md"
    if not legacy.exists():
        return
    destination = root / "docs" / "tasklist" / f"{slug}.md"
    if destination.exists():
        return
    try:
        title = _slug_to_title(slug)
        today = dt.date.today().isoformat()
        legacy_text = legacy.read_text(encoding="utf-8")
        body = _render_body_with_heading(legacy_text, title)
        front_matter = (
            "---\n"
            f"Feature: {slug}\n"
            "Status: draft\n"
            f"PRD: docs/prd/{slug}.prd.md\n"
            f"Plan: docs/plan/{slug}.md\n"
            f"Research: docs/research/{slug}.md\n"
            f"Updated: {today}\n"
            "---\n\n"
        )
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(front_matter + body, encoding="utf-8")
        legacy.unlink()
        print(f"[tasklist] migrated legacy tasklist.md to {destination}", file=sys.stderr)
    except Exception as exc:  # pragma: no cover - defensive logging
        print(f"[tasklist] failed to migrate legacy tasklist.md: {exc}", file=sys.stderr)


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
    _maybe_migrate_tasklist(root, args.slug)

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
