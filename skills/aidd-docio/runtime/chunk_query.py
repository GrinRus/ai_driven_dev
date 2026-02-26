#!/usr/bin/env python3
"""Unified JIT chunk query for markdown/jsonl/log/text sources."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Sequence, Tuple

from aidd_runtime import runtime
from aidd_runtime.io_utils import utc_timestamp, write_json

SCHEMA = "aidd.report.pack.v1"
PACK_VERSION = "v1"
BACKENDS = ("auto", "markdown", "jsonl", "log", "text")
OPS = ("peek", "slice", "search", "split", "get_chunk")


Line = Tuple[int, str]


def _detect_backend(path: Path, forced: str) -> str:
    mode = str(forced or "auto").strip().lower()
    if mode in {"markdown", "jsonl", "log", "text"}:
        return mode
    suffix = path.suffix.lower()
    if suffix in {".md", ".markdown"}:
        return "markdown"
    if suffix == ".jsonl":
        return "jsonl"
    if suffix in {".log", ".out"}:
        return "log"
    return "text"


def _read_lines(path: Path) -> List[Line]:
    raw_lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    return [(idx + 1, line) for idx, line in enumerate(raw_lines)]


def _compile_query(query: str) -> re.Pattern[str]:
    try:
        return re.compile(query, re.IGNORECASE)
    except re.error:
        return re.compile(re.escape(query), re.IGNORECASE)


def _extract_markdown_section(lines: Sequence[Line], selector: str) -> List[Line]:
    raw = str(selector or "").strip()
    section = raw[1:] if raw.startswith("#") else raw
    if not section.startswith("AIDD:"):
        raise ValueError("markdown selector must be AIDD section or @handoff marker")
    heading = f"## {section}"
    start = -1
    for idx, (_line_no, text) in enumerate(lines):
        if text.strip() == heading:
            start = idx
            break
    if start < 0:
        raise ValueError(f"section not found: {section}")
    end = len(lines)
    for idx in range(start + 1, len(lines)):
        if lines[idx][1].startswith("## "):
            end = idx
            break
    return list(lines[start:end])


def _extract_markdown_handoff(lines: Sequence[Line], selector: str) -> List[Line]:
    handoff_id = str(selector or "").strip().split("@handoff:", 1)[-1].strip()
    if not handoff_id:
        raise ValueError("handoff selector is empty")
    start_marker = f"<!-- handoff:{handoff_id} start"
    end_marker = f"<!-- handoff:{handoff_id} end"

    start = -1
    end = -1
    for idx, (_line_no, text) in enumerate(lines):
        stripped = text.strip()
        if start < 0 and stripped.startswith(start_marker):
            start = idx
            continue
        if start >= 0 and stripped.startswith(end_marker):
            end = idx
            break
    if start < 0:
        raise ValueError(f"handoff start marker not found: {handoff_id}")
    if end < 0:
        raise ValueError(f"handoff end marker not found: {handoff_id}")
    return list(lines[start : end + 1])


def _apply_selector(lines: Sequence[Line], backend: str, selector: str) -> List[Line]:
    raw = str(selector or "").strip()
    if not raw:
        return list(lines)
    if backend != "markdown":
        raise ValueError("--selector is supported only for markdown backend")
    if raw.startswith("@handoff:"):
        return _extract_markdown_handoff(lines, raw)
    return _extract_markdown_section(lines, raw)


def _trim_lines(lines: Sequence[Line], max_chars: int) -> Tuple[List[Line], bool]:
    limit = max(1, int(max_chars))
    kept: List[Line] = []
    size = 0
    for line_no, text in lines:
        line_size = len(text) + 1
        if kept and (size + line_size) > limit:
            return kept, True
        if not kept and line_size > limit:
            kept.append((line_no, text[:limit]))
            return kept, True
        kept.append((line_no, text))
        size += line_size
    return kept, False


def _slice_by_range(lines: Sequence[Line], *, line_start: int | None, line_end: int | None) -> List[Line]:
    if not lines:
        return []
    start = int(line_start) if line_start is not None else lines[0][0]
    end = int(line_end) if line_end is not None else lines[-1][0]
    if end < start:
        raise ValueError("--line-end must be >= --line-start")
    return [item for item in lines if start <= item[0] <= end]


def _chunk_lines(lines: Sequence[Line], chunk_size: int) -> List[List[Line]]:
    size = max(1, int(chunk_size))
    chunks: List[List[Line]] = []
    current: List[Line] = []
    for item in lines:
        current.append(item)
        if len(current) >= size:
            chunks.append(current)
            current = []
    if current:
        chunks.append(current)
    return chunks


def _line_entries(lines: Sequence[Line]) -> List[Dict[str, Any]]:
    return [{"line": line_no, "text": text} for line_no, text in lines]


def _chunk_pack_path(
    *,
    target: Path,
    ticket: str,
    source_rel: str,
    backend: str,
    op: str,
    selector: str,
    query: str,
    line_start: int | None,
    line_end: int | None,
    chunk_lines: int,
    chunk_index: int | None,
    max_chars: int,
    max_results: int,
) -> Path:
    key = {
        "source": source_rel,
        "backend": backend,
        "op": op,
        "selector": selector,
        "query": query,
        "line_start": line_start,
        "line_end": line_end,
        "chunk_lines": chunk_lines,
        "chunk_index": chunk_index,
        "max_chars": max_chars,
        "max_results": max_results,
    }
    digest = hashlib.sha1(json.dumps(key, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()[:10]
    return target / "reports" / "context" / f"{ticket}-chunk-{digest}.pack.json"


def _result_content(lines: Sequence[Line], max_chars: int) -> Dict[str, Any]:
    trimmed, truncated = _trim_lines(lines, max_chars)
    content = "\n".join(text for _line_no, text in trimmed)
    return {
        "line_start": trimmed[0][0] if trimmed else 0,
        "line_end": trimmed[-1][0] if trimmed else 0,
        "line_count": len(trimmed),
        "truncated": truncated,
        "content": content,
        "lines": _line_entries(trimmed),
    }


def _build_result(
    *,
    op: str,
    selected_lines: Sequence[Line],
    query: str,
    line_start: int | None,
    line_end: int | None,
    chunk_lines: int,
    chunk_index: int | None,
    max_chars: int,
    max_results: int,
    selector_set: bool,
) -> Dict[str, Any]:
    if op == "peek":
        return _result_content(selected_lines[: max(1, chunk_lines)], max_chars)

    if op == "slice":
        if not selector_set and line_start is None and line_end is None:
            raise ValueError("slice requires --selector or --line-start/--line-end")
        return _result_content(
            _slice_by_range(selected_lines, line_start=line_start, line_end=line_end),
            max_chars,
        )

    if op == "search":
        if not query:
            raise ValueError("search requires --query")
        pattern = _compile_query(query)
        all_matches = [(line_no, text) for line_no, text in selected_lines if pattern.search(text)]
        limited = all_matches[: max(1, max_results)]
        trimmed, char_truncated = _trim_lines(limited, max_chars)
        return {
            "query": query,
            "match_count_total": len(all_matches),
            "match_count": len(trimmed),
            "matches_truncated": len(all_matches) > len(limited),
            "chars_truncated": char_truncated,
            "matches": _line_entries(trimmed),
        }

    if op == "split":
        chunks = _chunk_lines(selected_lines, chunk_lines)
        limited = chunks[: max(1, max_results)]
        rows: List[Dict[str, Any]] = []
        for idx, chunk in enumerate(limited):
            rows.append(
                {
                    "chunk_index": idx,
                    "line_start": chunk[0][0],
                    "line_end": chunk[-1][0],
                    "line_count": len(chunk),
                    "preview": chunk[0][1][:160],
                }
            )
        return {
            "chunk_lines": max(1, chunk_lines),
            "chunk_count_total": len(chunks),
            "chunk_count": len(rows),
            "chunks_truncated": len(chunks) > len(limited),
            "chunks": rows,
        }

    if op == "get_chunk":
        if chunk_index is None:
            raise ValueError("get_chunk requires --chunk-index")
        chunks = _chunk_lines(selected_lines, chunk_lines)
        if chunk_index < 0 or chunk_index >= len(chunks):
            raise ValueError(f"chunk index out of range: {chunk_index} (total={len(chunks)})")
        chunk = chunks[chunk_index]
        payload = _result_content(chunk, max_chars)
        payload["chunk_index"] = int(chunk_index)
        payload["chunk_lines"] = max(1, chunk_lines)
        payload["chunk_count_total"] = len(chunks)
        return payload

    raise ValueError(f"unsupported op: {op}")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Query compact chunks from markdown/jsonl/log/text sources.")
    parser.add_argument("--path", required=True, help="Source path to inspect.")
    parser.add_argument("--op", choices=OPS, default="peek")
    parser.add_argument("--ticket", help="Ticket override (defaults to active ticket or _global).")
    parser.add_argument("--backend", choices=BACKENDS, default="auto")
    parser.add_argument("--query", default="", help="Query regex/token for search.")
    parser.add_argument("--selector", default="", help="Markdown selector: AIDD section or @handoff:<id>.")
    parser.add_argument("--line-start", type=int, help="Inclusive start line for slice.")
    parser.add_argument("--line-end", type=int, help="Inclusive end line for slice.")
    parser.add_argument("--chunk-lines", type=int, default=80, help="Chunk size in lines for split/get_chunk.")
    parser.add_argument("--chunk-index", type=int, help="Chunk index for get_chunk.")
    parser.add_argument("--max-chars", type=int, default=3000, help="Maximum chars in materialized content.")
    parser.add_argument("--max-results", type=int, default=20, help="Maximum matches/chunks for search/split.")
    parser.add_argument("--out", help="Optional explicit output path.")
    parser.add_argument("--format", choices=("text", "json"), default="text")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    try:
        args = parse_args(argv)
        _, target = runtime.require_workflow_root(Path.cwd())

        source_path = runtime.resolve_path_for_target(Path(args.path), target)
        if not source_path.exists():
            raise FileNotFoundError(f"source not found: {runtime.rel_path(source_path, target)}")

        ticket = (args.ticket or runtime.read_active_ticket(target) or "_global").strip() or "_global"
        backend = _detect_backend(source_path, args.backend)
        source_rel = runtime.rel_path(source_path, target)
        source_lines = _read_lines(source_path)
        selected_lines = _apply_selector(source_lines, backend, args.selector)

        result = _build_result(
            op=args.op,
            selected_lines=selected_lines,
            query=str(args.query or "").strip(),
            line_start=args.line_start,
            line_end=args.line_end,
            chunk_lines=max(1, int(args.chunk_lines)),
            chunk_index=args.chunk_index,
            max_chars=max(1, int(args.max_chars)),
            max_results=max(1, int(args.max_results)),
            selector_set=bool(str(args.selector or "").strip()),
        )

        output_path = (
            runtime.resolve_path_for_target(Path(args.out), target)
            if args.out
            else _chunk_pack_path(
                target=target,
                ticket=ticket,
                source_rel=source_rel,
                backend=backend,
                op=args.op,
                selector=str(args.selector or "").strip(),
                query=str(args.query or "").strip(),
                line_start=args.line_start,
                line_end=args.line_end,
                chunk_lines=max(1, int(args.chunk_lines)),
                chunk_index=args.chunk_index,
                max_chars=max(1, int(args.max_chars)),
                max_results=max(1, int(args.max_results)),
            )
        )

        payload: Dict[str, Any] = {
            "schema": SCHEMA,
            "pack_version": PACK_VERSION,
            "type": "context-chunk",
            "kind": "pack",
            "ticket": ticket,
            "generated_at": utc_timestamp(),
            "source_path": source_rel,
            "backend": backend,
            "op": args.op,
            "selector": str(args.selector or "").strip(),
            "query": str(args.query or "").strip(),
            "stats": {
                "source_lines": len(source_lines),
                "selected_lines": len(selected_lines),
                "line_start": selected_lines[0][0] if selected_lines else 0,
                "line_end": selected_lines[-1][0] if selected_lines else 0,
            },
            "result": result,
        }

        write_json(output_path, payload, sort_keys=True)
        chunk_rel = runtime.rel_path(output_path, target)

        result_payload = {
            "schema": "aidd.chunk_query.result.v1",
            "status": "ok",
            "ticket": ticket,
            "op": args.op,
            "backend": backend,
            "source_path": source_rel,
            "chunk_pack": chunk_rel,
        }
        if args.format == "json":
            print(json.dumps(result_payload, ensure_ascii=False, indent=2))
        else:
            print(f"chunk_pack={chunk_rel}")
            print(f"summary=op={args.op} backend={backend} selected_lines={len(selected_lines)}")
        return 0
    except Exception as exc:
        print(f"[chunk-query] ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
