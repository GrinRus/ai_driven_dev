#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import re
import subprocess
from pathlib import Path
from typing import Callable, Dict, Iterable, List, Optional, Tuple

from tools import runtime
from tools.rlm_config import base_root_for_label, load_rlm_settings, resolve_source_path


SCHEMA = "aidd.rlm_link.v1"
SCHEMA_VERSION = "v1"
DEFAULT_RG_BATCH_SIZE = 24


def _iter_nodes(path: Path) -> Iterable[Dict[str, object]]:
    if not path.exists():
        return []
    nodes: List[Dict[str, object]] = []
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


def _load_targets(path: Path) -> Dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def _normalize_text(text: str) -> str:
    return " ".join(text.strip().split())


def _match_line(text: str, symbol: str) -> Optional[Tuple[int, str]]:
    if not symbol:
        return None
    escaped = re.escape(symbol)
    pattern = re.compile(rf"\\b{escaped}\\b")
    for idx, line in enumerate(text.splitlines(), start=1):
        if pattern.search(line):
            return idx, line
    if symbol in text:
        for idx, line in enumerate(text.splitlines(), start=1):
            if symbol in line:
                return idx, line
    return None


def _evidence_ref(
    path: str,
    line_start: int,
    line_end: int,
    line_text: str,
    *,
    extractor: str,
) -> Dict[str, object]:
    normalized = _normalize_text(line_text)
    match_hash = hashlib.sha1(f"{path}:{line_start}:{line_end}:{normalized}".encode("utf-8")).hexdigest()
    return {
        "path": path,
        "line_start": line_start,
        "line_end": line_end,
        "extractor": extractor,
        "match_hash": match_hash,
    }


