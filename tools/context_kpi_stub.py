#!/usr/bin/env python3
"""Quick KPI stub for counting hook executions and log sizes.

Usage:
  python3 tools/context_kpi_stub.py --root . --log-dir aidd/.cache/logs
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Iterable, Tuple


DEFAULT_LOG_DIR = Path("aidd") / ".cache" / "logs"


def iter_log_files(log_dir: Path, pattern: str) -> Iterable[Path]:
    if not log_dir.exists():
        return []
    return sorted(log_dir.glob(pattern))


def count_lines(path: Path) -> int:
    try:
        return sum(1 for _ in path.open("r", encoding="utf-8", errors="replace"))
    except OSError:
        return 0


def summarize_logs(files: Iterable[Path]) -> Tuple[int, int, int]:
    total_files = 0
    total_lines = 0
    max_lines = 0
    for file_path in files:
        total_files += 1
        lines = count_lines(file_path)
        total_lines += lines
        if lines > max_lines:
            max_lines = lines
    return total_files, total_lines, max_lines


def main() -> int:
    parser = argparse.ArgumentParser(description="Summarize format-and-test log KPIs.")
    parser.add_argument("--root", default=".", help="Workspace root (default: current dir).")
    parser.add_argument(
        "--log-dir",
        default=str(DEFAULT_LOG_DIR),
        help="Log directory relative to root (default: aidd/.cache/logs).",
    )
    args = parser.parse_args()

    root = Path(args.root).resolve()
    log_dir = root / args.log_dir
    files = list(iter_log_files(log_dir, "format-and-test.*.log"))
    total, total_lines, max_lines = summarize_logs(files)
    avg_lines = int(total_lines / total) if total else 0

    print("KPI snapshot (format-and-test logs)")
    print(f"- log_dir: {log_dir}")
    print(f"- runs: {total}")
    print(f"- total_lines: {total_lines}")
    print(f"- avg_lines: {avg_lines}")
    print(f"- max_lines: {max_lines}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
