#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import re
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from tools import runtime

SCHEMA = "aidd.report.pack.v1"
PACK_VERSION = "v1"


def _pack_extension() -> str:
    return ".pack.toon" if os.getenv("AIDD_PACK_FORMAT", "").strip().lower() == "toon" else ".pack.yaml"


def _hash_slice_key(query: str, paths: Sequence[str], langs: Sequence[str]) -> str:
    parts = [query]
    if paths:
        parts.append("paths=" + ",".join(paths))
    if langs:
        parts.append("langs=" + ",".join(langs))
    return hashlib.sha1("|".join(parts).encode("utf-8")).hexdigest()[:10]


def _load_context_edges_path(root: Path, ticket: str) -> Optional[Path]:
    context_path = root / "reports" / "research" / f"{ticket}-context.json"
    if not context_path.exists():
        return None
    try:
        payload = json.loads(context_path.read_text(encoding="utf-8"))
    except Exception:
        return None
    edges_path = payload.get("call_graph_edges_path")
    resolved_edges = runtime.resolve_path_for_target(Path(edges_path), root) if edges_path else None
    return resolved_edges


def _compile_query(query: str) -> re.Pattern[str]:
    try:
        return re.compile(query, re.IGNORECASE)
    except re.error:
        return re.compile(re.escape(query), re.IGNORECASE)


def _edge_matches(edge: Dict[str, object], pattern: re.Pattern[str]) -> bool:
    for key in ("caller", "callee", "caller_file", "callee_file", "file", "caller_raw"):
        value = edge.get(key)
        if value and pattern.search(str(value)):
            return True
    return False


def _edge_matches_paths(edge: Dict[str, object], paths: Sequence[str]) -> bool:
    if not paths:
        return True
    caller_file = str(edge.get("caller_file") or edge.get("file") or "")
    callee_file = str(edge.get("callee_file") or edge.get("file") or "")
    for token in paths:
        if token and (token in caller_file or token in callee_file):
            return True
    return False


def _edge_matches_lang(edge: Dict[str, object], langs: Sequence[str]) -> bool:
    if not langs:
        return True
    lang = str(edge.get("lang") or edge.get("language") or "").lower()
    return lang in langs


def _iter_edges_from_jsonl(path: Path) -> Iterable[Dict[str, object]]:
    try:
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
    except OSError:
        return


def _collect_slice(
    edges: Iterable[Dict[str, object]],
    pattern: re.Pattern[str],
    *,
    max_edges: int,
    max_nodes: int,
    paths: Sequence[str],
    langs: Sequence[str],
) -> Tuple[List[Dict[str, object]], List[str], bool]:
    selected: List[Dict[str, object]] = []
    nodes: List[str] = []
    nodes_set: set[str] = set()
    truncated = False
    for edge in edges:
        if max_edges and len(selected) >= max_edges:
            truncated = True
            break
        if not _edge_matches_lang(edge, langs):
            continue
        if not _edge_matches_paths(edge, paths):
            continue
        if not _edge_matches(edge, pattern):
            continue
        caller = str(edge.get("caller") or "").strip()
        callee = str(edge.get("callee") or "").strip()
        new_nodes = [node for node in (caller, callee) if node and node not in nodes_set]
        if max_nodes and len(nodes_set) + len(new_nodes) > max_nodes:
            truncated = True
            break
        selected.append(
            {
                "caller": edge.get("caller"),
                "callee": edge.get("callee"),
                "caller_file": edge.get("caller_file") or edge.get("file"),
                "caller_line": edge.get("caller_line") or edge.get("line"),
                "callee_file": edge.get("callee_file") or edge.get("file"),
                "callee_line": edge.get("callee_line") or edge.get("line"),
                "lang": edge.get("lang") or edge.get("language"),
                "type": edge.get("type"),
            }
        )
        for node in new_nodes:
            nodes_set.add(node)
            nodes.append(node)
    return selected, nodes, truncated


def _write_pack(path: Path, payload: Dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    path.write_text(text, encoding="utf-8")


def parse_args(argv: List[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate a compact call-graph slice pack.")
    parser.add_argument("--ticket", required=False, help="Ticket identifier (defaults to docs/.active_ticket).")
    parser.add_argument("--query", required=True, help="Regex or token to match in call graph edges.")
    parser.add_argument("--max-edges", type=int, default=40, help="Maximum number of edges to include.")
    parser.add_argument("--max-nodes", type=int, default=20, help="Maximum number of nodes to include.")
    parser.add_argument(
        "--paths",
        help="Optional comma-separated list of path fragments to keep (matches caller/callee file).",
    )
    parser.add_argument("--lang", help="Optional comma-separated list of languages to keep (kt,kts,java,py,js).")
    parser.add_argument("--out", default=None, help="Optional output path for the pack.")
    return parser.parse_args(argv)


def main(argv: List[str] | None = None) -> int:
    args = parse_args(argv)
    _, target = runtime.require_workflow_root()
    ticket, context = runtime.require_ticket(target, ticket=args.ticket, slug_hint=None)

    edges_path = _load_context_edges_path(target, ticket)
    if edges_path is None:
        edges_path = target / "reports" / "research" / f"{ticket}-call-graph.edges.jsonl"

    pattern = _compile_query(args.query)
    max_edges = max(1, int(args.max_edges)) if args.max_edges else 40
    max_nodes = max(1, int(args.max_nodes)) if args.max_nodes else 20
    paths = [token.strip() for token in str(args.paths or "").split(",") if token.strip()]
    langs = [token.strip().lower() for token in str(args.lang or "").split(",") if token.strip()]

    edges_iter: Iterable[Dict[str, object]]
    if edges_path and edges_path.exists():
        edges_iter = _iter_edges_from_jsonl(edges_path)
    else:
        raise SystemExit("No call-graph edges available; generate research call-graph first.")

    edges, nodes, truncated = _collect_slice(
        edges_iter,
        pattern,
        max_edges=max_edges,
        max_nodes=max_nodes,
        paths=paths,
        langs=langs,
    )

    out_dir = target / "reports" / "context"
    ext = _pack_extension()
    query_hash = _hash_slice_key(args.query, paths, langs)
    default_path = out_dir / f"{ticket}-graph-slice-{query_hash}{ext}"
    output_path = runtime.resolve_path_for_target(Path(args.out), target) if args.out else default_path
    latest_path = out_dir / f"{ticket}-graph-slice.latest{ext}"

    payload: Dict[str, object] = {
        "schema": SCHEMA,
        "pack_version": PACK_VERSION,
        "type": "graph-slice",
        "kind": "pack",
        "ticket": ticket,
        "slug_hint": context.slug_hint,
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "query": args.query,
        "links": {
            "edges": runtime.rel_path(edges_path, target) if edges_path else None,
        },
        "stats": {
            "edges": len(edges),
            "nodes": len(nodes),
            "truncated": truncated,
            "max_edges": max_edges,
            "max_nodes": max_nodes,
        },
        "nodes": nodes,
        "edges": edges,
    }

    _write_pack(output_path, payload)
    _write_pack(latest_path, payload)
    rel_output = runtime.rel_path(output_path, target)
    print(f"[aidd] graph slice saved to {rel_output}.")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
