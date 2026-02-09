from __future__ import annotations

import argparse
import json
from pathlib import Path

from aidd_runtime.feature_ids import resolve_aidd_root, resolve_identifiers


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Resolve active feature identifiers (ticket and slug hint).",
    )
    parser.add_argument(
        "--ticket",
        help="Optional ticket override (defaults to docs/.active.json).",
    )
    parser.add_argument(
        "--slug-hint",
        dest="slug_hint",
        help="Optional slug hint override (defaults to docs/.active.json).",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit identifiers as JSON for automation.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    root = resolve_aidd_root(Path.cwd())
    identifiers = resolve_identifiers(root, ticket=args.ticket, slug_hint=args.slug_hint)
    if args.json:
        payload = {
            "ticket": identifiers.ticket,
            "slug_hint": identifiers.slug_hint,
            "resolved_ticket": identifiers.resolved_ticket,
        }
        print(json.dumps(payload, ensure_ascii=False))
        return 0

    ticket = identifiers.resolved_ticket or ""
    hint = (identifiers.slug_hint or "").strip()
    if hint and hint != ticket:
        if ticket:
            print(f"{ticket} ({hint})")
        else:
            print(hint)
    else:
        print(ticket)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
