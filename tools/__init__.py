from __future__ import annotations

import os
import sys
from typing import Type


_DEBUG_FLAGS = {"1", "true", "yes", "on", "debug"}


def _debug_enabled() -> bool:
    return os.getenv("AIDD_DEBUG", "").strip().lower() in _DEBUG_FLAGS


def _format_exception_message(exc: BaseException) -> str:
    text = str(exc).strip()
    if not text:
        return exc.__class__.__name__
    return " ".join(chunk.strip() for chunk in text.splitlines() if chunk.strip())


def _aidd_excepthook(exc_type: Type[BaseException], exc: BaseException, tb) -> None:
    if _debug_enabled():
        sys.__excepthook__(exc_type, exc, tb)
        return
    message = _format_exception_message(exc)
    sys.stderr.write(f"[aidd] ERROR: {message}\n")


sys.excepthook = _aidd_excepthook
