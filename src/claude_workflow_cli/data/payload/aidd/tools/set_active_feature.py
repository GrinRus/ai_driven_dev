#!/usr/bin/env python3
"""Persist the active feature ticket and refresh Researcher targets."""

from __future__ import annotations

import argparse
import datetime as dt
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Optional, Sequence

try:
    from run_cli import CliNotFoundError, run_cli  # type: ignore
except Exception:  # pragma: no cover - helper missing (legacy payload)
    CliNotFoundError = RuntimeError  # type: ignore
    run_cli = None  # type: ignore

REPO_ROOT = Path(__file__).resolve().parents[1]
REPO_SRC = REPO_ROOT / "src"
if REPO_SRC.is_dir():
    repo_src_str = str(REPO_SRC)
    if repo_src_str not in sys.path:
        sys.path.insert(0, repo_src_str)

try:
    from claude_workflow_cli.feature_ids import read_identifiers, write_identifiers  # type: ignore
except ImportError:  # pragma: no cover - fallback when installed standalone
    read_identifiers = None  # type: ignore
    write_identifiers = None  # type: ignore

try:
    from researcher_context import ResearcherContextBuilder, _parse_paths
except ImportError:  # pragma: no cover - fallback when module unavailable
    ResearcherContextBuilder = None  # type: ignore


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Write the provided ticket to docs/.active_ticket (under aidd/) and update Researcher targets."
    )
    parser.add_argument("ticket", help="Feature ticket identifier to persist")
    parser.add_argument(
        "--target",
        default="aidd",
        help="Project root containing docs/.active_ticket (default: aidd/ under the workspace).",
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
    parser.add_argument(
        "--skip-prd-scaffold",
        action="store_true",
        help="Skip automatic docs/prd/<ticket>.prd.md scaffold creation.",
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


def _cli_available() -> bool:
    if run_cli is None:
        return False
    try:
        import importlib.util

        if importlib.util.find_spec("claude_workflow_cli.cli"):
            return True
    except Exception:
        pass
    return bool(shutil.which("claude-workflow"))


def _run_cli_research_targets(
    root: Path,
    ticket: str,
    slug_hint: Optional[str],
    *,
    paths_arg: Optional[str],
    keywords_arg: Optional[str],
    config_arg: Optional[str],
) -> bool:
    if run_cli is None:
        return False
    if not _cli_available():
        return False
    cli_args = [
        "research",
        "--target",
        str(root),
        "--ticket",
        ticket,
        "--targets-only",
        "--auto",
        "--no-template",
    ]
    if slug_hint:
        cli_args.extend(["--slug-hint", slug_hint])
    if config_arg:
        cli_args.extend(["--config", config_arg])
    if paths_arg:
        cli_args.extend(["--paths", paths_arg])
    if keywords_arg:
        cli_args.extend(["--keywords", keywords_arg])
    try:
        run_cli(cli_args, cwd=str(root))
        return True
    except (CliNotFoundError, subprocess.CalledProcessError, Exception) as exc:
        if isinstance(exc, CliNotFoundError):
            print(str(exc), file=sys.stderr)
        return False
    return False


def _scaffold_prd_manual(root: Path, ticket: str) -> bool:
    docs_dir = root / "docs"
    template_path = docs_dir / "prd" / "template.md"
    prd_path = docs_dir / "prd" / f"{ticket}.prd.md"
    if not template_path.exists() or prd_path.exists():
        return False
    try:
        content = template_path.read_text(encoding="utf-8")
    except Exception:
        return False
    content = content.replace("<ticket>", ticket)
    prd_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        prd_path.write_text(content, encoding="utf-8")
    except Exception:
        return False
    return True


def main() -> None:
    args = parse_args()
    root = Path(args.target).resolve()
    env_root = os.getenv("CLAUDE_PLUGIN_ROOT")
    project_dir = os.getenv("CLAUDE_PROJECT_DIR")
    if env_root:
        root = Path(env_root).expanduser().resolve()
    elif not (root / "docs").is_dir():
        for candidate in (root / "aidd", root.parent / "aidd"):
            if (candidate / "docs").is_dir():
                root = candidate.resolve()
                break
        if project_dir and not (root / "docs").is_dir():
            project_candidate = Path(project_dir).expanduser().resolve()
            if (project_candidate / "docs").is_dir():
                root = project_candidate
    docs_dir = root / "docs"
    docs_dir.mkdir(parents=True, exist_ok=True)
    resolved_slug_hint = args.slug_hint
    scaffold_enabled = not args.skip_prd_scaffold

    if write_identifiers is not None:
        write_identifiers(
            root,
            ticket=args.ticket,
            slug_hint=args.slug_hint,
            scaffold_prd_file=scaffold_enabled,
        )
        if read_identifiers is not None:
            identifiers = read_identifiers(root)
            resolved_slug_hint = (identifiers.slug_hint or identifiers.ticket or args.ticket)
    else:  # pragma: no cover - minimal fallback without package
        (docs_dir / ".active_ticket").write_text(args.ticket, encoding="utf-8")
        hint_value = args.slug_hint if args.slug_hint is not None else args.ticket
        (docs_dir / ".active_feature").write_text(hint_value, encoding="utf-8")
        resolved_slug_hint = hint_value
        if scaffold_enabled and _scaffold_prd_manual(root, args.ticket):
            print(f"[prd] scaffolded docs/prd/{args.ticket}.prd.md", file=sys.stderr)
    print(f"active feature: {args.ticket}")
    _maybe_migrate_tasklist(root, args.ticket, resolved_slug_hint)

    if _run_cli_research_targets(
        root,
        args.ticket,
        resolved_slug_hint,
        paths_arg=args.paths,
        keywords_arg=args.keywords,
        config_arg=args.config,
    ):
        return

    if ResearcherContextBuilder is None:
        print("[researcher] skip: researcher_context module not found", file=sys.stderr)
        return

    config_path = Path(args.config).resolve() if args.config else None
    builder = ResearcherContextBuilder(root, config_path=config_path)
    scope = builder.build_scope(args.ticket, slug_hint=resolved_slug_hint)
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
