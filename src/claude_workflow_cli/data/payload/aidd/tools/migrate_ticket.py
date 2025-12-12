#!/usr/bin/env python3
"""Migrate repositories from slug-first workflow to the new ticket-first layout."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Iterable, Tuple


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Upgrade workflow artefacts to the ticket-first format. "
            "Creates docs/.active_ticket (under aidd/) when missing and injects Ticket/Slug hint front-matter "
            "into docs/tasklist/*.md."
        )
    )
    parser.add_argument(
        "--target",
        default="aidd",
        help="Project root containing docs/.active_feature (default: aidd/ under the workspace).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the actions that would be performed without modifying files.",
    )
    return parser.parse_args()


def read_text(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return None


def ensure_active_ticket(root: Path, *, dry_run: bool) -> Tuple[bool, str | None]:
    docs_dir = root / "docs"
    slug_file = docs_dir / ".active_feature"
    ticket_file = docs_dir / ".active_ticket"

    slug_value = read_text(slug_file)
    ticket_value_raw = read_text(ticket_file)
    ticket_value = ticket_value_raw.strip() if ticket_value_raw else ""

    if ticket_value:
        return False, ticket_value

    if not slug_value:
        return False, None

    slug_value = slug_value.strip()
    if not slug_value:
        return False, None

    if dry_run:
        print(f"[dry-run] write {ticket_file} ← {slug_value}")
    else:
        ticket_file.write_text(slug_value + "\n", encoding="utf-8")
        print(f"[migrate] created {ticket_file} from .active_feature")
    return True, slug_value


def migrate_tasklist_file(path: Path, *, dry_run: bool) -> bool:
    text = read_text(path)
    if text is None:
        return False

    lines = text.splitlines()
    if len(lines) < 3 or lines[0].strip() != "---":
        return False

    end_idx = None
    for idx in range(1, len(lines)):
        if lines[idx].strip() == "---":
            end_idx = idx
            break
    if end_idx is None:
        return False

    front = lines[1:end_idx]
    body = lines[end_idx + 1 :]

    ticket_line = next((ln for ln in front if ln.lower().startswith("ticket:")), None)
    slug_hint_line = next((ln for ln in front if ln.lower().startswith("slug hint:")), None)
    feature_line = next((ln for ln in front if ln.lower().startswith("feature:")), None)

    filename_ticket = path.stem
    feature_value = ""
    if feature_line:
        feature_value = feature_line.split(":", 1)[1].strip()

    updated = False
    new_front: list[str] = []

    def append_ticket_block() -> None:
        nonlocal ticket_line, slug_hint_line, updated
        if ticket_line is None:
            ticket_line = f"Ticket: {filename_ticket}"
            new_front.append(ticket_line)
            updated = True
        else:
            new_front.append(ticket_line)
        if slug_hint_line is None:
            slug_value = feature_value or filename_ticket
            slug_hint_line_local = f"Slug hint: {slug_value}"
            new_front.append(slug_hint_line_local)
            slug_hint_line = slug_hint_line_local
            updated = True
        else:
            new_front.append(slug_hint_line)

    inserted = False
    for line in front:
        if line.lower().startswith("ticket:"):
            new_front.append(line)
            inserted = True
            continue
        if line.lower().startswith("slug hint:"):
            if not inserted and ticket_line is None:
                new_front.append(f"Ticket: {filename_ticket}")
                inserted = True
                updated = True
            new_front.append(line)
            continue
        if line.lower().startswith("feature:") and not inserted:
            append_ticket_block()
            inserted = True
        new_front.append(line)

    if not inserted:
        append_ticket_block()

    if not updated:
        return False

    new_lines = ["---", *new_front, "---", *body]
    new_text = "\n".join(new_lines) + ("\n" if text.endswith("\n") else "")
    if dry_run:
        print(f"[dry-run] update front-matter in {path}")
    else:
        path.write_text(new_text, encoding="utf-8")
        print(f"[migrate] updated front-matter in {path}")
    return True


def migrate_tasklists(root: Path, *, dry_run: bool) -> int:
    tasklist_dir = root / "docs" / "tasklist"
    if not tasklist_dir.is_dir():
        return 0
    updated = 0
    for candidate in sorted(tasklist_dir.glob("*.md")):
        if migrate_tasklist_file(candidate, dry_run=dry_run):
            updated += 1
    return updated


def main() -> int:
    args = parse_args()
    root = Path(args.target).resolve()
    if not root.exists():
        print(f"[error] target directory {root} does not exist", file=sys.stderr)
        return 1

    created_ticket, ticket_value = ensure_active_ticket(root, dry_run=args.dry_run)
    tasklist_updates = migrate_tasklists(root, dry_run=args.dry_run)

    if args.dry_run:
        print("[dry-run] migration completed (no files modified).")
    else:
        if created_ticket:
            print(f"[summary] aidd/docs/.active_ticket set to '{ticket_value}'.")
        if tasklist_updates:
            print(f"[summary] updated {tasklist_updates} tasklist front-matter file(s).")
        if not created_ticket and tasklist_updates == 0:
            print("[summary] nothing to migrate — repository already uses ticket-first layout.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
