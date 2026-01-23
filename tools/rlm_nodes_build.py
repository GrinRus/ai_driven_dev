#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

from tools import runtime
from tools.rlm_config import file_id_for_path, load_rlm_settings


SCHEMA = "aidd.report.pack.v1"
PACK_VERSION = "v1"
NODE_SCHEMA = "aidd.rlm_node.v1"
NODE_SCHEMA_VERSION = "v1"
DEFAULT_DIR_CHILDREN_LIMIT = 50
DEFAULT_DIR_SUMMARY_CHARS = 600


def _pack_extension() -> str:
    return ".pack.toon" if os.getenv("AIDD_PACK_FORMAT", "").strip().lower() == "toon" else ".pack.yaml"


def _load_manifest(path: Path) -> Dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _iter_nodes(path: Path) -> Iterable[Dict[str, object]]:
    if not path.exists():
        return []
    nodes: List[Dict[str, object]] = []
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
                    nodes.append(payload)
    except OSError:
        return []
    return nodes


def _write_nodes(path: Path, nodes: Iterable[Dict[str, object]]) -> None:
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    with tmp_path.open("w", encoding="utf-8") as handle:
        for node in nodes:
            handle.write(json.dumps(node, ensure_ascii=False) + "\n")
    tmp_path.replace(path)


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


def _truncate_text(text: str, limit: int) -> str:
    if limit <= 0:
        return ""
    if len(text) <= limit:
        return text
    return text[:limit].rstrip()


def _entrypoints(child_nodes: Iterable[Dict[str, object]]) -> List[str]:
    entry_roles = {"web", "controller", "job", "config", "infra"}
    entrypaths: List[str] = []
    for node in child_nodes:
        roles = node.get("framework_roles") or []
        if any(role in entry_roles for role in roles):
            path = str(node.get("path") or "").strip()
            if path:
                entrypaths.append(path)
    return entrypaths


def _summarize_dir_nodes(
    child_nodes: List[Dict[str, object]],
    *,
    max_children: int,
    max_chars: int,
) -> tuple[list[str], str]:
    sorted_children = sorted(child_nodes, key=lambda item: str(item.get("path") or ""))
    children_ids = [
        str(node.get("file_id") or node.get("id") or "").strip()
        for node in sorted_children
        if str(node.get("file_id") or node.get("id") or "").strip()
    ]
    total = len(children_ids)
    children_ids = children_ids[:max_children] if max_children else children_ids

    summaries = [str(node.get("summary") or "").strip() for node in sorted_children if str(node.get("summary") or "").strip()]
    summaries = summaries[:3]

    symbols: List[str] = []
    for node in sorted_children:
        for symbol in node.get("public_symbols") or []:
            sym = str(symbol).strip()
            if sym and sym not in symbols:
                symbols.append(sym)
            if len(symbols) >= 8:
                break
        if len(symbols) >= 8:
            break

    entrypoints = _entrypoints(sorted_children)[:3]

    parts = [f"Module with {total} file(s)."]
    if entrypoints:
        parts.append(f"Entrypoints: {', '.join(entrypoints)}.")
    if symbols:
        parts.append(f"Symbols: {', '.join(symbols)}.")
    if summaries:
        parts.append(f"Highlights: {' | '.join(summaries)}.")
    summary = " ".join(parts).strip()
    return children_ids, _truncate_text(summary, max_chars)


def build_dir_nodes(
    nodes: List[Dict[str, object]],
    *,
    max_children: int = DEFAULT_DIR_CHILDREN_LIMIT,
    max_chars: int = DEFAULT_DIR_SUMMARY_CHARS,
) -> List[Dict[str, object]]:
    file_nodes = [node for node in nodes if node.get("node_kind") == "file" and node.get("path")]
    by_dir: Dict[str, List[Dict[str, object]]] = {}
    for node in file_nodes:
        path = Path(str(node.get("path")))
        for parent in path.parents:
            if parent.as_posix() in {".", ""}:
                continue
            key = parent.as_posix()
            by_dir.setdefault(key, []).append(node)

    dir_nodes: List[Dict[str, object]] = []
    for dir_path, children in sorted(by_dir.items(), key=lambda item: item[0]):
        dir_id = file_id_for_path(Path(dir_path))
        children_ids, summary = _summarize_dir_nodes(
            children,
            max_children=max_children,
            max_chars=max_chars,
        )
        dir_nodes.append(
            {
                "schema": NODE_SCHEMA,
                "schema_version": NODE_SCHEMA_VERSION,
                "node_kind": "dir",
                "id": dir_id,
                "dir_id": dir_id,
                "path": dir_path,
                "children_file_ids": children_ids,
                "children_count_total": len(children),
                "summary": summary,
            }
        )
    return dir_nodes


