from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Tuple

from aidd_runtime import runtime


_TASK_ID_RE = re.compile(r"\bid:\s*([A-Za-z0-9_.:-]+)")
_TASK_ID_SIGNATURE_RE = re.compile(r"(,?\s*id:\s*[A-Za-z0-9_.:-]+)")
_TASK_START_RE = re.compile(r"^\s*-\s*\[[ xX]\]")
_FIELD_HEADER_RE = re.compile(r"^(?P<indent>\s*)-\s*(?P<label>[A-Za-z][A-Za-z0-9 _-]*)\s*:")
_TASK_PRIORITY_RE = re.compile(r"\(Priority:\s*([^)]+)\)", re.IGNORECASE)
_TASK_BLOCKING_RE = re.compile(r"\(Blocking:\s*(true|false)\)", re.IGNORECASE)
_SOURCE_ALIASES = {"reviewer": "review"}
_PRIORITY_MAP = {
    "blocker": "critical",
    "critical": "critical",
    "major": "high",
    "high": "high",
    "minor": "low",
    "low": "low",
    "info": "low",
}
_PRESERVE_FIELDS = {"scope", "boundaries", "tests", "notes"}
_RESEARCH_NON_ACTIONABLE_SCOPES = {"", "n/a", "na"}


@dataclass
class TaskSpec:
    source: str
    task_id: str
    title: str
    scope: str
    dod: str
    priority: str
    blocking: bool
    status: str
    test_profile: str
    notes: str
    report_label: str


def _stable_task_id(prefix: str, *parts: object) -> str:
    digest = hashlib.sha1()
    digest.update(prefix.encode("utf-8"))
    for part in parts:
        normalized = " ".join(str(part or "").strip().split())
        digest.update(b"|")
        digest.update(normalized.encode("utf-8"))
    return digest.hexdigest()[:12]


def _task_id_from_line(line: str) -> str | None:
    match = _TASK_ID_RE.search(line)
    if not match:
        return None
    value = match.group(1).strip()
    return value or None


def _is_task_start(line: str) -> bool:
    return bool(_TASK_START_RE.match(line))


def _task_signature(line: str) -> str:
    normalized = " ".join(line.strip().split())
    normalized = _TASK_ID_SIGNATURE_RE.sub("", normalized)
    normalized = normalized.replace(" ,", ",")
    lowered = normalized.lower()
    source_idx = lowered.rfind(" (source:")
    if source_idx != -1:
        head = normalized[:source_idx]
        tail = normalized[source_idx:]
        if " — " in head:
            head = head.split(" — ", 1)[0]
        normalized = head + tail
    return " ".join(normalized.strip().split())


def _canonical_source(source: str) -> str:
    normalized = (source or "").strip().lower()
    if normalized in _SOURCE_ALIASES:
        return _SOURCE_ALIASES[normalized]
    return normalized


def _canonical_task_id(source: str, raw_id: str) -> str:
    prefix = _canonical_source(source)
    candidate = (raw_id or "").strip()
    if not candidate:
        return ""
    candidate = candidate.replace("reviewer:", "review:")
    while candidate.startswith(f"{prefix}:{prefix}:"):
        candidate = candidate[len(prefix) + 1 :]
    if candidate.startswith(f"{prefix}:"):
        return candidate
    return f"{prefix}:{candidate}"


def _rlm_reason_hash(reason: str, rule_kind: str, scope: str) -> str:
    normalized_reason = " ".join(str(reason or "").strip().split()).lower()
    normalized_kind = " ".join(str(rule_kind or "").strip().split()).lower()
    normalized_scope = " ".join(str(scope or "").strip().split()).lower()
    digest = hashlib.sha1()
    digest.update(normalized_reason.encode("utf-8"))
    digest.update(b"|")
    digest.update(normalized_kind.encode("utf-8"))
    digest.update(b"|")
    digest.update(normalized_scope.encode("utf-8"))
    return digest.hexdigest()


def _rlm_task_id(kind: str, file_id: str, reason: str, scope: str) -> str:
    reason_hash = _rlm_reason_hash(reason, kind, scope)
    return f"rlm:{kind}:{file_id}:{reason_hash}"


