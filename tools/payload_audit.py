#!/usr/bin/env python3
"""Audit payload contents against allowlist/denylist rules."""

from __future__ import annotations

import argparse
import fnmatch
import json
import sys
from pathlib import Path
from typing import Iterable


def iter_payload_files(root: Path) -> list[str]:
    files: list[str] = []
    for candidate in sorted(p for p in root.rglob("*") if p.is_file()):
        files.append(candidate.relative_to(root).as_posix())
    return files


def match_any(value: str, patterns: Iterable[str]) -> bool:
    return any(fnmatch.fnmatch(value, pattern) for pattern in patterns)


def load_rules(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    return {
        "allow_files": data.get("allow_files", []),
        "allow_globs": data.get("allow_globs", []),
        "deny_globs": data.get("deny_globs", []),
    }


def audit(payload_root: Path, rules_path: Path) -> int:
    rules = load_rules(rules_path)
    allow_files = set(rules["allow_files"])
    allow_globs = list(rules["allow_globs"])
    deny_globs = list(rules["deny_globs"])

    files = iter_payload_files(payload_root)

    missing_files = sorted([item for item in allow_files if item not in files])
    missing_globs = sorted(
        [pattern for pattern in allow_globs if not any(fnmatch.fnmatch(item, pattern) for item in files)]
    )

    denied = sorted([item for item in files if match_any(item, deny_globs)])
    unexpected = sorted(
        [
            item
            for item in files
            if item not in allow_files and not match_any(item, allow_globs)
        ]
    )

    if not (missing_files or missing_globs or denied or unexpected):
        print("[payload-audit] ok: payload contents match allowlist/denylist rules")
        return 0

    print("[payload-audit] issues found:")
    if missing_files:
        print("  - missing allow_files:")
        for item in missing_files:
            print(f"    - {item}")
    if missing_globs:
        print("  - allow_globs with no matches:")
        for item in missing_globs:
            print(f"    - {item}")
    if denied:
        print("  - denied files:")
        for item in denied:
            print(f"    - {item}")
    if unexpected:
        print("  - unexpected files:")
        for item in unexpected:
            print(f"    - {item}")
    return 1


def guess_payload_root() -> Path:
    here = Path(__file__).resolve()
    for parent in here.parents:
        candidate = parent / "src" / "claude_workflow_cli" / "data" / "payload"
        if candidate.is_dir():
            return candidate
        if parent.name == "payload" and (parent / "aidd").is_dir():
            return parent
    return here.parents[2]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Audit payload contents against allowlist/denylist rules.")
    parser.add_argument(
        "--payload-dir",
        default=str(guess_payload_root()),
        help="Payload directory to audit.",
    )
    parser.add_argument(
        "--rules",
        default=str(Path(__file__).with_name("payload_audit_rules.json")),
        help="Path to the allowlist/denylist rules JSON.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    payload_root = Path(args.payload_dir).resolve()
    if not payload_root.is_dir():
        parser.error(f"payload directory not found: {payload_root}")
    rules_path = Path(args.rules).resolve()
    if not rules_path.is_file():
        parser.error(f"rules file not found: {rules_path}")
    return audit(payload_root, rules_path)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
