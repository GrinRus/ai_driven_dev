#!/usr/bin/env python3
"""Shared PRD review gate logic for Claude workflow hooks.

The script checks that `docs/prd/<slug>.prd.md` contains a `## PRD Review`
section with an approved status and no unresolved action items. Behaviour is
configured through `config/gates.json` (see the `prd_review` section).

Exit codes:
    0 — gate passed or skipped (disabled / branch excluded / direct PRD edit).
    1 — gate failed (message is printed to stdout).
"""

from __future__ import annotations

import argparse
import json
from fnmatch import fnmatch
from pathlib import Path
from typing import Iterable, List, Set


DEFAULT_APPROVED = {"approved"}
DEFAULT_BLOCKING = {"blocked"}
REVIEW_HEADER = "## PRD Review"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate PRD review readiness.")
    parser.add_argument("--slug", required=True, help="Active feature slug.")
    parser.add_argument(
        "--file-path",
        default="",
        help="Path being modified (used to skip checks for direct PRD edits).",
    )
    parser.add_argument(
        "--branch",
        default="",
        help="Current branch name for branch-based filters.",
    )
    parser.add_argument(
        "--config",
        default="config/gates.json",
        help="Path to gates configuration file (default: config/gates.json).",
    )
    parser.add_argument(
        "--skip-on-prd-edit",
        action="store_true",
        help="Return success when the PRD file itself is being edited.",
    )
    return parser.parse_args()


def load_gate_config(path: Path) -> dict:
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:  # pragma: no cover - malformed configs are rare
        return {}
    section = data.get("prd_review", {})
    if isinstance(section, bool):
        return {"enabled": section}
    return section if isinstance(section, dict) else {}


def matches(patterns: Iterable[str], value: str) -> bool:
    if not value:
        return False
    for pattern in patterns or ():
        if pattern and fnmatch(value, pattern):
            return True
    return False


def parse_review_section(content: str) -> tuple[bool, str, List[str]]:
    inside = False
    found = False
    status = ""
    action_items: List[str] = []
    for raw in content.splitlines():
        stripped = raw.strip()
        if stripped.startswith("## "):
            inside = stripped == REVIEW_HEADER
            if inside:
                found = True
            continue
        if not inside:
            continue
        lower = stripped.lower()
        if lower.startswith("status:"):
            status = stripped.split(":", 1)[1].strip().lower()
        elif stripped.startswith("- ["):
            action_items.append(stripped)
    return found, status, action_items


def format_message(kind: str, slug: str, status: str | None = None) -> str:
    if kind == "missing_section":
        return f"BLOCK: нет раздела '## PRD Review' в docs/prd/{slug}.prd.md → выполните /review-prd {slug}"
    if kind == "missing_prd":
        return f"BLOCK: нет PRD → запустите /idea-new {slug}"
    if kind == "blocking_status":
        return f"BLOCK: PRD Review помечен как '{status}' → устраните блокеры и обновите статус через /review-prd {slug}"
    if kind == "not_approved":
        human = status or "pending"
        return f"BLOCK: PRD Review не утверждён (Status: {human}) → выполните /review-prd {slug}"
    if kind == "open_actions":
        return "BLOCK: В PRD Review остались незакрытые action items → перенесите их в tasklist и отметьте выполнение."
    return f"BLOCK: PRD Review не готов → выполните /review-prd {slug}"


def main() -> None:
    args = parse_args()
    gate = load_gate_config(Path(args.config))

    enabled = bool(gate.get("enabled", True))
    if not enabled:
        raise SystemExit(0)

    if matches(gate.get("skip_branches", []), args.branch):
        raise SystemExit(0)
    branches = gate.get("branches")
    if branches and not matches(branches, args.branch):
        raise SystemExit(0)

    prd_path = Path("docs/prd") / f"{args.slug}.prd.md"
    if not prd_path.is_file():
        print(format_message("missing_prd", args.slug))
        raise SystemExit(1)

    normalized = args.file_path.replace("\\", "/") if args.file_path else ""
    target_suffix = f"docs/prd/{args.slug}.prd.md"
    if args.skip_on_prd_edit and normalized.endswith(target_suffix):
        raise SystemExit(0)

    allow_missing = bool(gate.get("allow_missing_section", False))
    require_closed = bool(gate.get("require_action_items_closed", True))
    approved: Set[str] = {str(item).lower() for item in gate.get("approved_statuses", DEFAULT_APPROVED)}
    blocking: Set[str] = {str(item).lower() for item in gate.get("blocking_statuses", DEFAULT_BLOCKING)}

    content = prd_path.read_text(encoding="utf-8")
    found, status, action_items = parse_review_section(content)

    if not found:
        if allow_missing:
            raise SystemExit(0)
        print(format_message("missing_section", args.slug))
        raise SystemExit(1)

    if status in blocking:
        print(format_message("blocking_status", args.slug, status))
        raise SystemExit(1)

    if approved and status not in approved:
        print(format_message("not_approved", args.slug, status))
        raise SystemExit(1)

    if require_closed:
        for item in action_items:
            if item.startswith("- [ ]"):
                print(format_message("open_actions", args.slug, status))
                raise SystemExit(1)

    raise SystemExit(0)


if __name__ == "__main__":
    main()
