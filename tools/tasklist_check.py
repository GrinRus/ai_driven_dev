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

from tools import gates
from tools import runtime
from tools.feature_ids import resolve_aidd_root, resolve_identifiers


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
    for dep_id in deps:
        dep_id = normalize_dep_id(dep_id)
        if not dep_id:
            continue
        if dep_id in iteration_map:
            open_state, _ = pick_open_state(iteration_map[dep_id].checkbox, iteration_map[dep_id].state)
            if open_state is None or open_state:
                return False
            continue
        if dep_id in handoff_map:
            open_state, _ = handoff_open_state(handoff_map[dep_id].checkbox, handoff_map[dep_id].status)
            if open_state is None or open_state:
                return False
            continue
        return False
    return True


def build_open_items(
    iterations: List[IterationItem],
    handoff_items: List[HandoffItem],
    plan_order: List[str],
) -> tuple[List[WorkItem], dict[str, IterationItem], dict[str, HandoffItem]]:
    items: List[WorkItem] = []
    iteration_map = {item.item_id: item for item in iterations if item.item_id}
    handoff_map = {item.item_id: item for item in handoff_items if item.item_id}
    plan_index = {item_id: idx for idx, item_id in enumerate(plan_order)}

    for iteration in iterations:
        if not iteration.item_id:
            continue
        open_state, _ = pick_open_state(iteration.checkbox, iteration.state)
        if open_state is None or not open_state:
            continue
        if iteration.deps and not deps_satisfied(iteration.deps, iteration_map, handoff_map):
            continue
        priority = iteration.priority or "medium"
        if priority not in PRIORITY_ORDER:
            priority = "medium"
        blocking = bool(iteration.blocking)
        order_key = (
            0 if blocking else 1,
            PRIORITY_ORDER.get(priority, 99),
            1,
            plan_index.get(iteration.item_id, 10_000),
            iteration.item_id,
        )
        items.append(
            WorkItem(
                kind="iteration",
                item_id=iteration.item_id,
                title=iteration.title,
                priority=priority,
                blocking=blocking,
                order_key=order_key,
            )
        )

    for handoff in handoff_items:
        if not handoff.item_id:
            continue
        open_state, _ = handoff_open_state(handoff.checkbox, handoff.status)
        if open_state is None or not open_state:
            continue
        priority = handoff.priority or "medium"
        blocking = bool(handoff.blocking)
        order_key = (
            0 if blocking else 1,
            PRIORITY_ORDER.get(priority, 99),
            0,
            handoff.item_id,
        )
        items.append(
            WorkItem(
                kind="handoff",
                item_id=handoff.item_id,
                title=handoff.title,
                priority=priority,
                blocking=blocking,
                order_key=order_key,
            )
        )

    items.sort(key=lambda item: item.order_key)
    return items, iteration_map, handoff_map


def build_next3_lines(
    open_items: List[WorkItem],
    preamble: List[str],
) -> List[str]:
    lines = ["## AIDD:NEXT_3", *preamble]
    if not open_items:
        lines.append("- (none)")
        return lines
    count = min(3, len(open_items))
    for item in open_items[:count]:
        if item.kind == "iteration":
            ref = f"ref: iteration_id={item.item_id}"
            lines.append(f"- [ ] {item.item_id}: {item.title} ({ref})")
        else:
            ref = f"ref: id={item.item_id}"
            lines.append(f"- [ ] {item.item_id}: {item.title} ({ref})")
    return lines


def normalize_progress_section(
    lines: List[str],
    ticket: str,
    root: Path,
    summary: List[str],
    *,
    dry_run: bool = False,
) -> List[str]:
    body = lines[1:]
    preamble: List[str] = []
    content: List[str] = []
    for idx, line in enumerate(body):
        if line.strip().startswith("-"):
            content = body[idx:]
            break
        preamble.append(line)
    if not content:
        content = []
    entries, invalid = progress_entries_from_lines(content)
    deduped = dedupe_progress(entries)
    overflow = []
    if len(deduped) > 20:
        overflow = deduped[:-20]
        deduped = deduped[-20:]
    archive_path = progress_archive_path(root, ticket)
    if overflow and not dry_run:
        archive_path.parent.mkdir(parents=True, exist_ok=True)
        with archive_path.open("a", encoding="utf-8") as fh:
            for entry in overflow:
                fh.write(progress_entry_line(entry) + "\n")
        summary.append(f"archived {len(overflow)} progress entries -> {archive_path}")
    elif overflow:
        summary.append(f"(dry-run) would archive {len(overflow)} progress entries -> {archive_path}")
    if invalid:
        summary.append(f"dropped {len(invalid)} invalid progress entries")
    new_lines = [lines[0], *preamble]
    for entry in deduped:
        new_lines.append(progress_entry_line(entry))
    if len(new_lines) == 1 + len(preamble):
        new_lines.append("- (empty)")
    return new_lines


