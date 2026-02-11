#!/usr/bin/env python3
"""Tasklist normalization helpers split from tasklist_check."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, List

from aidd_runtime import tasklist_check as core


def deps_satisfied(
    deps: List[str],
    iteration_map: dict[str, core.IterationItem],
    handoff_map: dict[str, core.HandoffItem],
) -> bool:
    for dep_id in deps:
        dep_id = core.normalize_dep_id(dep_id)
        if not dep_id:
            continue
        if dep_id in iteration_map:
            open_state, _ = core.pick_open_state(iteration_map[dep_id].checkbox, iteration_map[dep_id].state)
            if open_state is None or open_state:
                return False
            continue
        if dep_id in handoff_map:
            open_state, _ = core.handoff_open_state(handoff_map[dep_id].checkbox, handoff_map[dep_id].status)
            if open_state is None or open_state:
                return False
            continue
        return False
    return True


def unmet_deps(
    deps: List[str],
    iteration_map: dict[str, core.IterationItem],
    handoff_map: dict[str, core.HandoffItem],
) -> List[str]:
    unmet: List[str] = []
    for dep_id in deps:
        dep_id = core.normalize_dep_id(dep_id)
        if not dep_id:
            continue
        if dep_id in iteration_map:
            open_state, _ = core.pick_open_state(iteration_map[dep_id].checkbox, iteration_map[dep_id].state)
            if open_state is None or open_state:
                unmet.append(dep_id)
            continue
        if dep_id in handoff_map:
            open_state, _ = core.handoff_open_state(handoff_map[dep_id].checkbox, handoff_map[dep_id].status)
            if open_state is None or open_state:
                unmet.append(dep_id)
            continue
        unmet.append(dep_id)
    return unmet


def build_open_items(
    iterations: List[core.IterationItem],
    handoff_items: List[core.HandoffItem],
    plan_order: List[str],
) -> tuple[List[core.WorkItem], dict[str, core.IterationItem], dict[str, core.HandoffItem]]:
    items: List[core.WorkItem] = []
    iteration_map = {item.item_id: item for item in iterations if item.item_id}
    handoff_map = {item.item_id: item for item in handoff_items if item.item_id}
    plan_index = {item_id: idx for idx, item_id in enumerate(plan_order)}

    for iteration in iterations:
        if not iteration.item_id:
            continue
        open_state, _ = core.pick_open_state(iteration.checkbox, iteration.state)
        if open_state is None or not open_state:
            continue
        if iteration.deps and not deps_satisfied(iteration.deps, iteration_map, handoff_map):
            continue
        priority = iteration.priority or "medium"
        if priority not in core.PRIORITY_ORDER:
            priority = "medium"
        blocking = bool(iteration.blocking)
        order_key = (
            0 if blocking else 1,
            core.PRIORITY_ORDER.get(priority, 99),
            1,
            plan_index.get(iteration.item_id, 10_000),
            iteration.item_id,
        )
        items.append(
            core.WorkItem(
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
        open_state, _ = core.handoff_open_state(handoff.checkbox, handoff.status)
        if open_state is None or not open_state:
            continue
        priority = handoff.priority or "medium"
        if priority not in core.PRIORITY_ORDER:
            priority = "medium"
        order_key = (
            0 if handoff.blocking else 1,
            core.PRIORITY_ORDER.get(priority, 99),
            0,
            handoff.item_id,
        )
        items.append(
            core.WorkItem(
                kind="handoff",
                item_id=handoff.item_id,
                title=handoff.title,
                priority=priority,
                blocking=handoff.blocking,
                order_key=order_key,
            )
        )

    items.sort(key=lambda item: item.order_key)
    return items, iteration_map, handoff_map


def build_next3_lines(open_items: List[core.WorkItem], preamble: List[str] | None = None) -> List[str]:
    lines = ["## AIDD:NEXT_3"]
    if preamble:
        lines.extend(preamble)
    if not open_items:
        lines.append("- (none) no pending items")
        return lines
    for item in open_items[:3]:
        if item.kind == "iteration":
            lines.append(f"- [ ] {item.item_id}: {item.title} (ref: iteration_id={item.item_id})")
        else:
            lines.append(f"- [ ] {item.title} (ref: id={item.item_id})")
    return lines


def normalize_progress_section(
    lines: List[str],
    ticket: str,
    root: Path,
    summary: List[str],
    *,
    dry_run: bool,
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
    entries, invalid = core.progress_entries_from_lines(content)
    deduped = core.dedupe_progress(entries)
    if len(deduped) != len(entries):
        summary.append(f"deduped {len(entries) - len(deduped)} progress entries")
    if invalid:
        summary.append(f"dropped {len(invalid)} invalid progress entries")
    new_lines = [lines[0], *preamble]
    for entry in deduped:
        new_lines.append(core.progress_entry_line(entry))
    if len(new_lines) == 1 + len(preamble):
        new_lines.append("- (empty)")

    if dry_run:
        return new_lines

    archive_path = core.progress_archive_path(root, ticket)
    archive_lines = []
    if archive_path.exists():
        archive_lines = archive_path.read_text(encoding="utf-8").splitlines()
    archive_entries, _ = core.progress_entries_from_lines(archive_lines)
    merged = core.dedupe_progress(archive_entries + deduped)
    archive_path.parent.mkdir(parents=True, exist_ok=True)
    archive_text = "\n".join(core.progress_entry_line(entry) for entry in merged)
    if archive_text:
        archive_text += "\n"
    archive_path.write_text(archive_text, encoding="utf-8")
    summary.append(f"archived {len(deduped)} progress entries")

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
    parsed = core.parse_qa_traceability(content)
    merged: List[str] = [lines[0], *preamble]
    for ac_id in sorted(parsed.keys()):
        status = parsed[ac_id].get("status") or "met"
        evidence_list = parsed[ac_id].get("evidence") or []
        evidence = "; ".join(dict.fromkeys(evidence_list)) if evidence_list else ""
        arrow = "->"
        if evidence:
            merged.append(f"- AC-{ac_id} {arrow} <check> {arrow} {status} {arrow} {evidence}")
        else:
            merged.append(f"- AC-{ac_id} {arrow} <check> {arrow} {status} {arrow} <evidence>")
    if len(parsed) == 0:
        merged.append("- AC-1 -> <check> -> met -> <evidence>")
    if len(parsed) > 0:
        summary.append(f"merged {len(parsed)} QA traceability entries")
    return merged


def normalize_handoff_section(sections: List[core.Section], summary: List[str]) -> List[str]:
    if not sections:
        return []
    base = sections[0]
    body: List[str] = []
    for section in sections:
        body.extend(core.section_body(section))
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
                source = core.normalize_source(match.group(1))
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
            if core.CHECKBOX_RE.match(line):
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
        task_blocks = core.split_checkbox_blocks(raw_lines)
        kept: List[List[str]] = []
        dedup: dict[str, List[str]] = {}
        deduped = 0
        source = core.normalize_source(source)

        for block in task_blocks:
            item_id = core.extract_handoff_id(block)
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
) -> core.NormalizeResult:
    lines = text.splitlines()
    front, _ = core.parse_front_matter(lines)
    sections, section_map = core.parse_sections(lines)
    summary: List[str] = []
    new_lines: List[str] = []
    consumed = 0

    def section_replacement(section: core.Section, all_sections: List[core.Section]) -> List[str]:
        title = section.title
        if title == "AIDD:HANDOFF_INBOX":
            return normalize_handoff_section(all_sections, summary)
        if title == "AIDD:PROGRESS_LOG":
            combined = [all_sections[0].lines[0]]
            for entry in all_sections:
                combined.extend(core.section_body(entry))
            return normalize_progress_section(combined, ticket, root, summary, dry_run=dry_run)
        if title == "AIDD:QA_TRACEABILITY":
            combined = [all_sections[0].lines[0]]
            for entry in all_sections:
                combined.extend(core.section_body(entry))
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

    sections, section_map = core.parse_sections(normalized_text.splitlines())
    next3_section = section_map.get("AIDD:NEXT_3", [])
    iter_section = section_map.get("AIDD:ITERATIONS_FULL", [])
    handoff_section = section_map.get("AIDD:HANDOFF_INBOX", [])

    if iter_section:
        iter_items = core.parse_iteration_items(core.section_body(iter_section[0]))
        handoff_items = core.parse_handoff_items(core.section_body(handoff_section[0]) if handoff_section else [])
        plan_ids = core.parse_plan_iteration_ids(root, core.resolve_plan_path(root, front, ticket))
        open_items, _, _ = build_open_items(iter_items, handoff_items, plan_ids)
        open_ref_tokens: set[str] = set()
        for item in open_items:
            if item.kind == "iteration":
                open_ref_tokens.add(f"(ref: iteration_id={item.item_id})")
            else:
                open_ref_tokens.add(f"(ref: id={item.item_id})")
        archived_refs: List[str] = []
        seen_archived_refs: set[str] = set()
        if next3_section:
            for block in core.parse_next3_items(core.section_body(next3_section[0])):
                kind, ref_id, _ = core.extract_ref_id(block)
                if not ref_id:
                    continue
                token = f"(ref: iteration_id={ref_id})" if kind == "iteration" else f"(ref: id={ref_id})"
                if token in open_ref_tokens or token in seen_archived_refs:
                    continue
                seen_archived_refs.add(token)
                archived_refs.append(token)
        preamble = []
        if next3_section:
            for line in core.section_body(next3_section[0]):
                if line.strip().startswith("-"):
                    break
                preamble.append(line)
        if archived_refs:
            for token in archived_refs:
                preamble.append(f"- archived: {token}")
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

    return core.NormalizeResult(updated_text=normalized_text, summary=summary, changed=normalized_text != text)
