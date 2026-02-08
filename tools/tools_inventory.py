#!/usr/bin/env python3
"""Generate an inventory of runtime shell entrypoints and their consumers."""

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


TOOL_PATTERN = re.compile(r"(?:\$\{CLAUDE_PLUGIN_ROOT\}/)?tools/([A-Za-z0-9_.-]+\.sh)")
SKILL_SCRIPT_PATTERN = re.compile(
    r"(?:\$\{CLAUDE_PLUGIN_ROOT\}/)?skills/([A-Za-z0-9_.-]+)/scripts/([A-Za-z0-9_.-]+\.sh)"
)
CANONICAL_EXEC_RE = re.compile(
    r'exec\s+"?\$\{CLAUDE_PLUGIN_ROOT\}/(skills/[A-Za-z0-9_.-]+/scripts/[A-Za-z0-9_.-]+\.sh)"?'
)
DEFERRED_CORE_APIS = {
    "tools/init.sh",
    "tools/research.sh",
    "tools/tasks-derive.sh",
    "tools/actions-apply.sh",
    "tools/context-expand.sh",
}
SHARED_SKILL_PREFIXES = ("skills/aidd-",)
SCAN_PATHS = (
    "commands",
    "agents",
    "hooks",
    "skills",
    "templates",
    "tests",
    "docs",
    "AGENTS.md",
    "README.md",
    "README.en.md",
    "CONTRIBUTING.md",
)
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


def _collect_skill_scripts(repo_root: Path) -> List[str]:
    return sorted(path.relative_to(repo_root).as_posix() for path in repo_root.glob("skills/*/scripts/*.sh"))


def _collect_entrypoints(repo_root: Path) -> List[str]:
    tools = [f"tools/{name}" for name in _collect_tool_scripts(repo_root)]
    skills = _collect_skill_scripts(repo_root)
    return sorted(set(tools + skills))


def _iter_scan_candidates(repo_root: Path) -> Iterable[Path]:
    for item in SCAN_PATHS:
        base = repo_root / item
        if not base.exists():
            continue
        if base.is_file():
            yield base
            continue
        yield from (path for path in base.rglob("*") if path.is_file())


def _scan_consumers(repo_root: Path, entrypoints: Iterable[str]) -> Dict[str, List[str]]:
    names = set(entrypoints)
    usage: Dict[str, List[str]] = {name: [] for name in names}
    for path in _iter_scan_candidates(repo_root):
        if _should_skip_path(path):
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for match in TOOL_PATTERN.finditer(text):
            tool = f"tools/{match.group(1)}"
            if tool in names:
                usage[tool].append(path.relative_to(repo_root).as_posix())
        for match in SKILL_SCRIPT_PATTERN.finditer(text):
            script = f"skills/{match.group(1)}/scripts/{match.group(2)}"
            if script in names:
                usage[script].append(path.relative_to(repo_root).as_posix())
    for key, items in usage.items():
        deduped = sorted(set(items))
        usage[key] = deduped
    return usage


def _extract_canonical_replacement(path: Path) -> str | None:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None
    match = CANONICAL_EXEC_RE.search(text)
    if not match:
        return None
    return match.group(1)


def _consumer_type(rel_path: str) -> str:
    if rel_path.startswith("agents/"):
        return "agent"
    if rel_path.startswith("skills/"):
        return "skill"
    if rel_path.startswith("hooks/"):
        return "hook"
    if rel_path.startswith("tests/"):
        return "test"
    if rel_path.startswith("templates/") or rel_path.startswith("docs/") or rel_path in {
        "AGENTS.md",
        "README.md",
        "README.en.md",
        "CONTRIBUTING.md",
    }:
        return "docs"
    if rel_path.startswith("tools/"):
        return "shim" if rel_path.endswith(".sh") else "tool"
    return "other"


def _classify_entrypoint(rel_path: str, canonical_replacement_path: str | None) -> tuple[str, bool, bool]:
    if rel_path in DEFERRED_CORE_APIS:
        return "core_api_deferred", True, True
    if rel_path.startswith("skills/"):
        if any(rel_path.startswith(prefix) for prefix in SHARED_SKILL_PREFIXES):
            return "shared_skill", False, False
        return "canonical_stage", False, False
    if canonical_replacement_path:
        return "shim", False, False
    return "shared_tool", False, False


