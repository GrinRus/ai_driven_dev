#!/usr/bin/env python3
"""Check git diff paths against loop-pack boundaries."""

from __future__ import annotations

import argparse
import fnmatch
import subprocess
import sys
from pathlib import Path
from typing import Iterable, List, Tuple

from tools import runtime

IGNORE_PREFIXES = ("aidd/", ".claude/", ".cursor/")
IGNORE_FILES = {"AGENTS.md", "CLAUDE.md", ".github/copilot-instructions.md"}


def normalize_path(path: str) -> str:
    return path.lstrip("./")


def is_ignored(path: str) -> bool:
    normalized = normalize_path(path)
    if normalized in IGNORE_FILES:
        return True
    return any(normalized.startswith(prefix) for prefix in IGNORE_PREFIXES)


def matches_pattern(path: str, pattern: str) -> bool:
    if not pattern:
        return False
    normalized = normalize_path(path)
    pattern = normalize_path(pattern.strip())
    if not pattern:
        return False
    if any(char in pattern for char in "*?["):
        if fnmatch.fnmatch(normalized, pattern):
            return True
        if pattern.startswith("**/") and fnmatch.fnmatch(normalized, pattern[3:]):
            return True
        return False
    if pattern.endswith("/**"):
        base = pattern[:-3].rstrip("/")
        return normalized == base or normalized.startswith(base + "/")
    if pattern.endswith("/"):
        base = pattern.rstrip("/")
        return normalized == base or normalized.startswith(base + "/")
    return normalized == pattern or normalized.startswith(pattern + "/")


def parse_front_matter(lines: List[str]) -> List[str]:
    if not lines or lines[0].strip() != "---":
        return []
    collected: List[str] = []
    for line in lines[1:]:
        if line.strip() == "---":
            break
        collected.append(line.rstrip("\n"))
    return collected


def extract_boundaries(front_matter: List[str]) -> Tuple[List[str], List[str]]:
    allowed: List[str] = []
    forbidden: List[str] = []
    in_boundaries = False
    current: str | None = None
    for raw in front_matter:
        stripped = raw.strip()
        if stripped == "boundaries:":
            in_boundaries = True
            current = None
            continue
        if not in_boundaries:
            continue
        if stripped and not raw.startswith(" "):
            in_boundaries = False
            current = None
            continue
        if stripped.startswith("allowed_paths:"):
            current = "allowed"
            if stripped.endswith("[]"):
                current = None
            continue
        if stripped.startswith("forbidden_paths:"):
            current = "forbidden"
            if stripped.endswith("[]"):
                current = None
            continue
        if stripped.startswith("-") and current:
            item = stripped[1:].strip()
            if item and item != "[]":
                if current == "allowed":
                    allowed.append(item)
                elif current == "forbidden":
                    forbidden.append(item)
    return allowed, forbidden


def parse_allowed_arg(value: str | None) -> List[str]:
    if not value:
        return []
    items: List[str] = []
    for chunk in value.replace(",", " ").split():
        chunk = chunk.strip()
        if chunk:
            items.append(chunk)
    return items


def git_lines(args: List[str]) -> List[str]:
    proc = subprocess.run(args, text=True, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    if proc.returncode != 0:
        return []
    return [line.strip() for line in proc.stdout.splitlines() if line.strip()]


def resolve_git_root(base: Path) -> Path:
    try:
        proc = subprocess.run(
            ["git", "-C", str(base), "rev-parse", "--show-toplevel"],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )
    except OSError:
        return base
    if proc.returncode != 0:
        return base
    root = proc.stdout.strip()
    if not root:
        return base
    return Path(root).resolve()


def collect_diff_files(base: Path) -> List[str]:
    git_root = resolve_git_root(base)
    files = set(git_lines(["git", "-C", str(git_root), "diff", "--name-only"]))
    files.update(git_lines(["git", "-C", str(git_root), "diff", "--cached", "--name-only"]))
    return sorted(files)


def parse_args(argv: List[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate diff files against loop-pack boundaries.")
    parser.add_argument("--ticket", help="Ticket identifier to use (defaults to docs/.active_ticket).")
    parser.add_argument("--loop-pack", help="Path to loop pack (default: resolve via .active_work_item).")
    parser.add_argument("--allowed", help="Override allowed paths (comma/space separated).")
    return parser.parse_args(argv)


def main(argv: List[str] | None = None) -> int:
    args = parse_args(argv)
    workspace_root, target = runtime.require_workflow_root()

    if args.loop_pack:
        pack_path = runtime.resolve_path_for_target(Path(args.loop_pack), target)
        ticket = args.ticket or read_active_ticket(target) or ""
    else:
        context = runtime.resolve_feature_context(target, ticket=args.ticket, slug_hint=None)
        ticket = (context.resolved_ticket or "").strip()
        if not ticket:
            raise ValueError("feature ticket is required; pass --ticket or set docs/.active_ticket via /feature-dev-aidd:idea-new.")
        active_work_item = read_active_work_item(target)
        if not active_work_item:
            raise FileNotFoundError("docs/.active_work_item not found; run loop-pack first")
        pack_path = target / "reports" / "loops" / ticket / f"{active_work_item}.loop.pack.md"

    if not pack_path.exists():
        raise FileNotFoundError(f"loop pack not found at {runtime.rel_path(pack_path, target)}")

    front_matter = parse_front_matter(read_text(pack_path).splitlines())
    allowed_paths, forbidden_paths = extract_boundaries(front_matter)
    override_allowed = parse_allowed_arg(args.allowed)
    if override_allowed:
        allowed_paths = override_allowed

    if not allowed_paths and not forbidden_paths:
        print("NO_BOUNDARIES_DEFINED")
        return 0

    diff_files = [path for path in collect_diff_files(target) if not is_ignored(path)]
    violations: List[str] = []
    for path in diff_files:
        if any(matches_pattern(path, pattern) for pattern in forbidden_paths):
            violations.append(f"FORBIDDEN {path}")
            continue
        if allowed_paths and not any(matches_pattern(path, pattern) for pattern in allowed_paths):
            violations.append(f"OUT_OF_SCOPE {path}")

    if violations:
        for line in sorted(violations):
            print(line)
        return 2

    print("OK")
    return 0


def read_active_ticket(root: Path) -> str:
    path = root / "docs" / ".active_ticket"
    try:
        return path.read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def read_active_work_item(root: Path) -> str:
    path = root / "docs" / ".active_work_item"
    try:
        return path.read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
