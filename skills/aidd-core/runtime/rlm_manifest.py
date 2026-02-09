#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path
from typing import Dict, Iterable, List

from aidd_runtime import runtime
from aidd_runtime.rlm_config import (
    base_root_for_label,
    detect_lang,
    file_id_for_path,
    load_rlm_settings,
    normalize_path,
    prompt_version,
    resolve_source_path,
    rev_sha_for_bytes,
    workspace_root_for,
)


SCHEMA = "aidd.rlm_manifest.v1"


def _load_targets(path: Path) -> Dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _iter_files(
    target: Path,
    files: Iterable[str],
    max_file_bytes: int,
    *,
    base_root: Path,
) -> List[Dict[str, object]]:
    entries: List[Dict[str, object]] = []
    workspace_root = workspace_root_for(target)
    for raw in files:
        if not raw:
            continue
        raw_path = Path(str(raw))
        path = resolve_source_path(
            raw_path,
            project_root=target,
            workspace_root=workspace_root,
            preferred_root=base_root,
        )
        if not path.exists() or not path.is_file():
            continue
        try:
            data = path.read_bytes()
        except OSError:
            continue
        size = len(data)
        if max_file_bytes and size > max_file_bytes:
            continue
        if raw_path.is_absolute():
            try:
                rel_path = path.relative_to(base_root)
            except ValueError:
                rel_path = path
            rel = normalize_path(rel_path)
        else:
            rel = normalize_path(raw_path)
        lang = detect_lang(path)
        if not lang:
            continue
        entry = {
            "file_id": file_id_for_path(Path(rel)),
            "path": rel,
            "rev_sha": rev_sha_for_bytes(data),
            "lang": lang,
            "size": size,
        }
        entries.append(entry)
    return entries


def build_manifest(
    target: Path,
    ticket: str,
    *,
    settings: Dict,
    targets_path: Path,
    base_root: Path | None = None,
) -> Dict[str, object]:
    payload = _load_targets(targets_path)
    files = payload.get("files") or []
    if not isinstance(files, list):
        files = []
    max_file_bytes = int(settings.get("max_file_bytes") or 0)
    if base_root is None:
        base_root = base_root_for_label(target, payload.get("paths_base"))
    entries = _iter_files(
        target,
        [str(item) for item in files],
        max_file_bytes,
        base_root=base_root,
    )
    prompt_ver = prompt_version(settings)
    for entry in entries:
        entry["prompt_version"] = prompt_ver

    entries = sorted(entries, key=lambda item: (item.get("path") or ""))
    return {
        "schema": SCHEMA,
        "ticket": ticket,
        "slug": payload.get("slug") or ticket,
        "slug_hint": payload.get("slug_hint"),
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "targets_path": runtime.rel_path(targets_path, target),
        "files": entries,
        "stats": {
            "files_total": len(entries),
        },
    }


def parse_args(argv: List[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate RLM manifest for target files.")
    parser.add_argument("--ticket", help="Ticket identifier (defaults to docs/.active.json).")
    parser.add_argument("--targets", help="Override rlm-targets.json path.")
    parser.add_argument("--output", help="Override manifest output path.")
    return parser.parse_args(argv)


def main(argv: List[str] | None = None) -> int:
    args = parse_args(argv)
    _, target = runtime.require_workflow_root()
    ticket, _ = runtime.require_ticket(target, ticket=args.ticket, slug_hint=None)

    settings = load_rlm_settings(target)
    targets_path = (
        runtime.resolve_path_for_target(Path(args.targets), target)
        if args.targets
        else target / "reports" / "research" / f"{ticket}-rlm-targets.json"
    )
    if not targets_path.exists():
        raise SystemExit(f"rlm targets not found: {targets_path}")

    payload = build_manifest(target, ticket, settings=settings, targets_path=targets_path)
    output = (
        runtime.resolve_path_for_target(Path(args.output), target)
        if args.output
        else target / "reports" / "research" / f"{ticket}-rlm-manifest.json"
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    rel_output = runtime.rel_path(output, target)
    print(f"[aidd] rlm manifest saved to {rel_output}.")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
