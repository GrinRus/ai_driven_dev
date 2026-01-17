#!/usr/bin/env python3
from __future__ import annotations

import os
import sys
from pathlib import Path


def _bootstrap() -> None:
    raw = os.environ.get("CLAUDE_PLUGIN_ROOT")
    if not raw:
        print("[context-gc-pretooluse] CLAUDE_PLUGIN_ROOT is required to run hooks.", file=sys.stderr)
        raise SystemExit(2)
    plugin_root = Path(raw).expanduser().resolve()
    if str(plugin_root) not in sys.path:
        sys.path.insert(0, str(plugin_root))
    vendor_dir = Path(__file__).resolve().parent / "_vendor"
    if vendor_dir.exists():
        sys.path.insert(0, str(vendor_dir))


def main() -> int:
    _bootstrap()
    from hooks.context_gc import pretooluse_guard

    result = pretooluse_guard.main()
    if isinstance(result, int):
        return result
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
