#!/usr/bin/env python3
"""Deterministic DocOps operations for loop stages."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import List, Tuple

from aidd_runtime import runtime
from aidd_runtime.tasklist_check import (
    CHECKBOX_RE,
    build_open_items,
    build_next3_lines,
    dedupe_progress,
    parse_front_matter,
    parse_handoff_items,
    parse_iteration_items,
    parse_plan_iteration_ids,
    parse_sections,
    progress_entries_from_lines,
    progress_entry_line,
    resolve_plan_path,
    section_body,
)


@dataclass
class DocOpsResult:
    changed: bool
    message: str
    error: bool = False


def _ensure_trailing_newline(text: str) -> str:
    if text and not text.endswith("\n"):
        return text + "\n"
    return text


def _replace_section_lines(lines: List[str], section_start: int, section_end: int, new_lines: List[str]) -> List[str]:
    return lines[:section_start] + new_lines + lines[section_end:]


def _mark_checkbox_done(lines: List[str], item_id: str, *, kind: str) -> Tuple[List[str], str]:
    pattern = None
    if kind == "iteration":
        pattern = re.compile(
            rf"^(?P<prefix>\s*-\s*\[)(?P<state>[ xX])(?P<suffix>\]\s+.*\biteration_id\s*[:=]\s*{re.escape(item_id)}\b.*)$",
            re.IGNORECASE,
        )
        fallback = re.compile(
            rf"^(?P<prefix>\s*-\s*\[)(?P<state>[ xX])(?P<suffix>\]\s+{re.escape(item_id)}\b.*)$",
            re.IGNORECASE,
        )
    else:
        pattern = re.compile(
            rf"^(?P<prefix>\s*-\s*\[)(?P<state>[ xX])(?P<suffix>\]\s+.*\bid\s*:\s*{re.escape(item_id)}\b.*)$",
            re.IGNORECASE,
        )
        fallback = re.compile(
            rf"^(?P<prefix>\s*-\s*\[)(?P<state>[ xX])(?P<suffix>\]\s+{re.escape(item_id)}\b.*)$",
            re.IGNORECASE,
        )

    found = False
    new_lines = list(lines)
    for idx, line in enumerate(lines):
        match = pattern.match(line) if pattern else None
        if not match:
            match = fallback.match(line) if fallback else None
        if not match:
            continue
        found = True
        state = match.group("state")
        if state.lower() == "x":
            return new_lines, "already_done"
        new_lines[idx] = f"{match.group('prefix')}x{match.group('suffix')}"
        # update optional State field inside the same block
        for j in range(idx + 1, len(new_lines)):
            if j != idx and CHECKBOX_RE.match(new_lines[j]):
                break
            if re.match(r"^\s*-?\s*State\s*:\s*", new_lines[j], re.IGNORECASE):
                new_lines[j] = re.sub(r"(^\s*-?\s*State\s*:)\s*.*$", r"\1 done", new_lines[j], flags=re.IGNORECASE)
                break
        return new_lines, "changed"
    if not found:
        return new_lines, "not_found"
    return new_lines, "unchanged"


def tasklist_set_iteration_done(root: Path, ticket: str, item_id: str, *, kind: str = "iteration") -> DocOpsResult:
    tasklist_path = root / "docs" / "tasklist" / f"{ticket}.md"
    if not tasklist_path.exists():
        return DocOpsResult(False, f"tasklist missing: {runtime.rel_path(tasklist_path, root)}", error=True)
    text = tasklist_path.read_text(encoding="utf-8")
    lines = text.splitlines()
    sections, section_map = parse_sections(lines)

    title = "AIDD:ITERATIONS_FULL" if kind == "iteration" else "AIDD:HANDOFF_INBOX"
    section = section_map.get(title, [])
    if not section:
        return DocOpsResult(False, f"missing section: {title}", error=True)

    entry = section[0]
    updated_section, status = _mark_checkbox_done(entry.lines, item_id, kind=kind)
    if status == "already_done":
        return DocOpsResult(False, f"item already done: {item_id}")
    if status == "not_found":
        return DocOpsResult(False, f"item not found: {item_id}", error=True)

    updated_lines = _replace_section_lines(lines, entry.start, entry.end, updated_section)
    tasklist_path.write_text(_ensure_trailing_newline("\n".join(updated_lines)), encoding="utf-8")
    return DocOpsResult(True, f"marked {kind} {item_id} done")


def tasklist_append_progress_log(root: Path, ticket: str, entry: dict) -> DocOpsResult:
    tasklist_path = root / "docs" / "tasklist" / f"{ticket}.md"
    if not tasklist_path.exists():
        return DocOpsResult(False, f"tasklist missing: {runtime.rel_path(tasklist_path, root)}", error=True)
    text = tasklist_path.read_text(encoding="utf-8")
    lines = text.splitlines()
    sections, section_map = parse_sections(lines)
    section = section_map.get("AIDD:PROGRESS_LOG", [])
    if not section:
        return DocOpsResult(False, "missing section: AIDD:PROGRESS_LOG", error=True)

    entry_key = (entry.get("date"), entry.get("source"), entry.get("item_id"), entry.get("hash"))

    block = section[0]
    body = section_body(block)
    preamble: List[str] = []
    content: List[str] = []
    for idx, line in enumerate(body):
        if line.strip().startswith("-"):
            content = body[idx:]
            break
        preamble.append(line)
    entries, _ = progress_entries_from_lines(content)
    for existing in entries:
        if (existing.get("date"), existing.get("source"), existing.get("item_id"), existing.get("hash")) == entry_key:
            return DocOpsResult(False, "progress entry already present")

    entries.append(entry)
    deduped = dedupe_progress(entries)
    new_block = [block.lines[0], *preamble]
    if deduped:
        for item in deduped:
            new_block.append(progress_entry_line(item))
    else:
        new_block.append("- (empty)")

    updated_lines = _replace_section_lines(lines, block.start, block.end, new_block)
    tasklist_path.write_text(_ensure_trailing_newline("\n".join(updated_lines)), encoding="utf-8")
    return DocOpsResult(True, "progress log appended")


def tasklist_next3_recompute(root: Path, ticket: str) -> DocOpsResult:
    tasklist_path = root / "docs" / "tasklist" / f"{ticket}.md"
    if not tasklist_path.exists():
        return DocOpsResult(False, f"tasklist missing: {runtime.rel_path(tasklist_path, root)}", error=True)
    text = tasklist_path.read_text(encoding="utf-8")
    lines = text.splitlines()
    front, _ = parse_front_matter(lines)
    sections, section_map = parse_sections(lines)

    iter_section = section_map.get("AIDD:ITERATIONS_FULL", [])
    handoff_section = section_map.get("AIDD:HANDOFF_INBOX", [])

    iterations = parse_iteration_items(section_body(iter_section[0])) if iter_section else []
    handoffs = parse_handoff_items(section_body(handoff_section[0])) if handoff_section else []
    plan_ids = parse_plan_iteration_ids(root, resolve_plan_path(root, front, ticket))
    open_items, _, _ = build_open_items(iterations, handoffs, plan_ids)

    preamble: List[str] = []
    next3_section = section_map.get("AIDD:NEXT_3", [])
    if next3_section:
        body = section_body(next3_section[0])
        for line in body:
            if line.strip().startswith("-"):
                break
            preamble.append(line)

    next3_lines = build_next3_lines(open_items, preamble)

    if next3_section:
        entry = next3_section[0]
        updated_lines = _replace_section_lines(lines, entry.start, entry.end, next3_lines)
    else:
        updated_lines = list(lines)
        insert_idx = len(lines)
        if iter_section:
            insert_idx = iter_section[0].end
        updated_lines = updated_lines[:insert_idx] + next3_lines + updated_lines[insert_idx:]

    if "\n".join(updated_lines) == text:
        return DocOpsResult(False, "AIDD:NEXT_3 already up to date")

    tasklist_path.write_text(_ensure_trailing_newline("\n".join(updated_lines)), encoding="utf-8")
    return DocOpsResult(True, "AIDD:NEXT_3 recomputed")


def _replace_list_section(lines: List[str], heading: str, items: List[str]) -> Tuple[List[str], bool]:
    for idx, line in enumerate(lines):
        if line.strip() != heading:
            continue
        start = idx + 1
        end = start
        while end < len(lines):
            if lines[end].startswith("## "):
                break
            if lines[end].lstrip().startswith("-") or not lines[end].strip():
                end += 1
                continue
            break
        replacement = [f"- {item}" for item in items] if items else ["- n/a"]
        return lines[:start] + replacement + lines[end:], True
    return lines, False


def _replace_inline_list(lines: List[str], heading: str, items: List[str]) -> Tuple[List[str], bool]:
    for idx, line in enumerate(lines):
        if line.strip() != heading:
            continue
        start = idx + 1
        end = start
        while end < len(lines):
            if lines[end].lstrip().startswith("-"):
                end += 1
                continue
            break
        replacement = [f"- {item}" for item in items] if items else ["- n/a"]
        return lines[:start] + replacement + lines[end:], True
    return lines, False


def _replace_frontmatter_value(lines: List[str], key: str, value: str) -> Tuple[List[str], bool]:
    needle = f"{key}:"
    for idx, line in enumerate(lines):
        if line.strip().startswith(needle):
            new_line = f"{key}: {value}"
            if line == new_line:
                return lines, False
            lines[idx] = new_line
            return lines, True
    return lines, False


def _replace_first_list_item(lines: List[str], heading: str, value: str) -> Tuple[List[str], bool]:
    for idx, line in enumerate(lines):
        if line.strip() != heading:
            continue
        for j in range(idx + 1, len(lines)):
            if lines[j].startswith("## "):
                break
            if lines[j].lstrip().startswith("-"):
                lines[j] = f"- {value or 'n/a'}"
                return lines, True
        # if no list item found, insert
        lines.insert(idx + 1, f"- {value or 'n/a'}")
        return lines, True
    return lines, False


def context_pack_update(root: Path, ticket: str, payload: dict) -> DocOpsResult:
    context_path = root / "reports" / "context" / f"{ticket}.pack.md"
    if not context_path.exists():
        return DocOpsResult(False, f"context pack missing: {runtime.rel_path(context_path, root)}", error=True)
    text = context_path.read_text(encoding="utf-8")
    lines = text.splitlines()
    changed = False

    read_log = payload.get("read_log")
    if read_log is not None:
        lines, updated = _replace_list_section(lines, "## AIDD:READ_LOG", read_log)
        changed = changed or updated

    read_next = payload.get("read_next")
    if read_next is not None:
        lines, updated = _replace_inline_list(lines, "read_next:", read_next)
        changed = changed or updated

    generated_at = payload.get("generated_at")
    if generated_at is not None:
        lines, updated = _replace_frontmatter_value(lines, "generated_at", str(generated_at))
        changed = changed or updated

    artefact_links = payload.get("artefact_links")
    if artefact_links is not None:
        lines, updated = _replace_inline_list(lines, "artefact_links:", artefact_links)
        changed = changed or updated

    what_to_do = payload.get("what_to_do")
    if what_to_do is not None:
        lines, updated = _replace_first_list_item(lines, "## What to do now", what_to_do)
        changed = changed or updated

    user_note = payload.get("user_note")
    if user_note is not None:
        lines, updated = _replace_first_list_item(lines, "## User note", user_note)
        changed = changed or updated

    if not changed:
        return DocOpsResult(False, "context pack already up to date")

    context_path.write_text(_ensure_trailing_newline("\n".join(lines)), encoding="utf-8")
    return DocOpsResult(True, "context pack updated")
