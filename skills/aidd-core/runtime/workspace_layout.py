from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Tuple

LEGACY_SHADOW_DIRS = ("docs", "reports", "config", ".cache")


class WorkspaceLayoutConflict(RuntimeError):
    def __init__(self, message: str, *, report_path: Path, conflicts: List[dict]) -> None:
        super().__init__(message)
        self.report_path = report_path
        self.conflicts = conflicts


@dataclass
class LayoutReconcileResult:
    migrated: List[str] = field(default_factory=list)
    archived: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    legacy_detected: bool = False


def reconcile_workspace_layout(
    workspace_root: Path,
    project_root: Path,
) -> LayoutReconcileResult:
    workspace_root = workspace_root.resolve()
    project_root = project_root.resolve()
    result = LayoutReconcileResult()

    legacy_paths: Dict[str, Path] = {name: workspace_root / name for name in LEGACY_SHADOW_DIRS}
    canonical_paths: Dict[str, Path] = {name: project_root / name for name in LEGACY_SHADOW_DIRS}
    legacy_existing = {name: path for name, path in legacy_paths.items() if path.exists()}
    if not legacy_existing:
        return result

    result.legacy_detected = True
    if not project_root.exists():
        project_root.mkdir(parents=True, exist_ok=True)

    conflicts: List[dict] = []
    comparable: Dict[str, Tuple[Tuple[str, str], Tuple[str, str]]] = {}
    for name, legacy_path in legacy_existing.items():
        canonical_path = canonical_paths[name]
        if not canonical_path.exists():
            continue
        legacy_fp = _path_fingerprint(legacy_path)
        canonical_fp = _path_fingerprint(canonical_path)
        comparable[name] = (legacy_fp, canonical_fp)
        if legacy_fp != canonical_fp:
            conflicts.append(
                {
                    "segment": name,
                    "legacy_path": legacy_path.as_posix(),
                    "canonical_path": canonical_path.as_posix(),
                    "legacy_kind": legacy_fp[0],
                    "canonical_kind": canonical_fp[0],
                    "legacy_hash": legacy_fp[1],
                    "canonical_hash": canonical_fp[1],
                }
            )
    if conflicts:
        report_path = _write_conflict_report(project_root, workspace_root, conflicts)
        message = (
            "workspace layout conflict: legacy-shadow content differs from canonical aidd/* layout "
            f"(reason_code=workspace_layout_conflict, report_path={report_path.as_posix()})"
        )
        raise WorkspaceLayoutConflict(message, report_path=report_path, conflicts=conflicts)

    backup_root = project_root / ".cache" / "workspace_layout" / "legacy_shadow"
    for name, legacy_path in legacy_existing.items():
        canonical_path = canonical_paths[name]
        if not canonical_path.exists():
            _safe_move(legacy_path, canonical_path)
            result.migrated.append(f"{name}: {legacy_path.as_posix()} -> {canonical_path.as_posix()}")
            continue

        legacy_fp, _canonical_fp = comparable[name]
        backup_target = backup_root / f"{name}.{legacy_fp[1][:12]}"
        if backup_target.exists():
            existing_fp = _path_fingerprint(backup_target)
            if existing_fp == legacy_fp:
                _remove_path(legacy_path)
                result.archived.append(f"{name}: duplicate removed (already archived at {backup_target.as_posix()})")
                continue
            backup_target = backup_root / f"{name}.{legacy_fp[1][:12]}.v2"
        _safe_move(legacy_path, backup_target)
        result.archived.append(f"{name}: {legacy_path.as_posix()} -> {backup_target.as_posix()}")
    return result


def _write_conflict_report(project_root: Path, workspace_root: Path, conflicts: List[dict]) -> Path:
    report_dir = project_root / "reports" / "events"
    report_dir.mkdir(parents=True, exist_ok=True)
    timestamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    report_path = report_dir / f"workspace_layout_conflict.{timestamp}.json"
    payload = {
        "schema": "aidd.workspace_layout_conflict.v1",
        "reason_code": "workspace_layout_conflict",
        "workspace_root": workspace_root.as_posix(),
        "project_root": project_root.as_posix(),
        "conflicts": conflicts,
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
    }
    report_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report_path


def _safe_move(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.exists():
        raise FileExistsError(f"refusing to overwrite existing destination during layout migration: {dst}")
    try:
        src.rename(dst)
        return
    except OSError as exc:
        if exc.errno not in {getattr(os, "EXDEV", 18), 18}:
            raise
    if src.is_dir():
        shutil.copytree(src, dst)
        shutil.rmtree(src)
    else:
        shutil.copy2(src, dst)
        src.unlink()


def _remove_path(path: Path) -> None:
    if not path.exists():
        return
    if path.is_dir():
        shutil.rmtree(path)
        return
    path.unlink()


def _path_fingerprint(path: Path) -> Tuple[str, str]:
    if path.is_symlink():
        target = os.readlink(path)
        digest = hashlib.sha256(target.encode("utf-8", errors="replace")).hexdigest()
        return "symlink", digest
    if path.is_file():
        return "file", _hash_file(path)
    if path.is_dir():
        return "dir", _hash_dir(path)
    return "other", hashlib.sha256(path.as_posix().encode("utf-8")).hexdigest()


def _hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def _hash_dir(path: Path) -> str:
    digest = hashlib.sha256()
    for item in sorted(path.rglob("*"), key=lambda p: p.as_posix()):
        rel = item.relative_to(path).as_posix()
        if item.is_symlink():
            digest.update(f"S:{rel}\n".encode("utf-8"))
            digest.update(os.readlink(item).encode("utf-8", errors="replace"))
            continue
        if item.is_dir():
            digest.update(f"D:{rel}\n".encode("utf-8"))
            continue
        if item.is_file():
            digest.update(f"F:{rel}\n".encode("utf-8"))
            digest.update(_hash_file(item).encode("utf-8"))
            continue
        digest.update(f"O:{rel}\n".encode("utf-8"))
    return digest.hexdigest()