def _task_block(spec: TaskSpec) -> List[str]:
    header = (
        f"- [ ] {spec.title} (id: {spec.task_id}) "
        f"(Priority: {spec.priority}) (Blocking: {str(spec.blocking).lower()})"
    )
    lines = [
        header,
        f"  - source: {spec.source}",
        f"  - Report: {spec.report_label}",
        f"  - Status: {spec.status}",
        f"  - title: {spec.title}",
        f"  - scope: {spec.scope}",
        f"  - DoD: {spec.dod}",
        "  - Boundaries:",
        "    - must-touch: []",
        "    - must-not-touch: []",
        "  - Tests:",
        f"    - profile: {spec.test_profile}",
        "    - tasks: []",
        "    - filters: []",
    ]
    if spec.notes:
        lines.append(f"  - Notes: {spec.notes}")
    return lines


def _extract_block_field(block: Sequence[str], field: str) -> str:
    field_key = field.strip().lower()
    for line in block:
        match = _FIELD_HEADER_RE.match(line)
        if not match:
            continue
        label = match.group("label").strip().lower()
        if label != field_key:
            continue
        return line.split(":", 1)[1].strip()
    return ""


def _is_actionable_research_block(block: Sequence[str]) -> bool:
    if not block:
        return False
    header = block[0]
    blocking_match = _TASK_BLOCKING_RE.search(header)
    if blocking_match and blocking_match.group(1).lower() == "true":
        return True
    priority_match = _TASK_PRIORITY_RE.search(header)
    if priority_match:
        priority = priority_match.group(1).strip().lower()
        if priority in {"critical", "high"}:
            return True
    scope = _extract_block_field(block, "scope").strip().lower()
    if scope and scope not in _RESEARCH_NON_ACTIONABLE_SCOPES:
        return True
    return False


def _filter_research_handoff_blocks(blocks: Sequence[List[str]]) -> List[List[str]]:
    return [block for block in blocks if _is_actionable_research_block(block)]




def _format_task_suffix(report_label: str, task_id: str | None = None) -> str:
    parts = [f"source: {report_label}"]
    if task_id:
        parts.append(f"id: {task_id}")
    return f" ({', '.join(parts)})"


_HANDOFF_SECTION_HINTS: Dict[str, Tuple[str, ...]] = {
    "qa": (
        "## aidd:handoff_inbox",
        "## 3. qa / проверки",
        "## qa",
        "## 3. qa",
        "## 3. qa / проверки",
    ),
    "review": (
        "## aidd:handoff_inbox",
        "## 2. реализация",
        "## реализация",
        "## implementation",
        "## 2. implementation",
    ),
    "research": (
        "## aidd:handoff_inbox",
        "## 1. аналитика и дизайн",
        "## аналитика",
        "## research",
        "## 7. примечания",
    ),
}


def _derive_tasks_from_findings(prefix: str, payload: Dict, report_label: str) -> List[List[str]]:
    raw_findings = payload.get("findings") or []
    findings = _inflate_columnar(raw_findings) if isinstance(raw_findings, dict) else raw_findings
    blocks: List[List[str]] = []
    source = _canonical_source(prefix.lower())
    for finding in findings:
        if not isinstance(finding, dict):
            continue
        severity = str(finding.get("severity") or "").strip().lower() or "info"
        scope = str(finding.get("scope") or "").strip() or "n/a"
        title = str(finding.get("title") or "").strip() or "issue"
        recommendation = str(finding.get("recommendation") or "").strip()
        details = str(finding.get("details") or "").strip()
        raw_id = str(finding.get("id") or "").strip()
        if not raw_id:
            raw_id = _stable_task_id(source, scope, title)
        task_id = _canonical_task_id(source, raw_id)
        priority = _PRIORITY_MAP.get(severity, "medium")
        blocking = severity in {"blocker", "critical"}
        test_profile = "targeted" if severity in {"blocker", "critical", "major"} else "fast"
        tag = f"{prefix} [{severity}]"
        full_title = f"{tag} {title}".strip()
        if recommendation:
            full_title = f"{full_title} — {recommendation}"
        dod = recommendation or details or f"See {report_label}"
        notes = details if recommendation and details and details != recommendation else ""
        spec = TaskSpec(
            source=source,
            task_id=task_id,
            title=full_title,
            scope=scope,
            dod=dod,
            priority=priority,
            blocking=blocking,
            status="open",
            test_profile=test_profile,
            notes=notes,
            report_label=report_label,
        )
        blocks.append(_task_block(spec))
    return blocks


