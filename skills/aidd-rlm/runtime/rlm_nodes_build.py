#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

from aidd_runtime import rlm_targets, runtime
from aidd_runtime.rlm_config import (
    base_root_for_label,
    file_id_for_path,
    load_rlm_settings,
    normalize_ignore_dirs,
    normalize_path,
    paths_base_for,
)


SCHEMA = "aidd.report.pack.v1"
PACK_VERSION = "v1"
NODE_SCHEMA = "aidd.rlm_node.v2"
NODE_SCHEMA_VERSION = "v2"
DEFAULT_DIR_CHILDREN_LIMIT = 50
DEFAULT_DIR_SUMMARY_CHARS = 600
BOOTSTRAP_SUMMARY_PREFIX = "Auto bootstrap node for"


def _pack_extension() -> str:
    return ".pack.json"


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


def _split_values(raw: object | Iterable[str] | None) -> List[str]:
    if raw is None:
        return []
    if isinstance(raw, (list, tuple, set)):
        items = list(raw)
    else:
        items = [raw]
    values: List[str] = []
    for item in items:
        if item is None:
            continue
        text = str(item)
        for chunk in text.split(","):
            cleaned = chunk.strip()
            if cleaned:
                values.append(cleaned)
    return list(dict.fromkeys(values))


def _normalize_worklist_paths(values: object | Iterable[str] | None, *, base_root: Path) -> List[str]:
    prefixes = rlm_targets.normalize_prefixes(_split_values(values))
    normalized: List[str] = []
    base_resolved = base_root.resolve()
    for prefix in prefixes:
        path = Path(prefix)
        if path.is_absolute():
            try:
                rel = path.resolve().relative_to(base_resolved)
                cleaned = normalize_path(rel)
            except ValueError:
                cleaned = normalize_path(path)
        else:
            cleaned = normalize_path(path)
        if cleaned:
            normalized.append(cleaned)
    return list(dict.fromkeys(normalized))


def _normalize_worklist_keywords(values: object | Iterable[str] | None) -> List[str]:
    keywords = [item for item in _split_values(values) if str(item).strip()]
    return list(dict.fromkeys(keywords))


def _resolve_base_root(target: Path, manifest: Dict) -> Path:
    raw_targets = manifest.get("targets_path")
    if raw_targets:
        try:
            targets_path = runtime.resolve_path_for_target(Path(str(raw_targets)), target)
        except (TypeError, ValueError):
            targets_path = None
        if targets_path and targets_path.exists():
            try:
                payload = json.loads(targets_path.read_text(encoding="utf-8"))
            except Exception:
                payload = {}
            base_label = payload.get("paths_base")
            if base_label:
                return base_root_for_label(target, base_label)
    return paths_base_for(target)


def _matches_prefix(path: str, prefixes: List[str]) -> bool:
    for prefix in prefixes:
        if path == prefix or path.startswith(f"{prefix}/"):
            return True
    return False


def _resolve_keyword_roots(base_root: Path, prefixes: List[str]) -> List[Path]:
    if prefixes:
        roots = [base_root / Path(prefix) for prefix in prefixes]
    else:
        roots = [base_root]
    return [path for path in roots if path.exists()]


def _filter_manifest_entries(
    target: Path,
    manifest: Dict,
    *,
    settings: Dict,
    worklist_paths: object | Iterable[str] | None,
    worklist_keywords: object | Iterable[str] | None,
) -> Tuple[List[Dict[str, object]], Dict[str, object] | None]:
    entries = manifest.get("files") or []
    if not isinstance(entries, list):
        entries = []
    entries = [item for item in entries if isinstance(item, dict)]

    base_root = _resolve_base_root(target, manifest)
    scope_paths = _normalize_worklist_paths(worklist_paths, base_root=base_root)
    scope_keywords = _normalize_worklist_keywords(worklist_keywords)
    if not scope_paths and not scope_keywords:
        return entries, None

    path_filtered = entries
    if scope_paths:
        path_filtered = []
        for item in entries:
            raw_path = str(item.get("path") or "").strip()
            if not raw_path:
                continue
            normalized = normalize_path(Path(raw_path))
            if _matches_prefix(normalized, scope_paths):
                path_filtered.append(item)
    path_filtered_paths = {
        normalize_path(Path(str(item.get("path") or "")))
        for item in path_filtered
        if str(item.get("path") or "").strip()
    }

    keyword_hits: set[str] = set()
    if scope_keywords:
        roots = _resolve_keyword_roots(base_root, scope_paths)
        ignore_dirs = normalize_ignore_dirs(settings.get("ignore_dirs"))
        if roots:
            keyword_hits = rlm_targets.rg_files_with_matches(
                base_root,
                scope_keywords,
                roots,
                ignore_dirs,
                base_root=base_root,
            )
        keyword_hits = {path for path in keyword_hits if path in path_filtered_paths}
        path_filtered = [
            item
            for item in path_filtered
            if normalize_path(Path(str(item.get("path") or ""))) in keyword_hits
        ]

    scope = {
        "paths": scope_paths,
        "keywords": scope_keywords,
        "counts": {
            "manifest_total": len(entries),
            "paths_matched": len(path_filtered_paths) if scope_paths else len(entries),
            "keyword_matches": len(keyword_hits) if scope_keywords else 0,
            "entries_selected": len(path_filtered),
        },
    }
    return path_filtered, scope


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


