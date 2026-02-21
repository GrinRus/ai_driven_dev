from __future__ import annotations

from pathlib import Path


def repo_root(start_file: str | Path) -> Path:
    here = Path(start_file).resolve()
    for candidate in (here.parent, *here.parents):
        if (candidate / ".claude-plugin").is_dir() and (candidate / "skills").is_dir():
            return candidate
    return here.parents[2]
