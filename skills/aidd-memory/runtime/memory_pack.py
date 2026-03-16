#!/usr/bin/env python3
"""Assemble decisions pack from append-only decision log."""

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

from aidd_runtime import memory_verify
from aidd_runtime import runtime


def _load_memory_settings(root: Path) -> dict:
    conventions_path = root / "config" / "conventions.json"
    if not conventions_path.exists():
        return {}
    try:
        payload = json.loads(conventions_path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    memory = payload.get("memory")
    return memory if isinstance(memory, dict) else {}


def _read_log(path: Path) -> List[dict]:
    if not path.exists():
        return []
    out: List[dict] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    for idx, raw in enumerate(lines):
        text = raw.strip()
        if not text:
            continue
        try:
            payload = json.loads(text)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"invalid decision JSONL line {idx + 1}: {exc}") from exc
        if not isinstance(payload, dict):
            raise RuntimeError(f"invalid decision JSONL line {idx + 1}: payload must be object")
        errors = memory_verify.validate_decision_data(payload)
        if errors:
            raise RuntimeError(f"invalid decision JSONL line {idx + 1}: {errors[0]}")
        out.append(payload)
    return out


def _iso_sort_key(payload: dict) -> str:
    return str(payload.get("created_at") or "")


def build_decisions_pack(ticket: str, entries: List[dict], *, top_n: int) -> dict:
    latest_by_id: Dict[str, dict] = {}
    superseded_ids: set[str] = set()
    conflicts: List[dict] = []

    for entry in entries:
        decision_id = str(entry.get("decision_id") or "").strip()
        if not decision_id:
            continue
        latest_by_id[decision_id] = entry
        superseded = entry.get("supersedes") if isinstance(entry.get("supersedes"), list) else []
        for item in superseded:
            value = str(item or "").strip()
            if value:
                superseded_ids.add(value)
        conflict_ids = entry.get("conflicts_with") if isinstance(entry.get("conflicts_with"), list) else []
        for item in conflict_ids:
            value = str(item or "").strip()
            if value:
                conflicts.append({"decision_id": decision_id, "conflicts_with": value})

    active: List[dict] = []
    superseded: List[dict] = []
    for decision_id, payload in latest_by_id.items():
        status = str(payload.get("status") or "active").strip().lower()
        effective_superseded = status == "superseded" or decision_id in superseded_ids
        if effective_superseded:
            superseded.append(payload)
        else:
            active.append(payload)

    active_sorted = sorted(active, key=_iso_sort_key, reverse=True)
    superseded_sorted = sorted(superseded, key=_iso_sort_key, reverse=True)
    top = active_sorted[: max(top_n, 0)]

    payload = {
        "schema": memory_verify.DECISIONS_PACK_SCHEMA,
        "schema_version": memory_verify.DECISIONS_PACK_SCHEMA,
        "ticket": ticket,
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "status": "ok",
        "active": active_sorted,
        "superseded": superseded_sorted,
        "top": top,
        "conflicts": conflicts,
        "counts": {
            "entries_total": len(entries),
            "decision_ids_total": len(latest_by_id),
            "active_total": len(active_sorted),
            "superseded_total": len(superseded_sorted),
            "top_total": len(top),
            "conflicts_total": len(conflicts),
        },
    }
    return payload


def parse_args(argv: List[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build decisions pack from memory decision log.")
    parser.add_argument("--ticket", help="Ticket identifier (defaults to docs/.active.json).")
    parser.add_argument("--slug-hint", help="Optional slug hint override.")
    parser.add_argument("--input", help="Path to <ticket>.decisions.jsonl")
    parser.add_argument("--output", help="Path to <ticket>.decisions.pack.json")
    parser.add_argument("--top-n", type=int, help="Number of top active decisions to keep.")
    return parser.parse_args(argv)


def main(argv: List[str] | None = None) -> int:
    args = parse_args(argv)
    _, root = runtime.require_workflow_root()
    ticket, _ = runtime.require_ticket(root, ticket=getattr(args, "ticket", None), slug_hint=getattr(args, "slug_hint", None))

    settings = _load_memory_settings(root)
    decisions_cfg = settings.get("decisions") if isinstance(settings, dict) else {}
    top_n = int(args.top_n or (decisions_cfg.get("top_n") if isinstance(decisions_cfg, dict) else 10) or 10)

    if args.input:
        log_path = runtime.resolve_path_for_target(Path(args.input), root)
    else:
        log_path = root / "reports" / "memory" / f"{ticket}.decisions.jsonl"
    if args.output:
        output_path = runtime.resolve_path_for_target(Path(args.output), root)
    else:
        output_path = root / "reports" / "memory" / f"{ticket}.decisions.pack.json"

    entries = _read_log(log_path)
    payload = build_decisions_pack(ticket, entries, top_n=top_n)

    errors = memory_verify.validate_decisions_pack_data(payload)
    if errors:
        for err in errors:
            print(f"[memory-pack] ERROR: {err}", file=sys.stderr)
        return 2

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"[memory-pack] OK: {runtime.rel_path(output_path, root)}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