def _derive_tasks_from_tests(payload: Dict, report_label: str) -> List[List[str]]:
    blocks: List[List[str]] = []
    summary = str(payload.get("tests_summary") or "").strip().lower() or "not-run"
    raw_executed = payload.get("tests_executed") or []
    executed = _inflate_columnar(raw_executed) if isinstance(raw_executed, dict) else raw_executed
    source = "qa"
    if summary == "fail":
        task_id = _canonical_task_id(source, f"qa-tests:{_stable_task_id('qa-tests', 'summary', summary)}")
        spec = TaskSpec(
            source=source,
            task_id=task_id,
            title="QA tests failed",
            scope="tests",
            dod=f"Tests passing (see {report_label})",
            priority="high",
            blocking=True,
            status="open",
            test_profile="targeted",
            notes="",
            report_label=report_label,
        )
        blocks.append(_task_block(spec))
    if summary in {"skipped", "not-run"}:
        task_id = _canonical_task_id(source, f"qa-tests:{_stable_task_id('qa-tests', summary)}")
        spec = TaskSpec(
            source=source,
            task_id=task_id,
            title="QA tests: run missing tests",
            scope="tests",
            dod=f"Tests executed and report saved ({report_label})",
            priority="medium",
            blocking=False,
            status="open",
            test_profile="targeted",
            notes="",
            report_label=report_label,
        )
        blocks.append(_task_block(spec))
    for entry in executed:
        if not isinstance(entry, dict):
            continue
        status = str(entry.get("status") or "").strip().lower()
        if status != "fail":
            continue
        command = str(entry.get("command") or "").strip()
        log_path = str(entry.get("log") or entry.get("log_path") or "").strip()
        task_id = _canonical_task_id(source, _stable_task_id("qa-tests", "fail", command, log_path))
        title = "QA tests: fix failure"
        if command:
            title = f"QA tests: fix failure ({command})"
        notes = f"log: {log_path}" if log_path else ""
        spec = TaskSpec(
            source=source,
            task_id=task_id,
            title=title,
            scope="tests",
            dod=f"Command passes (see {report_label})",
            priority="high",
            blocking=True,
            status="open",
            test_profile="targeted",
            notes=notes,
            report_label=report_label,
        )
        blocks.append(_task_block(spec))
    if summary == "fail" and not blocks:
        task_id = _canonical_task_id(source, f"qa-tests:{_stable_task_id('qa-tests', 'fail', 'summary')}")
        spec = TaskSpec(
            source=source,
            task_id=task_id,
            title="QA tests: fix failures",
            scope="tests",
            dod=f"Tests passing (see {report_label})",
            priority="high",
            blocking=True,
            status="open",
            test_profile="targeted",
            notes="",
            report_label=report_label,
        )
        blocks.append(_task_block(spec))
    return blocks


def _inflate_columnar(section: object) -> List[Dict]:
    if not isinstance(section, dict):
        return []
    cols = section.get("cols")
    rows = section.get("rows")
    if not isinstance(cols, list) or not isinstance(rows, list):
        return []
    items: List[Dict] = []
    for row in rows:
        if not isinstance(row, list):
            continue
        record: Dict[str, object] = {}
        for idx, col in enumerate(cols):
            if idx >= len(row):
                break
            record[str(col)] = row[idx]
        if record:
            items.append(record)
    return items


