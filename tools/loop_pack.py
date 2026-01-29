#!/usr/bin/env python3
"""Build a loop pack for a single work item."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

from tools import runtime

SECTION_RE = re.compile(r"^##\s+(AIDD:[A-Z0-9_]+)\b")
CHECKBOX_RE = re.compile(r"^\s*-\s*\[(?P<state>[ xX])\]\s+(?P<body>.+)$")
REF_RE = re.compile(r"\bref\s*:\s*([^\)]+)")
ITERATION_ID_RE = re.compile(r"\biteration_id\s*[:=]\s*([A-Za-z0-9_.:-]+)")
ITEM_ID_RE = re.compile(r"\bid\s*:\s*([A-Za-z0-9_.:-]+)")
PROGRESS_RE = re.compile(
    r"\bsource=(?P<source>[A-Za-z0-9_-]+)\b.*\bid=(?P<item_id>[A-Za-z0-9_.:-]+)\b.*\bkind=(?P<kind>[A-Za-z0-9_-]+)\b"
)


@dataclass(frozen=True)
class WorkItem:
    kind: str
    item_id: str
    key_prefix: str
    key_raw: str
    key_safe: str
    title: str
    state: str
    goal: str
    expected_paths: Tuple[str, ...]
    commands: Tuple[str, ...]
    tests_required: Tuple[str, ...]
    size_budget: Dict[str, str]
    exit_criteria: Tuple[str, ...]
    excerpt: Tuple[str, ...]


@dataclass(frozen=True)
class WorkItemRef:
    key_prefix: str
    item_id: str

    @property
    def key_raw(self) -> str:
        return f"{self.key_prefix}={self.item_id}"

    @property
    def key_safe(self) -> str:
        return sanitize_key(self.key_raw)


@dataclass(frozen=True)
class ReviewPackMeta:
    verdict: str
    work_item_key: str
    handoff_ids: Tuple[str, ...]


def _utc_timestamp() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def sanitize_key(value: str) -> str:
    return value.replace(":", "_")


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""


def parse_sections(lines: List[str]) -> Dict[str, List[str]]:
    sections: Dict[str, List[str]] = {}
    current: Optional[str] = None
    current_lines: List[str] = []
    for line in lines:
        match = SECTION_RE.match(line)
        if match:
            if current:
                sections[current] = current_lines
            current = match.group(1).strip()
            current_lines = [line]
            continue
        if current:
            current_lines.append(line)
    if current:
        sections[current] = current_lines
    return sections


def parse_front_matter(lines: List[str]) -> Dict[str, str]:
    if not lines or lines[0].strip() != "---":
        return {}
    data: Dict[str, str] = {}
    for line in lines[1:]:
        if line.strip() == "---":
            break
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        data[key.strip()] = value.strip()
    return data


def parse_review_pack_handoff_ids(lines: List[str]) -> Tuple[str, ...]:
    handoff_ids: List[str] = []
    in_section = False
    base_indent = 0
    for raw in lines:
        stripped = raw.strip()
        if stripped == "- handoff_ids:":
            in_section = True
            base_indent = len(raw) - len(raw.lstrip(" "))
            continue
        if not in_section:
            continue
        if not stripped:
            continue
        indent = len(raw) - len(raw.lstrip(" "))
        if indent <= base_indent and stripped.startswith("-"):
            break
        if indent <= base_indent and stripped:
            break
        if raw.lstrip().startswith("-") and indent > base_indent:
            item = raw.lstrip()[2:].strip()
            if _strip_placeholder(item):
                handoff_ids.append(item)
            continue
        if indent <= base_indent:
            break
    return tuple(handoff_ids)


def read_review_pack_meta(root: Path, ticket: str) -> ReviewPackMeta:
    pack_path = root / "reports" / "loops" / ticket / "review.latest.pack.md"
    if not pack_path.exists():
        return ReviewPackMeta("", "", tuple())
    lines = read_text(pack_path).splitlines()
    front = parse_front_matter(lines)
    schema = (front.get("schema") or "").strip()
    if schema and schema != "aidd.review_pack.v1":
        return ReviewPackMeta("", "", tuple())
    verdict = (front.get("verdict") or "").strip().upper()
    work_item_key = (front.get("work_item_key") or "").strip()
    handoff_ids = parse_review_pack_handoff_ids(lines)
    return ReviewPackMeta(verdict, work_item_key, handoff_ids)


def split_checkbox_blocks(lines: Iterable[str]) -> List[List[str]]:
    blocks: List[List[str]] = []
    current: List[str] = []
    for line in lines:
        if CHECKBOX_RE.match(line):
            if current:
                blocks.append(current)
                current = []
            current.append(line)
            continue
        if current:
            current.append(line)
    if current:
        blocks.append(current)
    return blocks


def _strip_placeholder(value: str) -> Optional[str]:
    stripped = value.strip()
    if not stripped:
        return None
    if stripped.startswith("<") and stripped.endswith(">"):
        return None
    return stripped


def extract_scalar_field(lines: List[str], field: str) -> Optional[str]:
    pattern = re.compile(rf"^\s*-\s*{re.escape(field)}\s*:\s*(.+)$", re.IGNORECASE)
    for line in lines:
        match = pattern.match(line)
        if match:
            value = match.group(1).strip()
            return _strip_placeholder(value) or value
    return None


def extract_list_field(lines: List[str], field: str) -> List[str]:
    pattern = re.compile(rf"^(?P<indent>\s*)-\s*{re.escape(field)}\s*:\s*$", re.IGNORECASE)
    for idx, line in enumerate(lines):
        match = pattern.match(line)
        if not match:
            continue
        base_indent = len(match.group("indent"))
        items: List[str] = []
        for raw in lines[idx + 1 :]:
            if not raw.strip():
                continue
            indent = len(raw) - len(raw.lstrip(" "))
            if indent <= base_indent and raw.lstrip().startswith("-"):
                break
            if indent <= base_indent and raw.strip():
                break
            if raw.lstrip().startswith("-") and indent > base_indent:
                item = raw.lstrip()[2:].strip()
                if _strip_placeholder(item):
                    items.append(item)
        return items
    return []


def extract_mapping_field(lines: List[str], field: str) -> Dict[str, str]:
    pattern = re.compile(rf"^(?P<indent>\s*)-\s*{re.escape(field)}\s*:\s*$", re.IGNORECASE)
    for idx, line in enumerate(lines):
        match = pattern.match(line)
        if not match:
            continue
        base_indent = len(match.group("indent"))
        result: Dict[str, str] = {}
        for raw in lines[idx + 1 :]:
            if not raw.strip():
                continue
            indent = len(raw) - len(raw.lstrip(" "))
            if indent <= base_indent and raw.lstrip().startswith("-"):
                break
            if indent <= base_indent and raw.strip():
                break
            if raw.lstrip().startswith("-") and indent > base_indent:
                item = raw.lstrip()[2:].strip()
                if ":" in item:
                    key, value = item.split(":", 1)
                    key = key.strip()
                    value = value.strip()
                    if _strip_placeholder(key) and _strip_placeholder(value):
                        result[key] = value
        return result
    return {}


def extract_title(block: List[str]) -> str:
    if not block:
        return ""
    match = CHECKBOX_RE.match(block[0])
    if not match:
        return block[0].strip()
    body = match.group("body").strip()
    title = re.sub(r"\s*\([^)]*\)\s*$", "", body).strip()
    return title or body


def extract_checkbox_state(block: List[str]) -> str:
    if not block:
        return "open"
    match = CHECKBOX_RE.match(block[0])
    if not match:
        return "open"
    state = match.group("state")
    return "done" if state.lower() == "x" else "open"


def build_excerpt(block: List[str], max_lines: int = 30) -> Tuple[str, ...]:
    if not block:
        return tuple()
    lines: List[str] = []
    lines.append(block[0].rstrip())

    wanted_prefixes = (
        "- goal:",
        "- dod:",
        "- boundaries:",
        "- commands:",
        "- tests:",
        "- acceptance mapping:",
        "- spec:",
    )
    capture_expected = False
    expected_indent = 0

    for raw in block[1:]:
        line = raw.rstrip()
        if not line.strip():
            continue
        stripped = line.strip()
        lower = stripped.lower()

        if capture_expected:
            indent = len(raw) - len(raw.lstrip(" "))
            if indent <= expected_indent and stripped.startswith("-"):
                capture_expected = False
            else:
                if stripped.startswith("-"):
                    lines.append(line)
                continue

        if lower.startswith("- expected paths"):
            lines.append(line)
            capture_expected = True
            expected_indent = len(raw) - len(raw.lstrip(" "))
            continue

        if any(lower.startswith(prefix) for prefix in wanted_prefixes):
            lines.append(line)
            continue

    if len(lines) > max_lines:
        lines = lines[:max_lines]
    return tuple(lines)


def parse_iteration_items(lines: List[str]) -> List[WorkItem]:
    items: List[WorkItem] = []
    for block in split_checkbox_blocks(lines):
        item_id = None
        for line in block:
            match = ITERATION_ID_RE.search(line)
            if match:
                item_id = match.group(1).strip()
                break
        if not item_id:
            continue
        title = extract_title(block)
        state = extract_checkbox_state(block)
        goal = extract_scalar_field(block, "Goal") or extract_scalar_field(block, "DoD") or title
        expected_paths = tuple(extract_list_field(block, "Expected paths"))
        commands = tuple(extract_list_field(block, "Commands"))
        tests_map = extract_mapping_field(block, "Tests")
        tests_required: Tuple[str, ...] = tuple()
        tasks_value = tests_map.get("tasks") or tests_map.get("Tasks")
        if tasks_value and _strip_placeholder(tasks_value):
            tests_required = (tasks_value,)
        size_budget = extract_mapping_field(block, "Size budget")
        exit_criteria = tuple(extract_list_field(block, "Exit criteria"))
        key_prefix = "iteration_id"
        key_raw = f"{key_prefix}={item_id}"
        items.append(
            WorkItem(
                kind="iteration",
                item_id=item_id,
                key_prefix=key_prefix,
                key_raw=key_raw,
                key_safe=sanitize_key(key_raw),
                title=title,
                state=state,
                goal=goal or title,
                expected_paths=expected_paths,
                commands=commands,
                tests_required=tests_required,
                size_budget=size_budget,
                exit_criteria=exit_criteria,
                excerpt=build_excerpt(block),
            )
        )
    return items


def parse_handoff_items(lines: List[str]) -> List[WorkItem]:
    items: List[WorkItem] = []
    for block in split_checkbox_blocks(lines):
        item_id = None
        for line in block:
            match = ITEM_ID_RE.search(line)
            if match:
                item_id = match.group(1).strip()
                break
        if not item_id:
            continue
        title = extract_title(block)
        state = extract_checkbox_state(block)
        goal = extract_scalar_field(block, "Goal") or extract_scalar_field(block, "DoD") or title
        key_prefix = "id"
        key_raw = f"{key_prefix}={item_id}"
        items.append(
            WorkItem(
                kind="handoff",
                item_id=item_id,
                key_prefix=key_prefix,
                key_raw=key_raw,
                key_safe=sanitize_key(key_raw),
                title=title,
                state=state,
                goal=goal or title,
                expected_paths=tuple(),
                commands=tuple(),
                tests_required=tuple(),
                size_budget={},
                exit_criteria=tuple(),
                excerpt=build_excerpt(block),
            )
        )
    return items


def parse_next3_refs(lines: List[str]) -> List[WorkItemRef]:
    refs: List[WorkItemRef] = []
    for line in lines:
        if "(none)" in line.lower():
            continue
        match = REF_RE.search(line)
        if not match:
            continue
        ref = match.group(1).strip()
        if ref.startswith("iteration_id="):
            refs.append(WorkItemRef("iteration_id", ref.split("=", 1)[1].strip()))
        elif ref.startswith("id="):
            refs.append(WorkItemRef("id", ref.split("=", 1)[1].strip()))
    return refs


def parse_progress_ref(lines: List[str]) -> Optional[WorkItemRef]:
    for line in reversed(lines):
        match = PROGRESS_RE.search(line)
        if not match:
            continue
        if match.group("source") != "implement":
            continue
        item_id = match.group("item_id").strip()
        kind = match.group("kind").strip().lower()
        key_prefix = "iteration_id" if kind == "iteration" else "id"
        return WorkItemRef(key_prefix, item_id)
    return None


def read_active_ticket(root: Path) -> str:
    path = root / "docs" / ".active_ticket"
    try:
        return path.read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def read_active_work_item(root: Path) -> str:
    path = root / "docs" / ".active_work_item"
    try:
        return path.read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def write_active_state(root: Path, ticket: str, work_item_key: str) -> None:
    docs_dir = root / "docs"
    docs_dir.mkdir(parents=True, exist_ok=True)
    (docs_dir / ".active_ticket").write_text(ticket + "\n", encoding="utf-8")
    (docs_dir / ".active_work_item").write_text(work_item_key + "\n", encoding="utf-8")


def find_work_item(items: Iterable[WorkItem], key_safe: str) -> Optional[WorkItem]:
    for item in items:
        if item.key_safe == key_safe:
            return item
    return None


def is_open_item(item: WorkItem) -> bool:
    return item.state != "done"


def select_first_matching(refs: Iterable[WorkItemRef], items: Iterable[WorkItem]) -> Optional[WorkItem]:
    for ref in refs:
        candidate = find_work_item(items, ref.key_safe)
        if candidate:
            return candidate
    return None


def select_first_open(refs: Iterable[WorkItemRef], items: Iterable[WorkItem]) -> Optional[WorkItem]:
    for ref in refs:
        candidate = find_work_item(items, ref.key_safe)
        if candidate and is_open_item(candidate):
            return candidate
    return None


def normalize_review_handoff_id(value: str) -> Tuple[str, ...]:
    raw = value.strip()
    if not raw:
        return tuple()
    if raw.startswith("reviewer:"):
        raw = raw.replace("reviewer:", "review:", 1)
    if raw.startswith("review:"):
        return (raw,)
    return (raw, f"review:{raw}")


def is_review_handoff_id(value: str) -> bool:
    raw = value.strip().lower()
    return raw.startswith("review:") or raw.startswith("reviewer:")


def select_first_open_handoff(handoff_ids: Iterable[str], handoffs: Iterable[WorkItem]) -> Optional[WorkItem]:
    for item_id in handoff_ids:
        for candidate_id in normalize_review_handoff_id(item_id):
            ref = WorkItemRef("id", candidate_id)
            candidate = find_work_item(handoffs, ref.key_safe)
            if candidate and is_open_item(candidate):
                return candidate
    return None


def build_front_matter(
    *,
    ticket: str,
    work_item: WorkItem,
    boundaries: Dict[str, List[str]],
    commands_required: List[str],
    tests_required: List[str],
    arch_profile: str,
    evidence_policy: str,
    updated_at: str,
) -> List[str]:
    lines = [
        "---",
        "schema: aidd.loop_pack.v1",
        f"updated_at: {updated_at}",
        f"ticket: {ticket}",
        f"work_item_id: {work_item.item_id}",
        f"work_item_key: {work_item.key_safe}",
        "boundaries:",
    ]
    allowed_paths = boundaries.get("allowed_paths", [])
    if allowed_paths:
        lines.append("  allowed_paths:")
        lines.extend([f"    - {path}" for path in allowed_paths])
    else:
        lines.append("  allowed_paths: []")
    forbidden_paths = boundaries.get("forbidden_paths", [])
    if forbidden_paths:
        lines.append("  forbidden_paths:")
        lines.extend([f"    - {path}" for path in forbidden_paths])
    else:
        lines.append("  forbidden_paths: []")
    if commands_required:
        lines.append("commands_required:")
        lines.extend([f"  - {command}" for command in commands_required])
    else:
        lines.append("commands_required: []")
    if tests_required:
        lines.append("tests_required:")
        lines.extend([f"  - {command}" for command in tests_required])
    else:
        lines.append("tests_required: []")
    lines.append(f"arch_profile: {arch_profile}")
    lines.append(f"evidence_policy: {evidence_policy}")
    lines.append("---")
    return lines


def build_pack(
    *,
    ticket: str,
    work_item: WorkItem,
    boundaries: Dict[str, List[str]],
    commands_required: List[str],
    tests_required: List[str],
    arch_profile: str,
    updated_at: str,
) -> str:
    front_matter = build_front_matter(
        ticket=ticket,
        work_item=work_item,
        boundaries=boundaries,
        commands_required=commands_required,
        tests_required=tests_required,
        arch_profile=arch_profile,
        evidence_policy="RLM-first",
        updated_at=updated_at,
    )
    lines: List[str] = []
    lines.extend(front_matter)
    lines.append("")
    lines.append(f"# Loop Pack — {ticket} / {work_item.key_safe}")
    lines.append("")
    lines.append("## Work item")
    lines.append(f"- work_item_id: {work_item.item_id}")
    lines.append(f"- work_item_key: {work_item.key_safe}")
    lines.append(f"- goal: {work_item.goal}")
    lines.append("")
    lines.append("## Do not read")
    lines.append("- PRD/Plan/Research — только если есть ссылка в pack")
    lines.append("- Полный tasklist — только excerpt ниже")
    lines.append("- Большие логи/диффы — только ссылки на отчёты")
    lines.append("")
    lines.append("## Boundaries")
    lines.append("- allowed_paths:")
    if boundaries.get("allowed_paths"):
        for path in boundaries["allowed_paths"]:
            lines.append(f"  - {path}")
    else:
        lines.append("  - []")
    lines.append("- forbidden_paths:")
    if boundaries.get("forbidden_paths"):
        for path in boundaries["forbidden_paths"]:
            lines.append(f"  - {path}")
    else:
        lines.append("  - []")
    lines.append("")
    lines.append("## Commands required")
    if commands_required:
        for command in commands_required:
            lines.append(f"- {command}")
    else:
        lines.append("- []")
    lines.append("")
    lines.append("## Tests required")
    if tests_required:
        for command in tests_required:
            lines.append(f"- {command}")
    else:
        lines.append("- []")
    lines.append("")
    lines.append("## Work item excerpt")
    if work_item.excerpt:
        lines.extend([f"> {line}" for line in work_item.excerpt])
    else:
        lines.append("> (none)")
    return "\n".join(lines).rstrip() + "\n"


def write_pack_for_item(
    *,
    root: Path,
    output_dir: Path,
    ticket: str,
    work_item: WorkItem,
    arch_profile: str,
) -> Tuple[Path, Dict[str, List[str]], List[str], List[str], str]:
    boundaries = {
        "allowed_paths": list(work_item.expected_paths),
        "forbidden_paths": [],
    }
    commands_required = list(work_item.commands)
    tests_required = list(work_item.tests_required)
    updated_at = _utc_timestamp()
    pack_text = build_pack(
        ticket=ticket,
        work_item=work_item,
        boundaries=boundaries,
        commands_required=commands_required,
        tests_required=tests_required,
        arch_profile=arch_profile,
        updated_at=updated_at,
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    pack_path = output_dir / f"{work_item.key_safe}.loop.pack.md"
    pack_path.write_text(pack_text, encoding="utf-8")
    return pack_path, boundaries, commands_required, tests_required, updated_at


def dump_yaml(data: object, indent: int = 0) -> List[str]:
    lines: List[str] = []
    prefix = " " * indent
    if isinstance(data, dict):
        for key, value in data.items():
            if isinstance(value, (dict, list)):
                lines.append(f"{prefix}{key}:")
                lines.extend(dump_yaml(value, indent + 2))
            else:
                lines.append(f"{prefix}{key}: {json.dumps(value)}")
    elif isinstance(data, list):
        for item in data:
            if isinstance(item, (dict, list)):
                lines.append(f"{prefix}-")
                lines.extend(dump_yaml(item, indent + 2))
            else:
                lines.append(f"{prefix}- {json.dumps(item)}")
    else:
        lines.append(f"{prefix}{json.dumps(data)}")
    return lines


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate loop pack for a single work item.")
    parser.add_argument("--ticket", help="Ticket identifier to use (defaults to docs/.active_ticket).")
    parser.add_argument("--slug-hint", help="Optional slug hint override.")
    parser.add_argument(
        "--stage",
        choices=("implement", "review"),
        default="implement",
        help="Stage for work item selection (implement|review).",
    )
    parser.add_argument(
        "--work-item",
        help="Explicit work item ref (iteration_id=I3 or id=review:F6).",
    )
    parser.add_argument(
        "--pick-next",
        action="store_true",
        help="Force selection from AIDD:NEXT_3 even if active_work_item exists.",
    )
    parser.add_argument(
        "--format",
        choices=("json", "yaml"),
        help="Emit structured output to stdout.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    _, target = runtime.require_workflow_root()
    context = runtime.resolve_feature_context(target, ticket=args.ticket, slug_hint=args.slug_hint)
    ticket = (context.resolved_ticket or "").strip()
    if not ticket:
        raise ValueError("feature ticket is required; pass --ticket or set docs/.active_ticket via /feature-dev-aidd:idea-new.")

    tasklist_path = target / "docs" / "tasklist" / f"{ticket}.md"
    if not tasklist_path.exists():
        raise FileNotFoundError(f"tasklist not found at {runtime.rel_path(tasklist_path, target)}")

    tasklist_lines = read_text(tasklist_path).splitlines()
    sections = parse_sections(tasklist_lines)
    iterations = parse_iteration_items(sections.get("AIDD:ITERATIONS_FULL", []))
    handoffs = parse_handoff_items(sections.get("AIDD:HANDOFF_INBOX", []))
    all_items = iterations + handoffs

    active_ticket = read_active_ticket(target)
    active_work_item = read_active_work_item(target)
    selected_item: Optional[WorkItem] = None
    selection_reason = ""
    review_meta = read_review_pack_meta(target, ticket) if args.stage == "implement" else ReviewPackMeta("", "", tuple())
    open_handoffs = [item for item in handoffs if is_open_item(item) and is_review_handoff_id(item.item_id)]
    revise_mode = args.stage == "implement" and review_meta.verdict == "REVISE" and not args.pick_next

    if args.work_item:
        raw = args.work_item.strip()
        if raw.startswith("iteration_id="):
            ref = WorkItemRef("iteration_id", raw.split("=", 1)[1].strip())
        elif raw.startswith("id="):
            ref = WorkItemRef("id", raw.split("=", 1)[1].strip())
        else:
            raise ValueError("--work-item must be iteration_id=... or id=...")
        selected_item = find_work_item(all_items, ref.key_safe)
        if not selected_item:
            raise ValueError(f"work item {raw} not found in tasklist")
        selection_reason = "override"
    elif args.stage == "implement":
        if revise_mode:
            review_key = sanitize_key(review_meta.work_item_key) if review_meta.work_item_key else ""
            if review_key:
                candidate = find_work_item(all_items, review_key)
                if candidate and is_open_item(candidate):
                    selected_item = candidate
                    selection_reason = "review-pack"
            if not selected_item and review_meta.handoff_ids:
                selected_item = select_first_open_handoff(review_meta.handoff_ids, handoffs)
                if selected_item:
                    selection_reason = "review-handoff"
            if not selected_item and open_handoffs:
                selected_item = open_handoffs[0]
                selection_reason = "handoff"
        if not selected_item and active_ticket == ticket and active_work_item and not args.pick_next:
            if revise_mode and (review_meta.work_item_key or open_handoffs):
                selected_item = None
            else:
                selected_item = find_work_item(all_items, active_work_item)
                if selected_item:
                    if is_open_item(selected_item):
                        selection_reason = "active"
                    else:
                        selected_item = None
        if not selected_item:
            next3_refs = parse_next3_refs(sections.get("AIDD:NEXT_3", []))
            if next3_refs:
                if revise_mode and open_handoffs:
                    selected_item = None
                else:
                    selected_item = select_first_open(next3_refs, all_items)
                    if selected_item:
                        selection_reason = "next3"
    else:
        if args.pick_next:
            next3_refs = parse_next3_refs(sections.get("AIDD:NEXT_3", []))
            if next3_refs:
                selected_item = select_first_matching(next3_refs, all_items)
                if selected_item:
                    selection_reason = "next3"
        if not selected_item:
            if active_ticket == ticket and active_work_item:
                selected_item = find_work_item(all_items, active_work_item)
                if selected_item:
                    selection_reason = "active"
        if not selected_item:
            progress_ref = parse_progress_ref(sections.get("AIDD:PROGRESS_LOG", []))
            if progress_ref:
                selected_item = find_work_item(all_items, progress_ref.key_safe)
                if selected_item:
                    selection_reason = "progress"

    if not selected_item:
        message = "BLOCKED: work item not found for loop pack selection"
        reason = "work_item_not_found"
        if revise_mode:
            message = "BLOCKED: review pack requires revise but no open review handoff item"
            reason = "review_revise_missing_handoff"
        if args.format:
            payload = {
                "schema": "aidd.loop_pack.v1",
                "status": "blocked",
                "ticket": ticket,
                "stage": args.stage,
                "reason": reason,
            }
            output = json.dumps(payload, ensure_ascii=False, indent=2) if args.format == "json" else "\n".join(dump_yaml(payload))
            print(output)
        else:
            print(message)
        return 2

    write_active_state(target, ticket, selected_item.key_safe)

    arch_profile_path = target / "docs" / "architecture" / "profile.md"
    arch_profile = runtime.rel_path(arch_profile_path, target)

    output_dir = target / "reports" / "loops" / ticket

    prewarm_items: List[WorkItem] = []
    if args.stage == "implement":
        next3_refs = parse_next3_refs(sections.get("AIDD:NEXT_3", []))
        if next3_refs:
            for ref in next3_refs:
                candidate = find_work_item(all_items, ref.key_safe)
                if candidate and is_open_item(candidate):
                    prewarm_items.append(candidate)
    prewarm_map: Dict[str, WorkItem] = {selected_item.key_safe: selected_item}
    for item in prewarm_items:
        prewarm_map.setdefault(item.key_safe, item)

    selected_pack_path = None
    boundaries: Dict[str, List[str]] = {}
    commands_required: List[str] = []
    tests_required: List[str] = []
    updated_at = _utc_timestamp()

    for item in prewarm_map.values():
        pack_path, item_boundaries, item_commands, item_tests, item_updated_at = write_pack_for_item(
            root=target,
            output_dir=output_dir,
            ticket=ticket,
            work_item=item,
            arch_profile=arch_profile,
        )
        if item.key_safe == selected_item.key_safe:
            selected_pack_path = pack_path
            boundaries = item_boundaries
            commands_required = item_commands
            tests_required = item_tests
            updated_at = item_updated_at

    if selected_pack_path is None:
        raise ValueError("failed to generate loop pack for selected work item")

    rel_path = runtime.rel_path(selected_pack_path, target)

    payload = {
        "schema": "aidd.loop_pack.v1",
        "updated_at": updated_at,
        "ticket": ticket,
        "stage": args.stage,
        "work_item_id": selected_item.item_id,
        "work_item_key": selected_item.key_safe,
        "selection": selection_reason,
        "path": rel_path,
        "boundaries": boundaries,
        "commands_required": commands_required,
        "tests_required": tests_required,
        "arch_profile": arch_profile,
        "evidence_policy": "RLM-first",
    }

    if args.format:
        output = json.dumps(payload, ensure_ascii=False, indent=2) if args.format == "json" else "\n".join(dump_yaml(payload))
        print(output)
        print(f"[loop-pack] saved {rel_path} ({selected_item.key_raw})", file=sys.stderr)
        return 0

    print(f"[loop-pack] saved {rel_path} ({selected_item.key_raw})")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
