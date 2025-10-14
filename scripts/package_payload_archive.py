#!/usr/bin/env python3
"""
Build a versioned payload archive and manifest copies for release uploads.

The script packs `src/claude_workflow_cli/data/payload` into a `.zip`, copies
the manifest with a versioned filename and emits `.sha256` checksum files for
both artefacts. Versions are resolved from `PAYLOAD_ARCHIVE_VERSION`,
`GITHUB_REF_NAME`, or `pyproject.toml` (in that order).
"""

from __future__ import annotations

import hashlib
import os
import shutil
import sys
from pathlib import Path

try:  # Python 3.11+
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - fallback for older interpreters
    import tomli as tomllib  # type: ignore[import-not-found]


def _determine_version() -> str:
    for env_var in ("PAYLOAD_ARCHIVE_VERSION", "GITHUB_REF_NAME"):
        value = os.getenv(env_var)
        if value:
            return value.replace("/", "-")

    pyproject = Path("pyproject.toml")
    if pyproject.exists():
        data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
        project = data.get("project") or {}
        version = project.get("version")
        if version:
            return str(version)
    return "snapshot"


def _write_checksum(path: Path) -> Path:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    checksum_path = path.with_suffix(path.suffix + ".sha256")
    checksum_path.write_text(f"{digest.hexdigest()}  {path.name}\n", encoding="utf-8")
    return checksum_path


def main() -> int:
    payload_root = Path("src") / "claude_workflow_cli" / "data" / "payload"
    if not payload_root.exists():
        print(f"[package-payload] payload directory not found: {payload_root}", file=sys.stderr)
        return 1

    dist_dir = Path("dist")
    dist_dir.mkdir(parents=True, exist_ok=True)

    version = _determine_version()
    archive_base = dist_dir / f"claude-workflow-payload-{version}"
    shutil.make_archive(str(archive_base), "zip", root_dir=payload_root)
    payload_zip = archive_base.with_suffix(".zip")
    _write_checksum(payload_zip)

    manifest_src = payload_root / "manifest.json"
    manifest_copy = dist_dir / f"claude-workflow-manifest-{version}.json"
    shutil.copy2(manifest_src, manifest_copy)
    _write_checksum(manifest_copy)

    print(
        "[package-payload] created payload archive and manifest:"
        f" {payload_zip.name}, {manifest_copy.name} (checksums alongside)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
