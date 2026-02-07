#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional, Tuple

from hooks.hooklib import load_config, resolve_aidd_root, resolve_context_gc_mode


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


def _extract_pack_excerpt(md: str, max_lines: int, max_chars: int) -> Optional[str]:
    text = md.strip()
    if not text:
        return None
    if max_lines > 0:
        text_lines = text.splitlines()
        if len(text_lines) > max_lines:
            text_lines = text_lines[:max_lines]
        text = "\n".join(text_lines).strip()
    if max_chars > 0 and len(text) > max_chars:
        text = text[:max_chars].rstrip()
    return text or None


def _rel_to_root(root: Path, path: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


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
    if resolve_context_gc_mode(cfg) == "off":
        return WorkingSet(text="", ticket=None, slug=None)

    ws_cfg = cfg.get("working_set", {})
    max_chars = int(ws_cfg.get("max_chars", 6000))
    max_tasks = int(ws_cfg.get("max_tasks", 25))
    pack_max_lines = int(ws_cfg.get("context_pack_max_lines", 20))
    pack_max_chars = int(ws_cfg.get("context_pack_max_chars", 1200))

    ticket = None
    slug = None
    stage = None

    if aidd_root:
        state_path = aidd_root / "docs" / ".active.json"
        if state_path.exists():
            try:
                payload = json.loads(state_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                payload = {}
            if isinstance(payload, dict):
                slug = str(payload.get("slug_hint") or "").strip() or None
                ticket = str(payload.get("ticket") or "").strip() or None
                stage = str(payload.get("stage") or "").strip() or None
        if ticket is None:
            ticket = slug

    parts: List[str] = []
    now = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
    parts.append("### AIDD Working Set (auto-generated)")
    parts.append(f"- Generated: {now}")
    if ticket:
        parts.append(f"- Ticket: {ticket}" + (f" (slug: {slug})" if slug else ""))
    if stage:
        parts.append(f"- Stage: {stage}")
    parts.append("")

    if aidd_root and ticket:
        context_pack_path = aidd_root / "reports" / "context" / f"{ticket}.pack.md"
        tasklist = aidd_root / "docs" / "tasklist" / f"{ticket}.md"
        if context_pack_path.exists():
            md = _strip_long_code_blocks(_read_text(context_pack_path))
            excerpt = _extract_pack_excerpt(md, pack_max_lines, pack_max_chars)
            if excerpt:
                parts.append("#### Context Pack (rolling)")
                parts.append(excerpt)
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
