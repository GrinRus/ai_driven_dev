from __future__ import annotations

from pathlib import Path
from typing import Tuple

DEFAULT_PROJECT_SUBDIR = "aidd"


def resolve_project_root(target: Path, subdir: str = DEFAULT_PROJECT_SUBDIR) -> Tuple[Path, Path]:
    """
    Treat ``target`` as the workspace root and always resolve the workflow under ``<workspace>/<subdir>``.

    If the caller points directly to the subdir (e.g., ``--target aidd``), the workspace root becomes its parent.
    Workspace-level settings (.claude/, .claude-plugin/) live alongside the workflow subdirectory.
    """
    target = target.resolve()
    if target.name == subdir:
        return target.parent, target
    return target, target / subdir
