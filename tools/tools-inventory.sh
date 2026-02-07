#!/usr/bin/env python3
"""Compatibility shim for legacy tools-inventory.sh entrypoint."""

from __future__ import annotations

import os
import sys
from pathlib import Path


def _plugin_root() -> Path:
    raw = os.environ.get("CLAUDE_PLUGIN_ROOT")
    if raw:
        return Path(raw).expanduser().resolve()
    plugin_root = Path(__file__).resolve().parent.parent
    os.environ["CLAUDE_PLUGIN_ROOT"] = str(plugin_root)
    return plugin_root


def main() -> int:
    plugin_root = _plugin_root()
    target = plugin_root / "tools" / "tools-inventory.py"
    os.execv(sys.executable, [sys.executable, str(target), *sys.argv[1:]])
    return 127


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
