"""Load reports with pack-first fallback."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Tuple

_PACK_FORMATS = {"yaml", "toon"}


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
    fmt = os.getenv("AIDD_PACK_FORMAT", "yaml").strip().lower()
    if fmt not in _PACK_FORMATS:
        fmt = "yaml"
    return ".pack.toon" if fmt == "toon" else ".pack.yaml"


def _fallback_pack_path(pack_path: Path) -> Path | None:
    if pack_path.name.endswith(".pack.toon"):
        candidate = pack_path.with_name(pack_path.name[: -len(".pack.toon")] + ".pack.yaml")
        if candidate.exists():
            return candidate
    if pack_path.name.endswith(".pack.yaml"):
        candidate = pack_path.with_name(pack_path.name[: -len(".pack.yaml")] + ".pack.toon")
        if candidate.exists():
            return candidate
    return None


def _json_path_for(pack_path: Path) -> Path:
    if pack_path.name.endswith(".pack.toon"):
        return pack_path.with_name(pack_path.name[: -len(".pack.toon")] + ".json")
    if pack_path.name.endswith(".pack.yaml"):
        return pack_path.with_name(pack_path.name[: -len(".pack.yaml")] + ".json")
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
    if prefer_pack:
        fallback = _fallback_pack_path(pack_path)
        if fallback and fallback.exists():
            payload = json.loads(fallback.read_text(encoding="utf-8"))
            return payload, "pack", fallback
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    return payload, "json", json_path


def load_report_for_path(path: Path, *, prefer_pack: bool = True) -> Tuple[Dict, str, ReportPaths]:
    if path.name.endswith(".pack.toon") or path.name.endswith(".pack.yaml"):
        pack_path = path
        json_path = _json_path_for(pack_path)
    else:
        json_path = path
        pack_path = _pack_path_for(json_path)
    payload, source, _ = load_report(json_path, pack_path, prefer_pack=prefer_pack)
    return payload, source, ReportPaths(json_path=json_path, pack_path=pack_path)
