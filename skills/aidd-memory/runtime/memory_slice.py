#!/usr/bin/env python3
"""Targeted read path for semantic/decisions memory packs."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
from pathlib import Path
from typing import Dict, List


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

from aidd_runtime import runtime


def _load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _match_tokens(text: str, tokens: List[str]) -> bool:
    probe = text.lower()
    return all(token in probe for token in tokens)


def _slice_semantic(payload: dict, tokens: List[str]) -> dict:
    sections = payload.get("sections") if isinstance(payload.get("sections"), dict) else {}
    sliced: Dict[str, List[str]] = {}
    for key in ("terms", "defaults", "constraints", "invariants", "open_questions"):
        values = sections.get(key) if isinstance(sections, dict) else []
        if not isinstance(values, list):
            continue
        hits = [str(item) for item in values if _match_tokens(str(item), tokens)]
        if hits:
            sliced[key] = hits
    return sliced


def _slice_decisions(payload: dict, tokens: List[str], *, max_items: int) -> List[dict]:
    active = payload.get("active") if isinstance(payload.get("active"), list) else []
    hits: List[dict] = []
    for item in active:
        if not isinstance(item, dict):
            continue
        text = "\n".join(
            [
                str(item.get("title") or ""),
                str(item.get("decision") or ""),
                str(item.get("rationale") or ""),
                " ".join(str(tag) for tag in (item.get("tags") or [])),
            ]
        )
        if _match_tokens(text, tokens):
            hits.append(item)
        if len(hits) >= max(max_items, 1):
            break
    return hits


def parse_args(argv: List[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create targeted memory slice artifact.")
    parser.add_argument("--ticket", help="Ticket identifier (defaults to docs/.active.json).")
    parser.add_argument("--slug-hint", help="Optional slug hint override.")
    parser.add_argument("--query", action="append", required=True, help="Query token (repeatable).")
    parser.add_argument("--kind", choices=("all", "semantic", "decisions"), default="all")
    parser.add_argument("--max-items", type=int, default=20)
    parser.add_argument("--output", help="Optional output path override.")
    return parser.parse_args(argv)


def main(argv: List[str] | None = None) -> int:
    args = parse_args(argv)
    _, root = runtime.require_workflow_root()
    ticket, _ = runtime.require_ticket(root, ticket=getattr(args, "ticket", None), slug_hint=getattr(args, "slug_hint", None))

    semantic_path = root / "reports" / "memory" / f"{ticket}.semantic.pack.json"
    decisions_path = root / "reports" / "memory" / f"{ticket}.decisions.pack.json"

    tokens = [str(item or "").strip().lower() for item in (args.query or []) if str(item or "").strip()]
    if not tokens:
        print("[memory-slice] ERROR: --query must provide at least one non-empty token", file=sys.stderr)
        return 2

    semantic_payload = _load_json(semantic_path)
    decisions_payload = _load_json(decisions_path)

    slice_payload = {
        "schema": "aidd.memory.slice.v1",
        "ticket": ticket,
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "query": tokens,
        "kind": args.kind,
        "semantic": {},
        "decisions": [],
    }

    if args.kind in {"all", "semantic"} and semantic_payload:
        slice_payload["semantic"] = _slice_semantic(semantic_payload, tokens)
    if args.kind in {"all", "decisions"} and decisions_payload:
        slice_payload["decisions"] = _slice_decisions(decisions_payload, tokens, max_items=int(args.max_items))

    if args.output:
        output_path = runtime.resolve_path_for_target(Path(args.output), root)
    else:
        output_path = root / "reports" / "context" / f"{ticket}-memory-slice.latest.pack.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(slice_payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"[memory-slice] OK: {runtime.rel_path(output_path, root)}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
