#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import re
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from aidd_runtime import runtime
from aidd_runtime.rlm_config import load_rlm_settings


SCHEMA = "aidd.report.pack.v1"
PACK_VERSION = "v1"


def _pack_extension() -> str:
    return ".pack.json"


def _hash_slice_key(query: str, paths: Sequence[str], langs: Sequence[str]) -> str:
    parts = [query]
    if paths:
        parts.append("paths=" + ",".join(paths))
    if langs:
        parts.append("langs=" + ",".join(langs))
    return hashlib.sha1("|".join(parts).encode("utf-8")).hexdigest()[:10]


def _compile_query(query: str) -> re.Pattern[str]:
    try:
        return re.compile(query, re.IGNORECASE)
    except re.error:
        return re.compile(re.escape(query), re.IGNORECASE)


def _iter_jsonl(path: Path) -> Iterable[Dict[str, object]]:
    if not path.exists():
        return
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            raw = line.strip()
            if not raw:
                continue
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if isinstance(payload, dict):
                yield payload


def _node_matches(node: Dict[str, object], pattern: re.Pattern[str]) -> bool:
    for key in ("path", "summary"):
        value = node.get(key)
        if value and pattern.search(str(value)):
            return True
    for key in ("public_symbols", "key_calls", "framework_roles", "test_hooks", "risks"):
        values = node.get(key) or []
        for item in values:
            if item and pattern.search(str(item)):
                return True
    return False


def _node_matches_paths(node: Dict[str, object], paths: Sequence[str]) -> bool:
    if not paths:
        return True
    raw_path = str(node.get("path") or "")
    return any(token in raw_path for token in paths if token)


def _node_matches_lang(node: Dict[str, object], langs: Sequence[str]) -> bool:
    if not langs:
        return True
    lang = str(node.get("lang") or "").lower()
    return lang in langs


def _link_matches(link: Dict[str, object], pattern: re.Pattern[str], file_paths: Dict[str, str]) -> bool:
    for key in ("type", "src_file_id", "dst_file_id"):
        value = link.get(key)
        if value and pattern.search(str(value)):
            return True
    evidence = link.get("evidence_ref") or {}
    path = evidence.get("path")
    if path and pattern.search(str(path)):
        return True
    src_path = file_paths.get(str(link.get("src_file_id") or ""), "")
    dst_path = file_paths.get(str(link.get("dst_file_id") or ""), "")
    return bool(src_path and pattern.search(src_path)) or bool(dst_path and pattern.search(dst_path))


def _write_pack(path: Path, payload: Dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    path.write_text(text, encoding="utf-8")


def parse_args(argv: List[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate a compact RLM slice pack.")
    parser.add_argument("--ticket", help="Ticket identifier (defaults to docs/.active.json).")
    parser.add_argument("--query", required=True, help="Regex or token to match in nodes/links.")
    parser.add_argument("--max-nodes", type=int, default=None, help="Maximum number of nodes to include.")
    parser.add_argument("--max-links", type=int, default=None, help="Maximum number of links to include.")
    parser.add_argument("--paths", help="Optional comma-separated list of path fragments to keep.")
    parser.add_argument("--lang", help="Optional comma-separated list of languages to keep.")
    parser.add_argument("--out", default=None, help="Optional output path for the pack.")
    return parser.parse_args(argv)


def main(argv: List[str] | None = None) -> int:
    args = parse_args(argv)
    _, target = runtime.require_workflow_root()
    ticket, context = runtime.require_ticket(target, ticket=args.ticket, slug_hint=None)

    settings = load_rlm_settings(target)
    slice_budget = settings.get("slice_budget") if isinstance(settings.get("slice_budget"), dict) else {}

    nodes_path = target / "reports" / "research" / f"{ticket}-rlm.nodes.jsonl"
    links_path = target / "reports" / "research" / f"{ticket}-rlm.links.jsonl"
    if not nodes_path.exists() or not links_path.exists():
        raise SystemExit("RLM nodes/links not found; build nodes and links first.")

    pattern = _compile_query(args.query)
    default_nodes = int(slice_budget.get("max_nodes") or 20)
    default_links = int(slice_budget.get("max_links") or 40)
    max_nodes = max(1, int(args.max_nodes)) if args.max_nodes else max(1, default_nodes)
    max_links = max(1, int(args.max_links)) if args.max_links else max(1, default_links)
    paths = [token.strip() for token in str(args.paths or "").split(",") if token.strip()]
    langs = [token.strip().lower() for token in str(args.lang or "").split(",") if token.strip()]

    selected_nodes: List[Dict[str, object]] = []
    node_ids: set[str] = set()
    file_paths: Dict[str, str] = {}
    truncated_nodes = False
    for node in _iter_jsonl(nodes_path):
        if not _node_matches_lang(node, langs):
            continue
        if not _node_matches_paths(node, paths):
            continue
        if not _node_matches(node, pattern):
            continue
        node_id = str(node.get("id") or node.get("file_id") or node.get("dir_id") or "")
        if not node_id or node_id in node_ids:
            continue
        if len(node_ids) >= max_nodes:
            truncated_nodes = True
            break
        node_ids.add(node_id)
        selected_nodes.append(
            {
                "id": node_id,
                "node_kind": node.get("node_kind"),
                "path": node.get("path"),
                "summary": node.get("summary"),
                "lang": node.get("lang"),
            }
        )
        if node.get("node_kind") == "file" and node.get("path"):
            file_paths[node_id] = str(node.get("path"))

    selected_links: List[Dict[str, object]] = []
    truncated_links = False
    for link in _iter_jsonl(links_path):
        if len(selected_links) >= max_links:
            truncated_links = True
            break
        if not _link_matches(link, pattern, file_paths):
            continue
        selected_links.append(
            {
                "link_id": link.get("link_id"),
                "src_file_id": link.get("src_file_id"),
                "dst_file_id": link.get("dst_file_id"),
                "type": link.get("type"),
                "evidence_ref": link.get("evidence_ref"),
            }
        )

    out_dir = target / "reports" / "context"
    ext = _pack_extension()
    query_hash = _hash_slice_key(args.query, paths, langs)
    default_path = out_dir / f"{ticket}-rlm-slice-{query_hash}{ext}"
    output_path = runtime.resolve_path_for_target(Path(args.out), target) if args.out else default_path
    latest_path = out_dir / f"{ticket}-rlm-slice.latest{ext}"

    payload: Dict[str, object] = {
        "schema": SCHEMA,
        "pack_version": PACK_VERSION,
        "type": "rlm-slice",
        "kind": "pack",
        "ticket": ticket,
        "slug_hint": context.slug_hint,
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "query": args.query,
        "links": {
            "nodes": runtime.rel_path(nodes_path, target),
            "edges": runtime.rel_path(links_path, target),
        },
        "stats": {
            "nodes": len(selected_nodes),
            "links": len(selected_links),
            "nodes_truncated": truncated_nodes,
            "links_truncated": truncated_links,
            "max_nodes": max_nodes,
            "max_links": max_links,
        },
        "nodes": selected_nodes,
        "edges": selected_links,
    }

    _write_pack(output_path, payload)
    _write_pack(latest_path, payload)
    rel_output = runtime.rel_path(output_path, target)
    print(f"[aidd] rlm slice saved to {rel_output}.")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
