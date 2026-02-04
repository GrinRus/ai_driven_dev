#!/usr/bin/env python3
"""Build a compact context pack from a template."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Optional

from tools import runtime
from tools.io_utils import utc_timestamp

DEFAULT_TEMPLATE = Path("reports") / "context" / "template.context-pack.md"


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""


def _apply_template(
    root: Path,
    *,
    ticket: str,
    agent: str,
    stage: str,
    template_path: Path,
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
        "<scope_key>": scope_key or "<scope_key>",
    }
    content = template_text
    for placeholder, value in replacements.items():
        content = content.replace(placeholder, value)
    if "<stage-specific goal>" in content:
        print(
            "[aidd] WARN: context pack template placeholder '<stage-specific goal>' remains.",
            file=sys.stderr,
        )
    return content.rstrip() + "\n"


def build_context_pack(
    root: Path,
    ticket: str,
    agent: str,
    *,
    stage: str = "",
    template_path: Optional[Path] = None,
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
    )


def write_context_pack(
    root: Path,
    *,
    ticket: str,
    agent: str,
    stage: str = "",
    template_path: Optional[Path] = None,
    output: Optional[Path] = None,
) -> Path:
    if output is None:
        output = root / "reports" / "context" / f"{ticket}.pack.md"
    output.parent.mkdir(parents=True, exist_ok=True)
    content = build_context_pack(root, ticket, agent, stage=stage, template_path=template_path)
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
    )
    rel = runtime.rel_path(pack_path, target)
    print(f"[aidd] context pack saved to {rel}.")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
