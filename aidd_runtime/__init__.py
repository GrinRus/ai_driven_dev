from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Type


_DEBUG_FLAGS = {"1", "true", "yes", "on", "debug"}

_PACKAGE_ROOT = Path(__file__).resolve().parent
_REPO_ROOT = _PACKAGE_ROOT.parent
_RUNTIME_DIRS = (
    _REPO_ROOT / "skills" / "aidd-core" / "runtime",
    _REPO_ROOT / "skills" / "aidd-docio" / "runtime",
    _REPO_ROOT / "skills" / "aidd-flow-state" / "runtime",
    _REPO_ROOT / "skills" / "aidd-observability" / "runtime",
    _REPO_ROOT / "skills" / "aidd-loop" / "runtime",
    _REPO_ROOT / "skills" / "aidd-rlm" / "runtime",
    _REPO_ROOT / "skills" / "aidd-init" / "runtime",
    _REPO_ROOT / "skills" / "idea-new" / "runtime",
    _REPO_ROOT / "skills" / "plan-new" / "runtime",
    _REPO_ROOT / "skills" / "researcher" / "runtime",
    _REPO_ROOT / "skills" / "review-spec" / "runtime",
    _REPO_ROOT / "skills" / "spec-interview" / "runtime",
    _REPO_ROOT / "skills" / "tasks-new" / "runtime",
    _REPO_ROOT / "skills" / "implement" / "runtime",
    _REPO_ROOT / "skills" / "review" / "runtime",
    _REPO_ROOT / "skills" / "qa" / "runtime",
    _REPO_ROOT / "skills" / "status" / "runtime",
)

# Runtime bridge for Wave 96: resolve `aidd_runtime.<module>` from
# canonical `skills/*/runtime` locations during path migration.
for runtime_dir in _RUNTIME_DIRS:
    if not runtime_dir.is_dir():
        continue
    runtime_dir_str = str(runtime_dir)
    if runtime_dir_str not in __path__:
        __path__.append(runtime_dir_str)


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
