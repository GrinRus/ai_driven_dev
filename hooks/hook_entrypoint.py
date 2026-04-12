#!/usr/bin/env python3
from __future__ import annotations

import importlib
import os
import sys
from pathlib import Path


def _bootstrap(hook_prefix: str) -> None:
    raw = os.environ.get("CLAUDE_PLUGIN_ROOT")
    if not raw:
        print(f"{hook_prefix} CLAUDE_PLUGIN_ROOT is required to run hooks.", file=sys.stderr)
        raise SystemExit(2)
    plugin_root = Path(raw).expanduser().resolve()
    if str(plugin_root) not in sys.path:
        sys.path.insert(0, str(plugin_root))
    vendor_dir = Path(__file__).resolve().parent / "_vendor"
    if vendor_dir.exists():
        sys.path.insert(0, str(vendor_dir))


def run_hook_module(*, hook_prefix: str, module_import_path: str) -> int:
    _bootstrap(hook_prefix)
    module = importlib.import_module(module_import_path)
    result = module.main()
    if isinstance(result, int):
        return result
    return 0
