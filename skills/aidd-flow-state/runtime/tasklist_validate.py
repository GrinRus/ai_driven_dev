#!/usr/bin/env python3
"""Tasklist validation helpers split from tasklist_check."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Dict, List

from aidd_runtime import tasklist_check as core
from aidd_runtime import tasklist_normalize as normalize


def check_tasklist_text(
    root: Path,
    ticket: str,
    text: str,
    *,
    normalize_fix_mode: bool = False,
) -> core.TasklistCheckResult:
    lines = text.splitlines()
    front, body_start = core.parse_front_matter(lines)
    sections, section_map = core.parse_sections(lines)

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

    for title in core.REQUIRED_SECTIONS:
        if title not in section_map:
            add_issue("error", f"missing section: ## {title}")

    context_pack = core.section_body(section_map.get("AIDD:CONTEXT_PACK", [None])[0]) if section_map.get("AIDD:CONTEXT_PACK") else []
    stage = core.resolve_stage(root, context_pack)

    front_status = (front.get("Status") or front.get("status") or "").strip().upper()
    context_status = (core.extract_field_value(context_pack, "Status") or "").strip().upper()
    if front_status and context_status and front_status != context_status:
        add_issue("error", f"Status mismatch (front-matter={front_status}, CONTEXT_PACK={context_status})")
    if not front_status:
        add_issue("error", "missing front-matter Status")
    if front_status and not context_status:
        add_issue("error", "missing CONTEXT_PACK Status")

    test_execution = core.section_body(section_map.get("AIDD:TEST_EXECUTION", [None])[0]) if section_map.get("AIDD:TEST_EXECUTION") else []
    for field in ("profile", "tasks", "filters", "when", "reason"):
        if not core.extract_field_value(test_execution, field):
            add_issue("error", f"AIDD:TEST_EXECUTION missing {field}")

    iterations_section = section_map.get("AIDD:ITERATIONS_FULL")
    iter_items = core.parse_iteration_items(core.section_body(iterations_section[0])) if iterations_section else []
    if not iter_items:
        add_issue("error", "AIDD:ITERATIONS_FULL has no iterations")

    handoff_section = section_map.get("AIDD:HANDOFF_INBOX")
    handoff_items = core.parse_handoff_items(core.section_body(handoff_section[0]) if handoff_section else [])

    for iteration in iter_items:
        if not iteration.item_id:
            continue
        steps = core.extract_list_field(iteration.lines, "Steps")
        steps_count = len(steps)
        if steps_count == 0:
            add_issue("warn", f"iteration {iteration.item_id} missing Steps")
        elif steps_count < 3:
            add_issue("warn", f"iteration {iteration.item_id} has {steps_count} steps (<3)")
        elif steps_count > 7:
            add_issue("warn", f"iteration {iteration.item_id} has {steps_count} steps (>7)")

        expected_paths = core.extract_list_field(iteration.lines, "Expected paths")
        if not expected_paths:
            add_issue("warn", f"iteration {iteration.item_id} missing Expected paths")
        elif len(expected_paths) > 3:
            add_issue("warn", f"iteration {iteration.item_id} has {len(expected_paths)} expected paths (>3)")

        size_budget = core.extract_mapping_field(iteration.lines, "Size budget")
        if not size_budget:
            add_issue("warn", f"iteration {iteration.item_id} missing Size budget")
        else:
            normalized_budget = {
                str(key).strip().lower().replace("-", "_"): str(value).strip()
                for key, value in size_budget.items()
            }
            max_files = core.parse_int(normalized_budget.get("max_files"))
            max_loc = core.parse_int(normalized_budget.get("max_loc"))
            if max_files is None:
                add_issue("warn", f"iteration {iteration.item_id} Size budget missing max_files")
            elif max_files < 3 or max_files > 8:
                add_issue("warn", f"iteration {iteration.item_id} max_files={max_files} outside 3-8")
            if max_loc is None:
                add_issue("warn", f"iteration {iteration.item_id} Size budget missing max_loc")
            elif max_loc < 80 or max_loc > 400:
                add_issue("warn", f"iteration {iteration.item_id} max_loc={max_loc} outside 80-400")

    plan_path = core.resolve_plan_path(root, front, ticket)
    prd_path = core.resolve_prd_path(root, front, ticket)
    spec_path = core.resolve_spec_path(root, front, ticket)
    spec_hint_path = spec_path or (root / "docs" / "spec" / f"{ticket}.spec.yaml")
    plan_ids: List[str] = []
    if plan_path.exists():
        plan_ids = core.parse_plan_iteration_ids(root, plan_path)
        if not plan_ids:
            add_issue(core.severity_for_stage(stage), "AIDD:ITERATIONS missing iteration_id")
    else:
        add_issue(core.severity_for_stage(stage), f"plan not found: {plan_path}")

    if (plan_path.exists() or prd_path.exists()) and not (spec_path and spec_path.exists()):
        plan_text = core.read_text(plan_path) if plan_path.exists() else ""
        prd_text = core.read_text(prd_path) if prd_path.exists() else ""
        plan_mentions_ui = core.mentions_spec_required(
            core.extract_section_text(
                plan_text,
                ("AIDD:FILES_TOUCHED", "AIDD:ITERATIONS", "AIDD:DESIGN", "AIDD:TEST_STRATEGY"),
            )
        )
        prd_mentions_ui = core.mentions_spec_required(
            core.extract_section_text(
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
                f"(detected in {source_label}); missing {core.rel_path(root, spec_hint_path)}. "
                "Run /feature-dev-aidd:spec-interview.",
            )

    iteration_ids = [item.item_id for item in iter_items if item.item_id]
    if plan_ids:
        missing_from_tasklist = sorted(set(plan_ids) - set(iteration_ids))
        if missing_from_tasklist:
            missing_ids_severity = "warn" if normalize_fix_mode else "error"
            add_issue(
                missing_ids_severity,
                f"AIDD:ITERATIONS_FULL missing iteration_id(s): {', '.join(missing_from_tasklist)}",
            )
        for iteration in iter_items:
            if not iteration.item_id:
                add_issue(core.severity_for_stage(stage), "iteration missing iteration_id")
                continue
            if iteration.item_id not in plan_ids:
                if not iteration.parent_id:
                    add_issue(core.severity_for_stage(stage), f"iteration_id {iteration.item_id} not in plan and missing parent_iteration_id")

    open_items, iteration_map, handoff_map = normalize.build_open_items(iter_items, handoff_items, plan_ids)
    open_ids = {item.item_id for item in open_items}

    for iteration in iter_items:
        if not iteration.item_id:
            continue
        if iteration.item_id in iteration.deps:
            add_issue(core.severity_for_stage(stage), f"iteration {iteration.item_id} depends on itself")
        unknown_deps = [
            dep for dep in iteration.deps if dep and dep not in iteration_map and dep not in handoff_map
        ]
        if unknown_deps:
            add_issue(
                core.severity_for_stage(stage),
                f"iteration {iteration.item_id} has unknown deps: {', '.join(sorted(unknown_deps))}",
            )

    next3_section = section_map.get("AIDD:NEXT_3")
    next3_lines = core.section_body(next3_section[0]) if next3_section else []
    next3_blocks = core.parse_next3_items(next3_lines)

    placeholder = core.next3_placeholder_present(next3_lines)
    expected = min(3, len(open_items)) if open_items else 0
    count_mismatch = False
    if open_items:
        count_mismatch = len(next3_blocks) != expected
        if placeholder:
            add_issue("error", "AIDD:NEXT_3 contains placeholder with open items")
    else:
        if next3_blocks:
            add_issue("error", "AIDD:NEXT_3 should not contain checkboxes when no open items")
        if not placeholder:
            add_issue("error", "AIDD:NEXT_3 missing (none) placeholder")

    next3_ids: List[str] = []
    next3_order_keys: List[tuple] = []
    next3_unmet: Dict[str, List[str]] = {}
    for block in next3_blocks:
        header = block[0].lower()
        if "[x]" in header:
            add_issue("error", "AIDD:NEXT_3 contains [x]")
        kind, ref_id, has_ref = core.extract_ref_id(block)
        if not ref_id:
            add_issue(core.severity_for_stage(stage), "AIDD:NEXT_3 item missing ref/id")
            continue
        if not has_ref:
            add_issue(core.severity_for_stage(stage), "AIDD:NEXT_3 item missing ref:")
        next3_ids.append(ref_id)
        if ref_id in iteration_map:
            item = iteration_map[ref_id]
            unmet: List[str] = []
            if item.deps:
                unmet = normalize.unmet_deps(item.deps, iteration_map, handoff_map)
                if unmet:
                    next3_unmet[ref_id] = unmet
                    deps_label = ", ".join(sorted(unmet))
                    add_issue("warn", f"AIDD:NEXT_3 item {ref_id} has unmet deps: {deps_label}")
            priority = item.priority or "medium"
            if priority not in core.PRIORITY_ORDER:
                priority = "medium"
            blocking = bool(item.blocking)
            order_key = (
                0 if blocking else 1,
                core.PRIORITY_ORDER.get(priority, 99),
                1,
                plan_ids.index(ref_id) if ref_id in plan_ids else 10_000,
                ref_id,
            )
            next3_order_keys.append(order_key)
            if not core.extract_field_value(item.lines, "DoD"):
                add_issue("error", f"iteration {ref_id} missing DoD")
            if not core.block_has_heading(item.lines, "Boundaries"):
                add_issue("error", f"iteration {ref_id} missing Boundaries")
            if not core.block_has_heading(item.lines, "Tests"):
                add_issue("error", f"iteration {ref_id} missing Tests")
            if ref_id not in open_ids and ref_id not in next3_unmet:
                add_issue("error", f"AIDD:NEXT_3 item {ref_id} is not open")
        elif ref_id in handoff_map:
            item = handoff_map[ref_id]
            priority = item.priority or "medium"
            order_key = (
                0 if item.blocking else 1,
                core.PRIORITY_ORDER.get(priority, 99),
                0,
                ref_id,
            )
            next3_order_keys.append(order_key)
            handoff_meta_severity = core.severity_for_stage(stage) if normalize_fix_mode else "error"
            if not core.extract_field_value(item.lines, "DoD"):
                add_issue(handoff_meta_severity, f"handoff {ref_id} missing DoD")
            if not core.block_has_heading(item.lines, "Boundaries"):
                add_issue(handoff_meta_severity, f"handoff {ref_id} missing Boundaries")
            if not core.block_has_heading(item.lines, "Tests"):
                add_issue(handoff_meta_severity, f"handoff {ref_id} missing Tests")
            if ref_id not in open_ids:
                add_issue("error", f"AIDD:NEXT_3 item {ref_id} is not open")
        else:
            add_issue("error", f"AIDD:NEXT_3 references unknown id {ref_id}")

    if len(next3_ids) != len(set(next3_ids)):
        add_issue("error", "AIDD:NEXT_3 has duplicate ids")

    if open_items and count_mismatch:
        if next3_unmet:
            unmet_ids = ", ".join(sorted(next3_unmet.keys()))
            add_issue(
                "warn",
                f"AIDD:NEXT_3 has {len(next3_blocks)} items, expected {expected} (unmet deps: {unmet_ids})",
            )
        else:
            add_issue("error", f"AIDD:NEXT_3 has {len(next3_blocks)} items, expected {expected}")

    if open_items and len(next3_ids) == expected:
        expected_ids = [item.item_id for item in open_items[:expected]]
        if next3_ids != expected_ids:
            add_issue(core.severity_for_stage(stage), "AIDD:NEXT_3 does not match top open items")

    sorted_keys = sorted(next3_order_keys)
    if next3_order_keys and next3_order_keys != sorted_keys:
        add_issue(core.severity_for_stage(stage), "AIDD:NEXT_3 is not sorted")

    qa_trace = core.section_body(section_map.get("AIDD:QA_TRACEABILITY", [None])[0]) if section_map.get("AIDD:QA_TRACEABILITY") else []
    qa_data = core.parse_qa_traceability(qa_trace)
    has_not_met = any(value.get("status") == "not-met" for value in qa_data.values())
    if front_status == "READY" and has_not_met:
        add_issue("error", "Status READY with QA_TRACEABILITY NOT MET")

    checklist_section = core.section_body(section_map.get("AIDD:CHECKLIST", [None])[0]) if section_map.get("AIDD:CHECKLIST") else []
    qa_checklist_lines = []
    if checklist_section:
        qa_checklist_lines = core.subsection_lines(checklist_section, "### AIDD:CHECKLIST_QA")
        if not qa_checklist_lines:
            qa_checklist_lines = core.subsection_lines(checklist_section, "### QA")
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

    for iteration in iter_items:
        if iteration.state and iteration.state not in core.ITERATION_STATE_VALUES:
            add_issue(core.severity_for_stage(stage), f"iteration {iteration.item_id or '?'} has invalid State={iteration.state}")
        if iteration.priority and iteration.priority not in core.PRIORITY_VALUES:
            add_issue(
                core.severity_for_stage(stage),
                f"iteration {iteration.item_id or '?'} invalid Priority={iteration.priority}",
            )
        if iteration.item_id and not iteration.explicit_id:
            add_issue(core.severity_for_stage(stage), f"iteration {iteration.item_id} missing explicit iteration_id")
        open_state, state = core.pick_open_state(iteration.checkbox, iteration.state)
        if open_state is None and iteration.item_id:
            add_issue(
                core.severity_for_stage(stage),
                f"iteration {iteration.item_id} missing open/done state (run tasklist-check --fix)",
            )

    for handoff in handoff_items:
        if not handoff.item_id:
            add_issue(core.severity_for_stage(stage), "handoff task missing id")
            continue
        if handoff.source and handoff.source not in core.HANDOFF_SOURCE_VALUES:
            add_issue(core.severity_for_stage(stage), f"handoff {handoff.item_id} invalid source={handoff.source}")
        if handoff.item_id and not handoff.source:
            add_issue(core.severity_for_stage(stage), f"handoff {handoff.item_id} missing source")
        if handoff.priority and handoff.priority not in core.PRIORITY_VALUES:
            add_issue(core.severity_for_stage(stage), f"handoff {handoff.item_id} invalid Priority={handoff.priority}")
        if handoff.item_id and not handoff.priority:
            add_issue(core.severity_for_stage(stage), f"handoff {handoff.item_id} missing Priority")
        if handoff.status and handoff.status not in core.HANDOFF_STATUS_VALUES:
            add_issue(core.severity_for_stage(stage), f"handoff {handoff.item_id} invalid Status={handoff.status}")
        if handoff.item_id and not handoff.status:
            add_issue(core.severity_for_stage(stage), f"handoff {handoff.item_id} missing Status")
        if handoff.checkbox in {"open", "done"} and handoff.status:
            if handoff.checkbox == "done" and handoff.status != "done":
                add_issue(core.severity_for_stage(stage), f"handoff {handoff.item_id} checkbox/status mismatch")
            if handoff.checkbox == "open" and handoff.status == "done":
                add_issue(core.severity_for_stage(stage), f"handoff {handoff.item_id} checkbox/status mismatch")
        open_state, status = core.handoff_open_state(handoff.checkbox, handoff.status)
        if open_state is None and handoff.item_id:
            add_issue(
                core.severity_for_stage(stage),
                f"handoff {handoff.item_id} missing open/done state (run tasklist-check --fix)",
            )

    progress_section = core.section_body(section_map.get("AIDD:PROGRESS_LOG", [None])[0]) if section_map.get("AIDD:PROGRESS_LOG") else []
    progress_entries, invalid_progress = core.progress_entries_from_lines(progress_section)
    if invalid_progress:
        add_issue(core.severity_for_stage(stage), "invalid PROGRESS_LOG format")
    for line in progress_section:
        if line.strip().startswith("-") and len(line) > 240:
            add_issue(core.severity_for_stage(stage), "PROGRESS_LOG entry exceeds 240 chars")
            break
    for entry in progress_entries:
        if entry.get("source") not in core.PROGRESS_SOURCES:
            add_issue(core.severity_for_stage(stage), f"PROGRESS_LOG invalid source={entry.get('source')}")
        if entry.get("kind") not in core.PROGRESS_KINDS:
            add_issue(core.severity_for_stage(stage), f"PROGRESS_LOG invalid kind={entry.get('kind')}")
        if stage in core.STRICT_STAGES and not entry.get("link"):
            add_issue("error", "PROGRESS_LOG entry missing link in review/qa stage")
        msg = entry.get("msg", "")
        if "\n" in msg or '"' in msg:
            add_issue(core.severity_for_stage(stage), "PROGRESS_LOG msg must be single-line without quotes")

    progress_ids = {entry.get("item_id") for entry in progress_entries}
    archive_ids = set()
    archive_path = core.progress_archive_path(root, ticket)
    if archive_path.exists():
        archive_lines = archive_path.read_text(encoding="utf-8").splitlines()
        archive_entries, _ = core.progress_entries_from_lines(archive_lines)
        archive_ids = {entry.get("item_id") for entry in archive_entries}
    evidence_ids = progress_ids | archive_ids

    warned_progress: set[tuple[str, str]] = set()
    for entry in progress_entries:
        item_id = str(entry.get("item_id") or "").strip()
        kind = str(entry.get("kind") or "").strip().lower()
        if not item_id or not kind:
            continue
        key = (kind, item_id)
        if key in warned_progress:
            continue
        if kind == "iteration" and item_id in iteration_map:
            open_state, _ = core.pick_open_state(iteration_map[item_id].checkbox, iteration_map[item_id].state)
            if open_state is None or open_state:
                add_issue("warn", f"PROGRESS_LOG entry for {item_id} but checkbox not done")
                warned_progress.add(key)
        elif kind == "handoff" and item_id in handoff_map:
            open_state, _ = core.handoff_open_state(handoff_map[item_id].checkbox, handoff_map[item_id].status)
            if open_state is None or open_state:
                add_issue("warn", f"PROGRESS_LOG entry for {item_id} but checkbox not done")
                warned_progress.add(key)

    def block_has_link(block: List[str]) -> bool:
        for line in block:
            if "link:" in line or "link=" in line or "aidd/reports/" in line:
                return True
        return False

    for iteration in iter_items:
        if iteration.checkbox != "done":
            continue
        if iteration.item_id and iteration.item_id not in evidence_ids and not block_has_link(iteration.lines):
            add_issue(core.severity_for_stage(stage), f"iteration {iteration.item_id} marked done without evidence")
    for handoff in handoff_items:
        if handoff.checkbox != "done":
            continue
        if handoff.item_id and handoff.item_id not in evidence_ids and not block_has_link(handoff.lines):
            add_issue(core.severity_for_stage(stage), f"handoff {handoff.item_id} marked done without evidence")

    slug_hint = core.runtime.read_active_slug(root) or None
    gates_cfg = core.runtime.load_gates_config(root)
    reviewer_cfg = gates_cfg.get("reviewer") if isinstance(gates_cfg, dict) else {}
    if not isinstance(reviewer_cfg, dict):
        reviewer_cfg = {}
    reviewer_template = str(
        reviewer_cfg.get("tests_marker")
        or reviewer_cfg.get("marker")
        or "aidd/reports/reviewer/{ticket}/{scope_key}.tests.json"
    )
    work_item_key = core.runtime.read_active_work_item(root)
    scope_key = core.runtime.resolve_scope_key(work_item_key, ticket)
    try:
        reviewer_marker = core.runtime.reviewer_marker_path(
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
            add_issue(core.severity_for_stage(stage), "test failures present with optional tests")

    if context_pack:
        tldr_lines = core.subsection_lines(context_pack, "### TL;DR")
        if core.extract_bullets(tldr_lines) > 12:
            add_issue(core.severity_for_stage(stage), "CONTEXT_PACK TL;DR exceeds 12 bullets")
        blockers = core.subsection_lines(context_pack, "### Blockers summary")
        if not blockers:
            blockers = core.subsection_lines(context_pack, "### Blockers summary (handoff)")
        blockers_count = sum(1 for line in blockers if line.strip())
        if blockers_count > 8:
            add_issue(core.severity_for_stage(stage), "CONTEXT_PACK Blockers summary exceeds 8 lines")

    for block in next3_blocks:
        if len(block) > 12:
            add_issue(core.severity_for_stage(stage), "AIDD:NEXT_3 item exceeds 12 lines")
            break

    for block in core.split_checkbox_blocks(core.section_body(handoff_section[0]) if handoff_section else []):
        if len(block) > 20:
            add_issue(core.severity_for_stage(stage), "HANDOFF_INBOX item exceeds 20 lines")
            break

    total_lines = len(lines)
    total_chars = len(text)
    if total_lines > 2000 or total_chars > 200_000:
        add_issue("error", "tasklist size exceeds hard limits")
    elif total_lines > 800:
        add_issue(core.severity_for_stage(stage), "tasklist size exceeds soft limit")

    if core.collect_stacktrace_flags(lines):
        for idx, line in enumerate(lines):
            if re.match(r"^\s+at\s+", line) or line.strip().startswith("Caused by:"):
                if not core.find_report_link_near(lines, idx):
                    add_issue("error", "stacktrace-like output without report link")
                    break
    if core.large_code_fence_without_report(lines):
        add_issue("error", "large code fence without report link")

    if errors:
        return core.TasklistCheckResult(status="error", message="tasklist check failed", details=errors, warnings=warnings)
    if warnings:
        return core.TasklistCheckResult(status="warn", message="tasklist check warning", details=warnings)
    return core.TasklistCheckResult(status="ok", message="tasklist ready")
