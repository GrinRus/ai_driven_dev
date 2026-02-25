from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Dict, Optional


def resolve_log_dir(project_dir: Path, aidd_root: Optional[Path], rel_log_dir: str) -> Path:
    candidate = Path(rel_log_dir)
    if candidate.is_absolute():
        return candidate
    if rel_log_dir.startswith("aidd/"):
        if aidd_root and aidd_root.name == "aidd":
            return aidd_root.parent / candidate
        return project_dir / candidate
    if aidd_root:
        return aidd_root / candidate
    return project_dir / candidate


def should_rate_limit(
    guard: Dict[str, Any],
    project_dir: Path,
    aidd_root: Optional[Path],
    guard_name: str,
) -> bool:
    min_interval = guard.get("min_interval_seconds", 0)
    try:
        min_interval = int(min_interval)
    except (TypeError, ValueError):
        min_interval = 0
    if min_interval <= 0:
        return False

    log_dir_raw = str(guard.get("log_dir", "aidd/reports/logs"))
    log_dir = resolve_log_dir(project_dir, aidd_root, log_dir_raw)
    stamp_path = log_dir / f".context-gc-{guard_name}.stamp"

    try:
        last_seen = float(stamp_path.read_text(encoding="utf-8").strip() or 0)
    except Exception:
        last_seen = 0.0

    now = time.time()
    if last_seen and (now - last_seen) < min_interval:
        return True

    try:
        log_dir.mkdir(parents=True, exist_ok=True)
        stamp_path.write_text(str(now), encoding="utf-8")
    except Exception:
        # If we cannot persist the stamp, keep running the guard.
        return False

    return False
