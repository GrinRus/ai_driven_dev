from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict


def _repo_root() -> Path:
    here = Path(__file__).resolve()
    for candidate in (here.parent, *here.parents):
        if (candidate / ".claude-plugin").is_dir() and (candidate / "skills").is_dir():
            return candidate
    return here.parents[3]


SCHEMA_DIR = Path(__file__).resolve().parent / "schemas" / "aidd"


SCHEMA_FILES: Dict[str, str] = {
    "aidd.actions.v0": "aidd.actions.v0.schema.json",
    "aidd.actions.v1": "aidd.actions.v1.json",
    "aidd.skill_contract.v1": "aidd.skill_contract.v1.json",
    "aidd.readmap.v1": "aidd.readmap.v1.json",
    "aidd.writemap.v1": "aidd.writemap.v1.json",
    "aidd.stage_result.preflight.v1": "aidd.stage_result.preflight.v1.json",
}


def schema_path(schema_name: str) -> Path:
    filename = SCHEMA_FILES.get(schema_name)
    if not filename:
        raise KeyError(f"unknown schema: {schema_name}")
    return SCHEMA_DIR / filename


def load_schema(schema_name: str) -> Dict[str, Any]:
    path = schema_path(schema_name)
    return json.loads(path.read_text(encoding="utf-8"))


def supported_schema_versions(prefix: str) -> tuple[str, ...]:
    values = [name for name in SCHEMA_FILES if name.startswith(prefix)]
    return tuple(sorted(values))
