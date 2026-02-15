from __future__ import annotations

import json
import re
import shlex
from typing import Dict, List, Optional, Tuple


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


PATH_TOKEN_RE = re.compile(
    r"(?:[A-Za-z0-9_.-]+/)+[A-Za-z0-9_.*/-]+|\b[A-Za-z0-9_.-]+\.[A-Za-z0-9_.-]+\b"
)
TASK_COMMAND_PREFIX_RE = re.compile(r"^(?P<label>[A-Za-z][A-Za-z0-9 _/+-]{2,40}):\s*(?P<command>.+)$")
COMMAND_LIKE_RE = re.compile(r"^(?:\./\S+|/\S+|[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)+|[A-Za-z0-9_.-]+)(?:\s|$)")
NON_COMMAND_TASK_HINT_RE = re.compile(
    r"\b(?:per-iteration(?:\s+test)?\s+commands?|iteration-specific\s+patterns?|test\s+commands?\s+listed\s+below|commands?\s+listed\s+below|see\s+below)\b",
    re.IGNORECASE,
)

SECTION_HEADER_RE = re.compile(r"^##\s+(.+?)\s*$")


def _dedupe(items: List[str]) -> List[str]:
    seen = set()
    deduped: List[str] = []
    for item in items:
        key = item.strip()
        if not key or key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped


def _extract_paths_from_brackets(text: str) -> List[str]:
    results: List[str] = []
    for match in re.findall(r"\[([^\]]+)\]", text):
        parts = re.split(r"[,\n]", match)
        for part in parts:
            cleaned = part.strip().strip("`'\" ")
            if cleaned:
                results.append(cleaned)
    return results


def _extract_paths_from_text(text: str) -> List[str]:
    candidates: List[str] = []
    candidates.extend(_extract_paths_from_brackets(text))
    for match in PATH_TOKEN_RE.findall(text):
        cleaned = match.strip().strip("`'\" ,;)")
        if cleaned:
            candidates.append(cleaned)
    return candidates


def extract_boundaries(lines: List[str]) -> Tuple[List[str], List[str], bool]:
    """Return (allowed_paths, forbidden_paths, has_boundaries)."""
    items = extract_list_field(lines, "Boundaries")
    scalar = extract_scalar_field(lines, "Boundaries")
    has_boundaries = bool(items or scalar)
    if not items and scalar:
        items = [scalar]
    allowed: List[str] = []
    forbidden: List[str] = []
    for item in items:
        lower = item.lower()
        paths = _extract_paths_from_text(item)
        if not paths:
            continue
        if any(token in lower for token in ("must-not-touch", "forbidden", "do not", "not touch")):
            forbidden.extend(paths)
        elif "must-touch" in lower or "allowed" in lower:
            allowed.extend(paths)
        else:
            allowed.extend(paths)
    return _dedupe(allowed), _dedupe(forbidden), has_boundaries


def extract_section(lines: List[str], title: str) -> List[str]:
    """Return section body lines for a given heading (without the heading line)."""
    in_section = False
    collected: List[str] = []
    for line in lines:
        match = SECTION_HEADER_RE.match(line)
        if match:
            heading = match.group(1).strip()
            if in_section:
                break
            if heading == title:
                in_section = True
            continue
        if in_section:
            collected.append(line)
    return collected


def _parse_inline_sequence(raw: str, *, split_pattern: str) -> List[str]:
    text = raw.strip()
    if not text:
        return []
    if text.startswith("[") and text.endswith("]"):
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            payload = None
        if isinstance(payload, list):
            values: List[str] = []
            for item in payload:
                value = _strip_placeholder(str(item))
                if value:
                    values.append(value)
            return values
        text = text[1:-1].strip()
        if not text:
            return []
        parts = [part.strip().strip("'\"") for part in re.split(r"\s*,\s*", text) if part.strip()]
    else:
        parts = [part.strip() for part in re.split(split_pattern, text) if part.strip()]
    values: List[str] = []
    for part in parts:
        value = _strip_placeholder(part)
        if value:
            values.append(value)
    return values


