#!/usr/bin/env python3
"""Apply RFC6902 patch operations to a JSON document."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = ROOT
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from tools import json_patch


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Apply RFC6902 patch to a JSON document.")
    parser.add_argument("--input", required=True, help="Path to the JSON document to patch.")
    parser.add_argument("--patch", required=True, help="Path to the RFC6902 patch file.")
    parser.add_argument("--output", help="Optional output path (default: stdout).")
    parser.add_argument(
        "--in-place",
        action="store_true",
        help="Overwrite the input file in-place (ignored when --output is provided).",
    )
    args = parser.parse_args(argv)

    input_path = Path(args.input)
    patch_path = Path(args.patch)
    payload = json.loads(input_path.read_text(encoding="utf-8"))
    patch_ops = json.loads(patch_path.read_text(encoding="utf-8"))
    result = json_patch.apply(payload, patch_ops)
    rendered = json.dumps(result, ensure_ascii=False, indent=2)

    if args.output:
        Path(args.output).write_text(rendered + "\n", encoding="utf-8")
        return 0
    if args.in_place:
        input_path.write_text(rendered + "\n", encoding="utf-8")
        return 0

    sys.stdout.write(rendered + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
