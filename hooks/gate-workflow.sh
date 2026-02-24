#!/usr/bin/env python3
from __future__ import annotations

import os
import sys
from pathlib import Path

HOOK_PREFIX = "[gate-workflow]"


def _bootstrap() -> None:
    raw = os.environ.get("CLAUDE_PLUGIN_ROOT")
    if not raw:
        print(f"{HOOK_PREFIX} CLAUDE_PLUGIN_ROOT is required to run hooks.", file=sys.stderr)
        raise SystemExit(2)
    plugin_root = Path(raw).expanduser().resolve()
    if str(plugin_root) not in sys.path:
        sys.path.insert(0, str(plugin_root))
    vendor_dir = Path(__file__).resolve().parent / "_vendor"
    if vendor_dir.exists():
        sys.path.insert(0, str(vendor_dir))


def main() -> int:
    _bootstrap()
    from hooks import gate_workflow as tools_module

    return tools_module.main()


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
