#!/usr/bin/env python3
"""Generate pack sidecars for existing research context reports."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import Iterable, List
import sys

ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from claude_workflow_cli.tools import reports_pack


def _repo_root() -> Path:
    return ROOT


def _resolve_aidd_root(root: Path) -> Path:
    if (root / "aidd").is_dir():
        return root / "aidd"
    if root.name == "aidd":
        return root
    return root


def _iter_contexts(reports_dir: Path) -> Iterable[Path]:
    if not reports_dir.exists():
        return []
    return sorted(p for p in reports_dir.glob("*-context.json") if p.is_file())


def _pack_path_for(json_path: Path) -> Path:
    fmt = os.getenv("AIDD_PACK_FORMAT", "yaml").strip().lower()
    ext = ".pack.toon" if fmt == "toon" else ".pack.yaml"
    if json_path.suffix == ".json":
        return json_path.with_suffix(ext)
    return json_path.with_name(json_path.name + ext)


def main() -> int:
    parser = argparse.ArgumentParser(description="Backfill pack sidecars for research context reports.")
    parser.add_argument("--root", default=str(_repo_root()), help="Repository root or aidd root.")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing pack sidecar files.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print planned updates without writing files.",
    )
    args = parser.parse_args()

    root = Path(args.root).resolve()
    aidd_root = _resolve_aidd_root(root)
    reports_dir = aidd_root / "reports" / "research"

    contexts = list(_iter_contexts(reports_dir))
    if not contexts:
        print("[pack-backfill] no research context reports found.")
        return 0

    updated: List[Path] = []
    for path in contexts:
        pack_path = _pack_path_for(path)
        if pack_path.exists() and not args.force:
            continue
        if args.dry_run:
            print(f"[pack-backfill] would write {pack_path.relative_to(aidd_root).as_posix()}")
            continue
        reports_pack.write_research_context_pack(path, output=pack_path, root=aidd_root)
        updated.append(pack_path)

    if updated:
        print(f"[pack-backfill] updated {len(updated)} pack file(s).")
    else:
        print("[pack-backfill] no pack updates required.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
