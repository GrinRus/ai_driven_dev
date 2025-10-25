#!/usr/bin/env python3
"""Persist the active feature ticket and refresh Researcher targets."""

from __future__ import annotations

import argparse
import datetime as dt
import sys
from pathlib import Path
from typing import Optional, Sequence

_SCRIPT_PATH = Path(__file__).resolve()
_REPO_ROOT_CANDIDATE: Optional[Path] = None
for _candidate in _SCRIPT_PATH.parents:
    if (_candidate / "src").is_dir():
        _REPO_ROOT_CANDIDATE = _candidate
        break
if _REPO_ROOT_CANDIDATE is None:
    _REPO_ROOT_CANDIDATE = _SCRIPT_PATH.parent
_REPO_SRC = _REPO_ROOT_CANDIDATE / "src"
if _REPO_SRC.is_dir():
    _reporc = str(_REPO_SRC)
    if _reporc not in sys.path:
        sys.path.insert(0, _reporc)

try:
    from claude_workflow_cli.feature_ids import write_identifiers  # type: ignore
except ImportError:  # pragma: no cover - fallback when installed standalone
    write_identifiers = None  # type: ignore

try:
    from researcher_context import ResearcherContextBuilder, _parse_paths
except ImportError:  # pragma: no cover - fallback when module unavailable
    ResearcherContextBuilder = None  # type: ignore


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Write the provided ticket to docs/.active_ticket and update Researcher targets."
    )
    parser.add_argument("ticket", help="Feature ticket identifier to persist")
    parser.add_argument(
        "--target",
        default=".",
        help="Project root containing docs/.active_ticket (default: current directory).",
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
    parser.add_argument(
        "--slug-note",
        dest="slug_hint",
        help="Optional slug hint to persist alongside the ticket.",
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


def _maybe_migrate_tasklist(root: Path, ticket: str, slug_hint: Optional[str]) -> None:
    legacy = root / "tasklist.md"
    if not legacy.exists():
        return
    destination = root / "docs" / "tasklist" / f"{ticket}.md"
    if destination.exists():
        return
    try:
        display_name = slug_hint or ticket
        title = _slug_to_title(display_name)
        slug_value = slug_hint or ticket
        today = dt.date.today().isoformat()
        legacy_text = legacy.read_text(encoding="utf-8")
        body = _render_body_with_heading(legacy_text, title)
        front_matter = (
            "---\n"
            f"Ticket: {ticket}\n"
            f"Slug hint: {slug_value}\n"
            f"Feature: {title}\n"
            "Status: draft\n"
            f"PRD: docs/prd/{ticket}.prd.md\n"
            f"Plan: docs/plan/{ticket}.md\n"
            f"Research: docs/research/{ticket}.md\n"
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
    if write_identifiers is not None:
        write_identifiers(root, ticket=args.ticket, slug_hint=args.slug_hint)
    else:  # pragma: no cover - minimal fallback without package
        (docs_dir / ".active_ticket").write_text(args.ticket, encoding="utf-8")
        hint_value = args.slug_hint if args.slug_hint is not None else args.ticket
        (docs_dir / ".active_feature").write_text(hint_value, encoding="utf-8")
    print(f"active feature: {args.ticket}")
    _maybe_migrate_tasklist(root, args.ticket, args.slug_hint)

    if ResearcherContextBuilder is None:
        print("[researcher] skip: researcher_context module not found", file=sys.stderr)
        return

    config_path = Path(args.config).resolve() if args.config else None
    builder = ResearcherContextBuilder(root, config_path=config_path)
    scope = builder.build_scope(args.ticket, slug_hint=args.slug_hint)
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
