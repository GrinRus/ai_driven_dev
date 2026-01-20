#!/usr/bin/env python3
"""Validate tasklist readiness before implement."""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from fnmatch import fnmatch
from pathlib import Path
from typing import Iterable, List

from tools.feature_ids import resolve_identifiers, resolve_project_root


PLACEHOLDER_VALUES = {"", "...", "<...>", "tbd", "<tbd>", "todo", "<todo>"}
NONE_VALUES = {"none", "\u043d\u0435\u0442", "n/a", "na"}


@dataclass
class TasklistCheckResult:
    status: str
    message: str = ""
    details: List[str] | None = None
    warnings: List[str] | None = None

    def exit_code(self) -> int:
        return 0 if self.status in {"ok", "skip"} else 2


def parse_args(argv: Iterable[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate tasklist readiness.")
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
    stripped = value.strip()
    lowered = stripped.lower()
    if lowered in PLACEHOLDER_VALUES:
        return True
    return stripped.startswith("<") and stripped.endswith(">")


def extract_field_value(item: str, field: str) -> str | None:
    pattern = re.compile(rf"^\s*(?:[-*]\s*)?{re.escape(field)}\s*:\s*(.*)$", re.IGNORECASE)
    for line in item.splitlines():
        match = pattern.match(line)
        if match:
            return match.group(1).strip()
    return None


def section_has_field(section: str, field: str) -> bool:
    pattern = re.compile(rf"^\s*(?:[-*]\s*)?{re.escape(field)}\s*:\s*(.*)$", re.IGNORECASE)
    for line in section.splitlines():
        match = pattern.match(line)
        if not match:
            continue
        value = match.group(1).strip()
        if not value or is_placeholder(value):
            continue
        return True
    return False


def section_has_steps(section: str) -> bool:
    return re.search(r"^\s*-\s*Steps\s*:\s*$", section, re.IGNORECASE | re.MULTILINE) is not None


def extract_iteration_ids(section: str) -> list[str]:
    ids: list[str] = []
    for line in section.splitlines():
        match = re.search(r"\biteration_id\s*:\s*([A-Za-z0-9_-]+)", line, re.IGNORECASE)
        if match:
            ids.append(match.group(1).strip())
            continue
        match = re.match(r"^\s*-\s*(?:Iteration\s+)?([A-Za-z]+[0-9]+)\b", line)
        if match:
            ids.append(match.group(1).strip())
    return [item for item in ids if item]


def item_has_fields(item: str) -> tuple[bool, list[str]]:
    missing: list[str] = []

    iteration_value = extract_field_value(item, "iteration_id")
    if iteration_value is None or is_placeholder(iteration_value):
        missing.append("iteration_id")

    dod_value = extract_field_value(item, "DoD")
    if dod_value is None or is_placeholder(dod_value):
        missing.append("DoD")

    boundaries_value = extract_field_value(item, "Boundaries")
    if boundaries_value is None or is_placeholder(boundaries_value):
        missing.append("Boundaries")

    if not section_has_steps(item):
        missing.append("Steps")

    if "Tests:" not in item:
        missing.append("Tests")
    else:
        if re.search(r"\bprofile:\s*(fast|targeted|full|none)\b", item) is None:
            missing.append("Tests.profile")

    acceptance_value = extract_field_value(item, "Acceptance mapping")
    if acceptance_value is None or is_placeholder(acceptance_value):
        missing.append("Acceptance mapping")

    risks_value = extract_field_value(item, "Risks & mitigations")
    if risks_value is None or is_placeholder(risks_value):
        missing.append("Risks & mitigations")

    return (len(missing) == 0, missing)


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

    spec_pack = find_section(text, "AIDD:SPEC_PACK")
    if not spec_pack:
        return fail("missing section: ## AIDD:SPEC_PACK")

    test_strategy = find_section(text, "AIDD:TEST_STRATEGY")
    if not test_strategy:
        return fail("missing section: ## AIDD:TEST_STRATEGY")

    test_execution = find_section(text, "AIDD:TEST_EXECUTION")
    if not test_execution:
        return fail("missing section: ## AIDD:TEST_EXECUTION")
    if not section_has_field(test_execution, "profile"):
        return fail("AIDD:TEST_EXECUTION missing profile")
    if not section_has_field(test_execution, "tasks"):
        return fail("AIDD:TEST_EXECUTION missing tasks")
    if not section_has_field(test_execution, "filters"):
        return fail("AIDD:TEST_EXECUTION missing filters")
    if not section_has_field(test_execution, "when"):
        return fail("AIDD:TEST_EXECUTION missing when")
    if not section_has_field(test_execution, "reason"):
        return fail("AIDD:TEST_EXECUTION missing reason")

    iterations_full = find_section(text, "AIDD:ITERATIONS_FULL")
    if not iterations_full:
        return fail("missing section: ## AIDD:ITERATIONS_FULL")
    has_iteration = False
    for line in iterations_full.splitlines():
        match = re.match(r"^\s*-\s*Iteration\s+[A-Za-z]*\d+\s*:\s*(.+)$", line, re.IGNORECASE)
        if not match:
            continue
        value = match.group(1).strip()
        if not value or is_placeholder(value):
            continue
        has_iteration = True
        break
    if not has_iteration:
        return fail("AIDD:ITERATIONS_FULL has no concrete iterations")
    if not section_has_field(iterations_full, "DoD"):
        return fail("AIDD:ITERATIONS_FULL missing DoD details")
    if not section_has_field(iterations_full, "Boundaries"):
        return fail("AIDD:ITERATIONS_FULL missing Boundaries details")
    if not section_has_steps(iterations_full):
        return fail("AIDD:ITERATIONS_FULL missing Steps details")
    if re.search(r"\bprofile:\s*(fast|targeted|full|none)\b", iterations_full) is None:
        return fail("AIDD:ITERATIONS_FULL missing Tests.profile")
    if not section_has_field(iterations_full, "Acceptance mapping"):
        return fail("AIDD:ITERATIONS_FULL missing Acceptance mapping")
    if not section_has_field(iterations_full, "Risks & mitigations"):
        return fail("AIDD:ITERATIONS_FULL missing Risks & mitigations")

    iteration_ids = extract_iteration_ids(iterations_full)
    if not iteration_ids:
        return fail("AIDD:ITERATIONS_FULL missing iteration_id")

    plan_path = root / "docs" / "plan" / f"{ticket}.md"
    if not plan_path.exists():
        return fail(f"plan not found: {plan_path}")
    plan_text = read_text(plan_path)
    plan_iterations = find_section(plan_text, "AIDD:ITERATIONS")
    if not plan_iterations:
        return fail("plan missing section: ## AIDD:ITERATIONS")
    plan_iteration_ids = extract_iteration_ids(plan_iterations)
    if not plan_iteration_ids:
        return fail("AIDD:ITERATIONS missing iteration_id")
    missing_from_tasklist = sorted(set(plan_iteration_ids) - set(iteration_ids))
    if missing_from_tasklist:
        return fail(f"AIDD:ITERATIONS_FULL missing iteration_id(s): {', '.join(missing_from_tasklist)}")

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
        iteration_value = extract_field_value(item, "iteration_id")
        if iteration_value and iteration_value not in plan_iteration_ids:
            failures.append(f"item {idx} iteration_id not in plan: {iteration_value}")

    if failures:
        return fail("AIDD:NEXT_3 items missing required fields", details=failures)

    warnings: list[str] = []
    for section in ("AIDD:QA_TRACEABILITY", "AIDD:CHECKLIST_REVIEW", "AIDD:CHECKLIST_QA"):
        if not find_section(text, section):
            warnings.append(f"missing section: ## {section}")

    return TasklistCheckResult(status="ok", warnings=warnings)


def run_check(args: argparse.Namespace) -> int:
    root = resolve_project_root(Path.cwd())
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

    if result.warnings:
        for warning in result.warnings:
            print(f"[tasklist-check] WARN: {warning}", file=sys.stderr)

    if result.status == "ok" and not args.quiet_ok:
        print("[tasklist-check] OK: tasklist READY for implement", file=sys.stderr)
    return result.exit_code()


def main(argv: Iterable[str] | None = None) -> int:
    args = parse_args(argv)
    return run_check(args)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
