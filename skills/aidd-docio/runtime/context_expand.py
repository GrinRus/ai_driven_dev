#!/usr/bin/env python3
"""Progressive disclosure helper: expand read/write maps with audit trail."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List

from aidd_runtime import runtime
from aidd_runtime import context_map_validate
from aidd_runtime.io_utils import append_jsonl, utc_timestamp, write_json

ALWAYS_ALLOW_REPORTS = ["aidd/reports/**", "aidd/reports/actions/**"]


def _dedupe_str(items: Iterable[str]) -> List[str]:
    out: List[str] = []
    seen: set[str] = set()
    for item in items:
        value = str(item or "").strip()
        if not value or value in seen:
            continue
        seen.add(value)
        out.append(value)
    return out


def _parse_ref(value: str) -> tuple[str, str]:
    raw = str(value or "").strip()
    if not raw:
        return "", ""
    if "#AIDD:" in raw:
        path, selector = raw.split("#", 1)
        return path.strip(), f"#{selector.strip()}"
    if "@handoff:" in raw:
        path, marker = raw.split("@handoff:", 1)
        return path.strip(), f"@handoff:{marker.strip()}"
    return raw, ""


def _load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))

def _render_readmap_md(readmap: Dict[str, Any]) -> str:
    lines = [
        "# Read Map",
        "",
        f"- schema: {readmap.get('schema')}",
        f"- ticket: {readmap.get('ticket')}",
        f"- stage: {readmap.get('stage')}",
        f"- scope_key: {readmap.get('scope_key')}",
        f"- work_item_key: {readmap.get('work_item_key')}",
        f"- generated_at: {readmap.get('generated_at')}",
        "",
        "## Entries",
    ]
    entries = readmap.get("entries") or []
    if not entries:
        lines.append("- (none)")
    for entry in entries:
        selector = str(entry.get("selector") or "")
        suffix = f" {selector}" if selector else ""
        lines.append(f"- {entry.get('path')}{suffix} (reason: {entry.get('reason')})")
    lines.extend(["", "## Allowed Paths"])
    for item in readmap.get("allowed_paths") or []:
        lines.append(f"- {item}")
    lines.extend(["", "## Loop Allowed Paths"])
    loop_allowed = readmap.get("loop_allowed_paths") or []
    if loop_allowed:
        for item in loop_allowed:
            lines.append(f"- {item}")
    else:
        lines.append("- (none)")
    return "\n".join(lines).rstrip() + "\n"


def _render_writemap_md(writemap: Dict[str, Any]) -> str:
    lines = [
        "# Write Map",
        "",
        f"- schema: {writemap.get('schema')}",
        f"- ticket: {writemap.get('ticket')}",
        f"- stage: {writemap.get('stage')}",
        f"- scope_key: {writemap.get('scope_key')}",
        f"- work_item_key: {writemap.get('work_item_key')}",
        f"- generated_at: {writemap.get('generated_at')}",
        "",
        "## Allowed Paths",
    ]
    for item in writemap.get("allowed_paths") or []:
        lines.append(f"- {item}")
    lines.extend(["", "## Loop Allowed Paths"])
    loop_allowed = writemap.get("loop_allowed_paths") or []
    if loop_allowed:
        for item in loop_allowed:
            lines.append(f"- {item}")
    else:
        lines.append("- (none)")
    lines.extend(["", "## DocOps Only Paths"])
    docops_only = writemap.get("docops_only_paths") or []
    if docops_only:
        for item in docops_only:
            lines.append(f"- {item}")
    else:
        lines.append("- (none)")
    lines.extend(["", "## Always Allow"])
    for item in writemap.get("always_allow") or []:
        lines.append(f"- {item}")
    return "\n".join(lines).rstrip() + "\n"


def _resolve_map_paths(target: Path, ticket: str, scope_key: str) -> Dict[str, Path]:
    context_base = target / "reports" / "context" / ticket
    audit_base = target / "reports" / "actions" / ticket / scope_key
    return {
        "base": context_base,
        "readmap_json": context_base / f"{scope_key}.readmap.json",
        "readmap_md": context_base / f"{scope_key}.readmap.md",
        "writemap_json": context_base / f"{scope_key}.writemap.json",
        "writemap_md": context_base / f"{scope_key}.writemap.md",
        "audit": audit_base / "context-expand.audit.jsonl",
    }


def _append_read_entry(readmap: Dict[str, Any], *, ref: str, reason_code: str, reason: str) -> None:
    path, selector = _parse_ref(ref)
    if not path:
        return
    entries = readmap.get("entries")
    if not isinstance(entries, list):
        entries = []
        readmap["entries"] = entries

    already = False
    for item in entries:
        if not isinstance(item, dict):
            continue
        if str(item.get("path") or "") == path and str(item.get("selector") or "") == selector:
            already = True
            break

    if not already:
        entries.append(
            {
                "ref": ref,
                "path": path,
                "selector": selector,
                "required": False,
                "reason": f"context-expand:{reason_code}",
                "detail": reason,
            }
        )

    allowed = readmap.get("allowed_paths")
    if not isinstance(allowed, list):
        allowed = []
    readmap["allowed_paths"] = _dedupe_str([str(item) for item in allowed] + [path] + ALWAYS_ALLOW_REPORTS)
    loop_allowed = readmap.get("loop_allowed_paths")
    if not isinstance(loop_allowed, list):
        readmap["loop_allowed_paths"] = []
    readmap.setdefault("always_allow", list(ALWAYS_ALLOW_REPORTS))
    readmap["generated_at"] = utc_timestamp()


def _append_write_entry(writemap: Dict[str, Any], *, ref: str, reason_code: str, reason: str) -> None:
    path, _selector = _parse_ref(ref)
    if not path:
        return
    allowed = writemap.get("allowed_paths")
    if not isinstance(allowed, list):
        allowed = []
    writemap["allowed_paths"] = _dedupe_str([str(item) for item in allowed] + [path] + ALWAYS_ALLOW_REPORTS)
    loop_allowed = writemap.get("loop_allowed_paths")
    if not isinstance(loop_allowed, list):
        writemap["loop_allowed_paths"] = []
    docops_only = writemap.get("docops_only_paths")
    if not isinstance(docops_only, list):
        writemap["docops_only_paths"] = []

    write_blocks = writemap.get("write_blocks")
    if not isinstance(write_blocks, list):
        write_blocks = []
    marker = f"{ref} (reason: context-expand:{reason_code} {reason})"
    if marker not in write_blocks:
        write_blocks.append(marker)
    writemap["write_blocks"] = write_blocks
    writemap.setdefault("always_allow", list(ALWAYS_ALLOW_REPORTS))
    writemap["generated_at"] = utc_timestamp()


def _regenerate_loop_pack(target: Path, *, ticket: str, stage: str, work_item_key: str) -> tuple[bool, str]:
    if stage == "review":
        loop_stage = "review"
    else:
        loop_stage = "implement"
    plugin_root = runtime.require_plugin_root()
    cmd = [
        sys.executable,
        str(plugin_root / "skills" / "aidd-loop" / "runtime" / "loop_pack.py"),
        "--ticket",
        ticket,
        "--stage",
        loop_stage,
        "--work-item",
        work_item_key,
    ]
    env = os.environ.copy()
    env["CLAUDE_PLUGIN_ROOT"] = str(plugin_root)
    env["PYTHONPATH"] = str(plugin_root) if not env.get("PYTHONPATH") else f"{plugin_root}:{env['PYTHONPATH']}"
    proc = subprocess.run(cmd, cwd=target, text=True, capture_output=True, env=env)
    output = (proc.stdout or "").strip() or (proc.stderr or "").strip()
    return proc.returncode == 0, output


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Expand readmap/writemap with audit trail.")
    parser.add_argument("--path", required=True, help="Path or block ref to add (path[#AIDD:..]|path@handoff:..)")
    parser.add_argument("--reason-code", required=True)
    parser.add_argument("--reason", required=True)
    parser.add_argument("--ticket", help="Ticket override")
    parser.add_argument("--scope-key", help="Scope key override")
    parser.add_argument("--work-item-key", help="Work item key override")
    parser.add_argument("--stage", help="Stage override")
    parser.add_argument("--expand-write", action="store_true", help="Also expand writemap (explicit boundary expansion).")
    parser.add_argument("--no-regenerate-pack", action="store_true", help="Skip loop-pack regeneration.")
    parser.add_argument("--format", choices=("text", "json"), default="text")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    _, target = runtime.require_workflow_root(Path.cwd())

    ticket = (args.ticket or runtime.read_active_ticket(target) or "").strip()
    if not ticket:
        print("[context-expand] ERROR: ticket is required (set docs/.active.json or pass --ticket)", file=sys.stderr)
        return 2

    work_item_key = (args.work_item_key or runtime.read_active_work_item(target) or "").strip()
    scope_key = (args.scope_key or runtime.resolve_scope_key(work_item_key, ticket)).strip()
    stage = (args.stage or runtime.read_active_stage(target) or "implement").strip().lower()

    map_paths = _resolve_map_paths(target, ticket, scope_key)
    readmap_json = map_paths["readmap_json"]
    writemap_json = map_paths["writemap_json"]
    readmap_md = map_paths["readmap_md"]
    writemap_md = map_paths["writemap_md"]

    if not readmap_json.exists():
        print(f"[context-expand] ERROR: missing readmap: {runtime.rel_path(readmap_json, target)}", file=sys.stderr)
        return 2

    readmap = _load_json(readmap_json)
    if not isinstance(readmap, dict):
        print(f"[context-expand] ERROR: invalid readmap payload: {runtime.rel_path(readmap_json, target)}", file=sys.stderr)
        return 2

    _append_read_entry(readmap, ref=args.path, reason_code=args.reason_code, reason=args.reason)
    readmap_errors = context_map_validate.validate_context_map_data(readmap)
    if readmap_errors:
        print(f"[context-expand] ERROR: invalid readmap after update: {'; '.join(readmap_errors)}", file=sys.stderr)
        return 2
    write_json(readmap_json, readmap, sort_keys=True)
    readmap_md.parent.mkdir(parents=True, exist_ok=True)
    readmap_md.write_text(_render_readmap_md(readmap), encoding="utf-8")

    writemap_updated = False
    if args.expand_write:
        if not writemap_json.exists():
            print(f"[context-expand] ERROR: missing writemap: {runtime.rel_path(writemap_json, target)}", file=sys.stderr)
            return 2
        writemap = _load_json(writemap_json)
        if not isinstance(writemap, dict):
            print(f"[context-expand] ERROR: invalid writemap payload: {runtime.rel_path(writemap_json, target)}", file=sys.stderr)
            return 2
        _append_write_entry(writemap, ref=args.path, reason_code=args.reason_code, reason=args.reason)
        writemap_errors = context_map_validate.validate_context_map_data(writemap)
        if writemap_errors:
            print(f"[context-expand] ERROR: invalid writemap after update: {'; '.join(writemap_errors)}", file=sys.stderr)
            return 2
        write_json(writemap_json, writemap, sort_keys=True)
        writemap_md.parent.mkdir(parents=True, exist_ok=True)
        writemap_md.write_text(_render_writemap_md(writemap), encoding="utf-8")
        writemap_updated = True

    regenerated_pack = False
    regenerate_message = ""
    regeneration_attempted = False
    if not args.no_regenerate_pack and stage in {"implement", "review", "qa"} and work_item_key:
        regeneration_attempted = True
        regenerated_pack, regenerate_message = _regenerate_loop_pack(
            target,
            ticket=ticket,
            stage=stage,
            work_item_key=work_item_key,
        )

    audit_payload: Dict[str, Any] = {
        "schema": "aidd.context_expand.audit.v1",
        "ts": utc_timestamp(),
        "ticket": ticket,
        "stage": stage,
        "scope_key": scope_key,
        "work_item_key": work_item_key,
        "path": args.path,
        "reason_code": args.reason_code,
        "reason": args.reason,
        "expand_write": bool(args.expand_write),
        "readmap_path": runtime.rel_path(readmap_json, target),
        "writemap_path": runtime.rel_path(writemap_json, target) if args.expand_write else "",
        "loop_pack_regenerated": bool(regenerated_pack),
        "loop_pack_message": regenerate_message,
    }
    append_jsonl(map_paths["audit"], audit_payload)

    if regeneration_attempted and not regenerated_pack:
        result_payload = {
            "schema": "aidd.context_expand.result.v1",
            "status": "blocked",
            "ticket": ticket,
            "stage": stage,
            "scope_key": scope_key,
            "work_item_key": work_item_key,
            "path": args.path,
            "expand_write": bool(args.expand_write),
            "readmap_path": runtime.rel_path(readmap_json, target),
            "writemap_path": runtime.rel_path(writemap_json, target),
            "audit_path": runtime.rel_path(map_paths["audit"], target),
            "reason_code": "loop_pack_regeneration_failed",
            "reason": regenerate_message or "loop-pack regeneration failed",
            "loop_pack_regenerated": False,
            "loop_pack_message": regenerate_message,
        }
        if args.format == "json":
            print(json.dumps(result_payload, ensure_ascii=False, indent=2))
        else:
            print(f"readmap_path={result_payload['readmap_path']}")
            if writemap_updated:
                print(f"writemap_path={result_payload['writemap_path']}")
            print(f"audit_path={result_payload['audit_path']}")
            print(
                "summary=BLOCKED"
                " reason_code=loop_pack_regeneration_failed"
                f" reason={result_payload['reason']}"
            )
        return 2

    result_payload = {
        "schema": "aidd.context_expand.result.v1",
        "status": "ok",
        "ticket": ticket,
        "stage": stage,
        "scope_key": scope_key,
        "work_item_key": work_item_key,
        "path": args.path,
        "expand_write": bool(args.expand_write),
        "readmap_path": runtime.rel_path(readmap_json, target),
        "writemap_path": runtime.rel_path(writemap_json, target),
        "audit_path": runtime.rel_path(map_paths["audit"], target),
        "loop_pack_regenerated": bool(regenerated_pack),
        "loop_pack_message": regenerate_message,
    }

    if args.format == "json":
        print(json.dumps(result_payload, ensure_ascii=False, indent=2))
    else:
        print(f"readmap_path={result_payload['readmap_path']}")
        if writemap_updated:
            print(f"writemap_path={result_payload['writemap_path']}")
        print(f"audit_path={result_payload['audit_path']}")
        print(
            "summary=context-expand ok"
            f" path={args.path}"
            f" expand_write={str(bool(args.expand_write)).lower()}"
            f" pack_regenerated={str(bool(regenerated_pack)).lower()}"
        )
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
