from __future__ import annotations

import hashlib
import json
from pathlib import Path


def _hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def test_manifest_covers_payload_files():
    project_root = Path(__file__).resolve().parents[1]
    payload_root = project_root / "src" / "claude_workflow_cli" / "data" / "payload"
    manifest_path = payload_root / "manifest.json"
    assert manifest_path.exists(), "manifest.json should be present in payload"

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    files = manifest.get("files", [])
    assert files, "manifest should list payload files"

    entries = {entry["path"]: entry for entry in files}
    assert len(entries) == len(files), "manifest should not contain duplicate paths"

    actual_paths = {}
    for path in sorted(payload_root.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(payload_root).as_posix()
        actual_paths[rel] = path

    assert set(entries) <= set(actual_paths), "manifest contains unknown paths"

    extras = set(actual_paths) - set(entries)
    assert extras <= {"manifest.json"}, "manifest missing unexpected files"

    for rel, path in actual_paths.items():
        if rel == "manifest.json":
            continue
        entry = entries[rel]
        assert entry.get("type") == "file", f"{rel} should be marked as file"
        assert entry.get("size") == path.stat().st_size, f"{rel} size mismatch"
        assert entry.get("sha256") == _hash_file(path), f"{rel} checksum mismatch"
