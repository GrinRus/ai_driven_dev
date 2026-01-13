#!/usr/bin/env python3
"""Validate tasklist spec readiness before implement."""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from fnmatch import fnmatch
from pathlib import Path
from typing import Iterable, List

from claude_workflow_cli.feature_ids import resolve_identifiers, resolve_project_root


PLACEHOLDER_VALUES = {"", "...", "<...>", "tbd", "<tbd>", "todo", "<todo>"}
NONE_VALUES = {"none", "\u043d\u0435\u0442", "n/a", "na"}


@dataclass
class TasklistCheckResult:
    status: str
    message: str = ""
    details: List[str] | None = None

    def exit_code(self) -> int:
        return 0 if self.status in {"ok", "skip"} else 2


def parse_args(argv: Iterable[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate tasklist spec readiness.")
    parser.add_argument(
        "--target",
        default=".",
        help="Workspace root (default: current; workflow lives in ./aidd).",
    )
    parser.add_argument("--ticket", default=None, help="Feature ticket (defaults to docs/.active_ticket).")
    parser.add_argument("--slug-hint", default=None, help="Optional slug hint override.")
    parser.add_argument("--branch", default="", help="Current branch name for branch filters.")
    parser.add_argument(
        "--config",
        default="config/gates.json",
        help="Path to gates configuration file (default: config/gates.json).",
    )
    parser.add_argument(
        "--quiet-ok",
        action="store_true",
        help="Suppress output when the check passes.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print skip diagnostics when the gate is disabled.",
    )
    return parser.parse_args(list(argv) if argv is not None else None)


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def find_section(text: str, title: str) -> str | None:
    pattern = re.compile(r"^##\s+" + re.escape(title) + r"\s*$", re.MULTILINE)
    matches = list(pattern.finditer(text))
    if not matches:
        return None
    start = matches[0].end()
    tail = text[start:]
    next_heading = re.search(r"^##\s+", tail, re.MULTILINE)
    end = start + next_heading.start() if next_heading else len(text)
    return text[start:end]


def extract_checkboxes(section_body: str) -> list[str]:
    items: list[str] = []
    current: list[str] = []
    for line in section_body.splitlines():
        if re.match(r"^\s*-\s+\[[ xX]\]\s+", line):
            if current:
                items.append("\n".join(current).strip())
                current = []
            current.append(line)
        elif current:
            current.append(line)
    if current:
        items.append("\n".join(current).strip())
    return [item for item in items if item]


def is_placeholder(value: str) -> bool:
    return value.strip().lower() in PLACEHOLDER_VALUES


def extract_field_value(item: str, field: str) -> str | None:
    pattern = re.compile(rf"^\s*(?:[-*]\s*)?{re.escape(field)}\s*:\s*(.*)$", re.IGNORECASE)
    for line in item.splitlines():
        match = pattern.match(line)
        if match:
            return match.group(1).strip()
    return None


def item_has_fields(item: str) -> tuple[bool, list[str]]:
    missing: list[str] = []

    dod_value = extract_field_value(item, "DoD")
    if dod_value is None or is_placeholder(dod_value):
        missing.append("DoD")

    boundaries_value = extract_field_value(item, "Boundaries")
    if boundaries_value is None or is_placeholder(boundaries_value):
        missing.append("Boundaries")

    if "Tests:" not in item:
        missing.append("Tests")
    else:
        if re.search(r"\bprofile:\s*(fast|targeted|full|none)\b", item) is None:
            missing.append("Tests.profile")

    return (len(missing) == 0, missing)


def extract_coverage_checklist(interview_text: str) -> list[str]:
    lines = interview_text.splitlines()
    start = None
    for idx, line in enumerate(lines):
        if "coverage checklist" in line.lower():
            start = idx + 1
            break
    if start is None:
        return []
    block: list[str] = []
    for line in lines[start:]:
        stripped = line.strip()
        if stripped.startswith("##") or stripped.startswith("###"):
            break
        if stripped.lower().startswith("question queue"):
            break
        block.append(line)
    return block


def load_gate_config(path: Path) -> dict | None:
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    section = data.get("tasklist_spec")
    if section is None:
        return None
    if isinstance(section, bool):
        return {"enabled": section}
    return section if isinstance(section, dict) else None


def matches(patterns: Iterable[str], value: str) -> bool:
    if not value:
        return False
    for pattern in patterns or ():
        if pattern and fnmatch(value, pattern):
            return True
    return False


def should_skip_gate(gate: dict | None, branch: str) -> tuple[bool, str]:
    if gate is None:
        return True, "gate config missing"
    enabled = bool(gate.get("enabled", True))
    if not enabled:
        return True, "gate disabled"
    if branch and matches(gate.get("skip_branches", []), branch):
        return True, "branch skipped"
    branches = gate.get("branches")
    if branch and branches and not matches(branches, branch):
        return True, "branch not in allowlist"
    return False, ""


def fail(message: str, *, details: List[str] | None = None) -> TasklistCheckResult:
    return TasklistCheckResult(status="error", message=message, details=details or [])


def check_tasklist(root: Path, ticket: str) -> TasklistCheckResult:
    tasklist_path = root / "docs" / "tasklist" / f"{ticket}.md"
    if not tasklist_path.exists():
        return fail(f"tasklist not found: {tasklist_path}")

    text = read_text(tasklist_path)

    spec_section = find_section(text, "AIDD:SPEC")
    if not spec_section:
        return fail("missing section: ## AIDD:SPEC")
    if re.search(r"(?im)^\s*Status:\s*READY\b", spec_section) is None:
        return fail("AIDD:SPEC Status is not READY")

    open_questions = find_section(text, "AIDD:OPEN_QUESTIONS")
    if open_questions:
        for line in open_questions.splitlines():
            if not re.search(r"\(blocker\)", line, re.IGNORECASE):
                continue
            tail = line.split(")", 1)[1] if ")" in line else line
            value = tail.lstrip(" :.-").strip()
            if not value:
                return fail("blocker questions present in AIDD:OPEN_QUESTIONS")
            if value.lower() in NONE_VALUES:
                continue
            if is_placeholder(value):
                return fail("blocker questions present in AIDD:OPEN_QUESTIONS")
            return fail("blocker questions present in AIDD:OPEN_QUESTIONS")

    next_3 = find_section(text, "AIDD:NEXT_3")
    if not next_3:
        return fail("missing section: ## AIDD:NEXT_3")

    items = extract_checkboxes(next_3)
    if len(items) < 3:
        return fail("AIDD:NEXT_3 has fewer than 3 checkboxes")

    failures: list[str] = []
    for idx, item in enumerate(items[:3], start=1):
        ok, missing = item_has_fields(item)
        if not ok:
            header = item.splitlines()[0].strip()
            failures.append(f"item {idx} missing: {', '.join(missing)} -> {header}")

    if failures:
        return fail("AIDD:NEXT_3 items missing required fields", details=failures)

    interview = find_section(text, "AIDD:INTERVIEW")
    if not interview:
        return fail("missing section: ## AIDD:INTERVIEW")
    coverage = extract_coverage_checklist(interview)
    if not coverage:
        return fail("coverage checklist missing in AIDD:INTERVIEW")
    if any(re.match(r"^\s*-\s+\[\s*\]\s+", line) for line in coverage):
        return fail("coverage checklist not complete in AIDD:INTERVIEW")

    return TasklistCheckResult(status="ok")


def run_check(args: argparse.Namespace) -> int:
    root = resolve_project_root(Path(args.target).resolve())
    config_path = Path(args.config)
    if not config_path.is_absolute():
        config_path = root / config_path

    gate = load_gate_config(config_path)
    skip_gate, skip_reason = should_skip_gate(gate, args.branch or "")
    if skip_gate:
        if args.verbose:
            print(f"[tasklist-check] SKIP: {skip_reason}", file=sys.stderr)
        return 0

    identifiers = resolve_identifiers(root, ticket=args.ticket, slug_hint=args.slug_hint)
    ticket = (identifiers.resolved_ticket or "").strip()
    if not ticket:
        result = fail("ticket not provided and docs/.active_ticket missing")
    else:
        result = check_tasklist(root, ticket)

    if result.status == "error":
        if result.details:
            for entry in result.details:
                print(f"[tasklist-check] {entry}", file=sys.stderr)
        print(f"[tasklist-check] FAIL: {result.message}", file=sys.stderr)
        return result.exit_code()

    if result.status == "ok" and not args.quiet_ok:
        print("[tasklist-check] OK: tasklist READY for implement", file=sys.stderr)
    return result.exit_code()


def main(argv: Iterable[str] | None = None) -> int:
    args = parse_args(argv)
    return run_check(args)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
