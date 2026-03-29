#!/usr/bin/env python3
"""Report runtime module size trends."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List

ROOT = Path(__file__).resolve().parents[2]
RUNTIME_GLOBS = ("skills/*/runtime/*.py", "skills/*/runtime/**/*.py")
THIN_ADAPTER_MAX_LINES = 40


def _line_count(path: Path) -> int:
    try:
        text = path.read_text(encoding="utf-8")
    except Exception:
        return 0
    if not text:
        return 0
    return text.count("\n") + (0 if text.endswith("\n") else 1)


def _is_thin_adapter(path: Path, lines: int) -> bool:
    if path.name == "__init__.py" or lines > THIN_ADAPTER_MAX_LINES:
        return False
    rel = path.relative_to(ROOT).as_posix()
    parts = rel.split("/")
    if len(parts) != 4 or parts[0] != "skills" or parts[2] != "runtime":
        return False
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return False
    return "_CORE_PATH" in text and "exec(compile(" in text


def _collect_sizes() -> Dict[str, int]:
    runtime_paths = sorted({path.resolve() for pattern in RUNTIME_GLOBS for path in ROOT.glob(pattern) if path.is_file()})
    sizes: Dict[str, int] = {}
    for path in runtime_paths:
        lines = _line_count(path)
        if path.name == "__init__.py":
            continue
        if _is_thin_adapter(path, lines):
            continue
        sizes[path.relative_to(ROOT).as_posix()] = lines
    return sizes


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Report runtime module line-count trends.")
    parser.add_argument("--top", type=int, default=15, help="How many largest modules to print.")
    parser.add_argument("--out", help="Optional JSON output path.")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    sizes = _collect_sizes()
    top = max(int(args.top or 0), 1)
    largest: List[tuple[str, int]] = sorted(sizes.items(), key=lambda item: item[1], reverse=True)[:top]

    payload = {
        "schema": "aidd.runtime_module_sizes.v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_modules": len(sizes),
        "top": [{"path": path, "lines": lines} for path, lines in largest],
    }

    if args.out:
        out_path = Path(args.out).resolve()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(
        f"[runtime-module-size-trends] modules={payload['total_modules']} "
        f"top={len(payload['top'])}"
    )
    for item in payload["top"]:
        print(f"[runtime-module-size-trends] {item['path']} -> {item['lines']} lines")

    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
