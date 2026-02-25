#!/usr/bin/env python3
"""Generate targeted memory slice packs from semantic and decisions packs."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List

from aidd_runtime import io_utils
from aidd_runtime import memory_common as common
from aidd_runtime import runtime

SCHEMA = "aidd.report.pack.v1"
PACK_VERSION = "v1"


def _compile_query(raw: str) -> re.Pattern[str]:
    try:
        return re.compile(raw, re.IGNORECASE)
    except re.error:
        return re.compile(re.escape(raw), re.IGNORECASE)


def _match_row(pattern: re.Pattern[str], row: List[Any]) -> bool:
    text = " | ".join(common.normalize_text(item) for item in row)
    return bool(text and pattern.search(text))


def _load_json(path: Path) -> Dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _append_hits_from_section(
    hits: List[List[str]],
    *,
    pattern: re.Pattern[str],
    section_name: str,
    source_path: str,
    section: Dict[str, Any],
    max_hits: int,
) -> None:
    cols = section.get("cols")
    rows = section.get("rows")
    if not isinstance(cols, list) or not isinstance(rows, list):
        return
    for row in rows:
        if len(hits) >= max_hits:
            return
        if not isinstance(row, list):
            continue
        if not _match_row(pattern, row):
            continue
        ref = common.normalize_text(row[0] if row else section_name)
        snippet = " | ".join(common.normalize_text(item) for item in row)[:220]
        hits.append([section_name, ref or section_name, snippet, source_path])


def parse_args(argv: List[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate query-based slice from memory packs.")
    parser.add_argument("--ticket", help="Ticket identifier (defaults to docs/.active.json).")
    parser.add_argument("--query", required=True, help="Regex/token query to match in memory packs.")
    parser.add_argument("--max-hits", type=int, default=None, help="Maximum number of slice hits.")
    parser.add_argument("--out", help="Optional output path.")
    parser.add_argument("--format", choices=("json", "text"), default="text", help="Output format.")
    return parser.parse_args(argv)


def main(argv: List[str] | None = None) -> int:
    try:
        args = parse_args(argv)
        _, project_root = runtime.require_workflow_root(Path.cwd())
        ticket, identifiers = runtime.require_ticket(project_root, ticket=args.ticket, slug_hint=None)
        settings = common.load_memory_settings(project_root)
        limits = common.slice_limits(settings)
        max_hits = int(args.max_hits or limits["max_hits"])
        max_chars = int(limits["max_chars"])
        pattern = _compile_query(args.query)

        semantic_path = common.semantic_pack_path(project_root, ticket)
        decisions_path = common.decisions_pack_path(project_root, ticket)
        semantic = _load_json(semantic_path) if semantic_path.exists() else {}
        decisions = _load_json(decisions_path) if decisions_path.exists() else {}
        if not semantic and not decisions:
            raise FileNotFoundError(
                f"memory packs not found for ticket {ticket}; expected {runtime.rel_path(semantic_path, project_root)} or "
                f"{runtime.rel_path(decisions_path, project_root)}"
            )

        hits: List[List[str]] = []
        if semantic:
            source = runtime.rel_path(semantic_path, project_root)
            for section_name in ("terms", "defaults", "constraints", "invariants"):
                section = semantic.get(section_name)
                if isinstance(section, dict):
                    _append_hits_from_section(
                        hits,
                        pattern=pattern,
                        section_name=section_name,
                        source_path=source,
                        section=section,
                        max_hits=max_hits,
                    )
            questions = semantic.get("open_questions")
            if isinstance(questions, list):
                for question in questions:
                    if len(hits) >= max_hits:
                        break
                    text = common.normalize_text(question)
                    if text and pattern.search(text):
                        hits.append(
                            [
                                "open_questions",
                                "question",
                                text[:220],
                                source,
                            ]
                        )

        if decisions and len(hits) < max_hits:
            source = runtime.rel_path(decisions_path, project_root)
            for section_name in ("active_decisions", "superseded_heads"):
                section = decisions.get(section_name)
                if isinstance(section, dict):
                    _append_hits_from_section(
                        hits,
                        pattern=pattern,
                        section_name=section_name,
                        source_path=source,
                        section=section,
                        max_hits=max_hits,
                    )
            conflicts = decisions.get("conflicts")
            if isinstance(conflicts, list):
                for conflict in conflicts:
                    if len(hits) >= max_hits:
                        break
                    text = common.normalize_text(conflict)
                    if text and pattern.search(text):
                        hits.append(
                            [
                                "conflicts",
                                "conflict",
                                text[:220],
                                source,
                            ]
                        )

        # Keep deterministic order and cap payload text pressure.
        hits = hits[:max_hits]
        for row in hits:
            row[2] = row[2][:max_chars]

        payload = {
            "schema": SCHEMA,
            "pack_version": PACK_VERSION,
            "type": "memory-slice",
            "kind": "pack",
            "ticket": ticket,
            "slug_hint": identifiers.slug_hint or ticket,
            "generated_at": io_utils.utc_timestamp(),
            "query": args.query,
            "links": {
                "semantic_pack": runtime.rel_path(semantic_path, project_root) if semantic else "",
                "decisions_pack": runtime.rel_path(decisions_path, project_root) if decisions else "",
            },
            "stats": {
                "hits": len(hits),
                "max_hits": max_hits,
                "query": args.query,
            },
            "matches": common.columnar(
                ["kind", "ref", "snippet", "source_path"],
                hits,
            ),
        }

        output_path = (
            runtime.resolve_path_for_target(Path(args.out), project_root)
            if args.out
            else common.memory_slice_path(project_root, ticket, args.query)
        )
        latest_path = common.memory_slice_latest_path(project_root, ticket)
        io_utils.write_json(output_path, payload, sort_keys=True)
        io_utils.write_json(latest_path, payload, sort_keys=True)

        result = {
            "schema": "aidd.memory.slice.result.v1",
            "status": "ok",
            "ticket": ticket,
            "slice_pack": runtime.rel_path(output_path, project_root),
            "latest_pack": runtime.rel_path(latest_path, project_root),
            "hits": len(hits),
        }
        if args.format == "json":
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            print(f"slice_pack={result['slice_pack']}")
            print(f"summary=hits={result['hits']}")
        return 0
    except Exception as exc:
        print(f"[memory-slice] ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())

