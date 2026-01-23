#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import subprocess
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from tools import runtime
from tools.rlm_config import (
    base_label,
    detect_lang,
    load_rlm_settings,
    normalize_ignore_dirs,
    normalize_path,
    paths_base_for,
    resolve_source_path,
    workspace_root_for,
)


SCHEMA = "aidd.rlm_targets.v1"


def _load_research_targets(target: Path, ticket: str) -> Dict:
    path = target / "reports" / "research" / f"{ticket}-targets.json"
    if not path.exists():
        raise FileNotFoundError(f"missing research targets: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _resolve_roots(target: Path, paths: Sequence[str], *, base_root: Path) -> List[Path]:
    roots: List[Path] = []
    workspace_root = workspace_root_for(target)
    for raw in paths:
        if not raw:
            continue
        path = resolve_source_path(
            Path(raw),
            project_root=target,
            workspace_root=workspace_root,
            preferred_root=base_root,
        )
        if path.exists():
            roots.append(path)
    return roots


def _parse_files_touched(plan_path: Path) -> List[str]:
    if not plan_path.exists():
        return []
    text = plan_path.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()
    start = None
    for idx, line in enumerate(lines):
        if line.strip().lower().startswith("## aidd:files_touched"):
            start = idx + 1
            break
    if start is None:
        return []
    items: List[str] = []
    for line in lines[start:]:
        if line.strip().startswith("## "):
            break
        stripped = line.strip()
        if not stripped.startswith("-"):
            continue
        stripped = stripped.lstrip("-").strip()
        if "—" in stripped:
            stripped = stripped.split("—", 1)[0].strip()
        if " - " in stripped:
            stripped = stripped.split(" - ", 1)[0].strip()
        stripped = stripped.strip("` ")
        if stripped:
            items.append(stripped)
    return items


def _walk_files(
    roots: Sequence[Path],
    *,
    base_root: Path,
    ignore_dirs: set[str],
    max_files: int,
    max_file_bytes: int,
) -> List[str]:
    files: List[str] = []
    base_root = base_root.resolve()
    for root in roots:
        if max_files and len(files) >= max_files:
            break
        if root.is_file():
            path = root.resolve()
            try:
                rel_path = path.relative_to(base_root)
            except ValueError:
                rel_path = path
            rel = normalize_path(rel_path)
            if rel not in files:
                files.append(rel)
            continue
        for base, dirs, filenames in os.walk(root):
            dirs[:] = [name for name in dirs if name.lower() not in ignore_dirs]
            if max_files and len(files) >= max_files:
                break
            for name in filenames:
                if max_files and len(files) >= max_files:
                    break
                path = (Path(base) / name).resolve()
                if path.is_symlink():
                    continue
                try:
                    rel_path = path.relative_to(base_root)
                except ValueError:
                    rel_path = path
                rel = normalize_path(rel_path)
                lang = detect_lang(path)
                if not lang:
                    continue
                try:
                    size = path.stat().st_size
                except OSError:
                    continue
                if max_file_bytes and size > max_file_bytes:
                    continue
                files.append(rel)
    return files


def _rg_files_with_matches(
    root: Path,
    keywords: Sequence[str],
    roots: Sequence[Path],
    ignore_dirs: set[str],
    *,
    base_root: Path,
) -> set[str]:
    if not keywords or not roots:
        return set()
    escaped = [re.escape(item) for item in keywords if item]
    if not escaped:
        return set()
    pattern = "|".join(escaped)
    cmd = ["rg", "--files-with-matches", "--no-messages", "-i"]
    for ignored in sorted(ignore_dirs):
        cmd.extend(["-g", f"!{ignored}/**"])
    cmd.extend(["--", pattern])
    cmd.extend([str(path) for path in roots])
    try:
        proc = subprocess.run(
            cmd,
            cwd=root,
            text=True,
            capture_output=True,
            check=False,
        )
    except FileNotFoundError:
        return set()
    if proc.returncode not in (0, 1):
        return set()
    root_resolved = root.resolve()
    base_root = base_root.resolve()
    hits: set[str] = set()
    for line in proc.stdout.splitlines():
        raw = line.strip()
        if not raw:
            continue
        path = Path(raw)
        if not path.is_absolute():
            path = (root_resolved / path).resolve()
        try:
            rel_path = path.relative_to(base_root)
        except ValueError:
            rel_path = path
        hits.add(normalize_path(rel_path))
    return hits


def build_targets(
    target: Path,
    ticket: str,
    *,
    settings: Dict,
    base_root: Optional[Path] = None,
) -> Dict[str, object]:
    research_targets = _load_research_targets(target, ticket)
    paths = [str(item) for item in research_targets.get("paths") or [] if str(item).strip()]
    paths_discovered = [
        str(item) for item in research_targets.get("paths_discovered") or [] if str(item).strip()
    ]
    keywords = [str(item) for item in research_targets.get("keywords") or [] if str(item).strip()]

    plan_path = target / "docs" / "plan" / f"{ticket}.md"
    files_touched = _parse_files_touched(plan_path)

    ignore_dirs = normalize_ignore_dirs(settings.get("ignore_dirs"))
    max_files = int(settings.get("max_files") or 0)
    max_file_bytes = int(settings.get("max_file_bytes") or 0)

    base_root = base_root or paths_base_for(target)
    roots = _resolve_roots(target, paths + paths_discovered, base_root=base_root)
    touched_roots = _resolve_roots(target, files_touched, base_root=base_root)
    roots = list(dict.fromkeys(roots + touched_roots))

    files = _walk_files(
        roots,
        base_root=base_root,
        ignore_dirs=ignore_dirs,
        max_files=max_files,
        max_file_bytes=max_file_bytes,
    )
    hit_files = _rg_files_with_matches(
        base_root,
        keywords,
        roots,
        ignore_dirs,
        base_root=base_root,
    )
    files = sorted(files, key=lambda value: (0 if value in hit_files else 1, value))
    if max_files and len(files) > max_files:
        files = files[:max_files]

    return {
        "schema": SCHEMA,
        "ticket": ticket,
        "slug": research_targets.get("slug") or ticket,
        "slug_hint": research_targets.get("slug_hint"),
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "config_source": research_targets.get("config_source"),
        "paths_base": base_label(target, base_root),
        "paths": paths,
        "paths_discovered": paths_discovered,
        "files_touched": files_touched,
        "keywords": keywords,
        "keyword_hits": sorted(hit_files),
        "files": files,
        "stats": {
            "files_total": len(files),
            "keyword_hits": len(hit_files),
        },
    }


def parse_args(argv: List[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate deterministic RLM targets.")
    parser.add_argument("--ticket", help="Ticket identifier (defaults to docs/.active_ticket).")
    parser.add_argument("--output", help="Optional output path for rlm-targets.json.")
    return parser.parse_args(argv)


def main(argv: List[str] | None = None) -> int:
    args = parse_args(argv)
    _, target = runtime.require_workflow_root()
    ticket, context = runtime.require_ticket(target, ticket=args.ticket, slug_hint=None)

    settings = load_rlm_settings(target)
    payload = build_targets(target, ticket, settings=settings)

    output = (
        runtime.resolve_path_for_target(Path(args.output), target)
        if args.output
        else target / "reports" / "research" / f"{ticket}-rlm-targets.json"
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    rel_output = runtime.rel_path(output, target)
    print(f"[aidd] rlm targets saved to {rel_output}.")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
