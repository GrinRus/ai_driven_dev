#!/usr/bin/env python3
"""Extract markdown slices by AIDD section or handoff block."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from aidd_runtime import runtime
from aidd_runtime.io_utils import utc_timestamp


@dataclass(frozen=True)
class SliceRef:
    source: str
    selector: str
    kind: str


def _slugify(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "_", value.strip())
    cleaned = cleaned.strip("._-")
    return cleaned or "slice"


def parse_ref(raw: str) -> SliceRef:
    value = str(raw or "").strip()
    if not value:
        raise ValueError("--ref is required")
    if "#AIDD:" in value:
        source, selector = value.split("#", 1)
        selector = selector.strip()
        if not source or not selector.startswith("AIDD:"):
            raise ValueError("invalid section ref; expected path.md#AIDD:SECTION")
        return SliceRef(source=source.strip(), selector=selector, kind="section")
    if "@handoff:" in value:
        source, marker = value.split("@handoff:", 1)
        handoff_id = marker.strip()
        if not source or not handoff_id:
            raise ValueError("invalid handoff ref; expected path.md@handoff:<id>")
        return SliceRef(source=source.strip(), selector=handoff_id, kind="handoff")
    raise ValueError("unsupported ref format; use path.md#AIDD:SECTION or path.md@handoff:<id>")


def _extract_section(lines: List[str], section_name: str) -> List[str]:
    start = -1
    heading = f"## {section_name}"
    for idx, line in enumerate(lines):
        if line.strip() == heading:
            start = idx
            break
    if start < 0:
        raise ValueError(f"section not found: {section_name}")

    end = len(lines)
    for idx in range(start + 1, len(lines)):
        if lines[idx].startswith("## "):
            end = idx
            break
    return lines[start:end]


def _extract_handoff(lines: List[str], handoff_id: str) -> List[str]:
    start = -1
    end = -1
    start_marker = f"<!-- handoff:{handoff_id} start"
    end_marker = f"<!-- handoff:{handoff_id} end"

    for idx, line in enumerate(lines):
        stripped = line.strip()
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
    return lines[start : end + 1]


def _slice_output_path(target: Path, ticket: str, source_path: Path, selector: str) -> Path:
    digest = hashlib.sha1(f"{source_path.as_posix()}::{selector}".encode("utf-8")).hexdigest()[:10]
    source_key = _slugify(source_path.as_posix())
    selector_key = _slugify(selector)
    name = f"{source_key}__{selector_key}__{digest}.slice.md"
    return target / "reports" / "context" / "slices" / ticket / name


def _render_slice(source_rel: str, selector: str, body_lines: List[str]) -> str:
    header = [
        "---",
        "schema: aidd.md_slice.v1",
        f"source_path: {source_rel}",
        f"selector: {selector}",
        f"generated_at: {utc_timestamp()}",
        f"line_count: {len(body_lines)}",
        "---",
        "",
    ]
    return "\n".join(header + body_lines).rstrip() + "\n"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Extract markdown slice by AIDD section or handoff block.")
    parser.add_argument("--ref", required=True, help="path.md#AIDD:SECTION or path.md@handoff:<id>")
    parser.add_argument("--ticket", help="Ticket identifier for slice output directory")
    parser.add_argument("--output", help="Optional explicit output path")
    parser.add_argument("--format", choices=("text", "json"), default="text")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    try:
        args = parse_args(argv)
        _, target = runtime.require_workflow_root(Path.cwd())

        ref = parse_ref(args.ref)
        source_path = runtime.resolve_path_for_target(Path(ref.source), target)
        if not source_path.exists():
            raise FileNotFoundError(f"source markdown not found: {runtime.rel_path(source_path, target)}")

        lines = source_path.read_text(encoding="utf-8").splitlines()
        if ref.kind == "section":
            body = _extract_section(lines, ref.selector)
            selector_label = f"#{ref.selector}"
        else:
            body = _extract_handoff(lines, ref.selector)
            selector_label = f"@handoff:{ref.selector}"

        ticket = (args.ticket or runtime.read_active_ticket(target) or "_global").strip() or "_global"
        output_path = runtime.resolve_path_for_target(Path(args.output), target) if args.output else _slice_output_path(
            target, ticket, source_path, selector_label
        )
        output_path.parent.mkdir(parents=True, exist_ok=True)
        source_rel = runtime.rel_path(source_path, target)
        output_path.write_text(_render_slice(source_rel, selector_label, body), encoding="utf-8")

        payload = {
            "schema": "aidd.md_slice.result.v1",
            "status": "ok",
            "ticket": ticket,
            "source": source_rel,
            "selector": selector_label,
            "line_count": len(body),
            "slice_path": runtime.rel_path(output_path, target),
        }

        if args.format == "json":
            print(json.dumps(payload, ensure_ascii=False, indent=2))
        else:
            print(f"slice_path={payload['slice_path']}")
            print(f"summary={ref.kind} {selector_label} lines={len(body)}")
        return 0
    except Exception as exc:
        print(f"[md-slice] ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
