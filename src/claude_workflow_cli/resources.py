from __future__ import annotations

from pathlib import Path
from typing import Tuple

DEFAULT_PROJECT_SUBDIR = "aidd"


def resolve_project_root(target: Path, subdir: str = DEFAULT_PROJECT_SUBDIR) -> Tuple[Path, Path]:
    """
    Derive workspace root and project root.

    - If target already contains `.claude`, treat it as project root.
    - If target name matches the configured subdir, project root is target, workspace is its parent.
    - Otherwise prefer `<target>/<subdir>` when present; fallback to the same path even if not created yet.
    """
    target = target.resolve()
    if (target / ".claude").exists():
        workspace_root = target.parent if target.name == subdir else target
        return workspace_root, target
    if target.name == subdir:
        return target.parent, target
    candidate = target / subdir
    if (candidate / ".claude").exists():
        return target, candidate
    return target, candidate