def _derive_tasks_from_rlm_pack(payload: Dict, report_label: str) -> List[List[str]]:
    blocks: List[List[str]] = []
    source = "research"

    def _node_file_id(node: Dict[str, object], kind: str, path: str) -> str:
        raw = str(node.get("file_id") or node.get("id") or "").strip()
        if raw:
            return raw
        return _stable_task_id("rlm", kind, path)

    def _make_task(
        *,
        kind: str,
        path: str,
        file_id: str,
        title: str,
        reason: str,
        priority: str,
        blocking: bool,
        test_profile: str,
        notes: str,
    ) -> None:
        task_id = _rlm_task_id(kind, file_id, reason, path)
        spec = TaskSpec(
            source=source,
            task_id=task_id,
            title=title,
            scope=path or "n/a",
            dod=f"Review RLM evidence ({report_label})",
            priority=priority,
            blocking=blocking,
            status="open",
            test_profile=test_profile,
            notes=notes,
            report_label=report_label,
        )
        blocks.append(_task_block(spec))

    for node in payload.get("integration_points") or []:
        if not isinstance(node, dict):
            continue
        path = str(node.get("path") or "").strip()
        if not path:
            continue
        file_id = _node_file_id(node, "integration", path)
        title = f"RLM integration: {path}"
        summary = str(node.get("summary") or "").strip()
        _make_task(
            kind="integration",
            path=path,
            file_id=file_id,
            title=title,
            reason="integration",
            priority="medium",
            blocking=False,
            test_profile="targeted",
            notes=summary,
        )

    for node in payload.get("test_hooks") or []:
        if not isinstance(node, dict):
            continue
        path = str(node.get("path") or "").strip()
        if not path:
            continue
        file_id = _node_file_id(node, "test-hook", path)
        hooks = node.get("test_hooks") or []
        hook_label = ", ".join(str(item).strip() for item in hooks if str(item).strip())
        title = f"RLM test hook: {path}"
        reason = hook_label or "test-hook"
        _make_task(
            kind="test-hook",
            path=path,
            file_id=file_id,
            title=title,
            reason=reason,
            priority="low",
            blocking=False,
            test_profile="fast",
            notes=hook_label,
        )

    for node in payload.get("risks") or []:
        if not isinstance(node, dict):
            continue
        path = str(node.get("path") or "").strip()
        if not path:
            continue
        file_id = _node_file_id(node, "risk", path)
        risks = node.get("risks") or []
        for risk in risks:
            risk_text = str(risk).strip()
            if not risk_text:
                continue
            title = f"RLM risk: {risk_text}"
            _make_task(
                kind="risk",
                path=path,
                file_id=file_id,
                title=title,
                reason=risk_text,
                priority="high",
                blocking=False,
                test_profile="targeted",
                notes="",
            )
    return blocks


def _derive_handoff_placeholder(source: str, ticket: str, report_label: str) -> List[List[str]]:
    canonical = _canonical_source(source)
    task_id = _canonical_task_id(canonical, f"{canonical}-report-{_stable_task_id(canonical, report_label, ticket)}")
    title = "Research: update context before next iteration"
    if canonical == "qa":
        title = "QA report: confirm no blockers"
    elif canonical == "review":
        title = "Review report: confirm no findings"
    spec = TaskSpec(
        source=canonical,
        task_id=task_id,
        title=title,
        scope="n/a",
        dod=f"Report reviewed ({report_label})",
        priority="medium",
        blocking=False,
        status="open",
        test_profile="none",
        notes="",
        report_label=report_label,
    )
    return [_task_block(spec)]


def _dedupe_task_blocks(blocks: Sequence[Sequence[str]]) -> List[List[str]]:
    seen = set()
    deduped: List[List[str]] = []
    for block in blocks:
        if not block:
            continue
        task_id = _task_id_from_line(block[0])
        signature = _task_signature(block[0])
        key = task_id or signature
        if not key or key in seen:
            continue
        seen.add(key)
        deduped.append(list(block))
    return deduped


def _split_task_blocks(lines: Sequence[str]) -> List[List[str]]:
    blocks: List[List[str]] = []
    current: List[str] = []
    for line in lines:
        if _is_task_start(line):
            if current:
                blocks.append(current)
            current = [line]
            continue
        if current:
            current.append(line)
        elif line.strip():
            blocks.append([line])
    if current:
        blocks.append(current)
    return blocks


def _flatten_task_blocks(blocks: Sequence[Sequence[str]]) -> List[str]:
    return [line for block in blocks for line in block]


def _block_checkbox_state(block: Sequence[str]) -> str:
    if not block:
        return ""
    match = _TASK_START_RE.match(block[0])
    if not match:
        return ""
    return "done" if "[x]" in block[0].lower() else "open"


