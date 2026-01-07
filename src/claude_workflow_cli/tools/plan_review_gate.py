#!/usr/bin/env python3
"""Shared plan review gate logic for Claude workflow hooks.

Checks that docs/plan/<ticket>.md contains a `## Plan Review` section with
Status READY and no open action items.
"""

from __future__ import annotations

import argparse
import json
import sys
from fnmatch import fnmatch
from pathlib import Path
from typing import Iterable, List, Set

from claude_workflow_cli.paths import AiddRootError, require_aidd_root

DEFAULT_APPROVED = {"ready"}
DEFAULT_BLOCKING = {"blocked"}
REVIEW_HEADER = "## Plan Review"


def parse_args(argv: Iterable[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate plan review readiness.")
    parser.add_argument(
        "--target",
        default=".",
        help="Workspace root (default: current; workflow lives in ./aidd).",
    )
    parser.add_argument("--ticket", required=True, help="Active feature ticket.")
    parser.add_argument("--file-path", default="", help="Path being modified.")
    parser.add_argument("--branch", default="", help="Current branch name.")
    parser.add_argument(
        "--config",
        default="config/gates.json",
        help="Path to gates configuration file (default: config/gates.json).",
    )
    parser.add_argument(
        "--skip-on-plan-edit",
        action="store_true",
        help="Return success when the plan file itself is being edited.",
    )
    return parser.parse_args(list(argv) if argv is not None else None)


def load_gate_config(path: Path) -> dict:
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    section = data.get("plan_review", {})
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


def detect_project_root(target: Path) -> Path:
    return require_aidd_root(target)


def normalize_path(raw: str) -> str:
    if not raw:
        return ""
    normalized = raw.replace("\\", "/")
    while normalized.startswith("./"):
        normalized = normalized[2:]
    if normalized.startswith("aidd/"):
        normalized = normalized[5:]
    return normalized.lstrip("/")


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


def run_gate(args: argparse.Namespace) -> int:
    try:
        root = detect_project_root(Path(args.target))
    except AiddRootError as exc:
        print(f"[plan-review-gate] {exc}", file=sys.stderr)
        return 2
    config_path = Path(args.config)
    if not config_path.is_absolute():
        config_path = root / config_path
    gate = load_gate_config(config_path)

    enabled = bool(gate.get("enabled", True))
    if not enabled:
        return 0

    if matches(gate.get("skip_branches", []), args.branch):
        return 0
    branches = gate.get("branches")
    if branches and not matches(branches, args.branch):
        return 0

    ticket = args.ticket.strip()
    plan_path = root / "docs" / "plan" / f"{ticket}.md"
    if not plan_path.is_file():
        print(f"BLOCK: нет плана (docs/plan/{ticket}.md) → выполните /plan-new {ticket}")
        return 1

    normalized = normalize_path(args.file_path)
    if args.skip_on_plan_edit and normalized.endswith(f"docs/plan/{ticket}.md"):
        return 0

    content = plan_path.read_text(encoding="utf-8")
    found, status, action_items = parse_review_section(content)

    allow_missing = bool(gate.get("allow_missing_section", False))
    if not found:
        if allow_missing:
            return 0
        print(f"BLOCK: нет раздела '## Plan Review' в docs/plan/{ticket}.md → выполните /review-spec {ticket}")
        return 1

    approved: Set[str] = {str(item).lower() for item in gate.get("approved_statuses", DEFAULT_APPROVED)}
    blocking: Set[str] = {str(item).lower() for item in gate.get("blocking_statuses", DEFAULT_BLOCKING)}

    if status in blocking:
        print(f"BLOCK: Plan Review помечен как '{status.upper()}' → устраните блокеры через /review-spec {ticket}")
        return 1

    if approved and status not in approved:
        print(f"BLOCK: Plan Review не READY (Status: {status.upper() or 'PENDING'}) → выполните /review-spec {ticket}")
        return 1

    if bool(gate.get("require_action_items_closed", True)):
        for item in action_items:
            if item.startswith("- [ ]"):
                print(f"BLOCK: В Plan Review остались незакрытые action items → обновите docs/plan/{ticket}.md")
                return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(run_gate(parse_args()))
