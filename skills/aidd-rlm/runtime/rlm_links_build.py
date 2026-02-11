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

from aidd_runtime import rlm_targets, runtime
from aidd_runtime.rlm_config import (
    base_root_for_label,
    file_id_for_path,
    load_rlm_settings,
    normalize_ignore_dirs,
    normalize_path,
    resolve_source_path,
)


SCHEMA = "aidd.rlm_link.v1"
SCHEMA_VERSION = "v1"
DEFAULT_RG_BATCH_SIZE = 24
_PASCAL_RE = re.compile(r"^[A-Z][A-Za-z0-9_]*$")
_DEFAULT_TYPE_REFS_EXCLUDES = ("java.", "jakarta.", "org.springframework.")


def _is_type_symbol(symbol: str) -> bool:
    if not symbol:
        return False
    tail = symbol
    if "::" in tail:
        tail = tail.split("::")[-1]
    if "." in tail:
        tail = tail.split(".")[-1]
    return bool(_PASCAL_RE.match(tail))


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


def _load_manifest(path: Path) -> Dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def _find_worklist_pack(root: Path, ticket: str) -> Optional[Path]:
    candidate = root / "reports" / "research" / f"{ticket}-rlm.worklist.pack.json"
    return candidate if candidate.exists() else None


def _load_worklist_scope(root: Path, ticket: str) -> Optional[Dict[str, object]]:
    worklist_path = _find_worklist_pack(root, ticket)
    if not worklist_path:
        return None
    try:
        payload = json.loads(worklist_path.read_text(encoding="utf-8"))
    except Exception:
        return None
    if not isinstance(payload, dict):
        return None
    scope = payload.get("worklist_scope")
    return scope if isinstance(scope, dict) else None


def _normalize_prefixes(values: Iterable[str]) -> List[str]:
    return rlm_targets.normalize_prefixes(values)


def _normalize_symbol_prefixes(raw: object) -> List[str]:
    prefixes: List[str] = []
    if isinstance(raw, str):
        items: Iterable[str] = re.split(r"[,:]", raw)
    elif isinstance(raw, Iterable):
        items = raw  # type: ignore[assignment]
    else:
        return prefixes
    for item in items:
        text = str(item or "").strip()
        if not text:
            continue
        prefixes.append(text)
    return list(dict.fromkeys(prefixes))


def _filter_type_refs(
    symbols: Iterable[str],
    *,
    include_prefixes: List[str],
    exclude_prefixes: List[str],
) -> List[str]:
    filtered: List[str] = []
    for raw in symbols:
        symbol = str(raw or "").strip()
        if not symbol:
            continue
        lowered = symbol.lower()
        if include_prefixes:
            if not any(lowered.startswith(prefix.lower()) for prefix in include_prefixes):
                continue
        if exclude_prefixes and any(lowered.startswith(prefix.lower()) for prefix in exclude_prefixes):
            continue
        filtered.append(symbol)
    return filtered


def _matches_prefix(path: str, prefixes: List[str]) -> bool:
    for prefix in prefixes:
        if path == prefix or path.startswith(f"{prefix}/"):
            return True
    return False


def _filter_paths_by_prefix(paths: Iterable[str], prefixes: List[str]) -> List[str]:
    if not prefixes:
        return [str(item) for item in paths if str(item).strip()]
    filtered: List[str] = []
    for raw in paths:
        text = str(raw or "").strip()
        if not text:
            continue
        normalized = normalize_path(Path(text))
        if _matches_prefix(normalized, prefixes):
            filtered.append(text)
    return filtered


def _resolve_keyword_roots(base_root: Path, prefixes: List[str]) -> List[Path]:
    if prefixes:
        roots = [base_root / Path(prefix) for prefix in prefixes]
    else:
        roots = [base_root]
    return [path for path in roots if path.exists()]


def _apply_worklist_scope(
    base_root: Path,
    *,
    target_files: List[str],
    keyword_hits: List[str],
    scope: Dict[str, object],
    ignore_dirs: set[str],
) -> Tuple[List[str], List[str], Dict[str, object]]:
    scope_paths = _normalize_prefixes(scope.get("paths") or [])
    scope_keywords = [str(item).strip() for item in scope.get("keywords") or [] if str(item).strip()]
    if not scope_paths and not scope_keywords:
        return target_files, keyword_hits, {
            "target_files_scope": "targets",
            "target_files_scope_total": len(target_files),
        }

    filtered_targets = _filter_paths_by_prefix(target_files, scope_paths) if scope_paths else list(target_files)
    filtered_keyword_hits = _filter_paths_by_prefix(keyword_hits, scope_paths) if scope_paths else list(keyword_hits)

    scope_stats: Dict[str, object] = {
        "target_files_scope": "worklist",
        "target_files_scope_total": len(filtered_targets),
        "worklist_scope_paths": len(scope_paths),
        "worklist_scope_keywords": len(scope_keywords),
    }

    if scope_keywords:
        roots = _resolve_keyword_roots(base_root, scope_paths)
        scope_hits = set()
        if roots:
            scope_hits = rlm_targets.rg_files_with_matches(
                base_root,
                scope_keywords,
                roots,
                ignore_dirs,
                base_root=base_root,
            )
        filtered_set = {normalize_path(Path(path)) for path in filtered_targets}
        filtered_keyword_hits = sorted(path for path in scope_hits if path in filtered_set)
        scope_stats["worklist_keyword_hits"] = len(filtered_keyword_hits)

    return filtered_targets, filtered_keyword_hits, scope_stats


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


