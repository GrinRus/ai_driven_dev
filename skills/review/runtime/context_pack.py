#!/usr/bin/env python3
"""Build a compact context pack from a template."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Optional

from aidd_runtime import runtime
from aidd_runtime.io_utils import utc_timestamp

DEFAULT_TEMPLATE = Path("reports") / "context" / "template.context-pack.md"


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""


def _replace_list_section(lines: list[str], header: str, items: list[str]) -> list[str]:
    for idx, line in enumerate(lines):
        if line.strip() != f"{header}:":
            continue
        start = idx + 1
        end = start
        while end < len(lines):
            if lines[end].lstrip().startswith("-"):
                end += 1
                continue
            break
        replacement = [f"- {item}" for item in items] if items else ["- n/a"]
        return lines[:start] + replacement + lines[end:]
    return lines


def _replace_first_list_item(lines: list[str], heading: str, value: str) -> list[str]:
    for idx, line in enumerate(lines):
        if line.strip() != heading:
            continue
        for j in range(idx + 1, len(lines)):
            if lines[j].lstrip().startswith("-"):
                lines[j] = f"- {value or 'n/a'}"
                return lines
            if lines[j].startswith("## "):
                break
        break
    return lines


def _apply_template(
    root: Path,
    *,
    ticket: str,
    agent: str,
    stage: str,
    template_path: Path,
    read_next: list[str],
    artefact_links: list[str],
    what_to_do: str,
    user_note: str,
) -> str:
    template_text = _read_text(template_path)
    if not template_text:
        raise FileNotFoundError(f"context pack template not found at {template_path}")
    scope_key = ""
    if stage in {"implement", "review"}:
        work_item_key = runtime.read_active_work_item(root)
        if work_item_key:
            scope_key = runtime.resolve_scope_key(work_item_key, ticket)
    replacements = {
        "<ticket>": ticket,
        "<stage>": stage,
        "<agent>": agent,
        "<UTC ISO-8601>": utc_timestamp(),
        "<scope_key>": scope_key or "n/a",
    }
    lines = template_text.splitlines()
    lines = [line for line in lines if "Fill stage/agent/read_next/artefact_links" not in line]
    lines = [line.replace("<read_next>", "n/a") for line in lines]
    for idx, line in enumerate(lines):
        for placeholder, value in replacements.items():
            if placeholder in line:
                lines[idx] = line.replace(placeholder, value)
    lines = _replace_list_section(lines, "read_next", read_next)
    lines = _replace_list_section(lines, "artefact_links", artefact_links)
    lines = _replace_first_list_item(lines, "## What to do now", what_to_do or "n/a")
    lines = _replace_first_list_item(lines, "## User note", user_note or "n/a")
    lines = _replace_first_list_item(lines, "## AIDD:READ_LOG", "n/a")

    content = "\n".join(lines).rstrip() + "\n"
    if "<stage-specific goal>" in content or "<arguments/note>" in content or "<" in content and ">" in content:
        print(
            "[aidd] WARN: context pack template placeholders remain; fill read_next/what_to_do/artefact_links.",
            file=sys.stderr,
        )
    if not read_next:
        print("[aidd] WARN: context pack missing read_next entries.", file=sys.stderr)
    if not artefact_links:
        print("[aidd] WARN: context pack missing artefact_links entries.", file=sys.stderr)
    if not what_to_do:
        print("[aidd] WARN: context pack missing what_to_do value.", file=sys.stderr)
    return content


def build_context_pack(
    root: Path,
    ticket: str,
    agent: str,
    *,
    stage: str = "",
    template_path: Optional[Path] = None,
    read_next: Optional[list[str]] = None,
    artefact_links: Optional[list[str]] = None,
    what_to_do: str = "",
    user_note: str = "",
) -> str:
    resolved_stage = stage.strip() or agent
    if not resolved_stage:
        raise ValueError("stage is required when using template packs")
    if template_path is None:
        template_path = root / DEFAULT_TEMPLATE
    return _apply_template(
        root,
        ticket=ticket,
        agent=agent,
        stage=resolved_stage,
        template_path=template_path,
        read_next=read_next or [],
        artefact_links=artefact_links or [],
        what_to_do=what_to_do,
        user_note=user_note,
    )


def write_context_pack(
    root: Path,
    *,
    ticket: str,
    agent: str,
    stage: str = "",
    template_path: Optional[Path] = None,
    output: Optional[Path] = None,
    read_next: Optional[list[str]] = None,
    artefact_links: Optional[list[str]] = None,
    what_to_do: str = "",
    user_note: str = "",
) -> Path:
    if output is None:
        output = root / "reports" / "context" / f"{ticket}.pack.md"
    output.parent.mkdir(parents=True, exist_ok=True)
    content = build_context_pack(
        root,
        ticket,
        agent,
        stage=stage,
        template_path=template_path,
        read_next=read_next,
        artefact_links=artefact_links,
        what_to_do=what_to_do,
        user_note=user_note,
    )
    output.write_text(content, encoding="utf-8")
    return output


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a compact context pack from a template.",
    )
    parser.add_argument(
        "--ticket",
        dest="ticket",
        help="Ticket identifier to pack (defaults to docs/.active.json).",
    )
    parser.add_argument(
        "--slug-hint",
        dest="slug_hint",
        help="Optional slug hint override (defaults to docs/.active.json).",
    )
    parser.add_argument(
        "--agent",
        help="Agent name to embed in the pack filename.",
    )
    parser.add_argument(
        "--stage",
        help="Optional stage name for template-based packs (defaults to agent).",
    )
    parser.add_argument(
        "--template",
        help="Optional template path (defaults to aidd/reports/context/template.context-pack.md).",
    )
    parser.add_argument(
        "--output",
        help="Optional output path override (default: aidd/reports/context/<ticket>.pack.md).",
    )
    parser.add_argument(
        "--read-next",
        action="append",
        help="Repeatable read_next entry for the context pack.",
    )
    parser.add_argument(
        "--artefact-link",
        action="append",
        help="Repeatable artefact link entry (e.g., 'prd: aidd/docs/prd/TICKET.prd.md').",
    )
    parser.add_argument(
        "--what-to-do",
        help="Single-line 'What to do now' entry for the context pack.",
    )
    parser.add_argument(
        "--user-note",
        help="Optional user note to store in the context pack.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    _, target = runtime.require_workflow_root()
    ticket, context = runtime.require_ticket(
        target,
        ticket=getattr(args, "ticket", None),
        slug_hint=getattr(args, "slug_hint", None),
    )
    agent = (args.agent or "").strip()
    if not agent:
        raise ValueError("agent name is required (use --agent <name>)")
    template_path = Path(args.template) if args.template else None
    if template_path is not None:
        template_path = runtime.resolve_path_for_target(template_path, target)
    output = Path(args.output) if args.output else None
    if output is not None:
        output = runtime.resolve_path_for_target(output, target)

    pack_path = write_context_pack(
        target,
        ticket=ticket,
        agent=agent,
        stage=(args.stage or "").strip(),
        template_path=template_path,
        output=output,
        read_next=[item for item in (args.read_next or []) if item],
        artefact_links=[item for item in (args.artefact_link or []) if item],
        what_to_do=(args.what_to_do or "").strip(),
        user_note=(args.user_note or "").strip(),
    )
    rel = runtime.rel_path(pack_path, target)
    print(f"[aidd] context pack saved to {rel}.")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
