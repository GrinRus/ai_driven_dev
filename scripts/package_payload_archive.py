#!/usr/bin/env python3
"""Build a versioned payload archive and manifest checksums."""

from __future__ import annotations

import hashlib
import os
import shutil
import sys
import zipfile
from pathlib import Path
from typing import Iterator


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_checksum(path: Path) -> Path:
    checksum_path = path.with_suffix(path.suffix + ".sha256")
    checksum_path.write_text(sha256(path), encoding="utf-8")
    return checksum_path


def iter_payload_files(root: Path) -> Iterator[Path]:
    for candidate in sorted(p for p in root.rglob("*") if p.is_file()):
        parts = set(candidate.parts)
        if "__pycache__" in parts or candidate.suffix in {".pyc", ".pyo"}:
            continue
        yield candidate


def main() -> int:
    project_root = Path(__file__).resolve().parents[1]
    payload_root = project_root / "src" / "claude_workflow_cli" / "data" / "payload"
    if not payload_root.is_dir():
        print(f"[payload] payload directory not found: {payload_root}", file=sys.stderr)
        return 1

    version = os.getenv("PAYLOAD_ARCHIVE_VERSION", "").strip() or "dev"
    dist_dir = project_root / "dist"
    dist_dir.mkdir(parents=True, exist_ok=True)

    archive_path = dist_dir / f"claude-workflow-payload-{version}.zip"
    manifest_src = payload_root / "manifest.json"
    manifest_copy = dist_dir / f"claude-workflow-manifest-{version}.json"

    if archive_path.exists():
        archive_path.unlink()
    if manifest_copy.exists():
        manifest_copy.unlink()

    with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for file_path in iter_payload_files(payload_root):
            rel = file_path.relative_to(payload_root)
            zf.write(file_path, rel.as_posix())

    shutil.copy2(manifest_src, manifest_copy)
    write_checksum(archive_path)
    write_checksum(manifest_copy)

    print(f"[payload] archive: {archive_path}")
    print(f"[payload] manifest: {manifest_copy}")
    return 0


if __name__ == "__main__":  # pragma: no cover - script entrypoint
    raise SystemExit(main())
