#!/usr/bin/env python3
"""Export work-item DAG with read/write boundaries and conflict hints."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List, Tuple

from aidd_runtime import runtime
from aidd_runtime.diff_boundary_check import extract_boundaries, parse_front_matter
from aidd_runtime.io_utils import utc_timestamp

STAGES = ["preflight", "implement", "review", "qa"]
IGNORE_CONFLICT_PATHS = {"aidd/reports/**", "aidd/reports/actions/**"}


def _load_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _parse_loop_pack(path: Path) -> Dict[str, Any]:
    lines = path.read_text(encoding="utf-8").splitlines()
    front = parse_front_matter(lines)
    allowed_paths, _forbidden = extract_boundaries(front)
    # parse_front_matter from diff_boundary_check returns raw front-matter lines only,
    # so we read simple key-values manually below.
    meta: Dict[str, str] = {}
    for raw in front:
        if ":" not in raw:
            continue
        key, value = raw.split(":", 1)
        meta[key.strip()] = value.strip()
    return {
        "scope_key": meta.get("scope_key") or path.name.replace(".loop.pack.md", ""),
        "work_item_key": meta.get("work_item_key") or "",
        "allowed_paths": [item for item in allowed_paths if str(item).strip()],
    }


def _scope_paths(loop_dir: Path) -> List[Path]:
    return sorted(path for path in loop_dir.glob("*.loop.pack.md") if path.is_file())


def _clean_conflict_paths(paths: List[str]) -> List[str]:
    cleaned: List[str] = []
    for item in paths:
        value = str(item or "").strip()
        if not value or value in IGNORE_CONFLICT_PATHS:
            continue
        if value.startswith("aidd/reports/") or value.startswith("reports/"):
            continue
        cleaned.append(value)
    deduped: List[str] = []
    for item in cleaned:
        if item not in deduped:
            deduped.append(item)
    return deduped


def _resolve_allowed_paths(
    target: Path,
    ticket: str,
    scope_key: str,
    loop_allowed: List[str],
) -> Tuple[List[str], str, str]:
    readmap_path = target / "reports" / "actions" / ticket / scope_key / "readmap.json"
    writemap_path = target / "reports" / "actions" / ticket / scope_key / "writemap.json"

    writemap = _load_json(writemap_path)
    readmap = _load_json(readmap_path)

    allowed = []
    if isinstance(writemap.get("allowed_paths"), list):
        allowed = [str(item) for item in writemap.get("allowed_paths") if str(item).strip()]
    if not allowed:
        allowed = list(loop_allowed)

    readmap_rel = runtime.rel_path(readmap_path, target) if readmap_path.exists() else ""
    writemap_rel = runtime.rel_path(writemap_path, target) if writemap_path.exists() else ""
    return allowed, readmap_rel, writemap_rel


def _build_nodes(
    target: Path,
    *,
    ticket: str,
    scopes: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    nodes: List[Dict[str, Any]] = []
    for scope in sorted(scopes, key=lambda item: str(item.get("scope_key") or "")):
        scope_key = str(scope.get("scope_key") or "")
        work_item_key = str(scope.get("work_item_key") or "")
        loop_allowed = [str(item) for item in scope.get("allowed_paths") or [] if str(item).strip()]
        allowed, readmap_rel, writemap_rel = _resolve_allowed_paths(target, ticket, scope_key, loop_allowed)

        for stage in STAGES:
            node_id = f"{scope_key}:{stage}"
            nodes.append(
                {
                    "id": node_id,
                    "stage": stage,
                    "scope_key": scope_key,
                    "work_item_key": work_item_key,
                    "allowed_paths": list(allowed),
                    "readmap": readmap_rel,
                    "writemap": writemap_rel,
                }
            )
    return nodes


def _build_edges(nodes: List[Dict[str, Any]]) -> List[Dict[str, str]]:
    by_scope: Dict[str, Dict[str, str]] = {}
    for node in nodes:
        scope_key = str(node.get("scope_key") or "")
        stage = str(node.get("stage") or "")
        node_id = str(node.get("id") or "")
        by_scope.setdefault(scope_key, {})[stage] = node_id

    edges: List[Dict[str, str]] = []
    for scope_key in sorted(by_scope):
        mapping = by_scope[scope_key]
        for idx in range(len(STAGES) - 1):
            src = mapping.get(STAGES[idx])
            dst = mapping.get(STAGES[idx + 1])
            if not src or not dst:
                continue
            edges.append({"from": src, "to": dst, "type": "sequential"})
    return edges


def _build_conflicts(nodes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    by_scope: Dict[str, List[str]] = {}
    for node in nodes:
        stage = str(node.get("stage") or "")
        if stage != "preflight":
            continue
        scope_key = str(node.get("scope_key") or "")
        paths = _clean_conflict_paths([str(item) for item in node.get("allowed_paths") or []])
        by_scope[scope_key] = paths

    conflicts: List[Dict[str, Any]] = []
    scopes = sorted(by_scope)
    for idx, left in enumerate(scopes):
        for right in scopes[idx + 1 :]:
            shared = sorted(set(by_scope[left]).intersection(by_scope[right]))
            if not shared:
                continue
            conflicts.append(
                {
                    "scope_a": left,
                    "scope_b": right,
                    "shared_paths": shared,
                    "recommendation": "do_not_parallelize",
                }
            )
    return conflicts


def _render_markdown(payload: Dict[str, Any]) -> str:
    lines = [
        f"# DAG Export — {payload.get('ticket')}",
        "",
        f"- schema: {payload.get('schema')}",
        f"- generated_at: {payload.get('generated_at')}",
        f"- nodes: {len(payload.get('nodes') or [])}",
        f"- edges: {len(payload.get('edges') or [])}",
        f"- conflicts: {len(payload.get('conflicts') or [])}",
        "",
        "## Nodes",
    ]
    for node in payload.get("nodes") or []:
        lines.append(
            f"- {node.get('id')} (scope: {node.get('scope_key')}, stage: {node.get('stage')}, "
            f"allowed_paths: {len(node.get('allowed_paths') or [])})"
        )

    lines.extend(["", "## Edges"])
    for edge in payload.get("edges") or []:
        lines.append(f"- {edge.get('from')} -> {edge.get('to')} ({edge.get('type')})")

    lines.extend(["", "## Conflicts"])
    conflicts = payload.get("conflicts") or []
    if not conflicts:
        lines.append("- none")
    else:
        for conflict in conflicts:
            shared = ", ".join(conflict.get("shared_paths") or [])
            lines.append(
                f"- {conflict.get('scope_a')} <-> {conflict.get('scope_b')}: {shared} "
                f"[{conflict.get('recommendation')}]"
            )

    return "\n".join(lines).rstrip() + "\n"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export workflow DAG for work items.")
    parser.add_argument("--ticket", help="Ticket identifier (defaults to docs/.active.json)")
    parser.add_argument("--slug-hint", help="Optional slug hint override")
    parser.add_argument("--format", choices=("text", "json"), default="text")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    _, target = runtime.require_workflow_root(Path.cwd())
    ticket, _context = runtime.require_ticket(target, ticket=args.ticket, slug_hint=args.slug_hint)

    loop_dir = target / "reports" / "loops" / ticket
    if not loop_dir.exists():
        raise FileNotFoundError(f"loop directory not found: {runtime.rel_path(loop_dir, target)}")

    scope_payloads = []
    for path in _scope_paths(loop_dir):
        payload = _parse_loop_pack(path)
        scope_key = str(payload.get("scope_key") or "").strip()
        if not scope_key:
            continue
        payload["scope_key"] = scope_key
        scope_payloads.append(payload)

    if not scope_payloads:
        raise FileNotFoundError("no loop pack files found for DAG export")

    nodes = _build_nodes(target, ticket=ticket, scopes=scope_payloads)
    edges = _build_edges(nodes)
    conflicts = _build_conflicts(nodes)

    payload = {
        "schema": "aidd.dag.v1",
        "ticket": ticket,
        "generated_at": utc_timestamp(),
        "nodes": nodes,
        "edges": edges,
        "conflicts": conflicts,
    }

    output_dir = target / "reports" / "dag"
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / f"{ticket}.json"
    md_path = output_dir / f"{ticket}.md"

    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    md_path.write_text(_render_markdown(payload), encoding="utf-8")

    if args.format == "json":
        print(
            json.dumps(
                {
                    "schema": "aidd.dag.export.result.v1",
                    "status": "ok",
                    "ticket": ticket,
                    "json_path": runtime.rel_path(json_path, target),
                    "md_path": runtime.rel_path(md_path, target),
                    "nodes": len(nodes),
                    "edges": len(edges),
                    "conflicts": len(conflicts),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
    else:
        print(f"json_path={runtime.rel_path(json_path, target)}")
        print(f"md_path={runtime.rel_path(md_path, target)}")
        print(f"summary=dag export ok nodes={len(nodes)} edges={len(edges)} conflicts={len(conflicts)}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
