from __future__ import annotations

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from aidd_runtime.entrypoint import export_module, run_main

export_module("aidd_runtime.loop_step_parts.core", globals())

if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(run_main("aidd_runtime.loop_step_parts.core"))
