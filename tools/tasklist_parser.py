from __future__ import annotations

import re
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