def _block_status_value(block: Sequence[str]) -> str:
    for line in block:
        match = re.match(r"^\s*-\s*Status\s*:\s*(\S+)\s*$", line, re.IGNORECASE)
        if match:
            return match.group(1).strip().lower()
    return ""


def _split_block_fields(block: Sequence[str]) -> tuple[str, List[Tuple[str, List[str]]], List[str]]:
    if not block:
        return "", [], []
    header = block[0]
    header_indent = len(header) - len(header.lstrip())
    field_indent = header_indent + 2
    fields: List[Tuple[str, List[str]]] = []
    extras: List[str] = []
    current_key: str | None = None
    current_lines: List[str] | None = None
    for line in block[1:]:
        match = _FIELD_HEADER_RE.match(line)
        if match and len(match.group("indent")) == field_indent:
            if current_lines is not None and current_key is not None:
                fields.append((current_key, current_lines))
            current_key = match.group("label").strip().lower()
            current_lines = [line]
            continue
        if current_lines is not None:
            current_lines.append(line)
        else:
            extras.append(line)
    if current_lines is not None and current_key is not None:
        fields.append((current_key, current_lines))
    return header, fields, extras


def _field_has_value(lines: Sequence[str]) -> bool:
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("-"):
            stripped = stripped.lstrip("-").strip()
        if ":" in stripped:
            _, value = stripped.split(":", 1)
            value = value.strip()
            if value and value != "[]":
                return True
            continue
        if stripped:
            return True
    return False


def _field_tokens(lines: Sequence[str]) -> List[str]:
    tokens: List[str] = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("-"):
            stripped = stripped.lstrip("-").strip()
        tokens.append(stripped.lower())
    return tokens


def _field_value(lines: Sequence[str]) -> str:
    for line in lines:
        stripped = line.strip()
        if ":" not in stripped:
            continue
        _, value = stripped.split(":", 1)
        return value.strip()
    return ""


def _header_recommendation(header_line: str) -> str:
    title = re.sub(r"^\s*-\s*\[[ xX]\]\s*", "", header_line).strip()
    cut_tokens = (" (id:", " (source:", " (Priority:", " (Blocking:")
    cut_points = [idx for token in cut_tokens if (idx := title.find(token)) != -1]
    if cut_points:
        title = title[: min(cut_points)].rstrip()
    if " — " not in title:
        return ""
    return title.split(" — ", 1)[1].strip()


def _is_default_boundaries_field(lines: Sequence[str]) -> bool:
    tokens = _field_tokens(lines)
    if not tokens or tokens[0] != "boundaries:":
        return False
    body = tokens[1:]
    return len(body) == 2 and set(body) == {"must-touch: []", "must-not-touch: []"}


def _is_default_tests_field(lines: Sequence[str]) -> bool:
    tokens = _field_tokens(lines)
    if not tokens or tokens[0] != "tests:":
        return False
    profile_seen = 0
    has_tasks = False
    has_filters = False
    for token in tokens[1:]:
        if token.startswith("profile: "):
            profile_seen += 1
            continue
        if token == "tasks: []":
            has_tasks = True
            continue
        if token == "filters: []":
            has_filters = True
            continue
        return False
    return profile_seen == 1 and has_tasks and has_filters


def _should_preserve_dod(
    existing_fields: Dict[str, List[str]],
    *,
    existing_header: str = "",
) -> bool:
    notes_lines = existing_fields.get("notes")
    if notes_lines and _field_has_value(notes_lines):
        return True
    boundaries_lines = existing_fields.get("boundaries")
    if boundaries_lines and not _is_default_boundaries_field(boundaries_lines):
        return True
    tests_lines = existing_fields.get("tests")
    if tests_lines and not _is_default_tests_field(tests_lines):
        return True
    dod_lines = existing_fields.get("dod")
    if dod_lines and _field_has_value(dod_lines):
        current_dod = _field_value(dod_lines)
        auto_recommendation = _header_recommendation(existing_header)
        if auto_recommendation and current_dod and current_dod != auto_recommendation:
            return True
    return False


