#!/usr/bin/env python3
"""Append immutable decision record to memory decision log."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import sys
from pathlib import Path
from typing import List


def _ensure_plugin_root_on_path() -> None:
    env_root = os.environ.get("CLAUDE_PLUGIN_ROOT", "").strip()
    if env_root:
        root = Path(env_root).resolve()
        if (root / "aidd_runtime").is_dir():
            if str(root) not in sys.path:
                sys.path.insert(0, str(root))
            return

    probe = Path(__file__).resolve()
    for parent in (probe.parent, *probe.parents):
        if (parent / "aidd_runtime").is_dir():
            os.environ.setdefault("CLAUDE_PLUGIN_ROOT", str(parent))
            if str(parent) not in sys.path:
                sys.path.insert(0, str(parent))
            return


_ensure_plugin_root_on_path()

from aidd_runtime import memory_verify
from aidd_runtime import runtime


def _parse_csv(raw: str | None) -> List[str]:
    if not raw:
        return []
    out: List[str] = []
    for chunk in str(raw).split(","):
        item = chunk.strip()
        if item and item not in out:
            out.append(item)
    return out


def _last_entry_hash(path: Path) -> str:
    if not path.exists():
        return ""
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return ""
    for raw in reversed(lines):
        text = raw.strip()
        if not text:
            continue
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            value = str(payload.get("entry_hash") or "").strip()
            if value:
                return value
    return ""


def _build_decision_id(ticket: str, title: str, decision: str, rationale: str, prev_hash: str) -> str:
    seed = "\n".join([ticket, title, decision, rationale, prev_hash or ""])
    digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()[:10]
    return f"DEC-{digest}".upper()


def _content_hash(title: str, decision: str, rationale: str) -> str:
    blob = f"{title}\n{decision}\n{rationale}".encode("utf-8")
    return f"sha256:{hashlib.sha256(blob).hexdigest()}"


def _entry_hash(payload: dict, prev_hash: str) -> str:
    clone = dict(payload)
    clone.pop("entry_hash", None)
    blob = json.dumps(clone, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    base = f"{prev_hash}|{blob}".encode("utf-8")
    return f"sha256:{hashlib.sha256(base).hexdigest()}"


def parse_args(argv: List[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Append decision entry to memory log.")
    parser.add_argument("--ticket", help="Ticket identifier (defaults to docs/.active.json).")
    parser.add_argument("--slug-hint", help="Optional slug hint override.")
    parser.add_argument("--decision-id", help="Optional explicit decision id.")
    parser.add_argument("--title", required=True, help="Decision title.")
    parser.add_argument("--decision", required=True, help="Decision content.")
    parser.add_argument("--rationale", default="", help="Decision rationale.")
    parser.add_argument("--stage", help="Stage label override (defaults to active stage).")
    parser.add_argument("--scope-key", help="Scope key override.")
    parser.add_argument("--source", default="loop", help="Decision source marker.")
    parser.add_argument("--tags", help="Comma-separated tags.")
    parser.add_argument("--supersedes", help="Comma-separated decision ids superseded by this entry.")
    parser.add_argument("--conflicts-with", dest="conflicts_with", help="Comma-separated conflicting ids.")
    parser.add_argument("--status", choices=("active", "superseded"), default="active")
    parser.add_argument("--output", help="Optional decision log path override.")
    parser.add_argument("--emit-json", action="store_true", help="Emit appended payload JSON to stdout.")
    return parser.parse_args(argv)


def main(argv: List[str] | None = None) -> int:
    args = parse_args(argv)
    _, root = runtime.require_workflow_root()
    ticket, _ = runtime.require_ticket(root, ticket=getattr(args, "ticket", None), slug_hint=getattr(args, "slug_hint", None))

    stage = str(args.stage or runtime.read_active_stage(root) or "unknown").strip().lower() or "unknown"
    scope_key = str(args.scope_key or runtime.resolve_scope_key(runtime.read_active_work_item(root), ticket)).strip() or ticket

    if args.output:
        log_path = runtime.resolve_path_for_target(Path(args.output), root)
    else:
        log_path = root / "reports" / "memory" / f"{ticket}.decisions.jsonl"

    prev_hash = _last_entry_hash(log_path)
    title = str(args.title or "").strip()
    decision = str(args.decision or "").strip()
    rationale = str(args.rationale or "").strip()
    decision_id = str(
        args.decision_id or _build_decision_id(ticket, title, decision, rationale, prev_hash)
    ).strip()

    payload = {
        "schema": memory_verify.DECISION_SCHEMA,
        "schema_version": memory_verify.DECISION_SCHEMA,
        "ticket": ticket,
        "decision_id": decision_id,
        "created_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "stage": stage,
        "scope_key": scope_key,
        "source": str(args.source or "loop").strip(),
        "title": title,
        "decision": decision,
        "rationale": rationale,
        "tags": _parse_csv(args.tags),
        "supersedes": _parse_csv(args.supersedes),
        "conflicts_with": _parse_csv(args.conflicts_with),
        "status": str(args.status or "active").strip().lower(),
        "content_hash": _content_hash(title, decision, rationale),
        "prev_hash": prev_hash,
    }
    payload["entry_hash"] = _entry_hash(payload, prev_hash)

    errors = memory_verify.validate_decision_data(payload)
    if errors:
        for err in errors:
            print(f"[decision-append] ERROR: {err}", file=sys.stderr)
        return 2

    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n")

    if args.emit_json:
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    else:
        print(f"[decision-append] OK: {runtime.rel_path(log_path, root)} id={decision_id}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
