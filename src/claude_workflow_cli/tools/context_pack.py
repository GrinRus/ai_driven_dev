#!/usr/bin/env python3
"""Build a compact context pack from AIDD anchors."""

from __future__ import annotations

import datetime as dt
import re
from pathlib import Path
from typing import Iterable, List, Optional, Tuple

SECTION_RE = re.compile(r"^##\s+(AIDD:[A-Z0-9_]+)\b", re.IGNORECASE)
HEADING_RE = re.compile(r"^##\s+")


def _utc_timestamp() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""


def extract_aidd_sections(text: str) -> List[Tuple[str, str]]:
    lines = text.splitlines()
    sections: List[Tuple[str, str]] = []
    index = 0
    while index < len(lines):
        line = lines[index].strip()
        match = SECTION_RE.match(line)
        if not match:
            index += 1
            continue
        name = match.group(1).upper()
        index += 1
        collected: List[str] = []
        while index < len(lines):
            if HEADING_RE.match(lines[index].strip()):
                break
            collected.append(lines[index].rstrip())
            index += 1
        content = "\n".join(collected).strip()
        if content:
            sections.append((name, content))
    return sections


def _format_sections(title: str, sections: Iterable[Tuple[str, str]]) -> List[str]:
    lines: List[str] = []
    section_list = list(sections)
    if not section_list:
        return lines
    lines.append(f"## {title}")
    for name, content in section_list:
        lines.append(f"### {name}")
        lines.append(content)
        lines.append("")
    return lines


def build_context_pack(root: Path, ticket: str, agent: str) -> str:
    prd_path = root / "docs" / "prd" / f"{ticket}.prd.md"
    plan_path = root / "docs" / "plan" / f"{ticket}.md"
    tasklist_path = root / "docs" / "tasklist" / f"{ticket}.md"

    prd_sections = extract_aidd_sections(_read_text(prd_path)) if prd_path.exists() else []
    plan_sections = extract_aidd_sections(_read_text(plan_path)) if plan_path.exists() else []
    tasklist_sections = extract_aidd_sections(_read_text(tasklist_path)) if tasklist_path.exists() else []

    parts: List[str] = []
    parts.append(f"# Context Pack — {ticket} ({agent})")
    parts.append(f"Generated: {_utc_timestamp()}")
    parts.append("Sources:")
    if prd_path.exists():
        parts.append(f"- PRD: {prd_path.as_posix()}")
    if plan_path.exists():
        parts.append(f"- Plan: {plan_path.as_posix()}")
    if tasklist_path.exists():
        parts.append(f"- Tasklist: {tasklist_path.as_posix()}")
    parts.append("")

    parts.extend(_format_sections("Tasklist anchors", tasklist_sections))
    parts.extend(_format_sections("Plan anchors", plan_sections))
    parts.extend(_format_sections("PRD anchors", prd_sections))

    return "\n".join(parts).rstrip() + "\n"


def write_context_pack(
    root: Path,
    *,
    ticket: str,
    agent: str,
    output: Optional[Path] = None,
) -> Path:
    if output is None:
        output = root / "reports" / "context" / f"{ticket}-{agent}.md"
    output.parent.mkdir(parents=True, exist_ok=True)
    content = build_context_pack(root, ticket, agent)
    output.write_text(content, encoding="utf-8")
    return output