def _merge_block_fields(existing_block: Sequence[str], new_block: Sequence[str]) -> List[str]:
    if not existing_block:
        return list(new_block)
    if not new_block:
        return list(existing_block)
    new_header, new_fields, new_extras = _split_block_fields(new_block)
    _, existing_fields, existing_extras = _split_block_fields(existing_block)
    existing_map = {key: lines for key, lines in existing_fields}
    merged_fields: List[List[str]] = []
    seen_keys: set[str] = set()
    for key, lines in new_fields:
        seen_keys.add(key)
        existing_lines = existing_map.get(key)
        if existing_lines and key in _PRESERVE_FIELDS and _field_has_value(existing_lines):
            merged_fields.append(existing_lines)
            continue
        if (
            key == "dod"
            and existing_lines
            and _field_has_value(existing_lines)
            and _should_preserve_dod(existing_map, existing_header=existing_block[0])
        ):
            merged_fields.append(existing_lines)
        else:
            merged_fields.append(lines)
    for key, lines in existing_fields:
        if key in seen_keys:
            continue
        merged_fields.append(lines)
    merged = [new_header]
    for field_lines in merged_fields:
        merged.extend(field_lines)
    extras = list(new_extras)
    for line in existing_extras:
        if line not in extras:
            extras.append(line)
    merged.extend(extras)
    return merged


def _apply_status_to_block(block: Sequence[str], checkbox: str, status: str) -> List[str]:
    if not block:
        return []
    header = block[0]
    if checkbox == "done":
        header = re.sub(r"\[\s*\]", "[x]", header, count=1)
    elif checkbox == "open":
        header = re.sub(r"\[\s*[xX]\s*\]", "[ ]", header, count=1)
    updated = [header]
    status_applied = False
    for line in block[1:]:
        if re.match(r"^\s*-\s*Status\s*:\s*", line, re.IGNORECASE):
            updated.append(re.sub(r":\s*.*$", f": {status}", line))
            status_applied = True
        else:
            updated.append(line)
    if not status_applied and status:
        updated.insert(1, f"  - Status: {status}")
    return updated


def _merge_handoff_tasks(existing: Sequence[str], new_tasks: Sequence[str], *, append: bool) -> List[str]:
    if not append:
        return list(new_tasks)

    merged_blocks = _split_task_blocks(existing)
    new_blocks = _split_task_blocks(new_tasks)
    by_id = {}
    by_signature = {}
    for idx, block in enumerate(merged_blocks):
        if not block or not _is_task_start(block[0]):
            continue
        task_id = _task_id_from_line(block[0])
        if task_id:
            by_id[task_id] = idx
        signature = _task_signature(block[0])
        if signature:
            by_signature[signature] = idx

    for block in new_blocks:
        if not block:
            continue
        header = block[0]
        task_id = _task_id_from_line(header) if _is_task_start(header) else None
        signature = _task_signature(header) if _is_task_start(header) else ""
        idx = None
        if task_id and task_id in by_id:
            idx = by_id[task_id]
        elif signature and signature in by_signature:
            idx = by_signature[signature]

        if idx is None:
            merged_blocks.append(block)
            idx = len(merged_blocks) - 1
        else:
            existing_block = merged_blocks[idx]
            existing_checkbox = _block_checkbox_state(existing_block)
            existing_status = _block_status_value(existing_block)
            desired_status = existing_status or ("done" if existing_checkbox == "done" else "open")
            desired_checkbox = "done" if existing_status == "done" else existing_checkbox
            merged = _apply_status_to_block(block, desired_checkbox or "open", desired_status or "open")
            merged = _merge_block_fields(existing_block, merged)
            merged_blocks[idx] = merged

        if task_id:
            by_id[task_id] = idx
        if signature:
            by_signature[signature] = idx

    return _flatten_task_blocks(merged_blocks)


def _extract_handoff_block(lines: List[str], source: str) -> tuple[int, int, List[str]]:
    canonical = _canonical_source(source)
    hint_label = f"handoff:{canonical}"
    start = -1
    end = -1
    for idx, line in enumerate(lines):
        if hint_label in line and line.strip().startswith("<!--"):
            start = idx
            break
    if start == -1:
        return -1, -1, []
    for idx in range(start + 1, len(lines)):
        if hint_label in lines[idx] and lines[idx].strip().endswith("-->"):
            end = idx + 1
            break
    if end == -1:
        end = start + 1
    return start, end, lines[start:end]


