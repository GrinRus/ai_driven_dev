#!/usr/bin/env python3
from __future__ import annotations

import os
import sys
from pathlib import Path


def _bootstrap() -> None:
    raw = os.environ.get("CLAUDE_PLUGIN_ROOT")
    if raw:
        plugin_root = Path(raw).expanduser().resolve()
    else:
        plugin_root = Path(__file__).resolve().parent.parent
        os.environ["CLAUDE_PLUGIN_ROOT"] = str(plugin_root)
    if str(plugin_root) not in sys.path:
        sys.path.insert(0, str(plugin_root))


def main() -> int:
    _bootstrap()
    from tools import researcher_context

    argv = sys.argv[1:]
    if argv and argv[0] == "--":
        argv = argv[1:]
    return researcher_context.main(argv)

if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
