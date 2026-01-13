#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


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


PLACEHOLDER_VALUES = {"", "...", "<...>", "tbd", "<tbd>", "todo", "<todo>"}
NONE_VALUES = {"none", "нет", "n/a", "na"}


def is_placeholder(value: str) -> bool:
    return value.strip().lower() in PLACEHOLDER_VALUES


def extract_field_value(item: str, field: str) -> str | None:
    pattern = re.compile(rf"^\s*{re.escape(field)}\s*:\s*(.*)$", re.IGNORECASE)
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


def resolve_repo_root() -> Path:
    path = Path(__file__).resolve()
    for parent in path.parents:
        if (parent / "pyproject.toml").exists() or (parent / ".git").exists():
            return parent
    return path.parents[2]


def resolve_ticket(repo_root: Path, ticket: str | None) -> str:
    if ticket:
        return ticket.strip()
    active_ticket = repo_root / "aidd" / "docs" / ".active_ticket"
    if active_ticket.exists():
        return active_ticket.read_text(encoding="utf-8").strip()
    return ""


def fail(message: str) -> int:
    print(f"[tasklist-check] FAIL: {message}", file=sys.stderr)
    return 2


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ticket", default=None)
    args = parser.parse_args()

    repo_root = resolve_repo_root()
    ticket = resolve_ticket(repo_root, args.ticket)
    if not ticket:
        return fail("ticket not provided and aidd/docs/.active_ticket missing")

    tasklist_path = repo_root / "aidd" / "docs" / "tasklist" / f"{ticket}.md"
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
        for entry in failures:
            print(f"[tasklist-check] {entry}", file=sys.stderr)
        return fail("AIDD:NEXT_3 items missing required fields")

    interview = find_section(text, "AIDD:INTERVIEW")
    if not interview:
        return fail("missing section: ## AIDD:INTERVIEW")
    coverage = extract_coverage_checklist(interview)
    if not coverage:
        return fail("coverage checklist missing in AIDD:INTERVIEW")
    if any(re.match(r"^\s*-\s+\[\s*\]\s+", line) for line in coverage):
        return fail("coverage checklist not complete in AIDD:INTERVIEW")

    print("[tasklist-check] OK: tasklist READY for implement", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
