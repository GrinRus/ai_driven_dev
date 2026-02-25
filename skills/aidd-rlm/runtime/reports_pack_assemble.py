#!/usr/bin/env python3
from __future__ import annotations

CLI_ADAPTER_LIBRARY = True

from pathlib import Path

_CORE_PATH = Path(__file__).resolve().with_name("reports_pack_assemble_parts") / "core.py"
exec(compile(_CORE_PATH.read_text(encoding="utf-8"), str(_CORE_PATH), "exec"), globals(), globals())
