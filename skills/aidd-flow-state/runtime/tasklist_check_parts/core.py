#!/usr/bin/env python3
"""Validate and normalize tasklists."""

from __future__ import annotations

import argparse
import hashlib
import difflib
import json
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, List, Optional

from aidd_runtime import gates
from aidd_runtime import runtime
from aidd_runtime.feature_ids import resolve_aidd_root, resolve_identifiers


PLACEHOLDER_VALUES = {"", "...", "<...>", "tbd", "<tbd>", "todo", "<todo>"}
NONE_VALUES = {"none", "нет", "n/a", "na"}
SPEC_PLACEHOLDERS = {"none", "нет", "n/a", "na", "-", "missing"}
SPEC_REQUIRED_PATTERNS = [
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"\bui\b",
        r"\bux\b",
        r"\bui/ux\b",
        r"\bfrontend\b",
        r"\bfront[- ]end\b",
        r"/ui/",
        r"/ux/",
        r"/frontend/",
        r"/front-end/",
        r"\bweb\b",
        r"\bинтерфейс",
        r"\bэкран",
        r"\bстраниц",
        r"\bформа\b",
        r"\bдизайн\b",
        r"\bвизуал",
        r"\bмакет",
        r"\blayout\b",
        r"\bapi\b",
        r"\bendpoint\b",
        r"\brest\b",
        r"\bgrpc\b",
        r"\bgraphql\b",
        r"\bcontract\b",
        r"\bschema\b",
        r"\bmigration\b",
        r"\bdb\b",
        r"\bdatabase\b",
        r"\bdata\b",
        r"\btable\b",
        r"\bcolumn\b",
        r"\bконтракт\b",
        r"\bсхем",
        r"\bмиграц",
        r"\bбаз",
        r"\bданн",
        r"\bтаблиц",
        r"\bколонк",
        r"\be2e\b",
        r"\bend[- ]to[- ]end\b",
        r"\bstaging\b",
        r"\bstand\b",
        r"\bстенд\b",
    )
]

REQUIRED_SECTIONS = {
    "AIDD:CONTEXT_PACK",
    "AIDD:SPEC_PACK",
    "AIDD:TEST_STRATEGY",
    "AIDD:TEST_EXECUTION",
    "AIDD:ITERATIONS_FULL",
    "AIDD:NEXT_3",
    "AIDD:HANDOFF_INBOX",
    "AIDD:QA_TRACEABILITY",
    "AIDD:CHECKLIST",
    "AIDD:PROGRESS_LOG",
    "AIDD:HOW_TO_UPDATE",
}

PRIORITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3}
PRIORITY_VALUES = set(PRIORITY_ORDER)
HANDOFF_STATUS_VALUES = {"open", "done", "blocked"}
HANDOFF_SOURCE_VALUES = {"research", "review", "qa", "manual"}
ITERATION_STATE_VALUES = {"open", "done", "blocked"}
PROGRESS_SOURCES = {"implement", "review", "qa", "research", "normalize"}
PROGRESS_KINDS = {"iteration", "handoff"}
STRICT_STAGES = {"review", "qa"}

SECTION_HEADER_RE = re.compile(r"^##\s+(.+?)\s*$")
CHECKBOX_RE = re.compile(r"^\s*-\s*\[(?P<state>[ xX])\]\s+(?P<body>.+)$")
REF_RE = re.compile(r"\bref\s*:\s*([^\)]+)")
ID_RE = re.compile(r"\bid\s*:\s*([A-Za-z0-9_.:-]+)")
ITERATION_ID_RE = re.compile(r"\biteration_id\s*[:=]\s*([A-Za-z0-9_.:-]+)")
STATE_RE = re.compile(r"\bstate\s*:\s*([A-Za-z0-9_-]+)", re.IGNORECASE)
PARENT_ITERATION_RE = re.compile(r"\bparent_iteration_id\s*:\s*([A-Za-z0-9_.:-]+)", re.IGNORECASE)
PROGRESS_LINE_RE = re.compile(
    r"^\s*-\s*(?P<date>\d{4}-\d{2}-\d{2})\s+"
    r"source=(?P<source>[A-Za-z0-9_-]+)\s+"
    r"id=(?P<item_id>[A-Za-z0-9_.:-]+)\s+"
    r"kind=(?P<kind>[A-Za-z0-9_-]+)\s+"
    r"hash=(?P<hash>[A-Za-z0-9]+)"
    r"(?:\s+link=(?P<link>\S+))?\s+"
    r"msg=(?P<msg>.+)$"
)


