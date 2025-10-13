#!/usr/bin/env python3
"""Generate branch names that follow config/conventions.json presets."""

from __future__ import annotations

import argparse
import re
import sys

BRANCH_TYPES = ("feat", "fix", "chore", "docs", "test", "refactor", "perf", "build", "ci", "revert")
MIXED_ALLOWED_TYPES = ("feat", "fix", "chore", "docs", "refactor", "perf")
TICKET_PATTERN = re.compile(r"^[A-Z]+\-\d+$")


def require(condition: bool, message: str) -> None:
    if not condition:
        sys.exit(message)


def build_branch(args: argparse.Namespace) -> str:
    branch_type = args.type

    if branch_type == "feature":
        require(args.arg1 and TICKET_PATTERN.match(args.arg1), "Use: feature <TICKET>")
        return f"feature/{args.arg1}"

    if branch_type in BRANCH_TYPES:
        require(args.arg1, f"Use: {branch_type} <scope>")
        return f"{branch_type}/{args.arg1}"

    if branch_type == "hotfix":
        require(args.arg1 and TICKET_PATTERN.match(args.arg1), "Use: hotfix <TICKET>")
        return f"hotfix/{args.arg1}"

    if branch_type == "mixed":
        require(args.arg1 and args.arg2 and args.arg3, "Use: mixed <TICKET> <type> <scope>")
        require(TICKET_PATTERN.match(args.arg1), "TICKET must be A-Z+-digits")
        require(args.arg2 in MIXED_ALLOWED_TYPES, "type must be feat|fix|chore|docs|refactor|perf")
        return f"feature/{args.arg1}/{args.arg2}/{args.arg3}"

    sys.exit("Unknown branch type")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("type")
    parser.add_argument("arg1", nargs="?")
    parser.add_argument("arg2", nargs="?")
    parser.add_argument("arg3", nargs="?")
    args = parser.parse_args()

    print(build_branch(args))


if __name__ == "__main__":
    main()
