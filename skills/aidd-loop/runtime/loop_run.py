#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import sys

_RUNTIME_DIR = Path(__file__).resolve().parent
if str(_RUNTIME_DIR) not in sys.path:
    sys.path.insert(0, str(_RUNTIME_DIR))
_CORE_PATH = Path(__file__).resolve().with_name("loop_run_parts") / "core.py"
_GLOBALS = globals()
_GLOBALS["__package__"] = "loop_run_parts"
exec(compile(_CORE_PATH.read_text(encoding="utf-8"), str(_CORE_PATH), "exec"), _GLOBALS, _GLOBALS)