@dataclass
class Section:
    title: str
    start: int
    end: int
    lines: List[str]


@dataclass
class Issue:
    severity: str
    message: str


@dataclass
class TasklistCheckResult:
    status: str
    message: str = ""
    details: List[str] | None = None
    warnings: List[str] | None = None

    def exit_code(self) -> int:
        return 0 if self.status in {"ok", "warn", "skip"} else 2


@dataclass
class IterationItem:
    item_id: str
    title: str
    state: str
    checkbox: str
    parent_id: str | None
    explicit_id: bool
    priority: str
    blocking: bool
    deps: List[str]
    locks: List[str]
    lines: List[str]


@dataclass
class HandoffItem:
    item_id: str
    title: str
    status: str
    checkbox: str
    priority: str
    blocking: bool
    source: str
    lines: List[str]


@dataclass
class WorkItem:
    kind: str
    item_id: str
    title: str
    priority: str
    blocking: bool
    order_key: tuple


@dataclass
class NormalizeResult:
    updated_text: str
    summary: List[str]
    changed: bool


def parse_args(argv: Iterable[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate tasklist readiness.")
    parser.add_argument("--ticket", default=None, help="Feature ticket (defaults to docs/.active.json).")
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
    parser.add_argument(
        "--fix",
        action="store_true",
        help="Normalize tasklist in place.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show changes without modifying files (requires --fix).",
    )
    return parser.parse_args(list(argv) if argv is not None else None)


def _tasklist_cache_path(root: Path) -> Path:
    return root / ".cache" / "tasklist.hash"


def _tasklist_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _load_tasklist_cache(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _write_tasklist_cache(
    path: Path,
    *,
    ticket: str,
    stage: str,
    hash_value: str,
    config_hash: str,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "ticket": ticket,
        "stage": stage,
        "hash": hash_value,
        "config_hash": config_hash,
        "updated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _config_fingerprint(path: Path) -> str:
    if not path.exists():
        return "missing"
    try:
        data = path.read_bytes()
    except OSError:
        return "error"
    return hashlib.sha256(data).hexdigest()


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def parse_front_matter(lines: List[str]) -> tuple[dict[str, str], int]:
    if not lines or lines[0].strip() != "---":
        return {}, 0
    end_idx = None
    for idx in range(1, len(lines)):
        if lines[idx].strip() == "---":
            end_idx = idx
            break
    if end_idx is None:
        return {}, 0
    front: dict[str, str] = {}
    for raw in lines[1:end_idx]:
        line = raw.strip()
        if not line or line.startswith("#") or ":" not in line:
            continue
        key, value = line.split(":", 1)
        front[key.strip()] = value.strip()
    return front, end_idx + 1


def parse_sections(lines: List[str]) -> tuple[List[Section], dict[str, List[Section]]]:
    sections: List[Section] = []
    for idx, line in enumerate(lines):
        match = SECTION_HEADER_RE.match(line)
        if not match:
            continue
        title = match.group(1).strip()
        if not title.startswith("AIDD:"):
            continue
        if sections:
            sections[-1].end = idx
        sections.append(Section(title=title, start=idx, end=len(lines), lines=[]))
    for section in sections:
        section.lines = lines[section.start:section.end]
    mapped: dict[str, List[Section]] = {}
    for section in sections:
        mapped.setdefault(section.title, []).append(section)
    return sections, mapped


def section_body(section: Section | None) -> List[str]:
    if not section:
        return []
    return section.lines[1:]


def extract_field_value(lines: List[str], field: str) -> str | None:
    pattern = re.compile(rf"^\s*(?:[-*]\s*)?{re.escape(field)}\s*:\s*(.*)$", re.IGNORECASE)
    for line in lines:
        match = pattern.match(line)
        if match:
            return match.group(1).strip()
    return None


def block_has_heading(lines: List[str], heading: str) -> bool:
    pattern = re.compile(rf"^\s*-\s*{re.escape(heading)}\s*:\s*(.*)$", re.IGNORECASE)
    for line in lines:
        if pattern.match(line):
            return True
    return False


def is_placeholder(value: str) -> bool:
    stripped = value.strip()
    lowered = stripped.lower()
    if lowered in PLACEHOLDER_VALUES:
        return True
    return stripped.startswith("<") and stripped.endswith(">")


def parse_inline_list(value: str) -> List[str]:
    raw = value.strip()
    if not raw:
        return []
    if raw.startswith("[") and raw.endswith("]"):
        raw = raw[1:-1].strip()
    if not raw:
        return []
    parts = raw.split(",") if "," in raw else raw.split()
    items = [part.strip() for part in parts if part.strip()]
    return [item for item in items if not is_placeholder(item)]


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
                if item and not is_placeholder(item):
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
                    if key and not is_placeholder(key) and not is_placeholder(value):
                        result[key] = value
        return result
    return {}


def normalize_dep_id(value: str) -> str:
    raw = value.strip()
    if not raw:
        return ""
    if "iteration_id=" in raw:
        return raw.split("iteration_id=", 1)[1].strip()
    if "id=" in raw:
        return raw.split("id=", 1)[1].strip()
    return raw


def parse_int(value: str | None) -> int | None:
    raw = str(value or "").strip()
    if not raw or is_placeholder(raw):
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def split_checkbox_blocks(lines: List[str]) -> List[List[str]]:
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


def extract_iteration_id(block: List[str]) -> str | None:
    for line in block:
        match = ITERATION_ID_RE.search(line)
        if match:
            return match.group(1).strip()
    header = block[0] if block else ""
    match = re.search(r"\bI\d+\b", header)
    return match.group(0) if match else None


def extract_handoff_id(block: List[str]) -> str | None:
    for line in block:
        match = ID_RE.search(line)
        if match:
            return match.group(1).strip()
    return None


def normalize_source(value: str | None) -> str:
    normalized = (value or "").strip().lower()
    if normalized == "reviewer":
        return "review"
    return normalized


def parse_parenthetical_fields(header: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    for group in re.findall(r"\(([^\)]+)\)", header):
        if ":" not in group:
            continue
        key, value = group.split(":", 1)
        key = key.strip().lower()
        fields[key] = value.strip()
    return fields


def split_iteration_blocks(lines: List[str]) -> List[List[str]]:
    blocks: List[List[str]] = []
    current: List[str] = []
    for line in lines:
        stripped = line.lstrip()
        if not stripped.startswith("-"):
            if current:
                current.append(line)
            continue
        if line != stripped:
            if current:
                current.append(line)
            continue
        is_checkbox = bool(CHECKBOX_RE.match(line))
        has_iteration = bool(ITERATION_ID_RE.search(line)) or bool(re.match(r"^-\s*I\d+\b", line))
        if is_checkbox or has_iteration:
            if current:
                blocks.append(current)
            current = [line]
            continue
        if current:
            current.append(line)
    if current:
        blocks.append(current)
    return blocks


def parse_iteration_items(section_lines: List[str]) -> List[IterationItem]:
    items: List[IterationItem] = []
    for block in split_iteration_blocks(section_lines):
        header = block[0].strip()
        checkbox_state = "unknown"
        checkbox_match = CHECKBOX_RE.match(header)
        if checkbox_match:
            checkbox_state = "done" if checkbox_match.group("state").lower() == "x" else "open"
        fields = parse_parenthetical_fields(header)
        iteration_id = extract_iteration_id(block) or ""
        explicit_id = any(ITERATION_ID_RE.search(line) for line in block)
        parent_id = None
        for line in block:
            parent_match = PARENT_ITERATION_RE.search(line)
            if parent_match:
                parent_id = parent_match.group(1).strip()
                break
        state_value = extract_field_value(block, "State")
        state = (state_value or "").strip().lower()
        if not state:
            state = ""
        title = header
        if checkbox_match:
            title = checkbox_match.group("body").strip()
        else:
            if title.startswith("-"):
                title = title.lstrip("-").strip()
        title = re.sub(r"\(iteration_id\s*[:=].*?\)", "", title, flags=re.IGNORECASE).strip()
        if iteration_id:
            title = re.sub(rf"^{re.escape(iteration_id)}\s*[:\-]\s*", "", title, flags=re.IGNORECASE).strip()
        priority = (fields.get("priority") or extract_field_value(block, "Priority") or "").strip().lower()
        blocking_raw = (fields.get("blocking") or extract_field_value(block, "Blocking") or "").strip().lower()
        blocking = blocking_raw == "true"
        deps = parse_inline_list(extract_field_value(block, "deps") or "")
        if not deps:
            deps = extract_list_field(block, "deps")
        locks = parse_inline_list(extract_field_value(block, "locks") or "")
        if not locks:
            locks = extract_list_field(block, "locks")
        deps = [normalize_dep_id(dep) for dep in deps if dep]
        items.append(
            IterationItem(
                item_id=iteration_id,
                title=title,
                state=state,
                checkbox=checkbox_state,
                parent_id=parent_id,
                explicit_id=explicit_id,
                priority=priority,
                blocking=blocking,
                deps=deps,
                locks=locks,
                lines=block,
            )
        )
    return items


def parse_handoff_items(section_lines: List[str]) -> List[HandoffItem]:
    parsed: List[HandoffItem] = []
    for block in split_checkbox_blocks(section_lines):
        header = block[0]
        checkbox_state = "unknown"
        match = CHECKBOX_RE.match(header)
        if match:
            checkbox_state = "done" if match.group("state").lower() == "x" else "open"
        title = match.group("body").strip() if match else header.strip()
        title = re.sub(r"\([^\)]*\)", "", title).strip()
        fields = parse_parenthetical_fields(header)
        item_id = fields.get("id") or extract_handoff_id(block) or ""
        priority = (fields.get("priority") or extract_field_value(block, "Priority") or "").strip().lower()
        blocking_raw = (fields.get("blocking") or extract_field_value(block, "Blocking") or "").strip().lower()
        blocking = blocking_raw == "true"
        source = normalize_source(extract_field_value(block, "source") or fields.get("source"))
        status = (extract_field_value(block, "Status") or "").strip().lower()
        if not status and checkbox_state in {"open", "done"}:
            status = checkbox_state
        parsed.append(
            HandoffItem(
                item_id=item_id,
                title=title,
                status=status,
                checkbox=checkbox_state,
                priority=priority,
                blocking=blocking,
                source=source,
                lines=block,
            )
        )
    return parsed


def parse_next3_items(section_lines: List[str]) -> List[List[str]]:
    return split_checkbox_blocks(section_lines)


def extract_ref_id(block: List[str]) -> tuple[str, str | None, bool]:
    ref_value = None
    for line in block:
        match = REF_RE.search(line)
        if match:
            ref_value = match.group(1).strip()
            break
    if ref_value:
        if "iteration_id=" in ref_value:
            return "iteration", ref_value.split("iteration_id=", 1)[1].strip(), True
        if "id=" in ref_value:
            return "handoff", ref_value.split("id=", 1)[1].strip(), True
    for line in block:
        match = ITERATION_ID_RE.search(line)
        if match:
            return "iteration", match.group(1).strip(), False
        match = ID_RE.search(line)
        if match:
            return "handoff", match.group(1).strip(), False
    return "", None, False


def progress_entries_from_lines(lines: List[str]) -> tuple[List[dict], List[str]]:
    entries: List[dict] = []
    invalid: List[str] = []
    for raw in lines:
        if not raw.strip().startswith("-"):
            continue
        stripped = raw.strip().lower()
        if stripped.startswith("- (empty)") or stripped.startswith("- ..."):
            continue
        match = PROGRESS_LINE_RE.match(raw)
        if not match:
            invalid.append(raw)
            continue
        info = match.groupdict()
        info["source"] = info["source"].lower()
        info["kind"] = info["kind"].lower()
        info["msg"] = info["msg"].strip()
        entries.append(info)
    return entries, invalid


def dedupe_progress(entries: List[dict]) -> List[dict]:
    seen = set()
    deduped: List[dict] = []
    for entry in entries:
        key = (entry.get("date"), entry.get("source"), entry.get("item_id"), entry.get("hash"))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(entry)
    return deduped


def progress_entry_line(entry: dict) -> str:
    parts = [
        f"- {entry['date']}",
        f"source={entry['source']}",
        f"id={entry['item_id']}",
        f"kind={entry['kind']}",
        f"hash={entry['hash']}",
    ]
    if entry.get("link"):
        parts.append(f"link={entry['link']}")
    msg = entry.get("msg") or ""
    if len(msg) > 200:
        msg = msg[:197] + "..."
    parts.append(f"msg={msg}")
    line = " ".join(parts)
    if len(line) > 240:
        line = line[:237] + "..."
    return line


def load_gate_config(path: Path) -> dict | None:
    if not path.is_file():
        return None
    try:
        data = gates.load_gates_config(path)
    except ValueError:
        return None
    if "tasklist_spec" not in data:
        return None
    section = data.get("tasklist_spec")
    if isinstance(section, bool):
        return {"enabled": section}
    return section if isinstance(section, dict) else None


def should_skip_gate(gate: dict | None, branch: str) -> tuple[bool, str]:
    if gate is None:
        return True, "gate config missing"
    enabled = bool(gate.get("enabled", True))
    if not enabled:
        return True, "gate disabled"
    if branch and gates.matches(gate.get("skip_branches"), branch):
        return True, "branch skipped"
    branches = gate.get("branches")
    if branch and branches and not gates.matches(branches, branch):
        return True, "branch not in allowlist"
    return False, ""


def severity_for_stage(stage: str, *, strict: bool = False) -> str:
    normalized = (stage or "").strip().lower()
    if strict or normalized in STRICT_STAGES:
        return "error"
    return "warn"


def resolve_stage(root: Path, context_pack: List[str]) -> str:
    value = runtime.read_active_stage(root)
    if value:
        return value.lower()
    stage_value = extract_field_value(context_pack, "Stage")
    return (stage_value or "").strip().lower()


def parse_plan_iteration_ids(root: Path, plan_path: Path) -> list[str]:
    try:
        text = plan_path.read_text(encoding="utf-8")
    except OSError:
        return []
    lines = text.splitlines()
    _, sections = parse_sections(lines)
    plan_section = sections.get("AIDD:ITERATIONS")
    if not plan_section:
        return []
    ids: list[str] = []
    for line in section_body(plan_section[0]):
        match = ITERATION_ID_RE.search(line)
        if match:
            ids.append(match.group(1).strip())
    return ids


def pick_open_state(checkbox_state: str, state_value: str) -> tuple[Optional[bool], str]:
    state = (state_value or "").strip().lower()
    if state and state not in ITERATION_STATE_VALUES:
        return None, state
    if checkbox_state == "done" or state == "done":
        return False, state
    if checkbox_state == "open" or state in {"open", "blocked"}:
        return True, state
    return None, state


def handoff_open_state(checkbox_state: str, status: str) -> tuple[Optional[bool], str]:
    status_value = (status or "").strip().lower()
    if status_value and status_value not in HANDOFF_STATUS_VALUES:
        return None, status_value
    if checkbox_state == "done" or status_value == "done":
        return False, status_value
    if checkbox_state == "open" or status_value in {"open", "blocked"}:
        return True, status_value
    return None, status_value


def next3_placeholder_present(lines: List[str]) -> bool:
    for line in lines:
        stripped = line.strip().lower()
        if stripped.startswith("- (none)") or "no pending" in stripped:
            return True
    return False


def extract_bullets(lines: List[str]) -> int:
    count = 0
    for line in lines:
        if re.match(r"^\s*-\s+", line):
            count += 1
    return count


def subsection_lines(section_lines: List[str], heading: str) -> List[str]:
    start = None
    for idx, line in enumerate(section_lines):
        if line.strip().lower() == heading.lower():
            start = idx + 1
            break
    if start is None:
        return []
    end = len(section_lines)
    for idx in range(start, len(section_lines)):
        if section_lines[idx].strip().startswith("### "):
            end = idx
            break
    return section_lines[start:end]


def collect_stacktrace_flags(lines: List[str]) -> bool:
    at_count = 0
    caused_count = 0
    in_fence = False
    fence_count = 0
    for line in lines:
        stripped = line.rstrip()
        if stripped.startswith("```"):
            in_fence = not in_fence
            if not in_fence:
                if fence_count > 20:
                    return True
                fence_count = 0
            continue
        if in_fence:
            fence_count += 1
            continue
        if re.match(r"^\s+at\s+", stripped):
            at_count += 1
            if at_count >= 5:
                return True
        else:
            at_count = 0
        if stripped.startswith("Caused by:"):
            caused_count += 1
            if caused_count >= 2:
                return True
        else:
            caused_count = 0
    return False


def large_code_fence_without_report(lines: List[str]) -> bool:
    in_fence = False
    fence_lines: List[int] = []
    start_idx = 0
    for idx, line in enumerate(lines):
        if line.strip().startswith("```"):
            if not in_fence:
                in_fence = True
                fence_lines = []
                start_idx = idx
            else:
                in_fence = False
                if len(fence_lines) > 20 and not find_report_link_near(lines, start_idx):
                    return True
            continue
        if in_fence:
            fence_lines.append(idx)
    return False


def find_report_link_near(lines: List[str], idx: int, window: int = 5) -> bool:
    start = max(0, idx - window)
    end = min(len(lines), idx + window + 1)
    for line in lines[start:end]:
        if "aidd/reports/" in line:
            return True
    return False


def parse_qa_traceability(section_lines: List[str]) -> dict[str, dict]:
    result: dict[str, dict] = {}
    for line in section_lines:
        match = re.search(r"\bAC-([A-Za-z0-9_-]+)\b", line)
        if not match:
            continue
        ac_id = match.group(1)
        status_match = re.search(r"\b(not[- ]met|not[- ]verified|met)\b", line, re.IGNORECASE)
        status = status_match.group(1).lower() if status_match else ""
        status = status.replace(" ", "-")
        evidence = ""
        if "→" in line:
            parts = [part.strip() for part in line.split("→")]
            if len(parts) >= 4:
                evidence = parts[-1]
        result.setdefault(ac_id, {"status": status, "evidence": []})
        if status:
            current = result[ac_id]["status"]
            order = {"met": 0, "not-verified": 1, "not-met": 2}
            if current in order and status in order:
                if order[status] > order[current]:
                    result[ac_id]["status"] = status
            else:
                result[ac_id]["status"] = status
        if evidence:
            result[ac_id]["evidence"].append(evidence)
    return result


def resolve_plan_path(root: Path, front: dict[str, str], ticket: str) -> Path:
    plan = front.get("Plan") or front.get("plan") or ""
    if plan:
        raw = Path(plan)
        if not raw.is_absolute():
            if raw.parts and raw.parts[0] == "aidd" and root.name == "aidd":
                return root / Path(*raw.parts[1:])
            return root / raw
        return raw
    return root / "docs" / "plan" / f"{ticket}.md"


def resolve_prd_path(root: Path, front: dict[str, str], ticket: str) -> Path:
    prd = front.get("PRD") or front.get("prd") or ""
    if prd:
        raw = Path(prd)
        if not raw.is_absolute():
            if raw.parts and raw.parts[0] == "aidd" and root.name == "aidd":
                return root / Path(*raw.parts[1:])
            return root / raw
        return raw
    return root / "docs" / "prd" / f"{ticket}.prd.md"


def resolve_spec_path(root: Path, front: dict[str, str], ticket: str) -> Path | None:
    spec = front.get("Spec") or front.get("spec") or ""
    if spec:
        lowered = spec.strip().lower()
        if is_placeholder(spec) or lowered in SPEC_PLACEHOLDERS:
            return None
        raw = Path(spec)
        if not raw.is_absolute():
            if raw.parts and raw.parts[0] == "aidd" and root.name == "aidd":
                return root / Path(*raw.parts[1:])
            return root / raw
        return raw
    return root / "docs" / "spec" / f"{ticket}.spec.yaml"


def rel_path(root: Path, path: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return str(path)


def extract_section_text(text: str, titles: Iterable[str]) -> str:
    lines = text.splitlines()
    _, section_map = parse_sections(lines)
    collected: List[str] = []
    for title in titles:
        for section in section_map.get(title, []):
            collected.extend(section_body(section))
    return "\n".join(collected) if collected else text


def mentions_spec_required(text: str) -> bool:
    if not text:
        return False
    return any(pattern.search(text) for pattern in SPEC_REQUIRED_PATTERNS)


def tasklist_path_for(root: Path, ticket: str) -> Path:
    return root / "docs" / "tasklist" / f"{ticket}.md"


def progress_archive_path(root: Path, ticket: str) -> Path:
    return root / "reports" / "progress" / f"{ticket}.log"


def deps_satisfied(
    deps: List[str],
    iteration_map: dict[str, IterationItem],
    handoff_map: dict[str, HandoffItem],
) -> bool:
    from aidd_runtime import tasklist_normalize as _tasklist_normalize

    return _tasklist_normalize.deps_satisfied(deps, iteration_map, handoff_map)


def unmet_deps(
    deps: List[str],
    iteration_map: dict[str, IterationItem],
    handoff_map: dict[str, HandoffItem],
) -> List[str]:
    from aidd_runtime import tasklist_normalize as _tasklist_normalize

    return _tasklist_normalize.unmet_deps(deps, iteration_map, handoff_map)


def build_open_items(
    iterations: List[IterationItem],
    handoff_items: List[HandoffItem],
    plan_order: List[str],
) -> tuple[List[WorkItem], dict[str, IterationItem], dict[str, HandoffItem]]:
    from aidd_runtime import tasklist_normalize as _tasklist_normalize

    return _tasklist_normalize.build_open_items(iterations, handoff_items, plan_order)


def build_next3_lines(open_items: List[WorkItem], preamble: List[str] | None = None) -> List[str]:
    from aidd_runtime import tasklist_normalize as _tasklist_normalize

    return _tasklist_normalize.build_next3_lines(open_items, preamble)


def normalize_progress_section(
    lines: List[str],
    ticket: str,
    root: Path,
    summary: List[str],
    *,
    dry_run: bool,
) -> List[str]:
    from aidd_runtime import tasklist_normalize as _tasklist_normalize

    return _tasklist_normalize.normalize_progress_section(lines, ticket, root, summary, dry_run=dry_run)


def normalize_qa_traceability(lines: List[str], summary: List[str]) -> List[str]:
    from aidd_runtime import tasklist_normalize as _tasklist_normalize

    return _tasklist_normalize.normalize_qa_traceability(lines, summary)


def normalize_handoff_section(sections: List[Section], summary: List[str]) -> List[str]:
    from aidd_runtime import tasklist_normalize as _tasklist_normalize

    return _tasklist_normalize.normalize_handoff_section(sections, summary)


def normalize_tasklist(
    root: Path,
    ticket: str,
    text: str,
    *,
    dry_run: bool = False,
) -> NormalizeResult:
    from aidd_runtime import tasklist_normalize as _tasklist_normalize

    return _tasklist_normalize.normalize_tasklist(root, ticket, text, dry_run=dry_run)


def check_tasklist_text(
    root: Path,
    ticket: str,
    text: str,
    *,
    normalize_fix_mode: bool = False,
) -> TasklistCheckResult:
    from aidd_runtime import tasklist_validate as _tasklist_validate

    return _tasklist_validate.check_tasklist_text(
        root,
        ticket,
        text,
        normalize_fix_mode=normalize_fix_mode,
    )

def check_tasklist(
    root: Path,
    ticket: str,
    *,
    normalize_fix_mode: bool = False,
) -> TasklistCheckResult:
    tasklist_path = tasklist_path_for(root, ticket)
    if not tasklist_path.exists():
        return TasklistCheckResult(status="error", message=f"tasklist not found: {tasklist_path}")
    text = read_text(tasklist_path)
    return check_tasklist_text(root, ticket, text, normalize_fix_mode=normalize_fix_mode)


def run_check(args: argparse.Namespace) -> int:
    root = resolve_aidd_root(Path.cwd())
    config_path = Path(args.config)
    if not config_path.is_absolute():
        config_path = root / config_path

    if args.fix and args.dry_run:
        pass

    if not args.fix:
        gate = load_gate_config(config_path)
        skip_gate, skip_reason = should_skip_gate(gate, args.branch or "")
        if skip_gate:
            if args.verbose:
                print(f"[tasklist-check] SKIP: {skip_reason}", file=sys.stderr)
            return 0

    identifiers = resolve_identifiers(root, ticket=args.ticket, slug_hint=args.slug_hint)
    ticket = (identifiers.resolved_ticket or "").strip()
    if not ticket:
        result = TasklistCheckResult(status="error", message="ticket not provided and docs/.active.json missing")
    else:
        tasklist_path = tasklist_path_for(root, ticket)
        if not tasklist_path.exists():
            result = TasklistCheckResult(status="error", message=f"tasklist not found: {tasklist_path}")
        else:
            tasklist_text = tasklist_path.read_text(encoding="utf-8")
            stage_value = runtime.read_active_stage(root)
            cache_path = _tasklist_cache_path(root)
            current_hash = _tasklist_hash(tasklist_text)
            config_hash = _config_fingerprint(config_path)

            if not args.fix and not args.dry_run:
                cache_payload = _load_tasklist_cache(cache_path)
                if (
                    cache_payload.get("ticket") == ticket
                    and cache_payload.get("stage") == stage_value
                    and cache_payload.get("hash") == current_hash
                    and cache_payload.get("config_hash") == config_hash
                ):
                    if not args.quiet_ok:
                        print("[tasklist-check] SKIP: cache hit (reason_code=cache_hit)", file=sys.stderr)
                    return 0

            if args.fix:
                original = tasklist_text
                normalized = normalize_tasklist(root, ticket, original, dry_run=args.dry_run)
                if args.dry_run:
                    diff = difflib.unified_diff(
                        original.splitlines(),
                        normalized.updated_text.splitlines(),
                        fromfile=str(tasklist_path),
                        tofile=str(tasklist_path),
                        lineterm="",
                    )
                    for line in diff:
                        print(line)
                    for line in normalized.summary:
                        print(f"[tasklist-check] {line}")
                    return 0
                if normalized.changed:
                    backup_dir = root / "reports" / "tasklist_backups" / ticket
                    backup_dir.mkdir(parents=True, exist_ok=True)
                    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
                    backup_path = backup_dir / f"{timestamp}.md"
                    backup_path.write_text(original, encoding="utf-8")
                    tasklist_path.write_text(normalized.updated_text, encoding="utf-8")
                    for line in normalized.summary:
                        print(f"[tasklist-check] {line}")
                    print(f"[tasklist-check] backup saved: {backup_path}")
                result = check_tasklist(root, ticket, normalize_fix_mode=True)
            else:
                result = check_tasklist_text(root, ticket, tasklist_text)

            if result.status in {"ok", "warn"}:
                updated_text = tasklist_path.read_text(encoding="utf-8")
                updated_hash = _tasklist_hash(updated_text)
                _write_tasklist_cache(
                    cache_path,
                    ticket=ticket,
                    stage=stage_value,
                    hash_value=updated_hash,
                    config_hash=config_hash,
                )
            if result.status == "error":
                if result.details:
                    for entry in result.details:
                        print(f"[tasklist-check] {entry}", file=sys.stderr)
                print(f"[tasklist-check] FAIL: {result.message}", file=sys.stderr)
                return result.exit_code()
            if result.status == "warn":
                if result.details:
                    for entry in result.details:
                        print(f"[tasklist-check] WARN: {entry}", file=sys.stderr)
            return result.exit_code()
    if result.status == "error":
        if result.details:
            for entry in result.details:
                print(f"[tasklist-check] {entry}", file=sys.stderr)
        print(f"[tasklist-check] FAIL: {result.message}", file=sys.stderr)
        return result.exit_code()

    if result.status == "warn":
        if result.details:
            for entry in result.details:
                print(f"[tasklist-check] WARN: {entry}", file=sys.stderr)
        return result.exit_code()

    if result.status == "ok" and not args.quiet_ok:
        print("[tasklist-check] OK: tasklist READY", file=sys.stderr)
    return result.exit_code()


def main(argv: Iterable[str] | None = None) -> int:
    args = parse_args(argv)
    return run_check(args)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
