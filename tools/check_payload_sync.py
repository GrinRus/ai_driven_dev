#!/usr/bin/env python3
"""Validate that repository root snapshots mirror the packaged payload."""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
from typing import Dict, Iterable, List, Sequence


DEFAULT_PATHS = [
    ".claude",
    "claude-presets",
    "config",
    "docs",
    "prompts",
    "templates",
    "tools",
    "README.md",
    "README.en.md",
    "CHANGELOG.md",
    "workflow.md",
    "CLAUDE.md",
    "conventions.md",
    "init-claude-workflow.sh",
    "scripts/ci-lint.sh",
    "scripts/migrate-tasklist.py",
    "scripts/prd-review-agent.py",
    "scripts/prd_review_gate.py",
    "scripts/qa-agent.py",
    "scripts/smoke-workflow.sh",
]


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


def collect_entries(base: Path, relative: str) -> Dict[str, str] | None:
    target = (base / relative).resolve()
    if not target.exists():
        return None
    rel_root = Path(relative)
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


def compare_paths(
    repo_root: Path,
    payload_root: Path,
    paths: Sequence[str],
) -> List[str]:
    mismatches: List[str] = []
    for relative in paths:
        relative = relative.strip()
        if not relative:
            continue
        repo_entries = collect_entries(repo_root, relative)
        payload_entries = collect_entries(payload_root, relative)
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
        default=str(Path(__file__).resolve().parents[1]),
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
    paths = parse_paths(args.paths)
    mismatches = compare_paths(repo_root, payload_root, paths)
    if mismatches:
        print("[payload-sync] detected mismatches:")
        for item in mismatches:
            print(f"  - {item}")
        return 1
    print("[payload-sync] payload matches repository snapshots.")
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entrypoint
    raise SystemExit(main())
