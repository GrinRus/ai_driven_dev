#!/usr/bin/env python3
from __future__ import annotations

import os
import sys
from pathlib import Path


def _bootstrap() -> None:
    raw = os.environ.get("CLAUDE_PLUGIN_ROOT")
    if not raw:
        print("[tools/prd-review-gate] CLAUDE_PLUGIN_ROOT is required to run tools.", file=sys.stderr)
        raise SystemExit(2)
    plugin_root = Path(raw).expanduser().resolve()
    if str(plugin_root) not in sys.path:
        sys.path.insert(0, str(plugin_root))


def main() -> int:
    _bootstrap()
    from tools import prd_review_gate

    args = prd_review_gate.parse_args(sys.argv[1:])
    return prd_review_gate.run_gate(args)

if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
