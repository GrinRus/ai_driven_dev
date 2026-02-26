#!/usr/bin/env python3
"""Append decision entries to Memory v2 append-only JSONL log."""

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


def _parse_alternatives(raw: str) -> List[str]:
    parts = [common.normalize_text(item) for item in str(raw or "").split(",")]
    return [item for item in parts if item]


def _load_payload_from_json(path: str) -> Dict[str, Any]:
    source = str(path or "").strip()
    if not source:
        return {}
    if source == "-":
        try:
            payload = json.load(sys.stdin)
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid JSON from stdin: {exc}") from exc
    else:
        file_path = Path(source)
        try:
            payload = json.loads(file_path.read_text(encoding="utf-8"))
        except OSError as exc:
            raise ValueError(f"cannot read JSON payload: {file_path}") from exc
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid JSON payload in {file_path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError("decision payload must be JSON object")
    return payload


def parse_args(argv: List[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Append one decision entry to memory decisions log.")
    parser.add_argument("--ticket", help="Ticket identifier (defaults to docs/.active.json).")
    parser.add_argument("--topic", help="Decision topic.")
    parser.add_argument("--decision", help="Decision statement.")
    parser.add_argument("--alternatives", default="", help="Comma-separated alternatives list.")
    parser.add_argument("--rationale", default="", help="Decision rationale.")
    parser.add_argument("--scope-key", help="Scope key override.")
    parser.add_argument("--stage", help="Stage override.")
    parser.add_argument("--source-path", help="Source path override.")
    parser.add_argument("--status", choices=("active", "superseded", "rejected"), default="active")
    parser.add_argument("--supersedes", help="Optional superseded decision id.")
    parser.add_argument("--input-json", help="Read payload from JSON file (or '-' for stdin).")
    parser.add_argument("--format", choices=("json", "text"), default="text", help="Output format.")
    return parser.parse_args(argv)


def _coalesce(*values: Any) -> str:
    for value in values:
        text = common.normalize_text(value)
        if text:
            return text
    return ""


def main(argv: List[str] | None = None) -> int:
    try:
        args = parse_args(argv)
        _, project_root = runtime.require_workflow_root(Path.cwd())
        ticket, _identifiers = runtime.require_ticket(project_root, ticket=args.ticket, slug_hint=None)
        json_payload = _load_payload_from_json(args.input_json)

        active_scope = runtime.resolve_scope_key(runtime.read_active_work_item(project_root), ticket)
        active_stage = runtime.read_active_stage(project_root) or "unknown"
        source_default = f"aidd/reports/context/{ticket}.pack.md"

        topic = _coalesce(args.topic, json_payload.get("topic"))
        decision_text = _coalesce(args.decision, json_payload.get("decision"))
        if not topic:
            raise ValueError("topic is required (use --topic or input-json.topic)")
        if not decision_text:
            raise ValueError("decision is required (use --decision or input-json.decision)")

        alternatives_raw = json_payload.get("alternatives")
        if isinstance(alternatives_raw, list):
            alternatives = common.dedupe_preserve_order(str(item) for item in alternatives_raw)
        else:
            alternatives = _parse_alternatives(args.alternatives)

        payload: Dict[str, Any] = {
            "schema": common.SCHEMA_DECISION,
            "schema_version": common.SCHEMA_DECISION,
            "ts": io_utils.utc_timestamp(),
            "ticket": ticket,
            "scope_key": _coalesce(args.scope_key, json_payload.get("scope_key"), active_scope),
            "stage": _coalesce(args.stage, json_payload.get("stage"), active_stage),
            "decision_id": _coalesce(
                json_payload.get("decision_id"),
                common.stable_id(ticket, topic.lower(), decision_text.lower()),
            ),
            "topic": topic,
            "decision": decision_text,
            "alternatives": alternatives,
            "rationale": _coalesce(args.rationale, json_payload.get("rationale")),
            "source_path": _coalesce(args.source_path, json_payload.get("source_path"), source_default),
            "status": _coalesce(args.status, json_payload.get("status"), "active").lower(),
        }
        supersedes = _coalesce(args.supersedes, json_payload.get("supersedes"))
        if supersedes:
            payload["supersedes"] = supersedes

        errors = memory_verify.validate_decision_data(payload)
        if errors:
            raise ValueError("; ".join(errors))

        log_path = common.decision_log_path(project_root, ticket)
        io_utils.append_jsonl(log_path, payload)

        result = {
            "schema": "aidd.memory.decision_append.result.v1",
            "status": "ok",
            "ticket": ticket,
            "decision_id": payload["decision_id"],
            "log_path": runtime.rel_path(log_path, project_root),
        }
        if args.format == "json":
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            print(f"log_path={result['log_path']}")
            print(f"summary=decision_id={result['decision_id']} status={payload['status']}")
        return 0
    except Exception as exc:
        print(f"[decision-append] ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())