def _group_consumers(consumers: List[str]) -> Dict[str, List[str]]:
    grouped: Dict[str, List[str]] = {}
    for rel_path in consumers:
        ctype = _consumer_type(rel_path)
        grouped.setdefault(ctype, []).append(rel_path)
    for key in list(grouped):
        grouped[key] = sorted(set(grouped[key]))
    return dict(sorted(grouped.items()))


def _build_payload(repo_root: Path) -> Dict[str, object]:
    entrypoints = _collect_entrypoints(repo_root)
    usage = _scan_consumers(repo_root, entrypoints)
    items: List[Dict[str, object]] = []
    for rel_path in entrypoints:
        abs_path = repo_root / rel_path
        canonical_replacement_path = None
        if rel_path.startswith("tools/"):
            canonical_replacement_path = _extract_canonical_replacement(abs_path)
        classification, core_api, migration_deferred = _classify_entrypoint(rel_path, canonical_replacement_path)
        consumers = usage.get(rel_path, [])
        grouped = _group_consumers(consumers)
        items.append(
            {
                "path": rel_path,
                "classification": classification,
                "core_api": core_api,
                "migration_deferred": migration_deferred,
                "canonical_replacement_path": canonical_replacement_path,
                "consumers": consumers,
                "consumer_count": len(consumers),
                "consumers_by_type": grouped,
                "consumer_types": sorted(grouped.keys()),
            }
        )
    return {
        "schema": "aidd.tools_inventory.v2",
        "generated_at": utc_timestamp(),
        "repo_root": repo_root.as_posix(),
        "scan_dirs": list(SCAN_PATHS),
        "entrypoints": items,
    }


def _render_md(payload: Dict[str, object]) -> str:
    lines = ["# Tools Inventory", ""]
    lines.append(f"generated_at: {payload.get('generated_at', '')}")
    lines.append("")
    for entry in payload.get("entrypoints", []):
        path = str(entry.get("path", ""))
        consumers = entry.get("consumers", []) or []
        lines.append(f"## {path}")
        lines.append(f"- classification: {entry.get('classification', '')}")
        if entry.get("core_api"):
            lines.append("- core_api: true")
        if entry.get("migration_deferred"):
            lines.append("- migration_deferred: true")
        if entry.get("canonical_replacement_path"):
            lines.append(f"- canonical_replacement_path: {entry.get('canonical_replacement_path')}")
        if not consumers:
            lines.append("- (no consumers in scanned repository sources)")
            lines.append("")
            continue
        lines.append("- consumers:")
        grouped = entry.get("consumers_by_type") or {}
        for ctype, refs in grouped.items():
            lines.append(f"  - {ctype}: {len(refs)}")
            for ref in refs:
                lines.append(f"    - {ref}")
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
    workflow_root: Path | None = None
    if not args.output_json or not args.output_md:
        try:
            _, workflow_root = runtime.resolve_roots(Path.cwd(), create=True)
        except Exception:
            workflow_root = repo_root / "aidd"
            workflow_root.mkdir(parents=True, exist_ok=True)

    payload = _build_payload(repo_root)

    if args.output_json:
        output_json = Path(args.output_json)
    else:
        output_json = (workflow_root or (repo_root / "aidd")) / "reports" / "tools" / "tools-inventory.json"
    if args.output_md:
        output_md = Path(args.output_md)
    else:
        output_md = (workflow_root or (repo_root / "aidd")) / "reports" / "tools" / "tools-inventory.md"

    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_md.parent.mkdir(parents=True, exist_ok=True)

    output_json.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    output_md.write_text(_render_md(payload), encoding="utf-8")

    if workflow_root is not None:
        print(f"[tools-inventory] JSON: {runtime.rel_path(output_json, workflow_root)}")
        print(f"[tools-inventory] MD: {runtime.rel_path(output_md, workflow_root)}")
    else:
        print(f"[tools-inventory] JSON: {output_json}")
        print(f"[tools-inventory] MD: {output_md}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