def _rg_find_match(
    root: Path,
    symbol: str,
    files: List[str],
    *,
    timeout_s: int,
    max_hits: int,
) -> Optional[Tuple[str, int, str]]:
    if not files:
        return None
    cmd = ["rg", "--no-messages", "-n", "-F", "-m", str(max_hits), "--", symbol]
    cmd.extend(files)
    try:
        proc = subprocess.run(
            cmd,
            cwd=root,
            text=True,
            capture_output=True,
            timeout=timeout_s if timeout_s > 0 else None,
            check=False,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None
    if proc.returncode not in (0, 1):
        return None
    for line in proc.stdout.splitlines():
        parts = line.split(":", 2)
        if len(parts) < 3:
            continue
        raw_path, raw_line, raw_text = parts[0], parts[1], parts[2]
        try:
            line_no = int(raw_line)
        except ValueError:
            continue
        path = raw_path.strip()
        text = raw_text.rstrip()
        if path:
            return path, line_no, text
    return None


def _chunked(items: List[str], size: int) -> Iterable[List[str]]:
    if size <= 0:
        yield items
        return
    for idx in range(0, len(items), size):
        yield items[idx : idx + size]


def _rg_batch_find_matches(
    root: Path,
    symbols: List[str],
    files: List[str],
    *,
    timeout_s: int,
    max_hits: int,
) -> Tuple[Dict[str, Tuple[str, int, str]], Optional[str]]:
    if not symbols or not files:
        return {}, None
    cmd = ["rg", "--no-messages", "-n", "-F"]
    if max_hits and len(symbols) == 1:
        cmd.extend(["-m", str(max_hits)])
    for symbol in symbols:
        if symbol:
            cmd.extend(["-e", symbol])
    cmd.extend(["--"])
    cmd.extend(files)
    try:
        proc = subprocess.run(
            cmd,
            cwd=root,
            text=True,
            capture_output=True,
            timeout=timeout_s if timeout_s > 0 else None,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return {}, "timeout"
    except FileNotFoundError:
        return {}, "missing"
    if proc.returncode not in (0, 1):
        return {}, "error"
    matches: Dict[str, Tuple[str, int, str]] = {}
    for line in proc.stdout.splitlines():
        parts = line.split(":", 2)
        if len(parts) < 3:
            continue
        raw_path, raw_line, raw_text = parts[0], parts[1], parts[2]
        try:
            line_no = int(raw_line)
        except ValueError:
            continue
        path = raw_path.strip()
        text = raw_text.rstrip()
        if not path:
            continue
        for symbol in symbols:
            if symbol in matches:
                continue
            if symbol and symbol in text:
                matches[symbol] = (path, line_no, text)
        if len(matches) == len(symbols):
            break
    return matches, None


def _build_symbol_index(nodes: Iterable[Dict[str, object]]) -> Dict[str, List[Dict[str, object]]]:
    index: Dict[str, List[Dict[str, object]]] = {}
    for node in nodes:
        if node.get("node_kind") != "file":
            continue
        verification = str(node.get("verification") or "").strip().lower()
        if verification == "failed":
            continue
        missing = set(str(item).strip() for item in node.get("missing_tokens") or [])
        for sym in node.get("public_symbols") or []:
            sym = str(sym).strip()
            if not sym or sym in missing:
                continue
            index.setdefault(sym, []).append(node)
    return index


def _build_links(
    resolve_path: Callable[[str], Path],
    rg_root: Path,
    nodes: Iterable[Dict[str, object]],
    *,
    symbol_index: Dict[str, List[Dict[str, object]]],
    target_files: List[str],
    max_links: int,
    max_symbols_per_file: int,
    max_definition_hits_per_symbol: int,
    rg_timeout_s: int,
    rg_batch_size: int,
) -> Tuple[List[Dict[str, object]], bool, Dict[str, int]]:
    links: Dict[str, Dict[str, object]] = {}
    truncated = False
    stats = {
        "symbols_total": 0,
        "symbols_scanned": 0,
        "symbols_truncated": 0,
        "candidate_truncated": 0,
        "rg_calls": 0,
        "rg_timeouts": 0,
        "rg_errors": 0,
    }
    rg_cache: Dict[str, Optional[Tuple[str, int, str]]] = {}

    def _prime_rg_cache(pending_symbols: List[str]) -> None:
        if not pending_symbols or not target_files:
            return
        pending = list(dict.fromkeys(sym for sym in pending_symbols if sym and sym not in rg_cache))
        if not pending:
            return
        for chunk in _chunked(pending, rg_batch_size):
            matches, error = _rg_batch_find_matches(
                rg_root,
                chunk,
                target_files,
                timeout_s=rg_timeout_s,
                max_hits=max_definition_hits_per_symbol or 0,
            )
            stats["rg_calls"] += 1
            if error == "timeout":
                stats["rg_timeouts"] += 1
            elif error:
                stats["rg_errors"] += 1
            for sym in chunk:
                rg_cache[sym] = matches.get(sym)

    for node in nodes:
        if node.get("node_kind") != "file":
            continue
        file_id = str(node.get("file_id") or node.get("id") or "").strip()
        src_path = str(node.get("path") or "").strip()
        if not file_id or not src_path:
            continue
        file_path = resolve_path(src_path)
        if not file_path.exists():
            continue
        try:
            text = file_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        missing = set(str(item).strip() for item in node.get("missing_tokens") or [])
        raw_key_calls = [str(item).strip() for item in node.get("key_calls") or [] if str(item).strip()]
        stats["symbols_total"] += len(raw_key_calls)
        key_calls = list(raw_key_calls)
        if max_symbols_per_file:
            if len(key_calls) > max_symbols_per_file:
                stats["symbols_truncated"] += len(key_calls) - max_symbols_per_file
                key_calls = key_calls[: max_symbols_per_file]
        stats["symbols_scanned"] += len(key_calls)
        src_matches: Dict[str, Optional[Tuple[int, str]]] = {}
        pending_rg: List[str] = []
        for symbol in key_calls:
            if symbol in missing:
                continue
            match = _match_line(text, symbol)
            src_matches[symbol] = match
            if match is None and symbol not in rg_cache:
                pending_rg.append(symbol)
        _prime_rg_cache(pending_rg)
        for symbol in key_calls:
            if symbol in missing:
                continue
            candidates = symbol_index.get(symbol) or []
            if max_definition_hits_per_symbol:
                if len(candidates) > max_definition_hits_per_symbol:
                    stats["candidate_truncated"] += len(candidates) - max_definition_hits_per_symbol
                    candidates = candidates[: max_definition_hits_per_symbol]
            for target_node in candidates:
                dst_file_id = str(target_node.get("file_id") or target_node.get("id") or "").strip()
                dst_path = str(target_node.get("path") or "").strip()
                if not dst_file_id or dst_file_id == file_id:
                    continue
                match = src_matches.get(symbol)
                extractor = "regex"
                evidence_path = src_path
                if match is None and dst_path:
                    dst_file = resolve_path(dst_path)
                    if dst_file.exists():
                        try:
                            dst_text = dst_file.read_text(encoding="utf-8", errors="replace")
                            match = _match_line(dst_text, symbol)
                            if match:
                                evidence_path = dst_path
                        except OSError:
                            match = None
                if match is None:
                    rg_match = rg_cache.get(symbol)
                    if rg_match:
                        rg_path, line_no, line_text = rg_match
                        match = (line_no, line_text)
                        evidence_path = rg_path
                        extractor = "rg"
                if match is None:
                    continue
                line_no, line_text = match
                evidence_ref = _evidence_ref(
                    evidence_path,
                    line_no,
                    line_no,
                    line_text,
                    extractor=extractor,
                )
                link_id = hashlib.sha1(
                    f"{file_id}:{dst_file_id}:calls:{evidence_ref['match_hash']}".encode("utf-8")
                ).hexdigest()
                if link_id in links:
                    continue
                links[link_id] = {
                    "schema": SCHEMA,
                    "schema_version": SCHEMA_VERSION,
                    "link_id": link_id,
                    "src_file_id": file_id,
                    "dst_file_id": dst_file_id,
                    "type": "calls",
                    "evidence_ref": evidence_ref,
                    "unverified": False,
                }
                if max_links and len(links) >= max_links:
                    truncated = True
                    return list(links.values()), truncated, stats
    return list(links.values()), truncated, stats


def _write_links(path: Path, links: Iterable[Dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for link in links:
            handle.write(json.dumps(link, ensure_ascii=False) + "\n")


def _write_stats(path: Path, payload: Dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def parse_args(argv: List[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build RLM links from verified nodes.")
    parser.add_argument("--ticket", help="Ticket identifier (defaults to docs/.active_ticket).")
    parser.add_argument("--nodes", help="Override nodes.jsonl path.")
    parser.add_argument("--targets", help="Override rlm-targets.json path.")
    parser.add_argument("--output", help="Override links.jsonl path.")
    return parser.parse_args(argv)


def main(argv: List[str] | None = None) -> int:
    args = parse_args(argv)
    workspace_root, project_root = runtime.require_workflow_root()
    ticket, _ = runtime.require_ticket(project_root, ticket=args.ticket, slug_hint=None)

    nodes_path = (
        runtime.resolve_path_for_target(Path(args.nodes), project_root)
        if args.nodes
        else project_root / "reports" / "research" / f"{ticket}-rlm.nodes.jsonl"
    )
    if not nodes_path.exists() or nodes_path.stat().st_size == 0:
        raise SystemExit("rlm links require non-empty nodes.jsonl; run W81-27 agent flow first.")

    targets_path = (
        runtime.resolve_path_for_target(Path(args.targets), project_root)
        if args.targets
        else project_root / "reports" / "research" / f"{ticket}-rlm-targets.json"
    )
    targets_payload = _load_targets(targets_path)
    target_files = [str(item) for item in targets_payload.get("files") or [] if str(item).strip()]
    paths_base = targets_payload.get("paths_base")
    base_root = base_root_for_label(project_root, paths_base)

    settings = load_rlm_settings(project_root)
    max_links = int(settings.get("max_links") or 0)
    max_symbols_per_file = int(settings.get("max_symbols_per_file") or 0)
    max_definition_hits_per_symbol = int(settings.get("max_definition_hits_per_symbol") or 0)
    rg_timeout_s = int(settings.get("rg_timeout_s") or 0)
    rg_batch_size = int(settings.get("rg_batch_size") or DEFAULT_RG_BATCH_SIZE)

    nodes = list(_iter_nodes(nodes_path))
    paths_by_id = {
        str(node.get("file_id") or node.get("id") or ""): str(node.get("path") or "")
        for node in nodes
        if node.get("node_kind") == "file"
    }
    symbol_index = _build_symbol_index(nodes)
    def _resolve(raw_path: str) -> Path:
        return resolve_source_path(
            Path(raw_path),
            project_root=project_root,
            workspace_root=workspace_root,
            preferred_root=base_root,
        )

    links, truncated, link_stats = _build_links(
        _resolve,
        base_root,
        nodes,
        symbol_index=symbol_index,
        target_files=target_files,
        max_links=max_links,
        max_symbols_per_file=max_symbols_per_file,
        max_definition_hits_per_symbol=max_definition_hits_per_symbol,
        rg_timeout_s=rg_timeout_s,
        rg_batch_size=rg_batch_size,
    )

    links = sorted(
        links,
        key=lambda item: (
            paths_by_id.get(str(item.get("src_file_id") or ""), ""),
            item.get("type") or "",
            paths_by_id.get(str(item.get("dst_file_id") or ""), ""),
            (item.get("evidence_ref") or {}).get("match_hash") or "",
        ),
    )

    output = (
        runtime.resolve_path_for_target(Path(args.output), project_root)
        if args.output
        else project_root / "reports" / "research" / f"{ticket}-rlm.links.jsonl"
    )
    _write_links(output, links)
    stats_path = project_root / "reports" / "research" / f"{ticket}-rlm.links.stats.json"
    stats_payload = {
        "schema": "aidd.rlm_links_stats.v1",
        "schema_version": "v1",
        "ticket": ticket,
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "links_total": len(links),
        "links_truncated": truncated,
        **link_stats,
    }
    _write_stats(stats_path, stats_payload)
    rel_output = runtime.rel_path(output, project_root)
    suffix = " (truncated)" if truncated else ""
    print(f"[aidd] rlm links saved to {rel_output}{suffix}.")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