def normalize_qa_traceability(lines: List[str], summary: List[str]) -> List[str]:
    body = lines[1:]
    preamble: List[str] = []
    content: List[str] = []
    for idx, line in enumerate(body):
        if line.strip().startswith("-"):
            content = body[idx:]
            break
        preamble.append(line)
    if not content:
        content = []
    parsed = parse_qa_traceability(content)
    merged: List[str] = [lines[0], *preamble]
    for ac_id in sorted(parsed.keys()):
        status = parsed[ac_id].get("status") or "met"
        evidence_list = parsed[ac_id].get("evidence") or []
        evidence = "; ".join(dict.fromkeys(evidence_list)) if evidence_list else ""
        arrow = "→"
        if evidence:
            merged.append(f"- AC-{ac_id} {arrow} <check> {arrow} {status} {arrow} {evidence}")
        else:
            merged.append(f"- AC-{ac_id} {arrow} <check> {arrow} {status} {arrow} <evidence>")
    if len(parsed) == 0:
        merged.append("- AC-1 → <check> → met → <evidence>")
    if len(parsed) > 0:
        summary.append(f"merged {len(parsed)} QA traceability entries")
    return merged


def normalize_handoff_section(sections: List[Section], summary: List[str]) -> List[str]:
    if not sections:
        return []
    base = sections[0]
    body: List[str] = []
    for section in sections:
        body.extend(section_body(section))
    manual_block: List[str] = []
    in_manual = False
    blocks_by_source: dict[str, List[str]] = {}
    block_order: List[str] = []
    current_source: str | None = None
    current_lines: List[str] = []
    outside_lines: List[str] = []

    def flush_block() -> None:
        nonlocal current_source, current_lines
        if current_source is None:
            return
        blocks_by_source.setdefault(current_source, []).extend(current_lines)
        if current_source not in block_order:
            block_order.append(current_source)
        current_source = None
        current_lines = []

    for line in body:
        if "<!--" in line and "handoff:" in line:
            match = re.search(r"handoff:([a-zA-Z0-9_-]+)", line)
            if match:
                source = normalize_source(match.group(1))
                if "start" in line:
                    if source == "manual":
                        in_manual = True
                        manual_block.append("<!-- handoff:manual start -->")
                        continue
                    flush_block()
                    current_source = source
                    continue
                if "end" in line:
                    if source == "manual":
                        manual_block.append("<!-- handoff:manual end -->")
                        in_manual = False
                        continue
                    flush_block()
                    continue
        if in_manual:
            manual_block.append(line)
            continue
        if current_source:
            current_lines.append(line)
        else:
            outside_lines.append(line)

    flush_block()

    def split_preamble_and_tasks(lines: List[str]) -> tuple[List[str], List[List[str]]]:
        preamble: List[str] = []
        tasks: List[List[str]] = []
        current: List[str] = []
        for line in lines:
            if CHECKBOX_RE.match(line):
                if current:
                    tasks.append(current)
                current = [line]
            elif current:
                current.append(line)
            else:
                preamble.append(line)
        if current:
            tasks.append(current)
        return preamble, tasks

    preamble, loose_tasks = split_preamble_and_tasks(outside_lines)

    manual_tasks: List[str] = []
    for block in loose_tasks:
        manual_tasks.extend(block)

    if manual_block:
        injected: List[str] = []
        inserted = False
        for line in manual_block:
            if "handoff:manual end" in line and manual_tasks and not inserted:
                injected.extend(manual_tasks)
                inserted = True
            injected.append(line)
        manual_block = injected
    else:
        manual_block = ["<!-- handoff:manual start -->", *manual_tasks, "<!-- handoff:manual end -->"]

    def clean_blocks(raw_lines: List[str], *, source: str) -> List[str]:
        task_blocks = split_checkbox_blocks(raw_lines)
        kept: List[List[str]] = []
        dedup: dict[str, List[str]] = {}
        deduped = 0
        source = normalize_source(source)

        for block in task_blocks:
            item_id = extract_handoff_id(block)
            block = [line.replace("source: reviewer", "source: review") for line in block]
            block = [line.replace("source: Reviewer", "source: review") for line in block]
            if not item_id:
                kept.append(block)
                continue
            if item_id in dedup:
                kept_block = dedup[item_id]
                if any("[x]" in line.lower() for line in block):
                    dedup[item_id] = block
                else:
                    dedup[item_id] = kept_block
                deduped += 1
            else:
                dedup[item_id] = block
        for block in dedup.values():
            kept.append(block)
        if deduped:
            summary.append(f"deduped {deduped} handoff task(s)")
        return [line for block in kept for line in block]

    merged_blocks: List[str] = [base.lines[0]]
    if preamble:
        merged_blocks.extend(preamble)
    if manual_block:
        merged_blocks.extend(manual_block)

    if not block_order and blocks_by_source:
        block_order = sorted(blocks_by_source.keys())

    for source in block_order:
        raw_lines = blocks_by_source.get(source, [])
        cleaned = clean_blocks(raw_lines, source=source)
        if not cleaned:
            continue
        merged_blocks.append(f"<!-- handoff:{source} start -->")
        merged_blocks.extend(cleaned)
        merged_blocks.append(f"<!-- handoff:{source} end -->")

    if len(merged_blocks) == 1:
        merged_blocks.append("<!-- handoff:manual start -->")
        merged_blocks.append("<!-- handoff:manual end -->")

    return merged_blocks


