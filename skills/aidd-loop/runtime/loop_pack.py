#!/usr/bin/env python3
"""Build a loop pack for a single work item."""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

from aidd_runtime import runtime
from aidd_runtime.feature_ids import write_active_state
from aidd_runtime.io_utils import dump_yaml, parse_front_matter, utc_timestamp
from aidd_runtime.tasklist_parser import PATH_TOKEN_RE, extract_boundaries

SECTION_RE = re.compile(r"^##\s+(AIDD:[A-Z0-9_]+)\b")
CHECKBOX_RE = re.compile(r"^\s*-\s*\[(?P<state>[ xX])\]\s+(?P<body>.+)$")
REF_RE = re.compile(r"\bref\s*:\s*([^\)]+)")
ITERATION_ID_RE = re.compile(r"\biteration_id\s*[:=]\s*([A-Za-z0-9_.:-]+)")
ITEM_ID_RE = re.compile(r"\bid\s*:\s*([A-Za-z0-9_.:-]+)")
PROGRESS_RE = re.compile(
    r"\bsource=(?P<source>[A-Za-z0-9_-]+)\b.*\bid=(?P<item_id>[A-Za-z0-9_.:-]+)\b.*\bkind=(?P<kind>[A-Za-z0-9_-]+)\b"
)
CHANGELOG_MASTER_PATH = "backend/src/main/resources/db/changelog/db.changelog-master.yaml"
CHANGELOG_DIR = "backend/src/main/resources/db/changelog/"


def _normalize_path(value: str) -> str:
    normalized = value.replace("\\", "/")
    if normalized.startswith("./"):
        normalized = normalized[2:]
    return normalized.lstrip("/")


def _needs_changelog_master(allowed_paths: Iterable[str]) -> bool:
    for raw in allowed_paths:
        normalized = _normalize_path(raw)
        if normalized == CHANGELOG_DIR.rstrip("/"):
            return True
        if normalized.startswith(CHANGELOG_DIR):
            return True
    return False


def _extend_boundaries_for_changelog(boundaries: Dict[str, List[str]]) -> None:
    allowed = boundaries.get("allowed_paths")
    if not allowed:
        return
    if _needs_changelog_master(allowed) and CHANGELOG_MASTER_PATH not in allowed:
        allowed.append(CHANGELOG_MASTER_PATH)


def _strip_placeholder(value: str) -> str:
    text = value.strip()
    if not text:
        return ""
    if text.startswith("<") and text.endswith(">"):
        return ""
    return text


def _dedupe_paths(paths: Iterable[str]) -> List[str]:
    seen = set()
    ordered: List[str] = []
    for raw in paths:
        item = raw.strip()
        if not item or item in seen:
            continue
        seen.add(item)
        ordered.append(item)
    return ordered


def parse_context_allowed_paths(lines: List[str]) -> List[str]:
    allowed: List[str] = []
    in_allowed = False
    header_indent = 0
    for raw in lines:
        stripped = raw.strip()
        if stripped.startswith("## "):
            if in_allowed:
                break
            continue
        lower = stripped.lower()
        if not in_allowed:
            if "allowed paths" in lower:
                in_allowed = True
                header_indent = len(raw) - len(raw.lstrip(" "))
            continue
        if "forbidden" in lower or "out-of-scope" in lower:
            break
        if stripped.startswith("-"):
            indent = len(raw) - len(raw.lstrip(" "))
            if indent <= header_indent and "allowed paths" not in lower:
                break
            item = _strip_placeholder(stripped.lstrip("-").strip())
            if item:
                allowed.append(item)
        elif stripped and (len(raw) - len(raw.lstrip(" ")) <= header_indent):
            break
    return _dedupe_paths(allowed)


