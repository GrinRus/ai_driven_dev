#!/usr/bin/env python3
"""Build semantic memory pack from docs/reports artifacts."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import sys
from pathlib import Path
from typing import Dict, Iterable, List


def _ensure_plugin_root_on_path() -> None:
    env_root = os.environ.get("CLAUDE_PLUGIN_ROOT", "").strip()
    if env_root:
        root = Path(env_root).resolve()
        if (root / "aidd_runtime").is_dir():
            if str(root) not in sys.path:
                sys.path.insert(0, str(root))
            return

    probe = Path(__file__).resolve()
    for parent in (probe.parent, *probe.parents):
        if (parent / "aidd_runtime").is_dir():
            os.environ.setdefault("CLAUDE_PLUGIN_ROOT", str(parent))
            if str(parent) not in sys.path:
                sys.path.insert(0, str(parent))
            return


_ensure_plugin_root_on_path()

from aidd_runtime import runtime
from aidd_runtime import memory_verify

_TOKEN_RE = re.compile(r"\b[A-Z][A-Z0-9_]{2,}\b")


def _load_memory_settings(root: Path) -> dict:
    conventions_path = root / "config" / "conventions.json"
    if not conventions_path.exists():
        return {}
    try:
        payload = json.loads(conventions_path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    memory = payload.get("memory")
    return memory if isinstance(memory, dict) else {}


def _read_existing(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""


def _candidate_sources(root: Path, ticket: str) -> List[Path]:
    return [
        root / "docs" / "prd" / f"{ticket}.prd.md",
        root / "docs" / "plan" / f"{ticket}.md",
        root / "docs" / "research" / f"{ticket}.md",
        root / "docs" / "tasklist" / f"{ticket}.md",
        root / "docs" / "spec" / f"{ticket}.spec.yaml",
        root / "reports" / "context" / f"{ticket}.pack.md",
    ]


def _collect_terms(lines: Iterable[str]) -> List[str]:
    terms: List[str] = []
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        tokens = _TOKEN_RE.findall(stripped)
        for token in tokens:
            terms.append(token)
    return terms


def _collect_by_keywords(lines: Iterable[str], keywords: Iterable[str]) -> List[str]:
    out: List[str] = []
    lowered = [item.lower() for item in keywords]
    for line in lines:
        stripped = line.strip("- ").strip()
        if not stripped:
            continue
        probe = stripped.lower()
        if any(keyword in probe for keyword in lowered):
            out.append(stripped)
    return out


def _collect_open_questions(lines: List[str]) -> List[str]:
    out: List[str] = []
    in_open_block = False
    for raw in lines:
        line = raw.rstrip()
        head = line.strip().lower()
        if head.startswith("## "):
            in_open_block = "open_questions" in head or "open questions" in head
            continue
        if in_open_block and line.strip().startswith("- "):
            out.append(line.strip("- ").strip())
            continue
        if "open question" in head or "открыт" in head or "вопрос" in head:
            cleaned = line.strip("- ").strip()
            if cleaned:
                out.append(cleaned)
    return out


def _normalize(values: Iterable[str], *, max_items: int) -> List[str]:
    unique: Dict[str, str] = {}
    for item in values:
        text = str(item or "").strip()
        if not text:
            continue
        key = text.lower()
        if key not in unique:
            unique[key] = text
    ordered = sorted(unique.values(), key=lambda value: (value.lower(), value))
    return ordered[: max(max_items, 1)]


def _trim_to_char_budget(sections: Dict[str, List[str]], max_chars: int) -> Dict[str, List[str]]:
    budget = max(max_chars, 100)
    cloned = {key: list(values) for key, values in sections.items()}

    def total_chars() -> int:
        return sum(len(item) for values in cloned.values() for item in values)

    while total_chars() > budget:
        candidates = [key for key, values in cloned.items() if values]
        if not candidates:
            break
        longest_key = max(candidates, key=lambda key: (len(cloned[key][-1]), len(cloned[key])))
        cloned[longest_key].pop()
    return cloned


def build_semantic_payload(root: Path, ticket: str, *, max_chars: int, max_items: int) -> dict:
    existing_sources = [path for path in _candidate_sources(root, ticket) if path.exists()]
    text_map = {path: _read_existing(path) for path in existing_sources}
    all_lines: List[str] = []
    for payload in text_map.values():
        all_lines.extend(payload.splitlines())

    sections = {
        "terms": _normalize(_collect_terms(all_lines), max_items=max_items),
        "defaults": _normalize(
            _collect_by_keywords(all_lines, ["default", "defaults", "по умолч", "default:"]),
            max_items=max_items,
        ),
        "constraints": _normalize(
            _collect_by_keywords(all_lines, ["must", "must not", "cannot", "forbid", "огранич", "запрещ", "обяз"]),
            max_items=max_items,
        ),
        "invariants": _normalize(
            _collect_by_keywords(all_lines, ["invariant", "always", "неизмен", "always:"]),
            max_items=max_items,
        ),
        "open_questions": _normalize(_collect_open_questions(all_lines), max_items=max_items),
    }
    sections = _trim_to_char_budget(sections, max_chars=max_chars)

    total_chars = sum(len(item) for values in sections.values() for item in values)
    total_items = sum(len(values) for values in sections.values())

    payload = {
        "schema": memory_verify.SEMANTIC_SCHEMA,
        "schema_version": memory_verify.SEMANTIC_SCHEMA,
        "ticket": ticket,
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "status": "ok",
        "source_paths": [runtime.rel_path(path, root) for path in existing_sources],
        "sections": sections,
        "budget": {
            "max_chars": max_chars,
            "max_items_per_section": max_items,
            "total_chars": total_chars,
            "total_items": total_items,
        },
    }
    return payload


def parse_args(argv: List[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate semantic memory pack.")
    parser.add_argument("--ticket", help="Ticket identifier (defaults to docs/.active.json).")
    parser.add_argument("--slug-hint", help="Optional slug hint override.")
    parser.add_argument("--output", help="Optional output path override.")
    parser.add_argument("--max-chars", type=int, help="Override semantic char budget.")
    parser.add_argument("--max-items", type=int, help="Override max items per section.")
    return parser.parse_args(argv)


def main(argv: List[str] | None = None) -> int:
    args = parse_args(argv)
    _, root = runtime.require_workflow_root()
    ticket, _ = runtime.require_ticket(root, ticket=getattr(args, "ticket", None), slug_hint=getattr(args, "slug_hint", None))

    settings = _load_memory_settings(root)
    semantic_cfg = settings.get("semantic") if isinstance(settings, dict) else {}
    max_chars = int(args.max_chars or (semantic_cfg.get("max_chars") if isinstance(semantic_cfg, dict) else 12000) or 12000)
    max_items = int(args.max_items or (semantic_cfg.get("max_items_per_section") if isinstance(semantic_cfg, dict) else 40) or 40)

    payload = build_semantic_payload(root, ticket, max_chars=max_chars, max_items=max_items)
    errors = memory_verify.validate_semantic_data(payload)
    if errors:
        for err in errors:
            print(f"[memory-extract] ERROR: {err}", file=sys.stderr)
        return 2

    if args.output:
        output_path = runtime.resolve_path_for_target(Path(args.output), root)
    else:
        output_path = root / "reports" / "memory" / f"{ticket}.semantic.pack.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"[memory-extract] OK: {runtime.rel_path(output_path, root)}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
