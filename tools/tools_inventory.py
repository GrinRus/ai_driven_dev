#!/usr/bin/env python3
"""Generate an inventory of tools/*.sh usages in repo sources."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Dict, Iterable, List


if __package__ in {None, ""}:
    _repo_root = Path(__file__).resolve().parents[1]
    if str(_repo_root) not in sys.path:
        sys.path.insert(0, str(_repo_root))

from tools import runtime
from tools.io_utils import utc_timestamp


TOOL_PATTERN = re.compile(r"tools/([A-Za-z0-9_.-]+\.sh)")
SCAN_DIRS = ("commands", "agents", "hooks", "tests")
EXCLUDED_DIRS = {
    "__pycache__",
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".tox",
    ".venv",
    "build",
    "dist",
    "node_modules",
    "venv",
}
EXCLUDED_SUFFIXES = {".pyc", ".pyo"}


def _should_skip_path(path: Path) -> bool:
    if path.suffix.lower() in EXCLUDED_SUFFIXES:
        return True
    return any(part in EXCLUDED_DIRS for part in path.parts)


def _collect_tool_scripts(repo_root: Path) -> List[str]:
    tools_dir = repo_root / "tools"
    return sorted(path.name for path in tools_dir.glob("*.sh"))


def _scan_consumers(repo_root: Path, tool_names: Iterable[str]) -> Dict[str, List[str]]:
    names = set(tool_names)
    usage: Dict[str, List[str]] = {name: [] for name in names}
    for folder in SCAN_DIRS:
        base = repo_root / folder
        if not base.exists():
            continue
        for path in base.rglob("*"):
            if not path.is_file():
                continue
            if _should_skip_path(path):
                continue
            try:
                text = path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            for match in TOOL_PATTERN.finditer(text):
                tool = match.group(1)
                if tool in names:
                    usage[tool].append(path.relative_to(repo_root).as_posix())
    for key, items in usage.items():
        deduped = sorted(set(items))
        usage[key] = deduped
    return usage


def _build_payload(repo_root: Path) -> Dict[str, object]:
    tool_names = _collect_tool_scripts(repo_root)
    usage = _scan_consumers(repo_root, tool_names)
    tools: List[Dict[str, object]] = []
    for name in sorted(tool_names):
        consumers = usage.get(name, [])
        tools.append(
            {
                "tool": f"tools/{name}",
                "consumers": consumers,
                "consumer_count": len(consumers),
            }
        )
    return {
        "schema": "aidd.tools_inventory.v1",
        "generated_at": utc_timestamp(),
        "repo_root": repo_root.as_posix(),
        "scan_dirs": list(SCAN_DIRS),
        "tools": tools,
    }


def _render_md(payload: Dict[str, object]) -> str:
    lines = ["# Tools Inventory", ""]
    lines.append(f"generated_at: {payload.get('generated_at', '')}")
    lines.append("")
    for entry in payload.get("tools", []):
        tool = entry.get("tool", "")
        consumers = entry.get("consumers", []) or []
        lines.append(f"## {tool}")
        if not consumers:
            lines.append("- (no consumers in commands/agents/hooks/tests)")
            lines.append("")
            continue
        for consumer in consumers:
            lines.append(f"- {consumer}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate tools usage inventory.")
    parser.add_argument(
        "--repo-root",
        default=None,
        help="Repository root (defaults to CLAUDE_PLUGIN_ROOT or script parent).",
    )
    parser.add_argument(
        "--output-json",
        default=None,
        help="Output JSON path (default: aidd/reports/tools/tools-inventory.json).",
    )
    parser.add_argument(
        "--output-md",
        default=None,
        help="Output Markdown path (default: aidd/reports/tools/tools-inventory.md).",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.repo_root:
        repo_root = Path(args.repo_root).resolve()
    else:
        repo_root = Path(__file__).resolve().parents[1]
    if "CLAUDE_PLUGIN_ROOT" not in os.environ:
        os.environ["CLAUDE_PLUGIN_ROOT"] = str(repo_root)
    _, workflow_root = runtime.resolve_roots(Path.cwd(), create=True)

    payload = _build_payload(repo_root)

    output_json = Path(args.output_json) if args.output_json else workflow_root / "reports" / "tools" / "tools-inventory.json"
    output_md = Path(args.output_md) if args.output_md else workflow_root / "reports" / "tools" / "tools-inventory.md"

    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_md.parent.mkdir(parents=True, exist_ok=True)

    output_json.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    output_md.write_text(_render_md(payload), encoding="utf-8")

    print(f"[tools-inventory] JSON: {runtime.rel_path(output_json, workflow_root)}")
    print(f"[tools-inventory] MD: {runtime.rel_path(output_md, workflow_root)}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
