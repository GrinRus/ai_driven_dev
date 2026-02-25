#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from hooks.format_and_test_parts.core import main


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
