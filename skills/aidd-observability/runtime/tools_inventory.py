from __future__ import annotations

from pathlib import Path
import runpy

_bootstrap = runpy.run_path(str(Path(__file__).with_name("_bootstrap.py")))
export_module = _bootstrap["export_module"]
run_main = _bootstrap["run_main"]

export_module("aidd_runtime.tools_inventory", globals())

if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(run_main("aidd_runtime.tools_inventory"))
