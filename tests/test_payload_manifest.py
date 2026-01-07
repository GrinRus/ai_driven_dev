from __future__ import annotations

import hashlib
import json
from pathlib import Path


DEV_ONLY_PATHS = ["doc/dev/backlog.md"]
BANNED_DOC_SNIPPETS = [
    "doc/dev/",
    "scripts/sync-payload.sh",
    "tools/check_payload_sync.py",
    "scripts/prompt-version",
    "tools/prompt_diff.py",
    "scripts/lint-prompts.py",
]


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


def test_dev_only_files_not_in_manifest_or_payload():
    project_root = Path(__file__).resolve().parents[1]
    payload_root = project_root / "src" / "claude_workflow_cli" / "data" / "payload"
    manifest_path = payload_root / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    entries = {entry["path"]: entry for entry in manifest.get("files", [])}

    for dev_path in DEV_ONLY_PATHS:
        assert dev_path not in entries, f"{dev_path} should not be shipped in payload manifest"
        assert not (payload_root / dev_path).exists(), f"{dev_path} should be dev-only and absent from payload"


def test_payload_docs_do_not_reference_repo_only_tools():
    project_root = Path(__file__).resolve().parents[1]
    payload_docs = project_root / "src" / "claude_workflow_cli" / "data" / "payload" / "aidd" / "docs"
    offenders = {}

    for doc_path in payload_docs.rglob("*.md"):
        text = doc_path.read_text(encoding="utf-8")
        for snippet in BANNED_DOC_SNIPPETS:
            if snippet in text:
                offenders.setdefault(snippet, []).append(doc_path)

    assert not offenders, "Repo-only references found in payload docs: " + ", ".join(
        f"{snippet} -> {[p.as_posix() for p in paths]}" for snippet, paths in offenders.items()
    )


def test_payload_excludes_legacy_runtime_dirs():
    project_root = Path(__file__).resolve().parents[1]
    payload_root = project_root / "src" / "claude_workflow_cli" / "data" / "payload"
    for path in payload_root.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(payload_root).as_posix()
        assert not rel.startswith("aidd/scripts/"), f"legacy scripts leaked into payload: {rel}"
        assert not rel.startswith("aidd/tools/"), f"legacy tools leaked into payload: {rel}"
        assert not rel.startswith("aidd/hooks/_vendor/"), f"legacy vendor copy leaked into payload: {rel}"
