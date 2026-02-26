#!/usr/bin/env python3
"""Shared helpers for parsing the PRD Review markdown section."""

from __future__ import annotations

import re
from typing import Callable, List, Tuple

PRD_REVIEW_HEADER_RE = re.compile(r"^##\s+(?:\d+\.\s+)?PRD\s+Review\s*$", re.IGNORECASE)
MARKDOWN_H2_RE = re.compile(r"^##\s+")


def is_markdown_h2(line: str) -> bool:
    return bool(MARKDOWN_H2_RE.match(str(line or "").strip()))


def is_prd_review_header(line: str) -> bool:
    return bool(PRD_REVIEW_HEADER_RE.match(str(line or "").strip()))


def extract_prd_review_section(
    content: str,
    *,
    normalize_status: Callable[[str], str] | None = None,
) -> Tuple[bool, str, List[str]]:
    """Return (found, status, action_items) for PRD Review section."""

    inside_section = False
    found_section = False
    status = ""
    action_items: List[str] = []
    for raw in str(content or "").splitlines():
        stripped = raw.strip()
        if is_markdown_h2(stripped):
            inside_section = is_prd_review_header(stripped)
            if inside_section:
                found_section = True
            continue
        if not inside_section:
            continue
        lower = stripped.lower()
        if lower.startswith("status:"):
            value = stripped.split(":", 1)[1].strip()
            if normalize_status:
                value = normalize_status(value)
            status = value
        elif stripped.startswith("- ["):
            action_items.append(stripped)
    return found_section, status, action_items
