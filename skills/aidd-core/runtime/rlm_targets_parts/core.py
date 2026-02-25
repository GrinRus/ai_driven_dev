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

from aidd_runtime import runtime
from aidd_runtime import research_hints
from aidd_runtime.rlm_config import (
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


def _load_hints(target: Path, ticket: str) -> tuple[research_hints.ResearchHints, Optional[str]]:
    prd_path = target / "docs" / "prd" / f"{ticket}.prd.md"
    hints = research_hints.load_research_hints(target, ticket)
    if prd_path.exists():
        source = f"{runtime.rel_path(prd_path, target)}#AIDD:RESEARCH_HINTS"
    else:
        source = None
    return hints, source


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


def _discover_common_paths(
    base_root: Path,
    *,
    ignore_dirs: set[str],
    max_depth: int = 4,
) -> List[str]:
    base_root = base_root.resolve()
    candidates = [
        Path("src/main"),
        Path("src/test"),
        Path("frontend/src"),
        Path("frontend/src/test"),
        Path("backend/src/main"),
        Path("backend/src/test"),
    ]
    discovered: List[str] = []
    for candidate in candidates:
        path = (base_root / candidate).resolve()
        if path.exists():
            discovered.append(normalize_path(path.relative_to(base_root)))

    for base, dirs, _ in os.walk(base_root):
        rel = Path(base).relative_to(base_root)
        if max_depth and len(rel.parts) > max_depth:
            dirs[:] = []
            continue
        dirs[:] = [name for name in dirs if name.lower() not in ignore_dirs]
        if not rel.parts:
            continue
        rel_str = rel.as_posix()
        if rel_str.endswith("src/main") or rel_str.endswith("src/test"):
            discovered.append(normalize_path(rel))
    return sorted(dict.fromkeys(discovered))


def _normalize_prefixes(values: Iterable[str]) -> List[str]:
    prefixes: List[str] = []
    for raw in values:
        text = str(raw or "").strip().replace("\\", "/")
        if not text:
            continue
        cleaned = text.lstrip("./").rstrip("/")
        if cleaned:
            prefixes.append(cleaned)
    return prefixes


def _filter_prefixes(paths: Iterable[str], prefixes: Iterable[str]) -> List[str]:
    if not prefixes:
        return [str(item) for item in paths if str(item).strip()]
    normalized_prefixes = _normalize_prefixes(prefixes)
    filtered: List[str] = []
    for raw in paths:
        text = str(raw or "").strip()
        if not text:
            continue
        normalized = normalize_path(Path(text))
        if any(
            normalized == prefix or normalized.startswith(f"{prefix}/")
            for prefix in normalized_prefixes
        ):
            continue
        filtered.append(text)
    return filtered


def _include_prefixes(paths: Iterable[str], prefixes: Iterable[str]) -> List[str]:
    normalized_prefixes = _normalize_prefixes(prefixes)
    if not normalized_prefixes:
        return [str(item) for item in paths if str(item).strip()]
    filtered: List[str] = []
    for raw in paths:
        text = str(raw or "").strip()
        if not text:
            continue
        normalized = normalize_path(Path(text))
        if any(
            normalized == prefix or normalized.startswith(f"{prefix}/")
            for prefix in normalized_prefixes
        ):
            filtered.append(text)
    return filtered


def normalize_prefixes(values: Iterable[str]) -> List[str]:
    return _normalize_prefixes(values)


def filter_prefixes(paths: Iterable[str], prefixes: Iterable[str]) -> List[str]:
    return _filter_prefixes(paths, prefixes)


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
        else:
            path = path.resolve()
        try:
            rel_path = path.relative_to(base_root)
        except ValueError:
            rel_path = path
        hits.add(normalize_path(rel_path))
    return hits


def _parse_override_paths(raw: Optional[str]) -> List[str]:
    if not raw:
        return []
    items: List[str] = []
    for chunk in re.split(r"[,:]", raw):
        cleaned = chunk.strip()
        if cleaned:
            items.append(cleaned)
    return items


def rg_files_with_matches(
    root: Path,
    keywords: Sequence[str],
    roots: Sequence[Path],
    ignore_dirs: set[str],
    *,
    base_root: Path,
) -> set[str]:
    return _rg_files_with_matches(
        root,
        keywords,
        roots,
        ignore_dirs,
        base_root=base_root,
    )


def build_targets(
    target: Path,
    ticket: str,
    *,
    settings: Dict,
    targets_mode: Optional[str] = None,
    paths_override: Optional[Sequence[str]] = None,
    keywords_override: Optional[Sequence[str]] = None,
    notes_override: Optional[Sequence[str]] = None,
    base_root: Optional[Path] = None,
) -> Dict[str, object]:
    hints, config_source = _load_hints(target, ticket)
    if paths_override:
        paths = _normalize_prefixes(paths_override)
    else:
        paths = _normalize_prefixes(hints.paths)
    paths_discovered: List[str] = []
    keywords = [str(item).strip().lower() for item in hints.keywords if str(item).strip()]
    notes = [str(item).strip() for item in hints.notes if str(item).strip()]
    if keywords_override:
        for item in keywords_override:
            token = str(item).strip().lower()
            if token:
                keywords.append(token)
    if notes_override:
        for item in notes_override:
            note = str(item).strip()
            if note:
                notes.append(note)
    keywords = list(dict.fromkeys(keywords))
    notes = list(dict.fromkeys(notes))
    if not (paths or keywords):
        raise ValueError(
            "AIDD:RESEARCH_HINTS must define Paths or Keywords "
            f"in docs/prd/{ticket}.prd.md (or pass --paths)."
        )

    mode_override = str(targets_mode).strip().lower() if targets_mode else ""
    if mode_override and mode_override not in {"auto", "explicit"}:
        mode_override = ""
    targets_mode = mode_override or str(settings.get("targets_mode") or "auto").strip().lower()
    if targets_mode not in {"auto", "explicit"}:
        targets_mode = "auto"
    if paths:
        targets_mode = "explicit"

    plan_path = target / "docs" / "plan" / f"{ticket}.md"
    files_touched = _parse_files_touched(plan_path)

    ignore_dirs = normalize_ignore_dirs(settings.get("ignore_dirs"))
    max_files = int(settings.get("max_files") or 0)
    max_file_bytes = int(settings.get("max_file_bytes") or 0)

    base_root = base_root or paths_base_for(target)
    auto_paths: List[str] = []
    if not (targets_mode == "explicit" and paths):
        auto_paths = _discover_common_paths(base_root, ignore_dirs=ignore_dirs)
    if auto_paths:
        paths_discovered = list(dict.fromkeys(paths_discovered + auto_paths))
    if targets_mode == "explicit" and paths:
        paths_discovered = []
    if paths_override:
        files_touched = _include_prefixes(files_touched, paths)
    if settings.get("exclude_path_prefixes"):
        paths = _filter_prefixes(paths, settings.get("exclude_path_prefixes") or [])
        paths_discovered = _filter_prefixes(paths_discovered, settings.get("exclude_path_prefixes") or [])
        files_touched = _filter_prefixes(files_touched, settings.get("exclude_path_prefixes") or [])
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

    feature_context = runtime.resolve_feature_context(target, ticket=ticket, slug_hint=None)
    slug_hint = (feature_context.slug_hint or "").strip() or None

    return {
        "schema": SCHEMA,
        "ticket": ticket,
        "slug": slug_hint or ticket,
        "slug_hint": slug_hint,
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "config_source": config_source,
        "targets_mode": targets_mode,
        "paths_base": base_label(target, base_root),
        "paths": paths,
        "paths_discovered": paths_discovered,
        "files_touched": files_touched,
        "keywords": keywords,
        "notes": notes,
        "keyword_hits": sorted(hit_files),
        "files": files,
        "stats": {
            "files_total": len(files),
            "keyword_hits": len(hit_files),
        },
    }


def parse_args(argv: List[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate deterministic RLM targets.")
    parser.add_argument("--ticket", help="Ticket identifier (defaults to docs/.active.json).")
    parser.add_argument("--output", help="Optional output path for rlm-targets.json.")
    parser.add_argument(
        "--paths",
        help="Comma- or colon-separated list of explicit paths to use for RLM targets.",
    )
    parser.add_argument(
        "--targets-mode",
        choices=("auto", "explicit"),
        help="Override targets_mode (auto|explicit).",
    )
    return parser.parse_args(argv)


def main(argv: List[str] | None = None) -> int:
    args = parse_args(argv)
    _, target = runtime.require_workflow_root()
    ticket, context = runtime.require_ticket(target, ticket=args.ticket, slug_hint=None)

    settings = load_rlm_settings(target)
    paths_override = _parse_override_paths(args.paths)
    payload = build_targets(
        target,
        ticket,
        settings=settings,
        targets_mode=args.targets_mode,
        paths_override=paths_override,
    )

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
