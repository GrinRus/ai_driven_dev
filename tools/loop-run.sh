#!/usr/bin/env python3
from __future__ import annotations

import os
import sys
from pathlib import Path


def _detect_plugin_root() -> tuple[Path, bool, str]:
    raw = os.environ.get("CLAUDE_PLUGIN_ROOT") or os.environ.get("AIDD_PLUGIN_DIR")
    warn = ""
    if raw:
        plugin_root = Path(raw).expanduser().resolve()
        if (plugin_root / "tools").exists() and (
            (plugin_root / "skills").exists() or (plugin_root / "commands").exists()
        ):
            return plugin_root, False, ""
        warn = f"[loop-run] WARN: CLAUDE_PLUGIN_ROOT invalid: {plugin_root}; trying auto-detect"
    candidate = Path(__file__).resolve().parent.parent
    if (candidate / "tools").exists() and ((candidate / "skills").exists() or (candidate / "commands").exists()):
        os.environ["CLAUDE_PLUGIN_ROOT"] = str(candidate)
        return candidate, True, warn
    raise RuntimeError("CLAUDE_PLUGIN_ROOT (or AIDD_PLUGIN_DIR) is required to run loop-run.")


def _bootstrap() -> None:
    plugin_root, used_auto, warn = _detect_plugin_root()
    if not plugin_root.exists():
        raise RuntimeError(f"plugin root not found: {plugin_root}")
    os.environ.setdefault("CLAUDE_PLUGIN_ROOT", str(plugin_root))
    if warn:
        print(warn, file=sys.stderr)
    if used_auto:
        print(f"[loop-run] WARN: CLAUDE_PLUGIN_ROOT not set; auto-detected {plugin_root}", file=sys.stderr)
    if str(plugin_root) not in sys.path:
        sys.path.insert(0, str(plugin_root))


def main() -> int:
    try:
        _bootstrap()
    except RuntimeError as exc:
        print(f"[loop-run] ERROR: {exc}", file=sys.stderr)
        return 2
    from tools import loop_run as tools_module

    return tools_module.main(sys.argv[1:])


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
