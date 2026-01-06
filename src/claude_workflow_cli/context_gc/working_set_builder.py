#!/usr/bin/env python3
from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional, Tuple

from .hooklib import load_config, resolve_aidd_root


CODE_FENCE_RE = re.compile(r"^```")
TASK_RE = re.compile(r"^\s*-\s*\[\s*\]\s+(.*)$")
DONE_TASK_RE = re.compile(r"^\s*-\s*\[\s*[xX]\s*\]\s+(.*)$")


@dataclass(frozen=True)
class WorkingSet:
    text: str
    ticket: Optional[str]
    slug: Optional[str]


def _read_text(path: Path, max_bytes: int = 300_000) -> str:
    if not path.exists():
        return ""
    try:
        data = path.read_bytes()
        if len(data) > max_bytes:
            data = data[:max_bytes]
        return data.decode("utf-8", errors="replace")
    except Exception:
        return ""


def _strip_long_code_blocks(md: str, max_block_lines: int = 25) -> str:
    lines = md.splitlines()
    out: List[str] = []
    in_fence = False
    fence_lines = 0
    for line in lines:
        if CODE_FENCE_RE.match(line.strip()):
            in_fence = not in_fence
            fence_lines = 0
            out.append(line)
            continue
        if in_fence:
            fence_lines += 1
            if fence_lines <= max_block_lines:
                out.append(line)
            elif fence_lines == max_block_lines + 1:
                out.append("... (code block truncated) ...")
            continue
        out.append(line)
    return "\n".join(out)


def _extract_status_line(md: str) -> Optional[str]:
    for line in md.splitlines()[:80]:
        if line.lower().startswith("status:"):
            return line.strip()
    return None


def _extract_heading_title(md: str) -> Optional[str]:
    for line in md.splitlines()[:40]:
        if line.startswith("#"):
            return line.strip()
    return None


def _extract_tasks(md: str, max_tasks: int) -> Tuple[List[str], int, int]:
    todos: List[str] = []
    total = 0
    done = 0
    for line in md.splitlines():
        m1 = TASK_RE.match(line)
        m2 = DONE_TASK_RE.match(line)
        if m1:
            total += 1
            if len(todos) < max_tasks:
                todos.append("- [ ] " + m1.group(1).strip())
        elif m2:
            total += 1
            done += 1
    return todos, done, total


def _run_git(project_dir: Path, args: List[str], timeout: float = 1.5) -> Optional[str]:
    try:
        proc = subprocess.run(
            ["git", "-C", str(project_dir), *args],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        if proc.returncode != 0:
            return None
        return proc.stdout.strip()
    except Exception:
        return None


def build_working_set(project_dir: Path) -> WorkingSet:
    aidd_root = resolve_aidd_root(project_dir)
    cfg = load_config(aidd_root)
    if not cfg.get("enabled", True):
        return WorkingSet(text="", ticket=None, slug=None)

    ws_cfg = cfg.get("working_set", {})
    max_chars = int(ws_cfg.get("max_chars", 6000))
    max_tasks = int(ws_cfg.get("max_tasks", 25))

    ticket = None
    slug = None

    if aidd_root:
        ticket_path = aidd_root / "docs" / ".active_ticket"
        slug_path = aidd_root / "docs" / ".active_feature"
        if ticket_path.exists():
            ticket = ticket_path.read_text(encoding="utf-8", errors="replace").strip() or None
        if slug_path.exists():
            slug = slug_path.read_text(encoding="utf-8", errors="replace").strip() or None

    parts: List[str] = []
    now = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
    parts.append("### AIDD Working Set (auto-generated)")
    parts.append(f"- Generated: {now}")
    if ticket:
        parts.append(f"- Ticket: {ticket}" + (f" (slug: {slug})" if slug else ""))
    parts.append("")

    if aidd_root and ticket:
        prd = aidd_root / "docs" / "prd" / f"{ticket}.prd.md"
        tasklist = aidd_root / "docs" / "tasklist" / f"{ticket}.md"
        research = aidd_root / "docs" / "research" / f"{ticket}.md"

        if prd.exists():
            md = _strip_long_code_blocks(_read_text(prd))
            title = _extract_heading_title(md)
            status = _extract_status_line(md)
            parts.append("#### PRD")
            if title:
                parts.append(f"- {title}")
            if status:
                parts.append(f"- {status}")
            excerpt = "\n".join(md.splitlines()[:220]).strip()
            if excerpt:
                parts.append("")
                parts.append(excerpt[:1500].rstrip())
                parts.append("")

        if research.exists():
            md = _strip_long_code_blocks(_read_text(research))
            parts.append("#### Research (excerpt)")
            parts.append(md[:1200].rstrip())
            parts.append("")

        if tasklist.exists():
            md = _read_text(tasklist)
            todos, done, total = _extract_tasks(md, max_tasks=max_tasks)
            parts.append("#### Tasklist")
            if total:
                parts.append(f"- Progress: {done}/{total} done")
            if todos:
                parts.extend(todos)
            parts.append("")

    if ws_cfg.get("include_git_status", True):
        branch = _run_git(project_dir, ["rev-parse", "--abbrev-ref", "HEAD"])
        status = _run_git(project_dir, ["status", "--porcelain", "-uno"])
        if branch or status:
            parts.append("#### Repo state")
            if branch:
                parts.append(f"- Branch: {branch}")
            if status:
                lines = status.splitlines()
                max_lines = int(ws_cfg.get("max_git_status_lines", 60))
                lines = lines[:max_lines]
                parts.append(f"- Dirty files: {len(lines)}")
                for line in lines[: min(10, len(lines))]:
                    parts.append(f"  - {line}")
            parts.append("")

    text = "\n".join(parts).strip()
    if len(text) > max_chars:
        text = text[: max_chars - 120].rstrip() + "\n\n... (truncated)\n"

    return WorkingSet(text=text, ticket=ticket, slug=slug)
