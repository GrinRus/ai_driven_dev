#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
import hashlib
import json
import sys
from pathlib import Path
from typing import List, Optional

from aidd_runtime import runtime


STATUS_RE = re.compile(r"^\s*Status:\s*([A-Za-z]+)", re.MULTILINE)
CACHE_FILENAME = "prd-check.hash"


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate PRD Status: READY.")
    parser.add_argument("--ticket", help="Ticket identifier (defaults to docs/.active.json).")
    parser.add_argument("--prd", help="Override PRD path.")
    return parser.parse_args(argv)


def _resolve_prd_path(project_root: Path, ticket: str, override: Optional[str]) -> Path:
    if override:
        return runtime.resolve_path_for_target(Path(override), project_root)
    return project_root / "docs" / "prd" / f"{ticket}.prd.md"


def _cache_path(root: Path) -> Path:
    return root / ".cache" / CACHE_FILENAME


def _load_cache(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _write_cache(path: Path, *, ticket: str, hash_value: str) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"ticket": ticket, "hash": hash_value}
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    except OSError:
        return


def _hash_prd(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def main(argv: Optional[List[str]] = None) -> int:
    args = parse_args(argv)
    _, project_root = runtime.require_workflow_root()
    ticket, _ = runtime.require_ticket(project_root, ticket=args.ticket, slug_hint=None)

    prd_path = _resolve_prd_path(project_root, ticket, args.prd)
    if not prd_path.exists():
        rel = runtime.rel_path(prd_path, project_root)
        raise SystemExit(f"BLOCK: PRD не найден: {rel}")

    text = prd_path.read_text(encoding="utf-8")
    current_hash = _hash_prd(text)
    cache_path = _cache_path(project_root)
    cache_payload = _load_cache(cache_path)
    if cache_payload.get("ticket") == ticket and cache_payload.get("hash") == current_hash:
        print("[prd-check] SKIP: cache hit (reason_code=cache_hit)", file=sys.stderr)
        return 0
    match = STATUS_RE.search(text)
    if not match:
        raise SystemExit("BLOCK: PRD не содержит строку `Status:` → установите Status: READY перед plan-new.")

    status = match.group(1).strip().upper()
    if status != "READY":
        raise SystemExit(
            f"BLOCK: PRD Status: {status} → установите Status: READY перед /feature-dev-aidd:plan-new {ticket}."
        )

    print(f"[aidd] PRD ready for `{ticket}` (status: READY).")
    _write_cache(cache_path, ticket=ticket, hash_value=current_hash)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