def normalize_test_execution_task(raw: str) -> str:
    value = _strip_placeholder(raw)
    if not value:
        return ""
    text = value.strip()
    if text.startswith("`") and text.endswith("`"):
        text = text[1:-1].strip()
    match = TASK_COMMAND_PREFIX_RE.match(text)
    if not match:
        return text
    command = match.group("command").strip()
    if not command:
        return text
    if not COMMAND_LIKE_RE.match(command):
        return text
    return command


def _looks_like_executable_task(command: str) -> bool:
    value = str(command or "").strip()
    if not value:
        return False
    if NON_COMMAND_TASK_HINT_RE.search(value):
        return False
    lowered = value.lower()
    if lowered in {"none", "n/a", "not set", "tbd"}:
        return False
    try:
        parts = shlex.split(value)
    except ValueError:
        return False
    if not parts:
        return False
    head = parts[0].strip()
    if not head:
        return False
    if head.lower() in {"none", "n/a", "not", "tbd"}:
        return False
    # Standalone shell builtins are not valid task entries for subprocess-based QA execution.
    if head == "cd":
        return False
    return bool(COMMAND_LIKE_RE.match(head))


def detect_shell_chain_token(command: str) -> str:
    """Return shell-chain token when a single task entry encodes chained commands."""
    value = str(command or "")
    if not value:
        return ""
    in_single = False
    in_double = False
    escaped = False
    idx = 0
    while idx < len(value):
        ch = value[idx]
        if escaped:
            escaped = False
            idx += 1
            continue
        if ch == "\\":
            escaped = True
            idx += 1
            continue
        if ch == "'" and not in_double:
            in_single = not in_single
            idx += 1
            continue
        if ch == '"' and not in_single:
            in_double = not in_double
            idx += 1
            continue
        if in_single or in_double:
            idx += 1
            continue
        if value.startswith("&&", idx):
            return "&&"
        if value.startswith("||", idx):
            return "||"
        if ch == ";":
            return ";"
        idx += 1
    return ""


def parse_test_execution(lines: List[str]) -> Dict[str, object]:
    profile = (extract_scalar_field(lines, "profile") or "").strip()
    tasks_raw = extract_scalar_field(lines, "tasks") or ""
    filters_raw = extract_scalar_field(lines, "filters") or ""
    when = (extract_scalar_field(lines, "when") or "").strip()
    reason = (extract_scalar_field(lines, "reason") or "").strip()
    tasks_list = extract_list_field(lines, "tasks")
    filters_list = extract_list_field(lines, "filters")
    tasks: List[str] = []
    if tasks_list:
        tasks = tasks_list
    elif tasks_raw:
        tasks = _parse_inline_sequence(tasks_raw, split_pattern=r"\s*;\s*")
    normalized_tasks: List[str] = []
    malformed_tasks: List[Dict[str, str]] = []
    for raw_task in tasks:
        normalized = normalize_test_execution_task(str(raw_task))
        if normalized:
            if not _looks_like_executable_task(normalized):
                malformed_tasks.append(
                    {
                        "task": normalized,
                        "reason_code": "tasklist_non_command_entry",
                        "token": "",
                    }
                )
                continue
            chain_token = detect_shell_chain_token(normalized)
            if chain_token:
                malformed_tasks.append(
                    {
                        "task": normalized,
                        "reason_code": "tasklist_shell_chain_single_entry",
                        "token": chain_token,
                    }
                )
                continue
            normalized_tasks.append(normalized)
    tasks = normalized_tasks
    filters: List[str] = []
    if filters_list:
        filters = filters_list
    elif filters_raw:
        filters = _parse_inline_sequence(filters_raw, split_pattern=r"\s*,\s*")
    return {
        "profile": profile,
        "tasks": tasks,
        "malformed_tasks": malformed_tasks,
        "filters": filters,
        "when": when,
        "reason": reason,
    }
