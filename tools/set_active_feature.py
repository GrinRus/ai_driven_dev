#!/usr/bin/env python3
"""Persist the active feature slug for workflow automation."""

from __future__ import annotations

import argparse
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Write the provided slug to docs/.active_feature."
    )
    parser.add_argument("slug", help="Feature identifier to persist")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    docs_dir = Path("docs")
    docs_dir.mkdir(parents=True, exist_ok=True)
    (docs_dir / ".active_feature").write_text(args.slug, encoding="utf-8")
    print(f"active feature: {args.slug}")


if __name__ == "__main__":
    main()
