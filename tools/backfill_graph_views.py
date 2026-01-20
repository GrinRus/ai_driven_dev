#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Optional

from tools import call_graph_views, reports_pack, runtime


def _load_edges_max(root: Path) -> int:
    config_path = root / "config" / "conventions.json"
    try:
        data = json.loads(config_path.read_text(encoding="utf-8"))
    except Exception:
        return 0
    researcher = data.get("researcher") if isinstance(data, dict) else {}
    call_graph = researcher.get("call_graph") if isinstance(researcher, dict) else {}
    try:
        return max(int(call_graph.get("edges_max", 0)), 0)
    except (TypeError, ValueError):
        return 0


def _edges_from_full(full_path: Path) -> list[dict]:
    try:
        payload = json.loads(full_path.read_text(encoding="utf-8"))
    except Exception:
        return []
    edges = payload.get("edges") if isinstance(payload, dict) else []
    return [edge for edge in edges if isinstance(edge, dict)]


def parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Backfill call-graph pack/view artifacts.")
    parser.add_argument("--root", default=".", help="Workspace or repo root (default: .).")
    return parser.parse_args(argv)


def main(argv: Optional[list[str]] = None) -> int:
    args = parse_args(argv)
    workspace_root, project_root = runtime.resolve_roots(Path(args.root), create=False)
    reports_dir = project_root / "reports" / "research"
    if not reports_dir.exists():
        print(f"[aidd] no research reports at {reports_dir}")
        return 0

    edges_max = _load_edges_max(project_root)
    full_graphs = sorted(reports_dir.glob("*-call-graph-full.json"))
    if not full_graphs:
        print("[aidd] no call-graph-full.json files found")
        return 0

    for full_path in full_graphs:
        ticket = full_path.name.replace("-call-graph-full.json", "")
        edges_path = full_path.with_name(f"{ticket}-call-graph.edges.jsonl")
        if not edges_path.exists():
            edges = _edges_from_full(full_path)
            limit = edges_max if edges_max > 0 else None
            count, truncated = call_graph_views.write_edges_jsonl(edges, edges_path, max_edges=limit)
            note = " (truncated)" if truncated else ""
            print(f"[aidd] edges view created for {ticket}: {count} edges{note}")

        pack_path = reports_dir / f"{ticket}-call-graph.pack.yaml"
        pack_toon = reports_dir / f"{ticket}-call-graph.pack.toon"
        if pack_path.exists() or pack_toon.exists():
            continue
        context_path = reports_dir / f"{ticket}-context.json"
        if not context_path.exists():
            print(f"[aidd] skip {ticket}: missing context.json for pack")
            continue
        try:
            pack = reports_pack.write_call_graph_pack(context_path, root=project_root)
        except Exception as exc:
            print(f"[aidd] failed to write pack for {ticket}: {exc}")
            continue
        rel_pack = runtime.rel_path(pack, project_root)
        print(f"[aidd] call-graph pack saved to {rel_pack}")

    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
