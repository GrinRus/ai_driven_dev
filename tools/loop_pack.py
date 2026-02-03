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
    goal: str
    expected_paths: Tuple[str, ...]
    skills: Tuple[str, ...]
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


def build_excerpt(block: List[str], max_lines: int = 30) -> Tuple[str, ...]:
    lines = [line.rstrip() for line in block if line.strip()]
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
        goal = extract_scalar_field(block, "Goal") or extract_scalar_field(block, "DoD") or title
        expected_paths = tuple(extract_list_field(block, "Expected paths"))
        skills = tuple(extract_list_field(block, "Skills"))
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
                goal=goal or title,
                expected_paths=expected_paths,
                skills=skills,
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
                goal=goal or title,
                expected_paths=tuple(),
                skills=tuple(),
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


def load_skill_index(path: Path) -> Dict[str, str]:
    if not path.exists():
        return {}
    skills: Dict[str, str] = {}
    current_id: Optional[str] = None
    for line in read_text(path).splitlines():
        if "skill_id:" in line:
            current_id = line.split("skill_id:", 1)[1].strip()
            continue
        if current_id and "path:" in line:
            skills[current_id] = line.split("path:", 1)[1].strip()
            current_id = None
    return skills


def find_work_item(items: Iterable[WorkItem], key_safe: str) -> Optional[WorkItem]:
    for item in items:
        if item.key_safe == key_safe:
            return item
    return None


def select_first_matching(refs: Iterable[WorkItemRef], items: Iterable[WorkItem]) -> Optional[WorkItem]:
    for ref in refs:
        candidate = find_work_item(items, ref.key_safe)
        if candidate:
            return candidate
    return None


def build_front_matter(
    *,
    ticket: str,
    work_item: WorkItem,
    boundaries: Dict[str, List[str]],
    skills_required: List[str],
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
    if skills_required:
        lines.append("skills_required:")
        lines.extend([f"  - {skill}" for skill in skills_required])
    else:
        lines.append("skills_required: []")
    if tests_required:
        lines.append("tests_required:")
        lines.extend([f"  - {skill}" for skill in tests_required])
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
    skills_required: List[str],
    tests_required: List[str],
    arch_profile: str,
    updated_at: str,
) -> str:
    front_matter = build_front_matter(
        ticket=ticket,
        work_item=work_item,
        boundaries=boundaries,
        skills_required=skills_required,
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
    lines.append("## Skills required")
    if skills_required:
        for skill in skills_required:
            lines.append(f"- {skill}")
    else:
        lines.append("- []")
    lines.append("")
    lines.append("## Tests required")
    if tests_required:
        for skill in tests_required:
            lines.append(f"- {skill}")
    else:
        lines.append("- []")
    if work_item.excerpt:
        lines.append("")
        lines.append("## Work item excerpt")
        lines.extend([f"> {line}" for line in work_item.excerpt])
    return "\n".join(lines).rstrip() + "\n"


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
        if active_ticket == ticket and active_work_item and not args.pick_next:
            selected_item = find_work_item(all_items, active_work_item)
            if selected_item:
                selection_reason = "active"
        if not selected_item:
            next3_refs = parse_next3_refs(sections.get("AIDD:NEXT_3", []))
            if next3_refs:
                selected_item = select_first_matching(next3_refs, all_items)
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
        if args.format:
            payload = {
                "schema": "aidd.loop_pack.v1",
                "status": "blocked",
                "ticket": ticket,
                "stage": args.stage,
                "reason": "work_item_not_found",
            }
            output = json.dumps(payload, ensure_ascii=False, indent=2) if args.format == "json" else "\n".join(dump_yaml(payload))
            print(output)
        else:
            print(message)
        return 2

    write_active_state(target, ticket, selected_item.key_safe)

    arch_profile_path = target / "docs" / "architecture" / "profile.md"
    arch_profile = runtime.rel_path(arch_profile_path, target)

    boundaries = {
        "allowed_paths": list(selected_item.expected_paths),
        "forbidden_paths": [],
    }
    skills_required = list(selected_item.skills)
    tests_required = list(selected_item.skills)

    skill_index_path = target / "skills" / "index.yaml"
    skill_index = load_skill_index(skill_index_path)
    missing_skills = [skill for skill in skills_required if skill not in skill_index]
    if missing_skills:
        print(f"[loop-pack] missing skill definitions: {', '.join(missing_skills)}", file=sys.stderr)

    updated_at = _utc_timestamp()
    pack_text = build_pack(
        ticket=ticket,
        work_item=selected_item,
        boundaries=boundaries,
        skills_required=skills_required,
        tests_required=tests_required,
        arch_profile=arch_profile,
        updated_at=updated_at,
    )

    output_dir = target / "reports" / "loops" / ticket
    output_dir.mkdir(parents=True, exist_ok=True)
    pack_path = output_dir / f"{selected_item.key_safe}.loop.pack.md"
    pack_path.write_text(pack_text, encoding="utf-8")
    rel_path = runtime.rel_path(pack_path, target)

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
        "skills_required": skills_required,
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
