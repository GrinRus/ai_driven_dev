#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

# loop-regression marker: aidd.loop_pack.v1
# loop-regression marker: active.json
_CORE_PATH = Path(__file__).resolve().with_name("loop_pack_parts") / "core.py"
exec(compile(_CORE_PATH.read_text(encoding="utf-8"), str(_CORE_PATH), "exec"), globals(), globals())
