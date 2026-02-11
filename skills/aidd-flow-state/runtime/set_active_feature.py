from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Optional

from aidd_runtime import runtime
from aidd_runtime.feature_ids import read_active_state, write_active_state, read_identifiers, resolve_aidd_root, write_identifiers
from aidd_runtime import rlm_targets
from aidd_runtime.rlm_config import load_rlm_settings


def _parse_paths(value: Optional[str]) -> list[str]:
    if not value:
        return []
    return [chunk.strip() for chunk in re.split(r"[,:]", value) if chunk.strip()]


def _parse_keywords(value: Optional[str]) -> list[str]:
    if not value:
        return []
    return [chunk.strip().lower() for chunk in re.split(r"[,\s]+", value) if chunk.strip()]


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Persist the active feature ticket.")
    parser.add_argument("ticket", help="Feature ticket identifier to persist.")
    parser.add_argument(
        "--paths",
        help="Optional explicit paths for best-effort rlm-targets refresh.",
    )
    parser.add_argument(
        "--keywords",
        help="Optional keywords for best-effort rlm-targets refresh.",
    )
    parser.add_argument("--config", help=argparse.SUPPRESS)
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
    previous_state = read_active_state(root)

    write_identifiers(
        root,
        ticket=args.ticket,
        slug_hint=args.slug_note,
        scaffold_prd_file=not args.skip_prd_scaffold,
    )
    previous_ticket = (previous_state.ticket or "").strip()
    next_ticket = args.ticket.strip()
    if previous_ticket and previous_ticket != next_ticket:
        write_active_state(root, stage="", work_item="")
    identifiers = read_identifiers(root)
    resolved_slug_hint = identifiers.slug_hint or identifiers.ticket or args.ticket

    print(f"active feature: {args.ticket}")

    try:
        settings = load_rlm_settings(root)
        payload = rlm_targets.build_targets(
            root,
            args.ticket,
            settings=settings,
            paths_override=_parse_paths(args.paths) or None,
            keywords_override=_parse_keywords(args.keywords) or None,
        )
        targets_path = root / "reports" / "research" / f"{args.ticket}-rlm-targets.json"
        targets_path.parent.mkdir(parents=True, exist_ok=True)
        targets_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        rel_targets = targets_path.relative_to(root).as_posix()
        print(f"[researcher] rlm targets saved to {rel_targets}.")
    except Exception as exc:
        print(f"[researcher] WARN: skipped rlm targets refresh ({exc})", file=sys.stderr)

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
