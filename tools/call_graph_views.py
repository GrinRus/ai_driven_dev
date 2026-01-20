from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

EDGE_SCHEMA = "aidd.call_graph_edge.v1"


def _edge_record(edge: Dict[str, object]) -> Dict[str, object]:
    return {
        "schema": EDGE_SCHEMA,
        "caller": edge.get("caller"),
        "callee": edge.get("callee"),
        "file": edge.get("file"),
        "line": edge.get("line"),
        "language": edge.get("language"),
        "caller_raw": edge.get("caller_raw"),
    }


def write_edges_jsonl(
    edges: Iterable[Dict[str, object]],
    output: Path,
    *,
    max_edges: int | None = None,
) -> Tuple[int, bool]:
    output.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    truncated = False
    with output.open("w", encoding="utf-8") as handle:
        for edge in edges:
            if max_edges is not None and max_edges > 0 and count >= max_edges:
                truncated = True
                break
            if not isinstance(edge, dict):
                continue
            handle.write(json.dumps(_edge_record(edge), ensure_ascii=False) + "\n")
            count += 1
    return count, truncated


def summarize_edges(edges: List[Dict[str, object]]) -> Dict[str, int]:
    total = len(edges)
    return {"edges_total": total}