def normalize_tasklist(
    root: Path,
    ticket: str,
    text: str,
    *,
    dry_run: bool = False,
) -> NormalizeResult:
    lines = text.splitlines()
    front, _ = parse_front_matter(lines)
    sections, section_map = parse_sections(lines)
    summary: List[str] = []
    new_lines: List[str] = []
    consumed = 0

    def section_replacement(section: Section, all_sections: List[Section]) -> List[str]:
        title = section.title
        if title == "AIDD:HANDOFF_INBOX":
            return normalize_handoff_section(all_sections, summary)
        if title == "AIDD:PROGRESS_LOG":
            combined = [all_sections[0].lines[0]]
            for entry in all_sections:
                combined.extend(section_body(entry))
            return normalize_progress_section(combined, ticket, root, summary, dry_run=dry_run)
        if title == "AIDD:QA_TRACEABILITY":
            combined = [all_sections[0].lines[0]]
            for entry in all_sections:
                combined.extend(section_body(entry))
            return normalize_qa_traceability(combined, summary)
        return section.lines

    processed_titles: set[str] = set()
    for section in sections:
        if section.title in processed_titles:
            continue
        processed_titles.add(section.title)
        new_lines.extend(lines[consumed:section.start])
        section_group = section_map.get(section.title, [section])
        replacement = section_replacement(section, section_group)
        new_lines.extend(replacement)
        consumed = max(entry.end for entry in section_group)
    new_lines.extend(lines[consumed:])

    normalized_text = "\n".join(new_lines)
    if normalized_text and not normalized_text.endswith("\n"):
        normalized_text += "\n"

    sections, section_map = parse_sections(normalized_text.splitlines())
    next3_section = section_map.get("AIDD:NEXT_3", [])
    iter_section = section_map.get("AIDD:ITERATIONS_FULL", [])
    handoff_section = section_map.get("AIDD:HANDOFF_INBOX", [])

    if iter_section:
        iter_items = parse_iteration_items(section_body(iter_section[0]))
        handoff_items = parse_handoff_items(section_body(handoff_section[0]) if handoff_section else [])
        plan_ids = parse_plan_iteration_ids(root, resolve_plan_path(root, front, ticket))
        open_items, _, _ = build_open_items(iter_items, handoff_items, plan_ids)
        preamble = []
        if next3_section:
            for line in section_body(next3_section[0]):
                if line.strip().startswith("-"):
                    break
                preamble.append(line)
        next3_lines = build_next3_lines(open_items, preamble)

        lines = normalized_text.splitlines()
        new_lines = []
        consumed = 0
        inserted = False
        for section in sections:
            new_lines.extend(lines[consumed:section.start])
            if section.title == "AIDD:NEXT_3":
                new_lines.extend(next3_lines)
                inserted = True
            else:
                new_lines.extend(section.lines)
            consumed = section.end
            if section.title == "AIDD:ITERATIONS_FULL" and not next3_section:
                new_lines.extend(next3_lines)
                inserted = True
        new_lines.extend(lines[consumed:])
        if not inserted and not next3_section:
            new_lines.extend(next3_lines)
        normalized_text = "\n".join(new_lines)
        if normalized_text and not normalized_text.endswith("\n"):
            normalized_text += "\n"
        summary.append("rebuilt AIDD:NEXT_3")

    return NormalizeResult(updated_text=normalized_text, summary=summary, changed=normalized_text != text)


