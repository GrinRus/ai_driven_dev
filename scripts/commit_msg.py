#!/usr/bin/env python3
"""Generate or validate commit messages based on config/conventions.json."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

CONFIG_PATH = Path("config/conventions.json")


def load_config() -> dict:
    with CONFIG_PATH.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def current_branch() -> str:
    try:
        output = subprocess.check_output(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            stderr=subprocess.DEVNULL,
        )
        return output.decode().strip()
    except subprocess.CalledProcessError:
        return ""


def validate_message(mode: str, message: str) -> bool:
    patterns = {
        "ticket-prefix": r"^[A-Z]+\-\d+: .+",
        "conventional": r"^(feat|fix|chore|docs|test|refactor|perf|build|ci|revert)(\([\w\-\*]+\))?: .+",
        "mixed": r"^[A-Z]+\-\d+ (feat|fix|chore|docs|refactor|perf)(\([\w\-\*]+\))?: .+",
    }
    regex = patterns.get(mode, r"^.+$")
    return re.match(regex, message or "") is not None


def build_message(cfg: dict, mode: str, branch: str, summary: str, override_type: str | None) -> str:
    commit_cfg = cfg["commit"]

    if mode == "ticket-prefix":
        match = re.match(commit_cfg["ticket"]["branch_pattern"], branch or "")
        if not match:
            sys.exit(f"[commit] Branch '{branch}' not ticket-prefix")
        ticket = match.group("ticket")
        return commit_cfg["ticket"]["format"].format(ticket=ticket, summary=summary)

    if mode == "conventional":
        match = re.match(commit_cfg["conventional"]["branch_pattern"], branch or "")
        if not match:
            sys.exit("[commit] Branch must be 'feat/scope' etc")
        commit_type = override_type or match.group("type")
        scope = match.group("scope")
        return commit_cfg["conventional"]["format"].format(type=commit_type, scope=scope, summary=summary)

    if mode == "mixed":
        match = re.match(commit_cfg["mixed"]["branch_pattern"], branch or "")
        if not match:
            sys.exit("[commit] Branch must be 'feature/TICKET/{type}/{scope}'")
        ticket = match.group("ticket")
        commit_type = override_type or match.group("type")
        scope = match.group("scope")
        return commit_cfg["mixed"]["format"].format(ticket=ticket, type=commit_type, scope=scope, summary=summary)

    sys.exit(f"[commit] Unknown mode: {mode}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--summary", default="")
    parser.add_argument("--type")
    parser.add_argument("--branch")
    parser.add_argument("--mode")
    parser.add_argument("--validate")
    args = parser.parse_args()

    config = load_config()
    mode = args.mode or config["commit"]["mode"]

    if args.validate is not None:
        verdict = "OK" if validate_message(mode, args.validate.strip()) else "FAIL"
        print(verdict)
        return

    summary = args.summary.strip()
    if not summary:
        sys.exit("[commit] require --summary")

    branch = args.branch or current_branch()
    print(build_message(config, mode, branch, summary, args.type))


if __name__ == "__main__":
    main()
