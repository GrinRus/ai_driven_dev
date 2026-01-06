#!/usr/bin/env python3
"""Validate that repository snapshots mirror the packaged payload."""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
from typing import Dict, Iterable, List, Sequence

DEFAULT_PATHS: list[str] = [
    ".claude",
    ".claude-plugin",
    "config",
    "docs",
    "conventions.md",
    "init-claude-workflow.sh",
]

DEFAULT_PAYLOAD_PREFIX = "aidd"
WORKSPACE_ROOT_DIRS = {".claude", ".claude-plugin"}
DEV_ONLY_PATHS = ["doc/dev", "doc/dev/backlog.md"]


def hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _should_skip(path: Path) -> bool:
    parts = set(path.parts)
    if "__pycache__" in parts:
        return True
    if path.suffix == ".pyc":
        return True
    return False


def collect_entries(base: Path, relative: str, *, prefix: str = "") -> Dict[str, str] | None:
    target_root = Path(prefix) / Path(relative)
    target = (base / target_root).resolve()
    rel_root = Path(relative)
    if not target.exists():
        return None
    entries: Dict[str, str] = {}
    if target.is_file():
        if _should_skip(target):
            return entries
        entries[str(rel_root.as_posix())] = hash_file(target)
        return entries
    for file_path in sorted(p for p in target.rglob("*") if p.is_file()):
        if _should_skip(file_path):
            continue
        rel_path = rel_root / file_path.relative_to(target)
        entries[str(rel_path.as_posix())] = hash_file(file_path)
    return entries


def is_workspace_path(relative: str) -> bool:
    parts = Path(relative).parts
    return bool(parts) and parts[0] in WORKSPACE_ROOT_DIRS


def _guess_repo_root(marker: str = "pyproject.toml") -> Path:
    path = Path(__file__).resolve()
    for parent in path.parents:
        if (parent / marker).exists() or (parent / ".git").exists():
            return parent
    return path.parents[1]


def resolve_snapshot_root(repo_root: Path, payload_prefix: str) -> Path:
    prefix = payload_prefix.strip("/")
    if not prefix:
        return repo_root
    candidate = repo_root / prefix
    if candidate.is_dir():
        return candidate
    return repo_root


def has_any_snapshot_paths(root: Path, paths: Sequence[str]) -> bool:
    return any((root / rel).exists() for rel in paths)


def compare_paths(
    repo_root: Path,
    payload_root: Path,
    snapshot_root: Path,
    paths: Sequence[str],
    *,
    payload_prefix: str = DEFAULT_PAYLOAD_PREFIX,
) -> List[str]:
    mismatches: List[str] = []
    for relative in paths:
        relative = relative.strip()
        if not relative:
            continue
        if is_workspace_path(relative):
            repo_entries = collect_entries(repo_root, relative)
            payload_entries = collect_entries(payload_root, relative)
        else:
            repo_entries = collect_entries(snapshot_root, relative)
            payload_entries = collect_entries(payload_root, relative, prefix=payload_prefix)
        if repo_entries is None and payload_entries is None:
            mismatches.append(f"{relative}: missing in repo and payload snapshots")
            continue
        if repo_entries is None:
            mismatches.append(f"{relative}: missing in repo snapshot ({repo_root})")
            continue
        if payload_entries is None:
            mismatches.append(f"{relative}: missing in payload ({payload_root})")
            continue
        keys = set(repo_entries) | set(payload_entries)
        for key in sorted(keys):
            repo_hash = repo_entries.get(key)
            payload_hash = payload_entries.get(key)
            if repo_hash is None:
                mismatches.append(f"{key}: exists only in payload snapshot")
            elif payload_hash is None:
                mismatches.append(f"{key}: missing from payload snapshot")
            elif repo_hash != payload_hash:
                mismatches.append(f"{key}: hash mismatch")
    return mismatches


def find_dev_only_in_payload(payload_root: Path, dev_only: Sequence[str]) -> List[str]:
    hits: List[str] = []
    for relative in dev_only:
        candidate = payload_root / relative
        if candidate.exists():
            hits.append(f"{relative}: dev-only path present in payload")
    return hits


def parse_paths(raw: Iterable[str] | None) -> List[str]:
    if not raw:
        return list(DEFAULT_PATHS)
    paths: List[str] = []
    for item in raw:
        if not item:
            continue
        segments = [segment.strip() for segment in item.split(",")]
        paths.extend(segment for segment in segments if segment)
    return paths or list(DEFAULT_PATHS)


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Ensure repository runtime snapshots mirror the packaged payload.",
    )
    parser.add_argument(
        "--repo-dir",
        default=str(_guess_repo_root()),
        help="Repository root (defaults to project root).",
    )
    parser.add_argument(
        "--payload-dir",
        default=None,
        help="Override payload root (defaults to src/claude_workflow_cli/data/payload).",
    )
    parser.add_argument(
        "--paths",
        action="append",
        help="Comma-separated subset of paths to compare (default: predefined list).",
    )
    parser.add_argument(
        "--payload-prefix",
        default=DEFAULT_PAYLOAD_PREFIX,
        help=f"Optional prefix under payload root (default: {DEFAULT_PAYLOAD_PREFIX}).",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_argument_parser()
    args = parser.parse_args(argv)
    repo_root = Path(args.repo_dir).resolve()
    if not repo_root.is_dir():
        parser.error(f"repo directory not found: {repo_root}")
    default_payload = repo_root / "src" / "claude_workflow_cli" / "data" / "payload"
    payload_root = Path(args.payload_dir).resolve() if args.payload_dir else default_payload
    if not payload_root.is_dir():
        parser.error(f"payload directory not found: {payload_root}")
    payload_prefix = args.payload_prefix.strip("/")
    paths = parse_paths(args.paths)
    snapshot_root = resolve_snapshot_root(repo_root, payload_prefix)
    if not args.paths and payload_prefix and snapshot_root == repo_root:
        print(
            f"[payload-sync] runtime snapshot not found at {repo_root / payload_prefix}; "
            "run scripts/sync-payload.sh --direction=to-root before checking."
        )
        return 0
    mismatches = compare_paths(
        repo_root,
        payload_root,
        snapshot_root,
        paths,
        payload_prefix=payload_prefix,
    )
    dev_only_hits = find_dev_only_in_payload(payload_root, DEV_ONLY_PATHS)
    mismatches.extend(dev_only_hits)
    if mismatches:
        print("[payload-sync] detected mismatches:")
        for item in mismatches:
            print(f"  - {item}")
        return 1
    print("[payload-sync] payload matches repository snapshots.")
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entrypoint
    raise SystemExit(main())