def check_tasklist_text(root: Path, ticket: str, text: str) -> TasklistCheckResult:
    lines = text.splitlines()
    front, body_start = parse_front_matter(lines)
    sections, section_map = parse_sections(lines)

    errors: List[str] = []
    warnings: List[str] = []

    def add_issue(severity: str, message: str) -> None:
        if severity == "error":
            errors.append(message)
        else:
            warnings.append(message)

    duplicate_titles = [title for title, items in section_map.items() if len(items) > 1]
    if duplicate_titles:
        add_issue(
            "error",
            f"duplicate AIDD sections: {', '.join(sorted(duplicate_titles))} "
            "(run tasklist-check --fix)",
        )

    for title in REQUIRED_SECTIONS:
        if title not in section_map:
            add_issue("error", f"missing section: ## {title}")

    context_pack = section_body(section_map.get("AIDD:CONTEXT_PACK", [None])[0]) if section_map.get("AIDD:CONTEXT_PACK") else []
    stage = resolve_stage(root, context_pack)

    front_status = (front.get("Status") or front.get("status") or "").strip().upper()
    context_status = (extract_field_value(context_pack, "Status") or "").strip().upper()
    if front_status and context_status and front_status != context_status:
        add_issue("error", f"Status mismatch (front-matter={front_status}, CONTEXT_PACK={context_status})")
    if not front_status:
        add_issue("error", "missing front-matter Status")
    if front_status and not context_status:
        add_issue("error", "missing CONTEXT_PACK Status")

    test_execution = section_body(section_map.get("AIDD:TEST_EXECUTION", [None])[0]) if section_map.get("AIDD:TEST_EXECUTION") else []
    for field in ("profile", "tasks", "filters", "when", "reason"):
        if not extract_field_value(test_execution, field):
            add_issue("error", f"AIDD:TEST_EXECUTION missing {field}")

    iterations_section = section_map.get("AIDD:ITERATIONS_FULL")
    iter_items = parse_iteration_items(section_body(iterations_section[0])) if iterations_section else []
    if not iter_items:
        add_issue("error", "AIDD:ITERATIONS_FULL has no iterations")

    handoff_section = section_map.get("AIDD:HANDOFF_INBOX")
    handoff_items = parse_handoff_items(section_body(handoff_section[0]) if handoff_section else [])

    for iteration in iter_items:
        if not iteration.item_id:
            continue
        steps = extract_list_field(iteration.lines, "Steps")
        steps_count = len(steps)
        if steps_count == 0:
            add_issue("warn", f"iteration {iteration.item_id} missing Steps")
        elif steps_count < 3:
            add_issue("warn", f"iteration {iteration.item_id} has {steps_count} steps (<3)")
        elif steps_count > 7:
            add_issue("warn", f"iteration {iteration.item_id} has {steps_count} steps (>7)")

        expected_paths = extract_list_field(iteration.lines, "Expected paths")
        if not expected_paths:
            add_issue("warn", f"iteration {iteration.item_id} missing Expected paths")
        elif len(expected_paths) > 3:
            add_issue("warn", f"iteration {iteration.item_id} has {len(expected_paths)} expected paths (>3)")

        size_budget = extract_mapping_field(iteration.lines, "Size budget")
        if not size_budget:
            add_issue("warn", f"iteration {iteration.item_id} missing Size budget")
        else:
            normalized_budget = {
                str(key).strip().lower().replace("-", "_"): str(value).strip()
                for key, value in size_budget.items()
            }
            max_files = parse_int(normalized_budget.get("max_files"))
            max_loc = parse_int(normalized_budget.get("max_loc"))
            if max_files is None:
                add_issue("warn", f"iteration {iteration.item_id} Size budget missing max_files")
            elif max_files < 3 or max_files > 8:
                add_issue("warn", f"iteration {iteration.item_id} max_files={max_files} outside 3-8")
            if max_loc is None:
                add_issue("warn", f"iteration {iteration.item_id} Size budget missing max_loc")
            elif max_loc < 80 or max_loc > 400:
                add_issue("warn", f"iteration {iteration.item_id} max_loc={max_loc} outside 80-400")

    plan_path = resolve_plan_path(root, front, ticket)
    prd_path = resolve_prd_path(root, front, ticket)
    spec_path = resolve_spec_path(root, front, ticket)
    spec_hint_path = spec_path or (root / "docs" / "spec" / f"{ticket}.spec.yaml")
    plan_ids: List[str] = []
    if plan_path.exists():
        plan_ids = parse_plan_iteration_ids(root, plan_path)
        if not plan_ids:
            add_issue(severity_for_stage(stage), "AIDD:ITERATIONS missing iteration_id")
    else:
        add_issue(severity_for_stage(stage), f"plan not found: {plan_path}")

    if (plan_path.exists() or prd_path.exists()) and not (spec_path and spec_path.exists()):
        plan_text = read_text(plan_path) if plan_path.exists() else ""
        prd_text = read_text(prd_path) if prd_path.exists() else ""
        plan_mentions_ui = mentions_spec_required(
            extract_section_text(
                plan_text,
                ("AIDD:FILES_TOUCHED", "AIDD:ITERATIONS", "AIDD:DESIGN", "AIDD:TEST_STRATEGY"),
            )
        )
        prd_mentions_ui = mentions_spec_required(
            extract_section_text(
                prd_text,
                ("AIDD:ACCEPTANCE", "AIDD:GOALS", "AIDD:NON_GOALS", "AIDD:ROLL_OUT"),
            )
        )
        if plan_mentions_ui or prd_mentions_ui:
            sources = []
            if plan_mentions_ui:
                sources.append("plan")
            if prd_mentions_ui:
                sources.append("prd")
            source_label = ", ".join(sources)
            add_issue(
                "error",
                "spec required for UI/UX/frontend or API/DATA/E2E changes "
                f"(detected in {source_label}); missing {rel_path(root, spec_hint_path)}. "
                "Run /feature-dev-aidd:spec-interview.",
            )

    iteration_ids = [item.item_id for item in iter_items if item.item_id]
    if plan_ids:
        missing_from_tasklist = sorted(set(plan_ids) - set(iteration_ids))
        if missing_from_tasklist:
            add_issue("error", f"AIDD:ITERATIONS_FULL missing iteration_id(s): {', '.join(missing_from_tasklist)}")
        for iteration in iter_items:
            if not iteration.item_id:
                add_issue(severity_for_stage(stage), "iteration missing iteration_id")
                continue
            if iteration.item_id not in plan_ids:
                if not iteration.parent_id:
                    add_issue(severity_for_stage(stage), f"iteration_id {iteration.item_id} not in plan and missing parent_iteration_id")

    open_items, iteration_map, handoff_map = build_open_items(iter_items, handoff_items, plan_ids)
    open_ids = {item.item_id for item in open_items}

    for iteration in iter_items:
        if not iteration.item_id:
            continue
        if iteration.item_id in iteration.deps:
            add_issue(severity_for_stage(stage), f"iteration {iteration.item_id} depends on itself")
        unknown_deps = [
            dep for dep in iteration.deps if dep and dep not in iteration_map and dep not in handoff_map
        ]
        if unknown_deps:
            add_issue(
                severity_for_stage(stage),
                f"iteration {iteration.item_id} has unknown deps: {', '.join(sorted(unknown_deps))}",
            )

    next3_section = section_map.get("AIDD:NEXT_3")
    next3_lines = section_body(next3_section[0]) if next3_section else []
    next3_blocks = parse_next3_items(next3_lines)

    placeholder = next3_placeholder_present(next3_lines)
    expected = min(3, len(open_items)) if open_items else 0
    if open_items:
        if len(next3_blocks) != expected:
            add_issue("error", f"AIDD:NEXT_3 has {len(next3_blocks)} items, expected {expected}")
        if placeholder:
            add_issue("error", "AIDD:NEXT_3 contains placeholder with open items")
    else:
        if next3_blocks:
            add_issue("error", "AIDD:NEXT_3 should not contain checkboxes when no open items")
        if not placeholder:
            add_issue("error", "AIDD:NEXT_3 missing (none) placeholder")

    next3_ids: List[str] = []
    next3_order_keys: List[tuple] = []
    for block in next3_blocks:
        header = block[0].lower()
        if "[x]" in header:
            add_issue("error", "AIDD:NEXT_3 contains [x]")
        kind, ref_id, has_ref = extract_ref_id(block)
        if not ref_id:
            add_issue(severity_for_stage(stage), "AIDD:NEXT_3 item missing ref/id")
            continue
        if not has_ref:
            add_issue(severity_for_stage(stage), "AIDD:NEXT_3 item missing ref:")
        next3_ids.append(ref_id)
        if ref_id not in open_ids:
            add_issue("error", f"AIDD:NEXT_3 item {ref_id} is not open")
        if ref_id in iteration_map:
            item = iteration_map[ref_id]
            if item.deps and not deps_satisfied(item.deps, iteration_map, handoff_map):
                add_issue("error", f"AIDD:NEXT_3 item {ref_id} has unmet deps")
            priority = item.priority or "medium"
            if priority not in PRIORITY_ORDER:
                priority = "medium"
            blocking = bool(item.blocking)
            order_key = (
                0 if blocking else 1,
                PRIORITY_ORDER.get(priority, 99),
                1,
                plan_ids.index(ref_id) if ref_id in plan_ids else 10_000,
                ref_id,
            )
            next3_order_keys.append(order_key)
            if not extract_field_value(item.lines, "DoD"):
                add_issue("error", f"iteration {ref_id} missing DoD")
            if not block_has_heading(item.lines, "Boundaries"):
                add_issue("error", f"iteration {ref_id} missing Boundaries")
            if not block_has_heading(item.lines, "Tests"):
                add_issue("error", f"iteration {ref_id} missing Tests")
        elif ref_id in handoff_map:
            item = handoff_map[ref_id]
            priority = item.priority or "medium"
            order_key = (
                0 if item.blocking else 1,
                PRIORITY_ORDER.get(priority, 99),
                0,
                ref_id,
            )
            next3_order_keys.append(order_key)
            if not extract_field_value(item.lines, "DoD"):
                add_issue("error", f"handoff {ref_id} missing DoD")
            if not block_has_heading(item.lines, "Boundaries"):
                add_issue("error", f"handoff {ref_id} missing Boundaries")
            if not block_has_heading(item.lines, "Tests"):
                add_issue("error", f"handoff {ref_id} missing Tests")
        else:
            add_issue("error", f"AIDD:NEXT_3 references unknown id {ref_id}")

    if len(next3_ids) != len(set(next3_ids)):
        add_issue("error", "AIDD:NEXT_3 has duplicate ids")

    if open_items and len(next3_ids) == expected:
        expected_ids = [item.item_id for item in open_items[:expected]]
        if next3_ids != expected_ids:
            add_issue(severity_for_stage(stage), "AIDD:NEXT_3 does not match top open items")

    sorted_keys = sorted(next3_order_keys)
    if next3_order_keys and next3_order_keys != sorted_keys:
        add_issue(severity_for_stage(stage), "AIDD:NEXT_3 is not sorted")

    qa_trace = section_body(section_map.get("AIDD:QA_TRACEABILITY", [None])[0]) if section_map.get("AIDD:QA_TRACEABILITY") else []
    qa_data = parse_qa_traceability(qa_trace)
    has_not_met = any(value.get("status") == "not-met" for value in qa_data.values())
    if front_status == "READY" and has_not_met:
        add_issue("error", "Status READY with QA_TRACEABILITY NOT MET")

    checklist_section = section_body(section_map.get("AIDD:CHECKLIST", [None])[0]) if section_map.get("AIDD:CHECKLIST") else []
    qa_checklist_lines = []
    if checklist_section:
        qa_checklist_lines = subsection_lines(checklist_section, "### AIDD:CHECKLIST_QA")
        if not qa_checklist_lines:
            qa_checklist_lines = subsection_lines(checklist_section, "### QA")
    if has_not_met and qa_checklist_lines:
        for line in qa_checklist_lines:
            if "[x]" in line.lower() and "accept" in line.lower():
                add_issue("error", "QA checklist marks acceptance verified while NOT MET")
                break

    if has_not_met:
        for line in lines:
            lower = line.lower()
            if "pass" in lower and "0 findings" in lower:
                add_issue("error", "keyword PASS/0 findings present while NOT MET")
                break
            if "ready for deploy" in lower:
                add_issue("error", "keyword ready for deploy present while NOT MET")
                break

    # enum validation
    for iteration in iter_items:
        if iteration.state and iteration.state not in ITERATION_STATE_VALUES:
            add_issue(severity_for_stage(stage), f"iteration {iteration.item_id or '?'} has invalid State={iteration.state}")
        if iteration.priority and iteration.priority not in PRIORITY_VALUES:
            add_issue(
                severity_for_stage(stage),
                f"iteration {iteration.item_id or '?'} invalid Priority={iteration.priority}",
            )
        if iteration.item_id and not iteration.explicit_id:
            add_issue(severity_for_stage(stage), f"iteration {iteration.item_id} missing explicit iteration_id")
        open_state, state = pick_open_state(iteration.checkbox, iteration.state)
        if open_state is None and iteration.item_id:
            add_issue(
                severity_for_stage(stage),
                f"iteration {iteration.item_id} missing open/done state (run tasklist-check --fix)",
            )

    for handoff in handoff_items:
        if not handoff.item_id:
            add_issue(severity_for_stage(stage), "handoff task missing id")
            continue
        if handoff.source and handoff.source not in HANDOFF_SOURCE_VALUES:
            add_issue(severity_for_stage(stage), f"handoff {handoff.item_id} invalid source={handoff.source}")
        if handoff.item_id and not handoff.source:
            add_issue(severity_for_stage(stage), f"handoff {handoff.item_id} missing source")
        if handoff.priority and handoff.priority not in PRIORITY_VALUES:
            add_issue(severity_for_stage(stage), f"handoff {handoff.item_id} invalid Priority={handoff.priority}")
        if handoff.item_id and not handoff.priority:
            add_issue(severity_for_stage(stage), f"handoff {handoff.item_id} missing Priority")
        if handoff.status and handoff.status not in HANDOFF_STATUS_VALUES:
            add_issue(severity_for_stage(stage), f"handoff {handoff.item_id} invalid Status={handoff.status}")
        if handoff.item_id and not handoff.status:
            add_issue(severity_for_stage(stage), f"handoff {handoff.item_id} missing Status")
        if handoff.checkbox in {"open", "done"} and handoff.status:
            if handoff.checkbox == "done" and handoff.status != "done":
                add_issue(severity_for_stage(stage), f"handoff {handoff.item_id} checkbox/status mismatch")
            if handoff.checkbox == "open" and handoff.status == "done":
                add_issue(severity_for_stage(stage), f"handoff {handoff.item_id} checkbox/status mismatch")
        open_state, status = handoff_open_state(handoff.checkbox, handoff.status)
        if open_state is None and handoff.item_id:
            add_issue(
                severity_for_stage(stage),
                f"handoff {handoff.item_id} missing open/done state (run tasklist-check --fix)",
            )

    # progress log validation
    progress_section = section_body(section_map.get("AIDD:PROGRESS_LOG", [None])[0]) if section_map.get("AIDD:PROGRESS_LOG") else []
    progress_entries, invalid_progress = progress_entries_from_lines(progress_section)
    if invalid_progress:
        add_issue(severity_for_stage(stage), "invalid PROGRESS_LOG format")
    for line in progress_section:
        if line.strip().startswith("-") and len(line) > 240:
            add_issue(severity_for_stage(stage), "PROGRESS_LOG entry exceeds 240 chars")
            break
    for entry in progress_entries:
        if entry.get("source") not in PROGRESS_SOURCES:
            add_issue(severity_for_stage(stage), f"PROGRESS_LOG invalid source={entry.get('source')}")
        if entry.get("kind") not in PROGRESS_KINDS:
            add_issue(severity_for_stage(stage), f"PROGRESS_LOG invalid kind={entry.get('kind')}")
        if stage in STRICT_STAGES and not entry.get("link"):
            add_issue("error", "PROGRESS_LOG entry missing link in review/qa stage")
        msg = entry.get("msg", "")
        if "\n" in msg or '"' in msg:
            add_issue(severity_for_stage(stage), "PROGRESS_LOG msg must be single-line without quotes")

    # evidence for completed items
    progress_ids = {entry.get("item_id") for entry in progress_entries}
    archive_ids = set()
    archive_path = progress_archive_path(root, ticket)
    if archive_path.exists():
        archive_lines = archive_path.read_text(encoding="utf-8").splitlines()
        archive_entries, _ = progress_entries_from_lines(archive_lines)
        archive_ids = {entry.get("item_id") for entry in archive_entries}
    evidence_ids = progress_ids | archive_ids

    def block_has_link(block: List[str]) -> bool:
        for line in block:
            if "link:" in line or "link=" in line or "aidd/reports/" in line:
                return True
        return False

    for iteration in iter_items:
        if iteration.checkbox != "done":
            continue
        if iteration.item_id and iteration.item_id not in evidence_ids and not block_has_link(iteration.lines):
            add_issue(severity_for_stage(stage), f"iteration {iteration.item_id} marked done without evidence")
    for handoff in handoff_items:
        if handoff.checkbox != "done":
            continue
        if handoff.item_id and handoff.item_id not in evidence_ids and not block_has_link(handoff.lines):
            add_issue(severity_for_stage(stage), f"handoff {handoff.item_id} marked done without evidence")

    # test failures
    slug_hint = runtime.read_active_slug(root) or None
    gates_cfg = runtime.load_gates_config(root)
    reviewer_cfg = gates_cfg.get("reviewer") if isinstance(gates_cfg, dict) else {}
    if not isinstance(reviewer_cfg, dict):
        reviewer_cfg = {}
    reviewer_template = str(
        reviewer_cfg.get("tests_marker")
        or reviewer_cfg.get("marker")
        or "aidd/reports/reviewer/{ticket}/{scope_key}.tests.json"
    )
    work_item_key = runtime.read_active_work_item(root)
    scope_key = runtime.resolve_scope_key(work_item_key, ticket)
    try:
        reviewer_marker = runtime.reviewer_marker_path(
            root,
            reviewer_template,
            ticket,
            slug_hint,
            scope_key=scope_key,
        )
    except Exception:
        reviewer_marker = root / "reports" / "reviewer" / ticket / f"{scope_key}.tests.json"
    tests_required = False
    tests_optional = False
    if reviewer_marker.exists():
        try:
            payload = json.loads(reviewer_marker.read_text(encoding="utf-8"))
        except Exception:
            payload = {}
        marker = str(payload.get("tests") or "").strip().lower()
        if marker == "required":
            tests_required = True
        elif marker == "optional":
            tests_optional = True
    if stage == "qa":
        tests_required = True

    test_failure = False
    for line in test_execution:
        lower = line.lower()
        if re.search(r"\b(result|status|summary)\s*:\s*(fail|failed|blocked|error|multiple issues)", lower):
            test_failure = True
            break
        if "compilation" in lower and "error" in lower:
            test_failure = True
            break
    if test_failure:
        if tests_required:
            add_issue("error", "test failures present with tests required")
        elif tests_optional:
            add_issue(severity_for_stage(stage), "test failures present with optional tests")

    # budgets
    if context_pack:
        tldr_lines = subsection_lines(context_pack, "### TL;DR")
        if extract_bullets(tldr_lines) > 12:
            add_issue(severity_for_stage(stage), "CONTEXT_PACK TL;DR exceeds 12 bullets")
        blockers = subsection_lines(context_pack, "### Blockers summary")
        if not blockers:
            blockers = subsection_lines(context_pack, "### Blockers summary (handoff)")
        blockers_count = sum(1 for line in blockers if line.strip())
        if blockers_count > 8:
            add_issue(severity_for_stage(stage), "CONTEXT_PACK Blockers summary exceeds 8 lines")

    for block in next3_blocks:
        if len(block) > 12:
            add_issue(severity_for_stage(stage), "AIDD:NEXT_3 item exceeds 12 lines")
            break

    for block in split_checkbox_blocks(section_body(handoff_section[0]) if handoff_section else []):
        if len(block) > 20:
            add_issue(severity_for_stage(stage), "HANDOFF_INBOX item exceeds 20 lines")
            break

    total_lines = len(lines)
    total_chars = len(text)
    if total_lines > 2000 or total_chars > 200_000:
        add_issue("error", "tasklist size exceeds hard limits")
    elif total_lines > 800:
        add_issue(severity_for_stage(stage), "tasklist size exceeds soft limit")

    if collect_stacktrace_flags(lines):
        for idx, line in enumerate(lines):
            if re.match(r"^\s+at\s+", line) or line.strip().startswith("Caused by:"):
                if not find_report_link_near(lines, idx):
                    add_issue("error", "stacktrace-like output without report link")
                    break
    if large_code_fence_without_report(lines):
        add_issue("error", "large code fence without report link")

    if errors:
        return TasklistCheckResult(status="error", message="tasklist check failed", details=errors, warnings=warnings)
    if warnings:
        return TasklistCheckResult(status="warn", message="tasklist check warning", details=warnings)
    return TasklistCheckResult(status="ok", message="tasklist ready")


def check_tasklist(root: Path, ticket: str) -> TasklistCheckResult:
    tasklist_path = tasklist_path_for(root, ticket)
    if not tasklist_path.exists():
        return TasklistCheckResult(status="error", message=f"tasklist not found: {tasklist_path}")
    text = read_text(tasklist_path)
    return check_tasklist_text(root, ticket, text)


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
                result = check_tasklist(root, ticket)
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
