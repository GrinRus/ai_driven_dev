from __future__ import annotations

from pathlib import Path
import runpy

_shared = runpy.run_path(str(Path(__file__).resolve().parents[3] / "aidd_runtime" / "_bootstrap.py"))
ensure_repo_root = _shared["ensure_repo_root"]
export_module = _shared["export_module"]
run_main = _shared["run_main"]

ensure_repo_root(__file__)
