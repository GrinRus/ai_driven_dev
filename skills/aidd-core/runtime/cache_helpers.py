from __future__ import annotations

import json
from pathlib import Path
from typing import Dict


def load_json_cache(path: Path) -> Dict[str, str]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    if not isinstance(payload, dict):
        return {}
    return {str(key): str(value) for key, value in payload.items()}


def write_ticket_hash_cache(path: Path, *, ticket: str, hash_value: str) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"ticket": ticket, "hash": hash_value}
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    except OSError:
        return
