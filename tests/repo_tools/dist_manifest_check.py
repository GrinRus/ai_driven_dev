#!/usr/bin/env python3
"""Validate dist manifest and distribution surface."""

from __future__ import annotations

import argparse
import fnmatch
import json
import subprocess
import sys
from pathlib import Path


def _tracked_files(root: Path) -> list[str]:
    proc = subprocess.run(["git", "ls-files"], cwd=root, text=True, capture_output=True, check=False)
    if proc.returncode != 0:
        print("[dist-check] failed to enumerate tracked files", file=sys.stderr)
        raise SystemExit(2)
    return [line.strip() for line in proc.stdout.splitlines() if line.strip()]


def _load_manifest(path: Path) -> dict:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"[dist-check] invalid manifest {path}: {exc}", file=sys.stderr)
        raise SystemExit(2)
    if not isinstance(payload, dict):
        print(f"[dist-check] manifest must be JSON object: {path}", file=sys.stderr)
        raise SystemExit(2)
    return payload


def _matches(path: str, patterns: list[str]) -> bool:
    return any(fnmatch.fnmatch(path, pattern) for pattern in patterns)


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate dist manifest and included distribution files.")
    parser.add_argument("--root", default=".", help="Repository root")
    parser.add_argument(
        "--manifest",
        default=".claude-plugin/dist-manifest.json",
        help="Path to dist manifest (relative to repo root)",
    )
    args = parser.parse_args()

    root = Path(args.root).resolve()
    manifest_path = root / args.manifest
    manifest = _load_manifest(manifest_path)

    include_globs = manifest.get("include_globs")
    exclude_globs = manifest.get("exclude_globs")
    if not isinstance(include_globs, list) or not all(isinstance(item, str) and item.strip() for item in include_globs):
        print("[dist-check] include_globs must be a non-empty list of strings", file=sys.stderr)
        return 2
    if not isinstance(exclude_globs, list) or not all(isinstance(item, str) and item.strip() for item in exclude_globs):
        print("[dist-check] exclude_globs must be a list of strings", file=sys.stderr)
        return 2

    tracked = _tracked_files(root)
    included = [
        path
        for path in tracked
        if _matches(path, include_globs) and not _matches(path, exclude_globs)
    ]

    errors: list[str] = []
    if not included:
        errors.append("dist include set is empty")

    required_prefixes = ("agents/", "skills/", "hooks/", ".claude-plugin/", "templates/aidd/")
    for prefix in required_prefixes:
        if not any(path.startswith(prefix) for path in included):
            errors.append(f"missing required dist surface: {prefix}")

    allowed_tops = {"agents", "skills", "hooks", ".claude-plugin", "templates"}
    for path in included:
        top = path.split("/", 1)[0]
        if top not in allowed_tops:
            errors.append(f"included unexpected top-level path: {path}")
        if top == "templates" and not path.startswith("templates/aidd/"):
            errors.append(f"templates dist surface must stay under templates/aidd/: {path}")

    forbidden_prefixes = ("tests/", "dev/", "docs/", "aidd_runtime/")
    for path in included:
        for prefix in forbidden_prefixes:
            if path.startswith(prefix):
                errors.append(f"forbidden path leaked into dist set: {path}")

    if errors:
        for entry in errors:
            print(f"[dist-check] {entry}", file=sys.stderr)
        return 2

    print(f"[dist-check] OK included_files={len(included)} manifest={manifest_path.relative_to(root).as_posix()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
