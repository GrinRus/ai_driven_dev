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
MANIFEST_TYPE = "memory-slices-manifest"
MANIFEST_SCHEMA = "aidd.memory.slices.manifest.v1"


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


def _load_manifest(path: Path) -> Dict[str, Any]:
    payload = _load_json(path)
    if not payload:
        return {}
    if str(payload.get("schema") or "").strip() != MANIFEST_SCHEMA:
        return {}
    return payload


def _manifest_row(query: str, slice_pack: str, latest_alias: str, hits: int) -> List[Any]:
    return [query, slice_pack, latest_alias, max(0, int(hits))]


def _upsert_manifest_entry(payload: Dict[str, Any], row: List[Any]) -> None:
    slices = payload.get("slices")
    if not isinstance(slices, dict):
        return
    rows = slices.get("rows")
    if not isinstance(rows, list):
        return
    query = str(row[0] or "").strip()
    replaced = False
    for idx, existing in enumerate(rows):
        if isinstance(existing, list) and existing and str(existing[0] or "").strip() == query:
            rows[idx] = row
            replaced = True
            break
    if not replaced:
        rows.append(row)


def _build_manifest_payload(
    *,
    ticket: str,
    slug_hint: str,
    stage: str,
    scope_key: str,
    source_slice_pack: str,
    latest_alias: str,
    query: str,
    hits: int,
    existing: Dict[str, Any] | None,
    max_slices: int,
    max_chars: int,
) -> Dict[str, Any]:
    payload = existing if existing else {}
    if not payload:
        payload = {
            "schema": MANIFEST_SCHEMA,
            "schema_version": MANIFEST_SCHEMA,
            "pack_version": PACK_VERSION,
            "type": MANIFEST_TYPE,
            "kind": "pack",
            "ticket": ticket,
            "slug_hint": slug_hint,
            "stage": stage,
            "scope_key": scope_key,
            "generated_at": io_utils.utc_timestamp(),
            "updated_at": io_utils.utc_timestamp(),
            "stats": {
                "max_slices": max(1, int(max_slices)),
                "max_chars": max(2000, int(max_chars)),
                "trimmed": False,
            },
            "slices": {
                "cols": ["query", "slice_pack", "latest_alias", "hits"],
                "rows": [],
            },
        }
    payload["generated_at"] = payload.get("generated_at") or io_utils.utc_timestamp()
    payload["updated_at"] = io_utils.utc_timestamp()
    payload["ticket"] = ticket
    payload["slug_hint"] = slug_hint
    payload["stage"] = stage
    payload["scope_key"] = scope_key

    _upsert_manifest_entry(payload, _manifest_row(query, source_slice_pack, latest_alias, hits))
    rows = payload.get("slices", {}).get("rows")
    if isinstance(rows, list):
        rows.sort(key=lambda row: str(row[0] if isinstance(row, list) and row else ""))
        if len(rows) > max_slices:
            del rows[max_slices:]
            payload.setdefault("stats", {})["trimmed"] = True

    serialized = common.canonical_json(payload)
    if len(serialized) > max_chars and isinstance(rows, list):
        while rows and len(common.canonical_json(payload)) > max_chars:
            rows.pop()
            payload.setdefault("stats", {})["trimmed"] = True

    payload.setdefault("stats", {})["slice_count"] = len(rows) if isinstance(rows, list) else 0
    return payload


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
    parser.add_argument("--stage", help="Optional stage label for stage-aware latest alias and manifest.")
    parser.add_argument("--scope-key", help="Optional scope key for stage-aware latest alias and manifest.")
    parser.add_argument("--latest-alias", help="Optional explicit latest alias output path.")
    parser.add_argument("--manifest", help="Optional path to stage slice manifest artifact.")
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
        policy = common.slice_policy(settings)
        max_hits = int(args.max_hits or limits["max_hits"])
        max_chars = int(limits["max_chars"])
        pattern = _compile_query(args.query)
        stage_value = str(args.stage or "").strip().lower()
        if stage_value == "review_spec":
            stage_value = "review-spec"
        scope_value = str(args.scope_key or "").strip()
        if stage_value and not scope_value:
            scope_value = runtime.resolve_scope_key(runtime.read_active_work_item(project_root), ticket)

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

        stage_latest_rel = ""
        stage_latest_path: Path | None = None
        if args.latest_alias:
            stage_latest_path = runtime.resolve_path_for_target(Path(args.latest_alias), project_root)
        elif stage_value:
            stage_latest_path = common.memory_slice_stage_latest_path(project_root, ticket, stage_value, scope_value or ticket)
        if stage_latest_path is not None:
            io_utils.write_json(stage_latest_path, payload, sort_keys=True)
            stage_latest_rel = runtime.rel_path(stage_latest_path, project_root)

        manifest_rel = ""
        if args.manifest or stage_value:
            manifest_path = (
                runtime.resolve_path_for_target(Path(args.manifest), project_root)
                if args.manifest
                else common.memory_slices_manifest_path(project_root, ticket, stage_value, scope_value or ticket)
            )
            existing_manifest = _load_manifest(manifest_path)
            manifest_payload = _build_manifest_payload(
                ticket=ticket,
                slug_hint=identifiers.slug_hint or ticket,
                stage=stage_value or "unknown",
                scope_key=scope_value or runtime.resolve_scope_key("", ticket),
                source_slice_pack=runtime.rel_path(output_path, project_root),
                latest_alias=stage_latest_rel or runtime.rel_path(latest_path, project_root),
                query=args.query,
                hits=len(hits),
                existing=existing_manifest if existing_manifest else None,
                max_slices=int(policy["manifest_budget"]["max_slices"]),
                max_chars=int(policy["manifest_budget"]["max_chars"]),
            )
            io_utils.write_json(manifest_path, manifest_payload, sort_keys=True)
            manifest_rel = runtime.rel_path(manifest_path, project_root)

        result = {
            "schema": "aidd.memory.slice.result.v1",
            "status": "ok",
            "ticket": ticket,
            "slice_pack": runtime.rel_path(output_path, project_root),
            "latest_pack": runtime.rel_path(latest_path, project_root),
            "stage_latest_pack": stage_latest_rel,
            "manifest_pack": manifest_rel,
            "stage": stage_value,
            "scope_key": scope_value,
            "hits": len(hits),
        }
        if args.format == "json":
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            print(f"slice_pack={result['slice_pack']}")
            if stage_latest_rel:
                print(f"stage_latest_pack={stage_latest_rel}")
            if manifest_rel:
                print(f"manifest_pack={manifest_rel}")
            print(f"summary=hits={result['hits']}")
        return 0
    except Exception as exc:
        print(f"[memory-slice] ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
