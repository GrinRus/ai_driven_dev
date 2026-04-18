#!/usr/bin/env python3
from __future__ import annotations

try:
    from aidd_runtime._bootstrap import ensure_repo_root
except ImportError:  # pragma: no cover - direct script execution
    from _bootstrap import ensure_repo_root

ensure_repo_root(__file__)

from aidd_runtime.entrypoint import bootstrap_wrapper

main = bootstrap_wrapper("aidd_runtime.tasklist_check_parts.core", globals())

if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