def _find_section(lines: List[str], candidates: Sequence[str]) -> tuple[int, Optional[str]]:
    if not candidates:
        return -1, None
    lowered = [line.strip().lower() for line in lines]
    for candidate in candidates:
        label = candidate.strip().lower()
        try:
            idx = lowered.index(label)
        except ValueError:
            continue
        return idx, candidate
    return -1, None


def _apply_handoff_tasks(
    text: str,
    *,
    source: str,
    report_label: str,
    tasks: Sequence[str],
    append: bool,
    section_candidates: Sequence[str],
) -> tuple[str, Optional[str], bool]:
    source = _canonical_source(source)
    lines = text.splitlines()
    handoff_start, handoff_end, block = _extract_handoff_block(lines, source)
    block_lines = block[1:-1] if len(block) >= 2 else []
    new_tasks = _merge_handoff_tasks(block_lines, tasks, append=append)

    if handoff_start != -1:
        start_marker = block[0] if block else f"<!-- handoff:{source} start -->"
        end_marker = block[-1] if block else f"<!-- handoff:{source} end -->"
        new_block = [start_marker, *new_tasks, end_marker]
        new_lines = lines[:handoff_start] + new_block + lines[handoff_end:]
        new_text = "\n".join(new_lines)
        if not new_text.endswith("\n"):
            new_text += "\n"
        return new_text, None, new_text != text

    insert_at, heading_label = _find_section(lines, section_candidates)
    if insert_at == -1:
        insert_at = len(lines)
    else:
        insert_at += 1
        while insert_at < len(lines) and not lines[insert_at].strip():
            insert_at += 1
    start_marker = f"<!-- handoff:{source} start (source: {report_label}) -->"
    end_marker = f"<!-- handoff:{source} end -->"
    block_lines = [start_marker, *new_tasks, end_marker]
    new_lines = lines[:insert_at] + block_lines + lines[insert_at:]
    new_text = "\n".join(new_lines)
    if not new_text.endswith("\n"):
        new_text += "\n"
    changed = new_text != text
    return new_text, heading_label, changed


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate tasklist candidates from QA/Research/Review reports.",
    )
    parser.add_argument(
        "--source",
        choices=("qa", "research", "review"),
        required=True,
        help="Report source to derive tasks from.",
    )
    parser.add_argument(
        "--ticket",
        dest="ticket",
        help="Ticket identifier to use (defaults to docs/.active.json).",
    )
    parser.add_argument(
        "--slug-hint",
        dest="slug_hint",
        help="Optional slug hint override used for messaging.",
    )
    parser.add_argument(
        "--report",
        help="Optional report path override (default depends on --source).",
    )
    parser.add_argument(
        "--append",
        action="store_true",
        help="Preserve existing handoff block and append new items instead of replacing it.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show planned changes without modifying files.",
    )
    parser.add_argument(
        "--prefer-pack",
        action="store_true",
        help="Prefer *.pack.json for research reports when available.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    _, target = runtime.require_workflow_root()

    context = runtime.resolve_feature_context(
        target,
        ticket=getattr(args, "ticket", None),
        slug_hint=getattr(args, "slug_hint", None),
    )
    ticket = (context.resolved_ticket or "").strip()
    slug_hint = (context.slug_hint or ticket or "").strip()
    if not ticket:
        raise ValueError("feature ticket is required; pass --ticket or set docs/.active.json via /feature-dev-aidd:idea-new.")
    work_item_key = runtime.read_active_work_item(target)
    scope_key = runtime.resolve_scope_key(work_item_key, ticket)

    source = (args.source or "").strip().lower()
    default_report = {
        "qa": "aidd/reports/qa/{ticket}.json",
        "research": "aidd/reports/research/{ticket}-rlm.pack.json",
    }.get(source)
    if source == "review":
        default_report = runtime.review_report_template(target)
    report_template = args.report or default_report
    if not report_template:
        raise ValueError("unsupported source; expected qa|research|review")

    def _fmt(text: str) -> str:
        return (
            text.replace("{ticket}", ticket)
            .replace("{slug}", slug_hint or ticket)
            .replace("{scope_key}", scope_key)
        )

    report_path = runtime.resolve_path_for_target(Path(_fmt(report_template)), target)

    def _env_truthy(value: str | None) -> bool:
        return str(value or "").strip().lower() in {"1", "true", "yes", "y"}

    prefer_pack = bool(getattr(args, "prefer_pack", False) or _env_truthy(os.getenv("AIDD_PACK_FIRST")))

    def _load_with_pack(path: Path, *, prefer_pack_first: bool) -> tuple[Dict, str]:
        from aidd_runtime.reports.loader import load_report_for_path

        payload, source_kind, report_paths = load_report_for_path(path, prefer_pack=prefer_pack_first)
        label_path = report_paths.pack_path if source_kind == "pack" else report_paths.json_path
        return payload, runtime.rel_path(label_path, target)

    is_pack_path = report_path.name.endswith(".pack.json")
    if source == "research":
        payload, report_label = _load_with_pack(report_path, prefer_pack_first=True)
    elif source == "qa" and (is_pack_path or not report_path.exists()):
        payload, report_label = _load_with_pack(report_path, prefer_pack_first=True)
    else:
        report_label = runtime.rel_path(report_path, target)
        if not report_path.exists():
            raise FileNotFoundError(f"{source} report not found at {report_label}")
        payload = runtime.load_json_file(report_path)
    if source == "qa":
        derived_blocks = _derive_tasks_from_findings("QA", payload, report_label)
        derived_blocks.extend(_derive_tasks_from_tests(payload, report_label))
    elif source == "review":
        derived_blocks = _derive_tasks_from_findings("Review", payload, report_label)
    elif source == "research":
        derived_blocks = _derive_tasks_from_rlm_pack(payload, report_label)
    else:
        derived_blocks = []

    derived_blocks = _dedupe_task_blocks(derived_blocks)
    if source == "research":
        derived_blocks = _filter_research_handoff_blocks(derived_blocks)
        if not derived_blocks:
            print(f"[aidd] no actionable research tasks found in {report_label}.")
    else:
        if not derived_blocks:
            derived_blocks = _dedupe_task_blocks(_derive_handoff_placeholder(source, ticket, report_label))
        if not derived_blocks:
            print(f"[aidd] no tasks found in {source} report ({report_label}).")
            return 0

    derived_tasks = _flatten_task_blocks(derived_blocks)

    tasklist_rel = Path("docs") / "tasklist" / f"{ticket}.md"
    tasklist_path = target / tasklist_rel
    if not tasklist_path.exists():
        raise FileNotFoundError(
            f"tasklist not found at {tasklist_rel}; create it via /feature-dev-aidd:tasks-new {ticket}."
        )
    tasklist_text = tasklist_path.read_text(encoding="utf-8")
    if source == "research" and not derived_tasks:
        existing_start, _, _ = _extract_handoff_block(tasklist_text.splitlines(), source)
        if existing_start == -1:
            return 0

    updated_text, heading_label, changed = _apply_handoff_tasks(
        tasklist_text,
        source=source,
        report_label=report_label,
        tasks=derived_tasks,
        append=bool(args.append),
        section_candidates=_HANDOFF_SECTION_HINTS.get(source, ()),
    )

    section_display = heading_label or "end of file"
    if args.dry_run:
        print(
            f"[aidd] (dry-run) {len(derived_blocks)} task(s) "
            f"from {source} → {tasklist_rel} (section: {section_display})"
        )
        for block in derived_blocks:
            for line in block:
                print(f"  {line}")
        return 0

    if not changed:
        print(f"[aidd] tasklist already up to date for {source} report ({report_label}).")
        return 0

    tasklist_path.write_text(updated_text, encoding="utf-8")
    print(
        f"[aidd] added {len(derived_blocks)} task(s) "
        f"from {source} report ({report_label}) to {tasklist_rel} "
        f"(section: {section_display}; mode={'append' if args.append else 'replace'})."
    )
    runtime.maybe_sync_index(target, ticket, slug_hint or None, reason="tasks-derive")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
