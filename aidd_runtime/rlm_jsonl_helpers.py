from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Iterable, List


def compact_nodes(nodes: List[Dict[str, object]]) -> List[Dict[str, object]]:
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


def write_nodes(path: Path, nodes: Iterable[Dict[str, object]]) -> None:
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    with tmp_path.open("w", encoding="utf-8") as handle:
        for node in nodes:
            handle.write(json.dumps(node, ensure_ascii=False) + "\n")
    tmp_path.replace(path)