def _build_worklist(manifest: Dict, nodes_path: Path) -> Tuple[List[Dict[str, object]], Dict[str, int]]:
    entries = manifest.get("files") or []
    if not isinstance(entries, list):
        entries = []

    existing: Dict[str, List[Dict[str, object]]] = {}
    for node in _iter_nodes(nodes_path):
        if node.get("node_kind") != "file":
            continue
        file_id = str(node.get("file_id") or node.get("id") or "").strip()
        if not file_id:
            continue
        existing.setdefault(file_id, []).append(node)

    worklist: List[Dict[str, object]] = []
    stats = {"missing": 0, "outdated": 0, "failed": 0}
    for item in entries:
        if not isinstance(item, dict):
            continue
        file_id = str(item.get("file_id") or "").strip()
        rev_sha = str(item.get("rev_sha") or "").strip()
        prompt_version = str(item.get("prompt_version") or "").strip()
        if not file_id:
            continue
        nodes_for_id = existing.get(file_id) or []
        reason = ""
        if not nodes_for_id:
            reason = "missing"
        else:
            matching = [
                node
                for node in nodes_for_id
                if str(node.get("rev_sha") or "").strip() == rev_sha
                and str(node.get("prompt_version") or "").strip() == prompt_version
            ]
            if not matching:
                reason = "outdated"
            else:
                failures = 0
                for node in matching:
                    verification = str(node.get("verification") or "").strip().lower()
                    if verification == "failed":
                        failures += 1
                if failures == len(matching):
                    reason = "failed"
        if reason:
            stats[reason] += 1
            worklist.append(
                {
                    "file_id": file_id,
                    "path": item.get("path"),
                    "rev_sha": rev_sha,
                    "lang": item.get("lang"),
                    "prompt_version": prompt_version,
                    "size": item.get("size"),
                    "reason": reason,
                }
            )
    worklist = sorted(worklist, key=lambda entry: (entry.get("path") or "", entry.get("file_id") or ""))
    return worklist, stats


def build_worklist_pack(
    target: Path,
    ticket: str,
    *,
    manifest_path: Path,
    nodes_path: Path,
) -> Dict[str, object]:
    manifest = _load_manifest(manifest_path)
    worklist, stats = _build_worklist(manifest, nodes_path)
    status = "ready" if not worklist else "pending"
    return {
        "schema": SCHEMA,
        "pack_version": PACK_VERSION,
        "type": "rlm-worklist",
        "kind": "pack",
        "ticket": ticket,
        "slug_hint": manifest.get("slug_hint"),
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "status": status,
        "links": {
            "manifest": runtime.rel_path(manifest_path, target),
            "nodes": runtime.rel_path(nodes_path, target),
        },
        "stats": {
            "total": len(worklist),
            **stats,
        },
        "entries": worklist,
    }


def parse_args(argv: List[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate RLM worklist pack for agent nodes.")
    parser.add_argument("--ticket", help="Ticket identifier (defaults to docs/.active_ticket).")
    parser.add_argument("--manifest", help="Override manifest path.")
    parser.add_argument("--nodes", help="Override nodes.jsonl path.")
    parser.add_argument("--output", help="Override output pack path.")
    parser.add_argument(
        "--mode",
        choices=("agent-worklist",),
        default="agent-worklist",
        help="Worklist mode (only agent-worklist is supported).",
    )
    parser.add_argument(
        "--dir-nodes",
        action="store_true",
        help="Generate directory nodes from existing file nodes and append them to nodes.jsonl.",
    )
    return parser.parse_args(argv)


def main(argv: List[str] | None = None) -> int:
    args = parse_args(argv)
    _, target = runtime.require_workflow_root()
    ticket, _ = runtime.require_ticket(target, ticket=args.ticket, slug_hint=None)

    manifest_path = (
        runtime.resolve_path_for_target(Path(args.manifest), target)
        if args.manifest
        else target / "reports" / "research" / f"{ticket}-rlm-manifest.json"
    )
    if not manifest_path.exists():
        raise SystemExit(f"rlm manifest not found: {manifest_path}")
    nodes_path = (
        runtime.resolve_path_for_target(Path(args.nodes), target)
        if args.nodes
        else target / "reports" / "research" / f"{ticket}-rlm.nodes.jsonl"
    )
    if args.dir_nodes:
        if not nodes_path.exists():
            raise SystemExit(f"rlm nodes not found: {nodes_path}")
        existing_nodes = list(_iter_nodes(nodes_path))
        settings = load_rlm_settings(target)
        max_children = int(settings.get("dir_children_limit") or DEFAULT_DIR_CHILDREN_LIMIT)
        max_chars = int(settings.get("dir_summary_max_chars") or DEFAULT_DIR_SUMMARY_CHARS)
        dir_nodes = build_dir_nodes(existing_nodes, max_children=max_children, max_chars=max_chars)
        merged = _compact_nodes(existing_nodes + dir_nodes)
        _write_nodes(nodes_path, merged)
        rel_nodes = runtime.rel_path(nodes_path, target)
        print(f"[aidd] rlm dir nodes updated in {rel_nodes} ({len(dir_nodes)} dirs).")
        return 0
    if args.mode != "agent-worklist":
        raise SystemExit(f"unsupported mode: {args.mode}")
    pack = build_worklist_pack(target, ticket, manifest_path=manifest_path, nodes_path=nodes_path)

    output = (
        runtime.resolve_path_for_target(Path(args.output), target)
        if args.output
        else target
        / "reports"
        / "research"
        / f"{ticket}-rlm.worklist{_pack_extension()}"
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(pack, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    rel_output = runtime.rel_path(output, target)
    print(f"[aidd] rlm worklist saved to {rel_output}.")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