def _extract_command_paths(commands: Iterable[str], root: Path) -> List[str]:
    paths: List[str] = []
    for command in commands:
        for match in PATH_TOKEN_RE.findall(str(command)):
            cleaned = match.strip().strip("`'\" ,);")
            if not cleaned or any(ch in cleaned for ch in "*?[]"):
                continue
            candidate = Path(cleaned)
            if not candidate.is_absolute():
                candidate = root / candidate
            try:
                if not candidate.exists():
                    continue
            except OSError:
                continue
            rel_path = runtime.rel_path(candidate, root)
            if root.name == "aidd" and rel_path.startswith("aidd/"):
                rel_path = rel_path.split("/", 1)[1]
            paths.append(rel_path)
    return _dedupe_paths(paths)


@dataclass(frozen=True)
class WorkItem:
    kind: str
    item_id: str
    key_prefix: str
    work_item_key: str
    scope_key: str
    title: str
    state: str
    goal: str
    boundaries_allowed: Tuple[str, ...]
    boundaries_forbidden: Tuple[str, ...]
    boundaries_defined: bool
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
    def work_item_key(self) -> str:
        return f"{self.key_prefix}={self.item_id}"

    @property
    def scope_key(self) -> str:
        return runtime.sanitize_scope_key(self.work_item_key)


@dataclass(frozen=True)
class ReviewPackMeta:
    verdict: str
    work_item_key: str
    scope_key: str
    handoff_ids: Tuple[str, ...]
    schema: str = ""


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


REVIEW_PACK_SCHEMAS = {"aidd.review_pack.v1", "aidd.review_pack.v2"}


def _load_review_pack_meta(pack_path: Path, ticket: str) -> ReviewPackMeta | None:
    lines = read_text(pack_path).splitlines()
    front = parse_front_matter(lines)
    schema = (front.get("schema") or "").strip()
    if schema and schema not in REVIEW_PACK_SCHEMAS:
        return None
    verdict = (front.get("verdict") or "").strip().upper()
    work_item_key = (front.get("work_item_key") or "").strip()
    scope_key = (front.get("scope_key") or "").strip() or runtime.resolve_scope_key(work_item_key, ticket)
    handoff_ids = parse_review_pack_handoff_ids(lines)
    return ReviewPackMeta(verdict, work_item_key, scope_key, handoff_ids, schema)


def read_review_pack_meta(root: Path, ticket: str) -> ReviewPackMeta:
    active_work_item = runtime.read_active_work_item(root)
    scope_key = runtime.resolve_scope_key(active_work_item, ticket) if active_work_item else ""
    if scope_key:
        candidate = root / "reports" / "loops" / ticket / scope_key / "review.latest.pack.md"
        if candidate.exists():
            meta = _load_review_pack_meta(candidate, ticket)
            return meta or ReviewPackMeta("", "", "", tuple())

    base_dir = root / "reports" / "loops" / ticket
    if base_dir.exists():
        fallback_meta: ReviewPackMeta | None = None
        for candidate in sorted(base_dir.glob("*/review.latest.pack.md")):
            meta = _load_review_pack_meta(candidate, ticket)
            if not meta:
                continue
            if meta.verdict == "REVISE":
                return meta
            if fallback_meta is None:
                fallback_meta = meta
        if fallback_meta:
            return fallback_meta
    return ReviewPackMeta("", "", "", tuple())


def review_pack_v2_required(root: Path) -> bool:
    config = runtime.load_gates_config(root)
    if not isinstance(config, dict):
        return False
    raw = config.get("review_pack_v2_required")
    if raw is None:
        return False
    if isinstance(raw, str):
        return raw.strip().lower() in {"1", "true", "yes", "block", "strict"}
    return bool(raw)


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


