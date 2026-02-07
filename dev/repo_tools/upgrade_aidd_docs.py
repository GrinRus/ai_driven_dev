#!/usr/bin/env python3
"""Compatibility shim for legacy dev/repo_tools upgrade entrypoint."""

from __future__ import annotations

import runpy
import sys
from pathlib import Path


def main() -> int:
    repo_root = Path(__file__).resolve().parents[2]
    target = repo_root / "tests" / "repo_tools" / "upgrade_aidd_docs.py"
    if not target.exists():
        print(f"[upgrade-aidd-docs] missing target script: {target}", file=sys.stderr)
        return 2

    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))
    runpy.run_path(str(target), run_name="__main__")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
