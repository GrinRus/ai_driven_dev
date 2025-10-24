#!/usr/bin/env python3
"""Migrate legacy slug-based tasklist.md into docs/tasklist/<slug>.md.

This helper targets pre-ticket installations. Modern projects should use
`tools/migrate_ticket.py` to adopt the ticket-first layout.

This helper is retained for repositories created before Wave 26 (when tasklists
were stored at the repo root and identified only by slug). Modern ticket-first
projects should use `tools/migrate_ticket.py` instead.
"""

from __future__ import annotations

import argparse
import datetime as dt
import sys
from pathlib import Path


def slug_to_title(slug: str) -> str:
    parts = [chunk for chunk in slug.replace("_", "-").split("-") if chunk]
    if not parts:
        return slug
    return " ".join(part.capitalize() for part in parts)


def resolve_slug(root: Path, provided: str | None) -> str:
    if provided:
        return provided.strip()
    active_file = root / "docs" / ".active_feature"
    if active_file.exists():
        raw = active_file.read_text(encoding="utf-8").strip()
        if raw:
            return raw
    plan_dir = root / "docs" / "plan"
    if plan_dir.exists():
        plans = sorted(path.stem for path in plan_dir.glob("*.md"))
        if len(plans) == 1:
            return plans[0]
    raise SystemExit("Cannot determine feature slug: use --slug or populate docs/.active_feature.")


def render_body_with_heading(original: str, title: str) -> str:
    lines = original.splitlines()
    idx = None
    for i, line in enumerate(lines):
        if line.strip():
            idx = i
            break
    if idx is None:
        return f"# Tasklist — {title}\n"
    first = lines[idx].strip()
    if first.lower().startswith("# tasklist"):
        lines[idx] = f"# Tasklist — {title}"
    else:
        lines.insert(idx, f"# Tasklist — {title}")
    return "\n".join(lines).rstrip() + "\n"


def migrate(root: Path, slug: str, force: bool) -> int:
    legacy = root / "tasklist.md"
    if not legacy.exists():
        print("[tasklist] legacy tasklist.md not found; nothing to migrate.")
        return 0

    destination = root / "docs" / "tasklist" / f"{slug}.md"
    if destination.exists() and not force:
        print(f"[tasklist] destination {destination} already exists. Use --force to overwrite.")
        return 1

    title = slug_to_title(slug)
    today = dt.date.today().isoformat()
    legacy_text = legacy.read_text(encoding="utf-8")
    body = render_body_with_heading(legacy_text, title)
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

    feature_file = root / "docs" / ".active_feature"
    feature_file.parent.mkdir(parents=True, exist_ok=True)
    feature_file.write_text(slug + "\n", encoding="utf-8")

    ticket_file = root / "docs" / ".active_ticket"
    ticket_file.parent.mkdir(parents=True, exist_ok=True)
    ticket_file.write_text(slug + "\n", encoding="utf-8")

    print(f"[tasklist] migrated to {destination}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Move legacy slug-based tasklist.md under docs/tasklist/<slug>.md (pre-ticket workflow)."
    )
    parser.add_argument("--slug", help="Feature slug to use; defaults to docs/.active_feature or single plan file.")
    parser.add_argument("--target", default=".", help="Project root containing legacy tasklist.md (default: cwd).")
    parser.add_argument("--force", action="store_true", help="Overwrite existing docs/tasklist/<slug>.md if present.")
    args = parser.parse_args(argv)

    root = Path(args.target).resolve()
    slug = resolve_slug(root, args.slug)
    return migrate(root, slug, args.force)


if __name__ == "__main__":
    sys.exit(main())
