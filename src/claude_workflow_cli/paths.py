from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Optional


class AiddRootError(FileNotFoundError):
    """Raised when the aidd workflow root cannot be resolved."""


def _has_docs(root: Path) -> bool:
    return (root / "docs").is_dir()


def _workspace_to_aidd(workspace: Path) -> Optional[Path]:
    if workspace.name == "aidd" and _has_docs(workspace):
        return workspace
    candidate = workspace / "aidd"
    if _has_docs(candidate):
        return candidate
    return None


def _git_root(start: Path) -> Optional[Path]:
    try:
        result = subprocess.run(
            ["git", "-C", str(start), "rev-parse", "--show-toplevel"],
            check=False,
            text=True,
            capture_output=True,
        )
    except (OSError, FileNotFoundError):
        return None
    if result.returncode != 0:
        return None
    value = (result.stdout or "").strip()
    if not value:
        return None
    return Path(value).expanduser().resolve()


def resolve_aidd_root(raw: Optional[Path] = None) -> Optional[Path]:
    start = (raw or Path.cwd()).expanduser().resolve()

    env_root = os.getenv("AIDD_ROOT")
    if env_root:
        candidate = Path(env_root).expanduser().resolve()
        if _has_docs(candidate):
            return candidate
        return None

    project_dir = os.getenv("CLAUDE_PROJECT_DIR")
    if project_dir:
        candidate = _workspace_to_aidd(Path(project_dir).expanduser().resolve())
        if candidate:
            return candidate

    plugin_root = os.getenv("CLAUDE_PLUGIN_ROOT")
    if plugin_root:
        candidate = Path(plugin_root).expanduser().resolve()
        if _has_docs(candidate):
            return candidate

    git_root = _git_root(start)
    if git_root:
        candidate = _workspace_to_aidd(git_root)
        if candidate:
            return candidate

    for base in (start, *start.parents):
        if base.name == "aidd" and _has_docs(base):
            return base
        candidate = base / "aidd"
        if _has_docs(candidate):
            return candidate

    return None


def require_aidd_root(raw: Optional[Path] = None) -> Path:
    root = resolve_aidd_root(raw)
    if root:
        return root
    target = (raw or Path.cwd()).expanduser().resolve()
    workspace = target if target.name != "aidd" else target.parent
    candidate = workspace / "aidd"
    raise AiddRootError(
        f"workflow not found at {candidate}. Initialise via "
        f"'claude-workflow init --target {workspace}' or set AIDD_ROOT."
    )