def _build_bootstrap_nodes(manifest: Dict[str, object]) -> List[Dict[str, object]]:
    entries = manifest.get("files") or []
    if not isinstance(entries, list):
        return []
    nodes: List[Dict[str, object]] = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        file_id = str(entry.get("file_id") or "").strip()
        path = str(entry.get("path") or "").strip()
        if not file_id or not path:
            continue
        summary = f"{BOOTSTRAP_SUMMARY_PREFIX} {path}."
        nodes.append(
            {
                "schema": NODE_SCHEMA,
                "schema_version": NODE_SCHEMA_VERSION,
                "node_kind": "file",
                "id": file_id,
                "file_id": file_id,
                "path": path,
                "rev_sha": entry.get("rev_sha") or "",
                "lang": entry.get("lang") or "",
                "prompt_version": entry.get("prompt_version") or "",
                "summary": summary,
                "public_symbols": [],
                "type_refs": [],
                "key_calls": [],
                "framework_roles": [],
                "test_hooks": [],
                "risks": [],
                "verification": "unverified",
                "missing_tokens": [],
            }
        )
    return nodes


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


def _build_worklist(entries: List[Dict[str, object]], nodes_path: Path) -> Tuple[List[Dict[str, object]], Dict[str, int]]:
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
    worklist_paths: List[str] | None = None,
    worklist_keywords: List[str] | None = None,
) -> Dict[str, object]:
    manifest = _load_manifest(manifest_path)
    settings = load_rlm_settings(target)
    raw_paths = worklist_paths if worklist_paths is not None else settings.get("worklist_paths")
    raw_keywords = worklist_keywords if worklist_keywords is not None else settings.get("worklist_keywords")
    filtered_entries, worklist_scope = _filter_manifest_entries(
        target,
        manifest,
        settings=settings,
        worklist_paths=raw_paths,
        worklist_keywords=raw_keywords,
    )
    worklist, stats = _build_worklist(filtered_entries, nodes_path)
    entries_total = len(worklist)
    max_entries = int(settings.get("worklist_max_entries") or 0)
    entries_trimmed = 0
    trim_reason = None
    if max_entries and entries_total > max_entries:
        entries_trimmed = entries_total - max_entries
        trim_reason = "max_entries"
        worklist = worklist[:max_entries]
    status = "ready" if not worklist else "pending"
    pack = {
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
            "entries_total": entries_total,
            "entries_trimmed": entries_trimmed,
            "trim_reason": trim_reason,
            **stats,
        },
        "entries": worklist,
    }
    if worklist_scope:
        pack["worklist_scope"] = worklist_scope
    return pack


def _load_existing_worklist_scope(path: Path) -> Tuple[List[str], List[str]] | None:
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    scope = payload.get("worklist_scope")
    if not isinstance(scope, dict):
        return None
    raw_paths = scope.get("paths") or []
    raw_keywords = scope.get("keywords") or []
    paths = [str(item).strip() for item in raw_paths if str(item).strip()]
    keywords = [str(item).strip() for item in raw_keywords if str(item).strip()]
    if not paths and not keywords:
        return None
    return paths, keywords


def parse_args(argv: List[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate RLM worklist pack for agent nodes.")
    parser.add_argument("--ticket", help="Ticket identifier (defaults to docs/.active.json).")
    parser.add_argument("--manifest", help="Override manifest path.")
    parser.add_argument("--nodes", help="Override nodes.jsonl path.")
    parser.add_argument("--output", help="Override output pack path.")
    parser.add_argument(
        "--worklist-paths",
        action="append",
        help="Comma-separated path prefixes to narrow worklist scope.",
    )
    parser.add_argument(
        "--worklist-keywords",
        action="append",
        help="Comma-separated keywords to narrow worklist scope.",
    )
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
    parser.add_argument(
        "--bootstrap",
        action="store_true",
        help="Create baseline file nodes from the manifest when nodes are missing.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing nodes when bootstrapping.",
    )
    parser.add_argument(
        "--refresh-worklist",
        action="store_true",
        help="Rewrite worklist pack (preserves previous scope when no explicit scope is provided).",
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
    if args.bootstrap:
        manifest = _load_manifest(manifest_path)
        new_nodes = _build_bootstrap_nodes(manifest)
        existing_nodes = [] if args.force or not nodes_path.exists() else list(_iter_nodes(nodes_path))
        existing_ids = {
            str(node.get("id") or node.get("file_id") or node.get("dir_id") or "").strip()
            for node in existing_nodes
        }
        added = [node for node in new_nodes if str(node.get("id") or "").strip() not in existing_ids]
        if existing_nodes and not args.force:
            merged = _compact_nodes(new_nodes + existing_nodes)
        else:
            merged = _compact_nodes(new_nodes)
        nodes_path.parent.mkdir(parents=True, exist_ok=True)
        _write_nodes(nodes_path, merged)
        rel_nodes = runtime.rel_path(nodes_path, target)
        print(
            f"[aidd] rlm bootstrap nodes saved to {rel_nodes} "
            f"(added={len(added)}, total={len(merged)})."
        )
        if not merged:
            print("[aidd] WARN: rlm bootstrap produced no nodes (empty manifest).")
        return 0
    if args.mode != "agent-worklist":
        raise SystemExit(f"unsupported mode: {args.mode}")
    output = (
        runtime.resolve_path_for_target(Path(args.output), target)
        if args.output
        else target
        / "reports"
        / "research"
        / f"{ticket}-rlm.worklist{_pack_extension()}"
    )
    worklist_paths = args.worklist_paths
    worklist_keywords = args.worklist_keywords
    if args.refresh_worklist and not worklist_paths and not worklist_keywords:
        scope = _load_existing_worklist_scope(output)
        if scope:
            worklist_paths, worklist_keywords = scope
    pack = build_worklist_pack(
        target,
        ticket,
        manifest_path=manifest_path,
        nodes_path=nodes_path,
        worklist_paths=worklist_paths,
        worklist_keywords=worklist_keywords,
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(pack, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    rel_output = runtime.rel_path(output, target)
    print(f"[aidd] rlm worklist saved to {rel_output}.")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
