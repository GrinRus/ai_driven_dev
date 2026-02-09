#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Dict, Iterable, List

from aidd_runtime import runtime
from aidd_runtime.io_utils import read_jsonl, write_jsonl


def _compact_nodes(nodes: List[Dict[str, object]]) -> List[Dict[str, object]]:
    dedup: Dict[str, Dict[str, object]] = {}
    for node in nodes:
        node_id = str(node.get("id") or node.get("file_id") or node.get("dir_id") or "").strip()
        if not node_id:
            continue
        dedup[node_id] = node
    def sort_key(item: Dict[str, object]) -> tuple:
        node_kind = str(item.get("node_kind") or "")
        path = str(item.get("path") or "")
        node_id = str(item.get("id") or item.get("file_id") or item.get("dir_id") or "")
        return (node_kind, path, node_id)
    return sorted(dedup.values(), key=sort_key)


def _compact_links(links: List[Dict[str, object]]) -> List[Dict[str, object]]:
    dedup: Dict[str, Dict[str, object]] = {}
    for link in links:
        link_id = str(link.get("link_id") or "").strip()
        if not link_id:
            continue
        dedup[link_id] = link
    def sort_key(item: Dict[str, object]) -> tuple:
        evidence = item.get("evidence_ref") or {}
        match_hash = evidence.get("match_hash") or ""
        return (
            str(item.get("src_file_id") or ""),
            str(item.get("type") or ""),
            str(item.get("dst_file_id") or ""),
            str(match_hash),
        )
    return sorted(dedup.values(), key=sort_key)


def parse_args(argv: List[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compact RLM JSONL files deterministically.")
    parser.add_argument("--ticket", help="Ticket identifier (defaults to docs/.active.json).")
    parser.add_argument("--nodes", help="Override nodes.jsonl path.")
    parser.add_argument("--links", help="Override links.jsonl path.")
    return parser.parse_args(argv)


def main(argv: List[str] | None = None) -> int:
    args = parse_args(argv)
    _, target = runtime.require_workflow_root()
    ticket, _ = runtime.require_ticket(target, ticket=args.ticket, slug_hint=None)

    nodes_path = (
        runtime.resolve_path_for_target(Path(args.nodes), target)
        if args.nodes
        else target / "reports" / "research" / f"{ticket}-rlm.nodes.jsonl"
    )
    links_path = (
        runtime.resolve_path_for_target(Path(args.links), target)
        if args.links
        else target / "reports" / "research" / f"{ticket}-rlm.links.jsonl"
    )

    if nodes_path.exists():
        nodes = read_jsonl(nodes_path)
        compacted = _compact_nodes(nodes)
        write_jsonl(nodes_path, compacted)

    if links_path.exists():
        links = read_jsonl(links_path)
        compacted = _compact_links(links)
        write_jsonl(links_path, compacted)

    print("[aidd] rlm jsonl compact complete.")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
