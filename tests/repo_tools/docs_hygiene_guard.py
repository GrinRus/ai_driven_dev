#!/usr/bin/env python3
"""Lightweight hygiene checks for internal markdown docs."""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCAN_GLOBS = (
    "AGENTS.md",
    "docs/**/*.md",
    "tests/repo_tools/e2e_prompt/*.md",
)
# Backlog and RFC intentionally reference planned/not-yet-created artifacts.
SKIP_MISSING_PATH_CHECK = {
    "docs/backlog.md",
    "docs/memory-v2-rfc.md",
}
ALLOWED_REPO_PREFIXES = (
    "skills/",
    "hooks/",
    "tests/",
    "docs/",
    "templates/",
    "agents/",
    ".claude-plugin/",
    "aidd_runtime/",
    ".github/",
)
SKIP_TOKEN_PREFIXES = (
    "http://",
    "https://",
    "mailto:",
    "#",
    "python3",
    "bash",
    "sh",
    "rg",
    "sed",
    "cat",
    "/feature-dev-aidd",
    "Bash(",
    "Read",
    "Write",
    "Edit",
    "Glob",
)
ABS_USERS_RE = re.compile(r"/Users/[^\s`)]*")
INLINE_CODE_RE = re.compile(r"`([^`]+)`")
MARKDOWN_LINK_RE = re.compile(r"\[[^\]]+\]\(([^)]+)\)")


def _collect_markdown_files() -> list[Path]:
    files: set[Path] = set()
    for pattern in SCAN_GLOBS:
        for path in ROOT.glob(pattern):
            if path.is_file():
                files.add(path.resolve())
    return sorted(files)


def _normalize_path_candidate(raw: str) -> str:
    token = str(raw or "").strip()
    if not token:
        return ""
    if token.startswith(SKIP_TOKEN_PREFIXES):
        return ""
    token = token.split("#", 1)[0].split("?", 1)[0].strip()
    if not token:
        return ""
    token = token.split()[0].rstrip(".,:;")
    if token.startswith("./"):
        token = token[2:]
    if not token:
        return ""
    if any(ch in token for ch in ("*", "$", "{", "}", "<", ">", "|")):
        return ""
    return token


def _path_exists(path: str) -> bool:
    probe = ROOT / path
    if probe.exists():
        return True
    if ":" in path:
        # Support refs like `path/to/file.py:SYMBOL` or `path.md:42`.
        left = path.split(":", 1)[0]
        if (ROOT / left).exists():
            return True
    return False


def main() -> int:
    md_files = _collect_markdown_files()
    if not md_files:
        print("[docs-hygiene-guard] no markdown files to scan")
        return 0

    abs_path_violations: list[str] = []
    missing_path_violations: list[str] = []

    for file_path in md_files:
        rel_file = file_path.relative_to(ROOT).as_posix()
        text = file_path.read_text(encoding="utf-8", errors="replace")
        lines = text.splitlines()

        for line_no, line in enumerate(lines, start=1):
            abs_match = ABS_USERS_RE.search(line)
            if abs_match:
                abs_path_violations.append(f"{rel_file}:{line_no}: contains machine-specific path `{abs_match.group(0)}`")

            if rel_file in SKIP_MISSING_PATH_CHECK:
                continue

            candidates: list[str] = []
            candidates.extend(m.group(1) for m in INLINE_CODE_RE.finditer(line))
            candidates.extend(m.group(1) for m in MARKDOWN_LINK_RE.finditer(line))
            for raw_candidate in candidates:
                candidate = _normalize_path_candidate(raw_candidate)
                if not candidate or not candidate.startswith(ALLOWED_REPO_PREFIXES):
                    continue
                if _path_exists(candidate):
                    continue
                missing_path_violations.append(
                    f"{rel_file}:{line_no}: missing repo-relative path `{candidate}`"
                )

    if abs_path_violations:
        for entry in abs_path_violations[:20]:
            print(f"[docs-hygiene-guard] {entry}", file=sys.stderr)
        print(
            f"[docs-hygiene-guard] found {len(abs_path_violations)} machine-specific absolute path references",
            file=sys.stderr,
        )
        return 1

    if missing_path_violations:
        for entry in missing_path_violations[:20]:
            print(f"[docs-hygiene-guard] {entry}", file=sys.stderr)
        print(
            f"[docs-hygiene-guard] found {len(missing_path_violations)} invalid repo-relative path references",
            file=sys.stderr,
        )
        return 1

    print(f"[docs-hygiene-guard] OK (scanned={len(md_files)})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