def _classify_link_type(line_text: str) -> str:
    text = line_text.strip()
    if not text:
        return "calls"
    lowered = text.lstrip().lower()
    if lowered.startswith("import ") or lowered.startswith("from "):
        return "imports"
    if re.search(r"\bextends\b", lowered):
        return "extends"
    if re.search(r"\bimplements\b", lowered):
        return "implements"
    return "calls"


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
    key_calls_source: str,
    type_refs_mode: str,
    type_refs_priority: str,
    fallback_mode: str,
    rg_verify_mode: str,
    type_refs_include_prefixes: List[str],
    type_refs_exclude_prefixes: List[str],
) -> Tuple[List[Dict[str, object]], bool, Dict[str, object]]:
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
        "fallback_nodes": 0,
        "fallback_symbols": 0,
        "type_refs_total": 0,
        "type_refs_used": 0,
    }
    rg_cache: Dict[str, Optional[Tuple[str, int, str]]] = {}
    sources_used: set[str] = set()

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

    nodes_by_id = {
        str(node.get("file_id") or node.get("id") or ""): node
        for node in nodes
        if node.get("node_kind") == "file"
    }

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
        raw_public_symbols = [
            str(item).strip() for item in node.get("public_symbols") or [] if str(item).strip()
        ]
        raw_type_refs = [str(item).strip() for item in node.get("type_refs") or [] if str(item).strip()]
        raw_type_refs = _filter_type_refs(
            raw_type_refs,
            include_prefixes=type_refs_include_prefixes,
            exclude_prefixes=type_refs_exclude_prefixes,
        )
        stats["type_refs_total"] += len(raw_type_refs)

        symbol_sources: Dict[str, str] = {}
        symbols: List[str] = []
        seen_symbols: set[str] = set()

        def _add_symbol(symbol: str, source: str) -> bool:
            if not symbol or symbol in seen_symbols:
                return False
            seen_symbols.add(symbol)
            symbols.append(symbol)
            symbol_sources[symbol] = source
            return True

        fallback_symbols: List[str] = []
        if key_calls_source == "public_symbols":
            for item in raw_public_symbols:
                _add_symbol(item, "public_symbols")
        elif key_calls_source == "both":
            for item in raw_key_calls:
                _add_symbol(item, "key_calls")
            for item in raw_public_symbols:
                _add_symbol(item, "public_symbols")
        else:
            for item in raw_key_calls:
                _add_symbol(item, "key_calls")
            if not symbols and raw_public_symbols:
                fallback_symbols = list(raw_public_symbols)
                if fallback_mode == "types_only":
                    fallback_symbols = [sym for sym in fallback_symbols if _is_type_symbol(sym)]
                for item in fallback_symbols:
                    _add_symbol(item, "fallback_public_symbols")

        if type_refs_mode == "only":
            symbols = []
            symbol_sources = {}
            seen_symbols = set()
            fallback_symbols = []
            for item in raw_type_refs:
                _add_symbol(item, "type_refs")
        elif type_refs_mode == "additive" and raw_type_refs:
            if type_refs_priority == "prefer" and fallback_symbols:
                symbols = [sym for sym in symbols if symbol_sources.get(sym) != "fallback_public_symbols"]
                symbol_sources = {
                    sym: source
                    for sym, source in symbol_sources.items()
                    if source != "fallback_public_symbols"
                }
                seen_symbols = set(symbols)
                fallback_symbols = []
            for item in raw_type_refs:
                _add_symbol(item, "type_refs")

        stats["symbols_total"] += len(symbols)
        symbols_to_scan = list(symbols)
        if max_symbols_per_file:
            if len(symbols_to_scan) > max_symbols_per_file:
                stats["symbols_truncated"] += len(symbols_to_scan) - max_symbols_per_file
                symbols_to_scan = symbols_to_scan[: max_symbols_per_file]

        fallback_symbols_used = [
            sym
            for sym in symbols_to_scan
            if symbol_sources.get(sym) == "fallback_public_symbols"
        ]
        if fallback_symbols_used:
            stats["fallback_nodes"] += 1
            stats["fallback_symbols"] += len(fallback_symbols_used)

        type_refs_used = [
            sym for sym in symbols_to_scan if symbol_sources.get(sym) == "type_refs"
        ]
        stats["type_refs_used"] += len(type_refs_used)
        for sym in symbols_to_scan:
            source = symbol_sources.get(sym)
            if source:
                if source == "fallback_public_symbols":
                    sources_used.add("public_symbols")
                else:
                    sources_used.add(source)

        stats["symbols_scanned"] += len(symbols_to_scan)
        src_matches: Dict[str, Optional[Tuple[int, str]]] = {}
        pending_rg = [symbol for symbol in symbols_to_scan if symbol not in rg_cache]
        for symbol in symbols_to_scan:
            if symbol in missing:
                continue
            match = _match_line(text, symbol)
            src_matches[symbol] = match
        _prime_rg_cache(pending_rg)
        for symbol in symbols_to_scan:
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
                link_type = _classify_link_type(line_text)
                evidence_ref = _evidence_ref(
                    evidence_path,
                    line_no,
                    line_no,
                    line_text,
                    extractor=extractor,
                )
                link_id = hashlib.sha1(
                    f"{file_id}:{dst_file_id}:{link_type}:{evidence_ref['match_hash']}".encode("utf-8")
                ).hexdigest()
                if link_id in links:
                    continue
                link_unverified = (
                    symbol_sources.get(symbol) == "fallback_public_symbols"
                    and fallback_mode == "types_only"
                )
                links[link_id] = {
                    "schema": SCHEMA,
                    "schema_version": SCHEMA_VERSION,
                    "link_id": link_id,
                    "src_file_id": file_id,
                    "dst_file_id": dst_file_id,
                    "type": link_type,
                    "evidence_ref": evidence_ref,
                    "unverified": link_unverified,
                }
                if max_links and len(links) >= max_links:
                    truncated = True
                    return list(links.values()), truncated, stats
            if candidates:
                continue
            rg_match = rg_cache.get(symbol)
            if not rg_match:
                continue
            rg_path, line_no, line_text = rg_match
            if not rg_path:
                continue
            link_type = _classify_link_type(line_text)
            evidence_ref = _evidence_ref(
                rg_path,
                line_no,
                line_no,
                line_text,
                extractor="rg",
            )
            dst_path = Path(rg_path)
            if dst_path.is_absolute():
                try:
                    rel = dst_path.relative_to(rg_root)
                except ValueError:
                    rel = dst_path
            else:
                rel = dst_path
            dst_file_id = file_id_for_path(Path(normalize_path(rel)))
            if not dst_file_id or dst_file_id == file_id:
                continue
            link_id = hashlib.sha1(
                f"{file_id}:{dst_file_id}:{link_type}:{evidence_ref['match_hash']}".encode("utf-8")
            ).hexdigest()
            if link_id in links:
                continue
            link_unverified = True
            if rg_verify_mode != "never":
                dst_node = nodes_by_id.get(dst_file_id)
                if dst_node and str(dst_node.get("verification") or "").strip().lower() != "failed":
                    link_unverified = False
            links[link_id] = {
                "schema": SCHEMA,
                "schema_version": SCHEMA_VERSION,
                "link_id": link_id,
                "src_file_id": file_id,
                "dst_file_id": dst_file_id,
                "type": link_type,
                "evidence_ref": evidence_ref,
                "unverified": link_unverified,
            }
            if max_links and len(links) >= max_links:
                truncated = True
                return list(links.values()), truncated, stats
    if sources_used:
        stats["symbols_source"] = "+".join(sorted(sources_used))
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
    parser.add_argument("--ticket", help="Ticket identifier (defaults to docs/.active.json).")
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
        raise SystemExit(
            "rlm links require non-empty nodes.jsonl; run agent-flow or "
            "`skills/aidd-rlm/runtime/rlm_nodes_build.py --bootstrap --ticket <ticket>` first."
        )

    targets_path = (
        runtime.resolve_path_for_target(Path(args.targets), project_root)
        if args.targets
        else project_root / "reports" / "research" / f"{ticket}-rlm-targets.json"
    )
    targets_payload = _load_targets(targets_path)
    target_files = [str(item) for item in targets_payload.get("files") or [] if str(item).strip()]
    keyword_hits = [str(item) for item in targets_payload.get("keyword_hits") or [] if str(item).strip()]
    paths_base = targets_payload.get("paths_base")
    base_root = base_root_for_label(project_root, paths_base)

    settings = load_rlm_settings(project_root)
    max_files = int(settings.get("max_files") or 0)
    key_calls_source = str(settings.get("link_key_calls_source") or "key_calls").strip().lower()
    if key_calls_source not in {"key_calls", "public_symbols", "both"}:
        key_calls_source = "key_calls"
    fallback_mode = str(settings.get("link_fallback_mode") or "types_only").strip().lower()
    if fallback_mode not in {"types_only", "all"}:
        fallback_mode = "types_only"
    rg_verify_mode = str(settings.get("link_rg_verify") or "auto").strip().lower()
    if rg_verify_mode not in {"auto", "never"}:
        rg_verify_mode = "auto"
    type_refs_include_prefixes = _normalize_symbol_prefixes(settings.get("type_refs_include_prefixes"))
    raw_excludes = settings.get("type_refs_exclude_prefixes")
    type_refs_exclude_prefixes = (
        _normalize_symbol_prefixes(raw_excludes)
        if raw_excludes is not None
        else list(_DEFAULT_TYPE_REFS_EXCLUDES)
    )
    link_target_threshold = int(settings.get("link_target_threshold") or 0)
    target_files_source = "targets"
    target_files_trimmed = 0
    scope_stats: Dict[str, object] = {}
    ignore_dirs = normalize_ignore_dirs(settings.get("ignore_dirs"))
    worklist_scope = _load_worklist_scope(project_root, ticket)
    if not target_files:
        manifest_path = project_root / "reports" / "research" / f"{ticket}-rlm-manifest.json"
        manifest_payload = _load_manifest(manifest_path)
        manifest_files = [
            str(item.get("path"))
            for item in (manifest_payload.get("files") or [])
            if isinstance(item, dict) and str(item.get("path") or "").strip()
        ]
        if max_files and len(manifest_files) > max_files:
            manifest_files = manifest_files[:max_files]
        if manifest_files:
            target_files = manifest_files
            target_files_source = "manifest"
    if worklist_scope:
        target_files, keyword_hits, scope_stats = _apply_worklist_scope(
            base_root,
            target_files=target_files,
            keyword_hits=keyword_hits,
            scope=worklist_scope,
            ignore_dirs=ignore_dirs,
        )
    else:
        scope_stats = {
            "target_files_scope": "targets",
            "target_files_scope_total": len(target_files),
        }
    if target_files and link_target_threshold and len(target_files) >= link_target_threshold and keyword_hits:
        target_files = keyword_hits
        target_files_source = "keyword_hits"
    if target_files and max_files and len(target_files) > max_files and keyword_hits:
        target_files = keyword_hits
        target_files_source = "keyword_hits"
    target_files_total = len(target_files)
    if max_files and len(target_files) > max_files:
        target_files_trimmed = len(target_files) - max_files
        target_files = target_files[:max_files]
    max_links = int(settings.get("max_links") or 0)
    max_symbols_per_file = int(settings.get("max_symbols_per_file") or 0)
    max_definition_hits_per_symbol = int(settings.get("max_definition_hits_per_symbol") or 0)
    rg_timeout_s = int(settings.get("rg_timeout_s") or 0)
    rg_batch_size = int(settings.get("rg_batch_size") or DEFAULT_RG_BATCH_SIZE)
    type_refs_mode = str(settings.get("link_type_refs_mode") or "additive").strip().lower()
    if type_refs_mode not in {"off", "additive", "only"}:
        type_refs_mode = "additive"
    type_refs_priority = str(settings.get("link_type_refs_priority") or "prefer").strip().lower()
    if type_refs_priority not in {"prefer", "fallback"}:
        type_refs_priority = "prefer"

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
        key_calls_source=key_calls_source,
        type_refs_mode=type_refs_mode,
        type_refs_priority=type_refs_priority,
        fallback_mode=fallback_mode,
        rg_verify_mode=rg_verify_mode,
        type_refs_include_prefixes=type_refs_include_prefixes,
        type_refs_exclude_prefixes=type_refs_exclude_prefixes,
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
        "target_files_source": target_files_source,
        "target_files_total": target_files_total,
        "target_files_trimmed": target_files_trimmed,
        **scope_stats,
        **link_stats,
    }
    if "symbols_source" not in stats_payload:
        symbols_source = key_calls_source
        if type_refs_mode == "only":
            symbols_source = "type_refs"
        elif type_refs_mode == "additive":
            symbols_source = f"{key_calls_source}+type_refs"
        stats_payload["symbols_source"] = symbols_source
    _write_stats(stats_path, stats_payload)
    rel_output = runtime.rel_path(output, project_root)
    suffix = " (truncated)" if truncated else ""
    print(f"[aidd] rlm links saved to {rel_output}{suffix}.")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
