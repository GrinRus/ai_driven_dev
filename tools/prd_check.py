#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import List, Optional

from tools import runtime


STATUS_RE = re.compile(r"^\s*Status:\s*([A-Za-z]+)", re.MULTILINE)


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate PRD Status: READY.")
    parser.add_argument("--ticket", help="Ticket identifier (defaults to docs/.active_ticket).")
    parser.add_argument("--prd", help="Override PRD path.")
    return parser.parse_args(argv)


def _resolve_prd_path(project_root: Path, ticket: str, override: Optional[str]) -> Path:
    if override:
        return runtime.resolve_path_for_target(Path(override), project_root)
    return project_root / "docs" / "prd" / f"{ticket}.prd.md"


def main(argv: Optional[List[str]] = None) -> int:
    args = parse_args(argv)
    _, project_root = runtime.require_workflow_root()
    ticket, _ = runtime.require_ticket(project_root, ticket=args.ticket, slug_hint=None)

    prd_path = _resolve_prd_path(project_root, ticket, args.prd)
    if not prd_path.exists():
        rel = runtime.rel_path(prd_path, project_root)
        raise SystemExit(f"BLOCK: PRD не найден: {rel}")

    text = prd_path.read_text(encoding="utf-8")
    match = STATUS_RE.search(text)
    if not match:
        raise SystemExit("BLOCK: PRD не содержит строку `Status:` → установите Status: READY перед plan-new.")

    status = match.group(1).strip().upper()
    if status != "READY":
        raise SystemExit(
            f"BLOCK: PRD Status: {status} → установите Status: READY перед /feature-dev-aidd:plan-new {ticket}."
        )

    print(f"[aidd] PRD ready for `{ticket}` (status: READY).")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
