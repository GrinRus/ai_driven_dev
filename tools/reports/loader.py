"""Load reports with pack-first fallback."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Tuple


@dataclass(frozen=True)
class ReportPaths:
    json_path: Path
    pack_path: Path


def _pack_path_for(json_path: Path) -> Path:
    ext = _pack_extension()
    if json_path.name.endswith(ext):
        return json_path
    if json_path.suffix == ".json":
        return json_path.with_suffix(ext)
    return json_path.with_name(json_path.name + ext)


def _pack_extension() -> str:
    return ".pack.json"


def _json_path_for(pack_path: Path) -> Path:
    if pack_path.name.endswith(".pack.json"):
        return pack_path.with_name(pack_path.name[: -len(".pack.json")] + ".json")
    return pack_path.with_suffix(".json")


def get_report_paths(root: Path, report_type: str, ticket: str, kind: str | None = None) -> ReportPaths:
    name = f"{ticket}-{kind}" if kind else ticket
    json_path = root / "reports" / report_type / f"{name}.json"
    pack_path = _pack_path_for(json_path)
    return ReportPaths(json_path=json_path, pack_path=pack_path)


def load_report(json_path: Path, pack_path: Path, *, prefer_pack: bool = True) -> Tuple[Dict, str, Path]:
    if prefer_pack and pack_path.exists():
        payload = json.loads(pack_path.read_text(encoding="utf-8"))
        return payload, "pack", pack_path
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    return payload, "json", json_path


def load_report_for_path(path: Path, *, prefer_pack: bool = True) -> Tuple[Dict, str, ReportPaths]:
    if path.name.endswith(".pack.json"):
        pack_path = path
        json_path = _json_path_for(pack_path)
    else:
        json_path = path
        pack_path = _pack_path_for(json_path)
    payload, source, _ = load_report(json_path, pack_path, prefer_pack=prefer_pack)
    return payload, source, ReportPaths(json_path=json_path, pack_path=pack_path)
