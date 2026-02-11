#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Dict, Iterable, List

from aidd_runtime import runtime
from aidd_runtime.rlm_config import load_rlm_settings, resolve_source_path


def _symbol_variants(symbol: str) -> List[str]:
    symbol = symbol.strip()
    if not symbol:
        return []
    variants = [symbol]
    if "." in symbol:
        variants.append(symbol.split(".")[-1])
    if "::" in symbol:
        variants.append(symbol.split("::")[-1])
    return list(dict.fromkeys(variants))


def _contains_symbol(text: str, symbol: str) -> bool:
    return symbol in text


def _validate_symbols(text: str, symbols: Iterable[str]) -> List[str]:
    missing: List[str] = []
    for sym in symbols:
        sym = str(sym).strip()
        if not sym:
            continue
        variants = _symbol_variants(sym)
        if not variants:
            continue
        if any(_contains_symbol(text, variant) for variant in variants):
            continue
        missing.append(sym)
    return missing


def _iter_nodes(path: Path) -> List[Dict[str, object]]:
    nodes: List[Dict[str, object]] = []
    if not path.exists():
        return nodes
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
    return nodes


def _write_nodes(path: Path, nodes: Iterable[Dict[str, object]]) -> None:
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    with tmp_path.open("w", encoding="utf-8") as handle:
        for node in nodes:
            handle.write(json.dumps(node, ensure_ascii=False) + "\n")
    tmp_path.replace(path)


def verify_nodes(
    project_root: Path,
    workspace_root: Path,
    nodes_path: Path,
    *,
    max_file_bytes: int,
) -> int:
    nodes = _iter_nodes(nodes_path)
    updated = 0
    for node in nodes:
        if node.get("node_kind") != "file":
            continue
        raw_path = node.get("path")
        if not raw_path:
            node["verification"] = "failed"
            node["missing_tokens"] = []
            updated += 1
            continue
        file_path = resolve_source_path(
            Path(str(raw_path)),
            project_root=project_root,
            workspace_root=workspace_root,
        )
        if not file_path.exists():
            node["verification"] = "failed"
            node["missing_tokens"] = []
            updated += 1
            continue
        try:
            data = file_path.read_bytes()
        except OSError:
            node["verification"] = "failed"
            node["missing_tokens"] = []
            updated += 1
            continue
        if max_file_bytes and len(data) > max_file_bytes:
            node["verification"] = "failed"
            node["missing_tokens"] = []
            updated += 1
            continue
        text = data.decode("utf-8", errors="replace")
        public_symbols = node.get("public_symbols") or []
        key_calls = node.get("key_calls") or []
        type_refs = node.get("type_refs") or []
        expected_symbols = [
            sym for sym in list(public_symbols) + list(type_refs) + list(key_calls) if str(sym).strip()
        ]
        missing = _validate_symbols(text, expected_symbols)
        node["missing_tokens"] = missing
        if not expected_symbols:
            node["verification"] = "passed"
        elif missing and len(missing) >= len(expected_symbols):
            node["verification"] = "failed"
        elif missing:
            node["verification"] = "partial"
        else:
            node["verification"] = "passed"
        updated += 1
    _write_nodes(nodes_path, nodes)
    return updated


def parse_args(argv: List[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Verify RLM nodes against source files.")
    parser.add_argument("--ticket", help="Ticket identifier (defaults to docs/.active.json).")
    parser.add_argument("--nodes", help="Override nodes.jsonl path.")
    return parser.parse_args(argv)


def main(argv: List[str] | None = None) -> int:
    args = parse_args(argv)
    workspace_root, project_root = runtime.require_workflow_root()
    ticket, _ = runtime.require_ticket(project_root, ticket=args.ticket, slug_hint=None)
    settings = load_rlm_settings(project_root)
    max_file_bytes = int(settings.get("max_file_bytes") or 0)

    nodes_path = (
        runtime.resolve_path_for_target(Path(args.nodes), project_root)
        if args.nodes
        else project_root / "reports" / "research" / f"{ticket}-rlm.nodes.jsonl"
    )
    if not nodes_path.exists():
        raise SystemExit(f"rlm nodes not found: {nodes_path}")
    updated = verify_nodes(project_root, workspace_root, nodes_path, max_file_bytes=max_file_bytes)
    rel_nodes = runtime.rel_path(nodes_path, project_root)
    print(f"[aidd] rlm verify updated {updated} nodes in {rel_nodes}.")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
