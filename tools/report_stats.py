#!/usr/bin/env python3
"""Collect simple size stats for reports and optionally update reports-format.md."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Iterable, List, Tuple

MARKER_START = "<!-- report-stats:start -->"
MARKER_END = "<!-- report-stats:end -->"


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _resolve_aidd_root(root: Path) -> Path:
    if (root / "aidd").is_dir():
        return root / "aidd"
    if root.name == "aidd":
        return root
    return root


def _iter_reports(reports_dir: Path) -> Iterable[Path]:
    if not reports_dir.exists():
        return []
    return sorted(p for p in reports_dir.rglob("*.json") if p.is_file())


def _stats_for(path: Path) -> Tuple[int, int, int]:
    text = path.read_text(encoding="utf-8", errors="replace")
    chars = len(text)
    lines = text.count("\n") + (1 if text else 0)
    keys = 0
    try:
        payload = json.loads(text) if text else None
        if isinstance(payload, dict):
            keys = len(payload)
        elif isinstance(payload, list):
            keys = len(payload)
    except json.JSONDecodeError:
        keys = 0
    return chars, lines, keys


def _render_table(rows: List[Tuple[str, int, int, int]]) -> str:
    if not rows:
        return "No reports found. Run `python3 tools/report_stats.py --write` after reports exist."
    header = "| report | chars | lines | keys |"
    sep = "| --- | --- | --- | --- |"
    body = "\n".join(
        f"| {path} | {chars} | {lines} | {keys} |" for path, chars, lines, keys in rows
    )
    return "\n".join([header, sep, body])


def _update_doc(doc_path: Path, block: str) -> bool:
    text = doc_path.read_text(encoding="utf-8")
    if MARKER_START not in text or MARKER_END not in text:
        raise ValueError(f"Missing markers in {doc_path}")
    before, rest = text.split(MARKER_START, 1)
    _, after = rest.split(MARKER_END, 1)
    new_text = f"{before}{MARKER_START}\n{block}\n{MARKER_END}{after}"
    if new_text != text:
        doc_path.write_text(new_text, encoding="utf-8")
        return True
    return False


def main() -> int:
    parser = argparse.ArgumentParser(description="Collect report size stats.")
    parser.add_argument("--root", default=str(_repo_root()), help="Repository root.")
    parser.add_argument("--limit", type=int, default=3, help="Top-N reports by size.")
    parser.add_argument(
        "--write",
        action="store_true",
        help="Update doc/dev/reports-format.md between report-stats markers.",
    )
    args = parser.parse_args()

    root = Path(args.root).resolve()
    aidd_root = _resolve_aidd_root(root)
    reports_dir = aidd_root / "reports"

    rows: List[Tuple[str, int, int, int]] = []
    for path in _iter_reports(reports_dir):
        rel = path.relative_to(aidd_root).as_posix()
        chars, lines, keys = _stats_for(path)
        rows.append((rel, chars, lines, keys))

    rows.sort(key=lambda item: item[1], reverse=True)
    rows = rows[: max(args.limit, 0)]

    block = _render_table(rows)
    print(block)

    if args.write:
        doc_path = root / "doc" / "dev" / "reports-format.md"
        updated = _update_doc(doc_path, block)
        if updated:
            print(f"[report-stats] updated {doc_path}")
        else:
            print(f"[report-stats] no changes for {doc_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
