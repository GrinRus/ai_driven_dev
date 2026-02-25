#!/usr/bin/env python3
"""Assemble deterministic decisions memory pack from append-only JSONL log."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

from aidd_runtime import io_utils
from aidd_runtime import memory_common as common
from aidd_runtime import memory_verify
from aidd_runtime import runtime


def _iter_decision_entries(path: Path) -> tuple[List[Dict[str, Any]], int]:
    valid: List[Dict[str, Any]] = []
    invalid = 0
    if not path.exists():
        return valid, invalid
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return valid, invalid
    for raw in lines:
        line = raw.strip()
        if not line:
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            invalid += 1
            continue
        if not isinstance(payload, dict):
            invalid += 1
            continue
        errors = memory_verify.validate_decision_data(payload)
        if errors:
            invalid += 1
            continue
        valid.append(payload)
    return valid, invalid


def _trim_to_budget(
    payload: Dict[str, Any],
    *,
    max_chars: int,
    max_lines: int,
) -> Dict[str, int]:
    trim_stats: Dict[str, int] = {}
    while common.budget_exceeded(payload, max_chars=max_chars, max_lines=max_lines):
        trimmed = False
        active = payload.get("active_decisions")
        if isinstance(active, dict):
            rows = active.get("rows")
            if isinstance(rows, list) and rows:
                rows.pop()
                trim_stats["active_decisions"] = trim_stats.get("active_decisions", 0) + 1
                trimmed = True
        if not trimmed:
            superseded = payload.get("superseded_heads")
            if isinstance(superseded, dict):
                rows = superseded.get("rows")
                if isinstance(rows, list) and rows:
                    rows.pop()
                    trim_stats["superseded_heads"] = trim_stats.get("superseded_heads", 0) + 1
                    trimmed = True
        if not trimmed:
            conflicts = payload.get("conflicts")
            if isinstance(conflicts, list) and conflicts:
                conflicts.pop()
                trim_stats["conflicts"] = trim_stats.get("conflicts", 0) + 1
                trimmed = True
        if not trimmed:
            break
    return trim_stats


def parse_args(argv: List[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build decisions pack from append-only decisions log.")
    parser.add_argument("--ticket", help="Ticket identifier (defaults to docs/.active.json).")
    parser.add_argument("--out", help="Optional output path.")
    parser.add_argument("--max-active", type=int, default=None, help="Optional active decisions cap override.")
    parser.add_argument("--format", choices=("json", "text"), default="text", help="Output format.")
    return parser.parse_args(argv)


def main(argv: List[str] | None = None) -> int:
    try:
        args = parse_args(argv)
        _, project_root = runtime.require_workflow_root(Path.cwd())
        ticket, identifiers = runtime.require_ticket(project_root, ticket=args.ticket, slug_hint=None)
        settings = common.load_memory_settings(project_root)
        limits = common.decisions_limits(settings)
        max_active = int(args.max_active or limits["max_active"])

        log_path = common.decision_log_path(project_root, ticket)
        entries, invalid_count = _iter_decision_entries(log_path)

        latest_by_id: Dict[str, Dict[str, Any]] = {}
        for entry in entries:
            latest_by_id[str(entry.get("decision_id"))] = entry

        latest_entries = list(latest_by_id.values())
        active_entries = [item for item in latest_entries if str(item.get("status")) == "active"]
        superseded_entries = [item for item in latest_entries if str(item.get("status")) == "superseded"]
        rejected_entries = [item for item in latest_entries if str(item.get("status")) == "rejected"]

        active_entries = sorted(
            active_entries,
            key=lambda item: (
                str(item.get("topic") or "").lower(),
                str(item.get("decision_id") or ""),
            ),
        )
        truncated_active = max(0, len(active_entries) - max_active)
        active_rows = [
            [
                item.get("decision_id"),
                item.get("topic"),
                item.get("decision"),
                item.get("status"),
                item.get("ts"),
                item.get("scope_key"),
                item.get("stage"),
                item.get("source_path"),
            ]
            for item in active_entries[:max_active]
        ]

        superseded_rows = [
            [
                item.get("decision_id"),
                item.get("supersedes"),
                item.get("topic"),
                item.get("status"),
                item.get("ts"),
            ]
            for item in sorted(
                superseded_entries,
                key=lambda row: (str(row.get("topic") or "").lower(), str(row.get("decision_id") or "")),
            )
        ]

        topic_to_decisions: Dict[str, set[str]] = {}
        for item in active_entries:
            topic = common.normalize_text(item.get("topic"))
            decision_text = common.normalize_text(item.get("decision"))
            if not topic:
                continue
            topic_to_decisions.setdefault(topic, set()).add(decision_text)
        conflicts = sorted(
            f"{topic}: {len(values)} active variants"
            for topic, values in topic_to_decisions.items()
            if len(values) > 1
        )

        payload: Dict[str, Any] = {
            "schema": common.SCHEMA_DECISIONS_PACK,
            "schema_version": common.SCHEMA_DECISIONS_PACK,
            "pack_version": common.PACK_VERSION,
            "type": "memory-decisions",
            "kind": "pack",
            "ticket": ticket,
            "slug_hint": identifiers.slug_hint or ticket,
            "generated_at": io_utils.utc_timestamp(),
            "source_path": runtime.rel_path(log_path, project_root),
            "active_decisions": common.columnar(
                ["decision_id", "topic", "decision", "status", "ts", "scope_key", "stage", "source_path"],
                active_rows,
            ),
            "superseded_heads": common.columnar(
                ["decision_id", "supersedes", "topic", "status", "ts"],
                superseded_rows,
            ),
            "conflicts": conflicts,
            "stats": {
                "entries_total": len(entries),
                "invalid_entries": invalid_count,
                "latest_decisions": len(latest_entries),
                "active_total": len(active_entries),
                "superseded_total": len(superseded_entries),
                "rejected_total": len(rejected_entries),
                "active_truncated": truncated_active,
            },
        }

        trim_stats = _trim_to_budget(
            payload,
            max_chars=int(limits["max_chars"]),
            max_lines=int(limits["max_lines"]),
        )
        size = common.payload_size(payload)
        payload["stats"]["size"] = size
        payload["stats"]["budget"] = {
            "max_chars": int(limits["max_chars"]),
            "max_lines": int(limits["max_lines"]),
        }
        if trim_stats:
            payload["stats"]["trimmed"] = trim_stats

        verify_errors = memory_verify.validate_memory_data(
            payload,
            max_chars=int(limits["max_chars"]),
            max_lines=int(limits["max_lines"]),
        )
        if verify_errors:
            raise ValueError("; ".join(verify_errors[:5]))

        output_path = (
            runtime.resolve_path_for_target(Path(args.out), project_root)
            if args.out
            else common.decisions_pack_path(project_root, ticket)
        )
        io_utils.write_json(output_path, payload, sort_keys=True)

        result = {
            "schema": "aidd.memory.pack.result.v1",
            "status": "ok",
            "ticket": ticket,
            "decisions_pack": runtime.rel_path(output_path, project_root),
            "active_total": len(payload["active_decisions"]["rows"]),
            "conflicts_total": len(payload["conflicts"]),
            "invalid_entries": invalid_count,
        }
        if args.format == "json":
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            print(f"decisions_pack={result['decisions_pack']}")
            print(
                "summary="
                f"active={result['active_total']} conflicts={result['conflicts_total']} invalid={result['invalid_entries']}"
            )
        return 0
    except Exception as exc:
        print(f"[memory-pack] ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())

