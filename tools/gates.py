from __future__ import annotations

import json
from fnmatch import fnmatch
from pathlib import Path
from typing import Iterable


def _resolve_gates_path(target: Path) -> Path:
    return target / "config" / "gates.json" if target.is_dir() else target


def load_gates_config(target: Path) -> dict:
    path = _resolve_gates_path(target)
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise ValueError(f"не удалось прочитать {path}: {exc}")


def load_gate_section(target: Path, section: str) -> dict:
    config = load_gates_config(target)
    raw = config.get(section)
    if isinstance(raw, bool):
        return {"enabled": raw}
    return raw if isinstance(raw, dict) else {}


def normalize_patterns(raw: Iterable[str] | None) -> list[str] | None:
    if not raw:
        return None
    patterns: list[str] = []
    for item in raw:
        text = str(item).strip()
        if text:
            patterns.append(text)
    return patterns or None


def matches(patterns: Iterable[str] | None, value: str) -> bool:
    if not value:
        return False
    if isinstance(patterns, str):
        patterns = (patterns,)
    for pattern in patterns or ():
        if pattern and fnmatch(value, pattern):
            return True
    return False


def branch_enabled(branch: str | None, *, allow: Iterable[str] | None = None, skip: Iterable[str] | None = None) -> bool:
    if not branch:
        return True
    if skip and matches(skip, branch):
        return False
    if allow and not matches(allow, branch):
        return False
    return True
