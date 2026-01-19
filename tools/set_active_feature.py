from __future__ import annotations

import argparse
from pathlib import Path
from typing import Optional

from tools import runtime
from tools.feature_ids import read_identifiers, resolve_project_root as resolve_aidd_root, write_identifiers
from tools.researcher_context import (
    ResearcherContextBuilder,
    _parse_keywords as _research_parse_keywords,
    _parse_paths as _research_parse_paths,
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Persist the active feature ticket and refresh Researcher targets.",
    )
    parser.add_argument("ticket", help="Feature ticket identifier to persist.")
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
        help="Path to conventions JSON with researcher section (defaults to config/conventions.json).",
    )
    parser.add_argument(
        "--slug-note",
        dest="slug_note",
        help="Optional slug hint to persist alongside the ticket.",
    )
    parser.add_argument(
        "--skip-prd-scaffold",
        action="store_true",
        help="Skip automatic docs/prd/<ticket>.prd.md scaffold creation.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    root = resolve_aidd_root(Path.cwd())
    docs_dir = root / "docs"
    docs_dir.mkdir(parents=True, exist_ok=True)

    write_identifiers(
        root,
        ticket=args.ticket,
        slug_hint=args.slug_note,
        scaffold_prd_file=not args.skip_prd_scaffold,
    )
    identifiers = read_identifiers(root)
    resolved_slug_hint = identifiers.slug_hint or identifiers.ticket or args.ticket

    print(f"active feature: {args.ticket}")

    config_path: Optional[Path] = None
    if args.config:
        config_path = Path(args.config)
        if not config_path.is_absolute():
            config_path = (root / config_path).resolve()
        else:
            config_path = config_path.resolve()

    builder = ResearcherContextBuilder(root, config_path=config_path)
    scope = builder.build_scope(args.ticket, slug_hint=resolved_slug_hint)
    scope = builder.extend_scope(
        scope,
        extra_paths=_research_parse_paths(args.paths),
        extra_keywords=_research_parse_keywords(args.keywords),
    )
    targets_path = builder.write_targets(scope)
    rel_targets = targets_path.relative_to(root).as_posix()
    print(f"[researcher] targets saved to {rel_targets} ({len(scope.paths)} paths, {len(scope.docs)} docs)")

    index_ticket = identifiers.resolved_ticket or args.ticket
    index_slug = resolved_slug_hint or index_ticket
    runtime.maybe_sync_index(
        root,
        index_ticket,
        index_slug,
        reason="set-active-feature",
        announce=True,
    )
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