def _normalize_tests_value(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    cleaned = value.strip()
    if not cleaned or cleaned.lower() in {"[]", "none", "n/a"}:
        return None
    return cleaned


def _normalize_tests_required(tests_map: Dict[str, str]) -> Tuple[str, ...]:
    tasks = _normalize_tests_value(tests_map.get("tasks") or tests_map.get("Tasks"))
    profile = _normalize_tests_value(tests_map.get("profile") or tests_map.get("Profile"))
    filters = _normalize_tests_value(tests_map.get("filters") or tests_map.get("Filters"))
    required: List[str] = []
    if tasks:
        required.append(tasks)
    if profile:
        required.append(f"profile:{profile}")
    if filters:
        required.append(f"filters:{filters}")
    return tuple(required)


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
        "- acceptance mapping:",
        "- spec:",
    )
    capture_block = False
    capture_indent = 0

    for raw in block[1:]:
        line = raw.rstrip()
        if not line.strip():
            continue
        stripped = line.strip()
        lower = stripped.lower()

        if capture_block:
            indent = len(raw) - len(raw.lstrip(" "))
            if indent <= capture_indent and stripped.startswith("-"):
                capture_block = False
            else:
                if stripped.startswith("-"):
                    lines.append(line)
                continue

        if lower.startswith("- expected paths") or lower.startswith("- size budget") or lower.startswith("- tests"):
            lines.append(line)
            capture_block = True
            capture_indent = len(raw) - len(raw.lstrip(" "))
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
        boundaries_allowed, boundaries_forbidden, boundaries_defined = extract_boundaries(block)
        expected_paths = tuple(extract_list_field(block, "Expected paths"))
        commands = tuple(extract_list_field(block, "Commands"))
        tests_map = extract_mapping_field(block, "Tests")
        tests_required = _normalize_tests_required(tests_map)
        size_budget = extract_mapping_field(block, "Size budget")
        exit_criteria = tuple(extract_list_field(block, "Exit criteria"))
        key_prefix = "iteration_id"
        work_item_key = f"{key_prefix}={item_id}"
        scope_key = runtime.sanitize_scope_key(work_item_key)
        items.append(
            WorkItem(
                kind="iteration",
                item_id=item_id,
                key_prefix=key_prefix,
                work_item_key=work_item_key,
                scope_key=scope_key,
                title=title,
                state=state,
                goal=goal or title,
                boundaries_allowed=tuple(boundaries_allowed),
                boundaries_forbidden=tuple(boundaries_forbidden),
                boundaries_defined=boundaries_defined,
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
        boundaries_allowed, boundaries_forbidden, boundaries_defined = extract_boundaries(block)
        key_prefix = "id"
        work_item_key = f"{key_prefix}={item_id}"
        scope_key = runtime.sanitize_scope_key(work_item_key)
        items.append(
            WorkItem(
                kind="handoff",
                item_id=item_id,
                key_prefix=key_prefix,
                work_item_key=work_item_key,
                scope_key=scope_key,
                title=title,
                state=state,
                goal=goal or title,
                boundaries_allowed=tuple(boundaries_allowed),
                boundaries_forbidden=tuple(boundaries_forbidden),
                boundaries_defined=boundaries_defined,
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


def find_work_item(items: Iterable[WorkItem], scope_key: str) -> Optional[WorkItem]:
    for item in items:
        if item.scope_key == scope_key:
            return item
    return None


def is_open_item(item: WorkItem) -> bool:
    return item.state != "done"


def select_first_matching(refs: Iterable[WorkItemRef], items: Iterable[WorkItem]) -> Optional[WorkItem]:
    for ref in refs:
        candidate = find_work_item(items, ref.scope_key)
        if candidate:
            return candidate
    return None


def select_first_open(refs: Iterable[WorkItemRef], items: Iterable[WorkItem]) -> Optional[WorkItem]:
    for ref in refs:
        candidate = find_work_item(items, ref.scope_key)
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
            candidate = find_work_item(handoffs, ref.scope_key)
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
    evidence_policy: str,
    updated_at: str,
    reason_code: str = "",
) -> List[str]:
    lines = [
        "---",
        "schema: aidd.loop_pack.v1",
        f"updated_at: {updated_at}",
        f"ticket: {ticket}",
        f"work_item_id: {work_item.item_id}",
        f"work_item_key: {work_item.work_item_key}",
        f"scope_key: {work_item.scope_key}",
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
    lines.append(f"evidence_policy: {evidence_policy}")
    if reason_code:
        lines.append(f"reason_code: {reason_code}")
    lines.append("---")
    return lines


def build_pack(
    *,
    ticket: str,
    work_item: WorkItem,
    boundaries: Dict[str, List[str]],
    commands_required: List[str],
    tests_required: List[str],
    updated_at: str,
    reason_code: str = "",
) -> str:
    front_matter = build_front_matter(
        ticket=ticket,
        work_item=work_item,
        boundaries=boundaries,
        commands_required=commands_required,
        tests_required=tests_required,
        evidence_policy="RLM-first",
        updated_at=updated_at,
        reason_code=reason_code,
    )
    lines: List[str] = []
    lines.extend(front_matter)
    lines.append("")
    lines.append(f"# Loop Pack — {ticket} / {work_item.scope_key}")
    lines.append("")
    lines.append("## Work item")
    lines.append(f"- work_item_id: {work_item.item_id}")
    lines.append(f"- work_item_key: {work_item.work_item_key}")
    lines.append(f"- scope_key: {work_item.scope_key}")
    lines.append(f"- goal: {work_item.goal}")
    lines.append("")
    lines.append("## Read order")
    lines.append("- Prefer excerpt; read full tasklist/PRD/Plan/Research/Spec only if excerpt misses Goal/DoD/Boundaries/Expected paths/Size budget/Tests/Acceptance or REVISE needs context.")
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
    context_allowed_paths: List[str],
) -> Tuple[Path, Dict[str, List[str]], List[str], List[str], str, str]:
    if work_item.boundaries_defined:
        boundaries = {
            "allowed_paths": list(work_item.boundaries_allowed),
            "forbidden_paths": list(work_item.boundaries_forbidden),
        }
        reason_code = ""
    else:
        boundaries = {"allowed_paths": [], "forbidden_paths": []}
        reason_code = "no_boundaries_defined_warn"
    if work_item.expected_paths:
        missing_expected = [
            path for path in work_item.expected_paths if path and path not in boundaries["allowed_paths"]
        ]
        if missing_expected:
            boundaries["allowed_paths"].extend(missing_expected)
            reason_code = "auto_boundary_extend_warn"
    if not boundaries.get("allowed_paths") and context_allowed_paths:
        boundaries["allowed_paths"].extend(context_allowed_paths)
        reason_code = "auto_boundary_extend_warn"
    if boundaries.get("allowed_paths"):
        boundaries["allowed_paths"] = list(dict.fromkeys(boundaries["allowed_paths"]))
    _extend_boundaries_for_changelog(boundaries)
    commands_required = list(work_item.commands)
    command_paths = _extract_command_paths(commands_required, root)
    if command_paths:
        missing_command_paths = [
            path for path in command_paths if path not in boundaries.get("allowed_paths", [])
        ]
        if missing_command_paths:
            boundaries["allowed_paths"].extend(missing_command_paths)
            boundaries["allowed_paths"] = list(dict.fromkeys(boundaries["allowed_paths"]))
            reason_code = "auto_boundary_extend_warn"
    tests_required = list(work_item.tests_required)
    updated_at = utc_timestamp()
    pack_text = build_pack(
        ticket=ticket,
        work_item=work_item,
        boundaries=boundaries,
        commands_required=commands_required,
        tests_required=tests_required,
        updated_at=updated_at,
        reason_code=reason_code,
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    pack_path = output_dir / f"{work_item.scope_key}.loop.pack.md"
    pack_path.write_text(pack_text, encoding="utf-8")
    return pack_path, boundaries, commands_required, tests_required, updated_at, reason_code


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate loop pack for a single work item.")
    parser.add_argument("--ticket", help="Ticket identifier to use (defaults to docs/.active.json).")
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
        raise ValueError("feature ticket is required; pass --ticket or set docs/.active.json via /feature-dev-aidd:idea-new.")

    tasklist_path = target / "docs" / "tasklist" / f"{ticket}.md"
    if not tasklist_path.exists():
        raise FileNotFoundError(f"tasklist not found at {runtime.rel_path(tasklist_path, target)}")

    tasklist_lines = read_text(tasklist_path).splitlines()
    sections = parse_sections(tasklist_lines)
    context_allowed_paths = parse_context_allowed_paths(sections.get("AIDD:CONTEXT_PACK", []))
    iterations = parse_iteration_items(sections.get("AIDD:ITERATIONS_FULL", []))
    handoffs = parse_handoff_items(sections.get("AIDD:HANDOFF_INBOX", []))
    all_items = iterations + handoffs

    active_ticket = runtime.read_active_ticket(target)
    active_work_item = runtime.read_active_work_item(target)
    selected_item: Optional[WorkItem] = None
    selection_reason = ""
    review_meta = (
        read_review_pack_meta(target, ticket)
        if args.stage == "implement"
        else ReviewPackMeta("", "", "", tuple())
    )
    open_handoffs = [item for item in handoffs if is_open_item(item) and is_review_handoff_id(item.item_id)]
    revise_mode = args.stage == "implement" and review_meta.verdict == "REVISE" and not args.pick_next

    if args.stage == "review" and not args.work_item:
        if active_ticket and active_ticket != ticket:
            message = "BLOCKED: review active ticket mismatch"
            reason = "review_active_ticket_mismatch"
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
        if not active_work_item:
            message = "BLOCKED: review active work item missing"
            reason = "review_active_work_item_missing"
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

    if args.stage == "implement" and review_meta.schema == "aidd.review_pack.v1" and review_pack_v2_required(target):
        message = "BLOCKED: review pack v2 required"
        reason = "review_pack_v2_required"
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

    if args.work_item:
        raw = args.work_item.strip()
        if raw.startswith("iteration_id="):
            ref = WorkItemRef("iteration_id", raw.split("=", 1)[1].strip())
        elif raw.startswith("id="):
            ref = WorkItemRef("id", raw.split("=", 1)[1].strip())
        else:
            raise ValueError("--work-item must be iteration_id=... or id=...")
        selected_item = find_work_item(all_items, ref.scope_key)
        if not selected_item:
            raise ValueError(f"work item {raw} not found in tasklist")
        selection_reason = "override"
    elif args.stage == "implement":
        if revise_mode:
            if active_ticket == ticket and active_work_item:
                candidate = find_work_item(all_items, runtime.sanitize_scope_key(active_work_item))
                if candidate and is_open_item(candidate):
                    selected_item = candidate
                    selection_reason = "active-revise"
                elif candidate:
                    message = "BLOCKED: review pack requires revise but active work item is closed"
                    reason = "review_revise_closed_item"
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
                else:
                    message = "BLOCKED: review pack requires revise but active work item is missing"
                    reason = "review_revise_missing_active"
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
            else:
                message = "BLOCKED: review pack requires revise but active work item is missing"
                reason = "review_revise_missing_active"
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
        else:
            if review_meta.scope_key:
                candidate = find_work_item(all_items, review_meta.scope_key)
                if candidate and is_open_item(candidate):
                    selected_item = candidate
                    selection_reason = "review-pack"
            if not selected_item and review_meta.handoff_ids:
                selected_item = select_first_open_handoff(review_meta.handoff_ids, handoffs)
                if selected_item:
                    selection_reason = "review-handoff"
            if not selected_item and active_ticket == ticket and active_work_item and not args.pick_next:
                selected_item = find_work_item(all_items, runtime.sanitize_scope_key(active_work_item))
                if selected_item:
                    if is_open_item(selected_item):
                        selection_reason = "active"
                    else:
                        selected_item = None
            if not selected_item:
                next3_refs = parse_next3_refs(sections.get("AIDD:NEXT_3", []))
                if next3_refs:
                    selected_item = select_first_open(next3_refs, all_items)
                    if selected_item:
                        selection_reason = "next3"
            if not selected_item and open_handoffs:
                selected_item = open_handoffs[0]
                selection_reason = "handoff"
    else:
        if args.pick_next:
            next3_refs = parse_next3_refs(sections.get("AIDD:NEXT_3", []))
            if next3_refs:
                selected_item = select_first_matching(next3_refs, all_items)
                if selected_item:
                    selection_reason = "next3"
        if not selected_item:
            if active_ticket == ticket and active_work_item:
                selected_item = find_work_item(all_items, runtime.sanitize_scope_key(active_work_item))
                if selected_item:
                    selection_reason = "active"
        if not selected_item:
            progress_ref = parse_progress_ref(sections.get("AIDD:PROGRESS_LOG", []))
            if progress_ref:
                selected_item = find_work_item(all_items, progress_ref.scope_key)
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

    if args.stage == "review" and not args.work_item and active_work_item:
        active_scope = runtime.sanitize_scope_key(active_work_item)
        if selected_item.scope_key != active_scope:
            message = "BLOCKED: review work item mismatch with active_work_item"
            reason = "review_work_item_mismatch"
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

    write_active_state(target, ticket=ticket, work_item=selected_item.work_item_key)

    output_dir = target / "reports" / "loops" / ticket

    prewarm_items: List[WorkItem] = []
    if args.stage == "implement":
        next3_refs = parse_next3_refs(sections.get("AIDD:NEXT_3", []))
        if next3_refs:
            for ref in next3_refs:
                candidate = find_work_item(all_items, ref.scope_key)
                if candidate and is_open_item(candidate):
                    prewarm_items.append(candidate)
    prewarm_map: Dict[str, WorkItem] = {selected_item.scope_key: selected_item}
    for item in prewarm_items:
        prewarm_map.setdefault(item.scope_key, item)

    selected_pack_path = None
    boundaries: Dict[str, List[str]] = {}
    commands_required: List[str] = []
    tests_required: List[str] = []
    updated_at = utc_timestamp()

    selected_reason_code = ""
    for item in prewarm_map.values():
        pack_path, item_boundaries, item_commands, item_tests, item_updated_at, item_reason_code = write_pack_for_item(
            root=target,
            output_dir=output_dir,
            ticket=ticket,
            work_item=item,
            context_allowed_paths=context_allowed_paths,
        )
        if item.scope_key == selected_item.scope_key:
            selected_pack_path = pack_path
            boundaries = item_boundaries
            commands_required = item_commands
            tests_required = item_tests
            updated_at = item_updated_at
            selected_reason_code = item_reason_code

    if selected_pack_path is None:
        raise ValueError("failed to generate loop pack for selected work item")

    rel_path = runtime.rel_path(selected_pack_path, target)

    payload = {
        "schema": "aidd.loop_pack.v1",
        "updated_at": updated_at,
        "ticket": ticket,
        "stage": args.stage,
        "work_item_id": selected_item.item_id,
        "work_item_key": selected_item.work_item_key,
        "scope_key": selected_item.scope_key,
        "selection": selection_reason,
        "path": rel_path,
        "boundaries": boundaries,
        "commands_required": commands_required,
        "tests_required": tests_required,
        "evidence_policy": "RLM-first",
    }
    if selected_reason_code:
        payload["reason_code"] = selected_reason_code

    if args.format:
        output = json.dumps(payload, ensure_ascii=False, indent=2) if args.format == "json" else "\n".join(dump_yaml(payload))
        print(output)
        print(f"[loop-pack] saved {rel_path} ({selected_item.work_item_key})", file=sys.stderr)
        return 0

    print(f"[loop-pack] saved {rel_path} ({selected_item.work_item_key})")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
