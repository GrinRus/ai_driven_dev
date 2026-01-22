#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional, Tuple

from hooks.hooklib import load_config, resolve_aidd_root


CODE_FENCE_RE = re.compile(r"^```")
TASK_RE = re.compile(r"^\s*-\s*\[\s*\]\s+(.*)$")
DONE_TASK_RE = re.compile(r"^\s*-\s*\[\s*[xX]\s*\]\s+(.*)$")
CONTEXT_PACK_RE = re.compile(r"^##\s*AIDD:CONTEXT_PACK\b", re.IGNORECASE)
HEADING_RE = re.compile(r"^##\s+")


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


def _extract_context_pack(md: str, max_lines: int, max_chars: int) -> Optional[str]:
    lines = md.splitlines()
    start = None
    for idx, line in enumerate(lines):
        if CONTEXT_PACK_RE.match(line.strip()):
            start = idx + 1
            break
    if start is None:
        return None
    collected: List[str] = []
    for line in lines[start:]:
        if HEADING_RE.match(line) and not CONTEXT_PACK_RE.match(line.strip()):
            break
        collected.append(line)
    text = "\n".join(collected).strip()
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


def _find_graph_artifacts(aidd_root: Path, ticket: str) -> dict:
    context_path = aidd_root / "reports" / "research" / f"{ticket}-context.json"
    edges_path: Optional[Path] = None
    if context_path.exists():
        try:
            payload = json.loads(context_path.read_text(encoding="utf-8"))
        except Exception:
            payload = {}
        edges_raw = payload.get("call_graph_edges_path")
        if isinstance(edges_raw, str) and edges_raw:
            edges_path = aidd_root / edges_raw if not Path(edges_raw).is_absolute() else Path(edges_raw)
    if edges_path is None:
        candidate = aidd_root / "reports" / "research" / f"{ticket}-call-graph.edges.jsonl"
        if candidate.exists():
            edges_path = candidate
    pack_path = None
    for suffix in (".pack.yaml", ".pack.toon"):
        candidate = aidd_root / "reports" / "research" / f"{ticket}-call-graph{suffix}"
        if candidate.exists():
            pack_path = candidate
            break
    return {
        "pack": _rel_to_root(aidd_root, pack_path) if pack_path else None,
        "edges": _rel_to_root(aidd_root, edges_path) if edges_path else None,
    }


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
    pack_max_lines = int(ws_cfg.get("context_pack_max_lines", 20))
    pack_max_chars = int(ws_cfg.get("context_pack_max_chars", 1200))

    ticket = None
    slug = None
    stage = None

    if aidd_root:
        ticket_path = aidd_root / "docs" / ".active_ticket"
        slug_path = aidd_root / "docs" / ".active_feature"
        stage_path = aidd_root / "docs" / ".active_stage"
        if ticket_path.exists():
            ticket = ticket_path.read_text(encoding="utf-8", errors="replace").strip() or None
        if slug_path.exists():
            slug = slug_path.read_text(encoding="utf-8", errors="replace").strip() or None
        if stage_path.exists():
            stage = stage_path.read_text(encoding="utf-8", errors="replace").strip() or None

    parts: List[str] = []
    now = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
    parts.append("### AIDD Working Set (auto-generated)")
    parts.append(f"- Generated: {now}")
    if ticket:
        parts.append(f"- Ticket: {ticket}" + (f" (slug: {slug})" if slug else ""))
    if stage:
        parts.append(f"- Stage: {stage}")
        if aidd_root:
            anchor_path = aidd_root / "docs" / "anchors" / f"{stage}.md"
            if anchor_path.exists():
                rel_anchor = anchor_path.relative_to(aidd_root).as_posix()
                parts.append(f"- Stage anchor: {rel_anchor}")
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

        graph_artifacts = _find_graph_artifacts(aidd_root, ticket)
        if graph_artifacts.get("pack") or graph_artifacts.get("edges"):
            parts.append("#### Call Graph (pack-first)")
            if graph_artifacts.get("pack"):
                parts.append(f"- Pack: {graph_artifacts['pack']}")
            if graph_artifacts.get("edges"):
                parts.append(
                    f"- Slice (prefer): ${{CLAUDE_PLUGIN_ROOT}}/tools/graph-slice.sh --ticket {ticket} --query \"<token>\""
                )
                parts.append(f"- Edges view (spot-check): {graph_artifacts['edges']}")
                parts.append(f"- Spot-check: rg \"<token>\" {graph_artifacts['edges']}")
            parts.append("")

        if tasklist.exists():
            md = _read_text(tasklist)
            context_pack = _extract_context_pack(md, pack_max_lines, pack_max_chars)
            todos, done, total = _extract_tasks(md, max_tasks=max_tasks)
            if context_pack:
                parts.append("#### Context Pack")
                parts.append(context_pack)
                parts.append("")
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
