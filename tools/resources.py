from __future__ import annotations

from pathlib import Path
from typing import Tuple

DEFAULT_PROJECT_SUBDIR = "aidd"
_WORKSPACE_MARKERS = (".git", ".claude-plugin", "pyproject.toml")


def _find_workspace_boundary(target: Path) -> Path | None:
    for parent in (target, *target.parents):
        for marker in _WORKSPACE_MARKERS:
            marker_path = parent / marker
            if marker_path.is_dir() or marker_path.is_file():
                return parent
    return None


def resolve_project_root(target: Path, subdir: str = DEFAULT_PROJECT_SUBDIR) -> Tuple[Path, Path]:
    """
    Resolve workspace and workflow roots for any path inside the workspace.

    - If ``target`` is inside an existing ``<subdir>`` directory, use that as workflow root.
    - If ``target`` is the workflow root itself, workspace is its parent.
    - Otherwise treat ``target`` as the workspace root and place workflow under ``<workspace>/<subdir>``.
    """
    target = target.resolve()
    boundary = _find_workspace_boundary(target)
    for parent in (target, *target.parents):
        if parent.name == subdir:
            return parent.parent, parent
        candidate = parent / subdir
        if candidate.is_dir():
            return parent, candidate
        if boundary and parent == boundary:
            break
    if target.name == subdir:
        return target.parent, target
    return target, target / subdir
