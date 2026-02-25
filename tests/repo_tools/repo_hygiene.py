#!/usr/bin/env python3
"""Repo hygiene guard for prod-like repository layout."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]

ALLOWED_ROOT_FILES = {
    ".gitignore",
    ".markdownlint.yaml",
    ".pre-commit-config.yaml",
    "AGENTS.md",
    "CHANGELOG.md",
    "CONTRIBUTING.md",
    "LICENSE",
    "README.md",
    "README.en.md",
    "backlog.md",
    "pyproject.toml",
}

ALLOWED_ROOT_DIRS = {
    ".claude-plugin",
    ".github",
    "agents",
    "aidd_runtime",
    "dev",
    "docs",
    "hooks",
    "skills",
    "templates",
    "tests",
}

FORBIDDEN_TRACKED_GLOBS = (
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
)

FORBIDDEN_TRACKED_PREFIXES = (
    "dev/reports/revision/",
)

FORBIDDEN_TRACKED_ROOT_GLOBS = (
    "aidd_test_flow_prompt_",
)


def _tracked_files() -> list[str]:
    proc = subprocess.run(
        ["git", "ls-files"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        print("[repo-hygiene] failed to enumerate tracked files", file=sys.stderr)
        raise SystemExit(2)
    return [line.strip() for line in proc.stdout.splitlines() if line.strip()]


def _contains_forbidden_part(path: str) -> str:
    parts = path.split("/")
    for marker in FORBIDDEN_TRACKED_GLOBS:
        if marker in parts:
            return marker
    return ""


def main() -> int:
    errors: list[str] = []
    tracked = _tracked_files()

    for rel in tracked:
        if not (ROOT / rel).exists():
            # Ignore paths removed from working tree but not yet staged.
            continue
        for prefix in FORBIDDEN_TRACKED_PREFIXES:
            if rel.startswith(prefix):
                errors.append(f"{rel}: tracked generated report is forbidden")

        bad = _contains_forbidden_part(rel)
        if bad:
            errors.append(f"{rel}: tracked cache/artifact path contains '{bad}'")

        if "/" not in rel:
            if rel not in ALLOWED_ROOT_FILES:
                if any(rel.startswith(prefix) for prefix in FORBIDDEN_TRACKED_ROOT_GLOBS):
                    errors.append(f"{rel}: forbidden root artifact")
                else:
                    errors.append(f"{rel}: unexpected root file (not in allowlist)")
            continue

        top = rel.split("/", 1)[0]
        if top not in ALLOWED_ROOT_DIRS:
            errors.append(f"{rel}: top-level directory '{top}' is not allowlisted")

    if errors:
        for item in errors[:200]:
            print(f"[repo-hygiene] {item}", file=sys.stderr)
        if len(errors) > 200:
            print(f"[repo-hygiene] ... and {len(errors) - 200} more", file=sys.stderr)
        return 2

    print("[repo-hygiene] OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
