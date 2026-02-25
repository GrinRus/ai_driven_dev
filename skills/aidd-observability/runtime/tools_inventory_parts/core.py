#!/usr/bin/env python3
"""Generate an inventory of runtime entrypoints and their consumers."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Dict, Iterable, List, Set


def _repo_root() -> Path:
    try:
        from aidd_runtime import repo_paths as _repo_paths

        return _repo_paths.repo_root(__file__)
    except Exception:
        here = Path(__file__).resolve()
        for candidate in (here.parent, *here.parents):
            if (candidate / ".claude-plugin").is_dir() and (candidate / "skills").is_dir():
                return candidate
        return here.parents[2]


if __package__ in {None, ""}:
    _ROOT_FOR_SYS_PATH = _repo_root()
    if str(_ROOT_FOR_SYS_PATH) not in sys.path:
        sys.path.insert(0, str(_ROOT_FOR_SYS_PATH))

from aidd_runtime import runtime
from aidd_runtime.io_utils import utc_timestamp


TOOL_PATTERN = re.compile(r"(?:\$\{CLAUDE_PLUGIN_ROOT\}/)?tools/([A-Za-z0-9_.-]+\.(?:sh|py))")
SKILL_RUNTIME_PATTERN = re.compile(
    r"(?:\$\{CLAUDE_PLUGIN_ROOT\}/)?skills/([A-Za-z0-9_.-]+)/runtime/([A-Za-z0-9_.-]+\.py)"
)
HOOK_PATTERN = re.compile(r"(?:\$\{CLAUDE_PLUGIN_ROOT\}/)?hooks/([A-Za-z0-9_.-]+\.(?:py|sh))")

CANONICAL_EXEC_RE = re.compile(
    r'exec\s+"?\$\{CLAUDE_PLUGIN_ROOT\}/(skills/[A-Za-z0-9_.-]+/runtime/[A-Za-z0-9_.-]+\.py)"?'
)
SCRIPT_REF_RE = re.compile(
    r"(?:\$\{CLAUDE_PLUGIN_ROOT\}/)?((?:skills/[A-Za-z0-9_.-]+/runtime/[A-Za-z0-9_.-]+\.py)|(?:hooks/[A-Za-z0-9_.-]+\.(?:py|sh))|(?:tools/[A-Za-z0-9_.-]+\.(?:sh|py)))"
)
PYTHON_CALL_RE = re.compile(
    r"\bpython(?:3)?\s+(?:\"|')?\$\{CLAUDE_PLUGIN_ROOT\}/([A-Za-z0-9_./-]+\.py)(?:\"|')?"
)
AIDD_RUN_PY_MODULE_RE = re.compile(
    r'aidd_run_python_module\s+"[^"]+"\s+"[^"]+"\s+"([^"]+\.py)"'
)

DEFERRED_CORE_APIS: set[str] = set()
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


def _collect_tool_entrypoints(repo_root: Path) -> List[str]:
    tools_dir = repo_root / "tools"
    if not tools_dir.exists():
        return []
    return sorted(path.name for path in tools_dir.glob("*") if path.is_file() and path.suffix in {".sh", ".py"})


def _collect_skill_runtime(repo_root: Path) -> List[str]:
    return sorted(path.relative_to(repo_root).as_posix() for path in repo_root.glob("skills/*/runtime/*.py"))


def _collect_hook_scripts(repo_root: Path) -> List[str]:
    return sorted(
        path.relative_to(repo_root).as_posix()
        for path in repo_root.glob("hooks/*")
        if path.is_file() and path.suffix in {".py", ".sh"}
    )


def _collect_entrypoints(repo_root: Path) -> List[str]:
    tools = [f"tools/{name}" for name in _collect_tool_entrypoints(repo_root)]
    skills = _collect_skill_runtime(repo_root)
    hooks = _collect_hook_scripts(repo_root)
    return sorted(set(tools + skills + hooks))


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
        for match in SKILL_RUNTIME_PATTERN.finditer(text):
            runtime_path = f"skills/{match.group(1)}/runtime/{match.group(2)}"
            if runtime_path in names:
                usage[runtime_path].append(path.relative_to(repo_root).as_posix())
        for match in HOOK_PATTERN.finditer(text):
            hook_script = f"hooks/{match.group(1)}"
            if hook_script in names:
                usage[hook_script].append(path.relative_to(repo_root).as_posix())
    for key, items in usage.items():
        usage[key] = sorted(set(items))
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
        return "redirect_wrapper" if rel_path.endswith(".sh") else "tool"
    return "other"


def _classify_entrypoint(rel_path: str, canonical_replacement_path: str | None) -> tuple[str, bool, bool]:
    if rel_path in DEFERRED_CORE_APIS:
        return "core_api_deferred", True, True
    if rel_path.startswith("skills/"):
        if any(rel_path.startswith(prefix) for prefix in SHARED_SKILL_PREFIXES):
            return "shared_skill", False, False
        return "canonical_stage", False, False
    if rel_path.startswith("hooks/"):
        return "hook_entrypoint", False, False
    if canonical_replacement_path:
        return "redirect_wrapper", False, False
    return "shared_tool", False, False


def _group_consumers(consumers: List[str]) -> Dict[str, List[str]]:
    grouped: Dict[str, List[str]] = {}
    for rel_path in consumers:
        ctype = _consumer_type(rel_path)
        grouped.setdefault(ctype, []).append(rel_path)
    for key in list(grouped):
        grouped[key] = sorted(set(grouped[key]))
    return dict(sorted(grouped.items()))


def _normalize_repo_rel(raw: str) -> str:
    text = str(raw or "").strip().replace("\\", "/")
    if not text:
        return ""
    text = text.replace("${CLAUDE_PLUGIN_ROOT}/", "")
    while text.startswith("./"):
        text = text[2:]
    return text.lstrip("/")


def _read_script_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return ""


def _script_shebang(text: str) -> str:
    if not text:
        return ""
    lines = text.splitlines()
    if not lines:
        return ""
    return lines[0].strip()


def _extract_direct_python_targets(rel_path: str, text: str, shebang: str) -> List[str]:
    targets: Set[str] = set()
    if rel_path.endswith(".py"):
        targets.add(rel_path)
    if shebang.startswith("#!/usr/bin/env python"):
        targets.add(rel_path)
    for match in AIDD_RUN_PY_MODULE_RE.finditer(text):
        value = _normalize_repo_rel(match.group(1))
        if value.endswith(".py"):
            targets.add(value)
    for match in PYTHON_CALL_RE.finditer(text):
        value = _normalize_repo_rel(match.group(1))
        if value.endswith(".py"):
            targets.add(value)
    return sorted(targets)


def _extract_direct_shell_targets(text: str) -> List[str]:
    targets: Set[str] = set()
    for match in SCRIPT_REF_RE.finditer(text):
        value = _normalize_repo_rel(match.group(1))
        if value.endswith((".sh", ".py")):
            targets.add(value)
    return sorted(targets)


def _build_wrapper_meta(repo_root: Path, entrypoints: List[str]) -> Dict[str, Dict[str, object]]:
    meta: Dict[str, Dict[str, object]] = {}
    for rel_path in entrypoints:
        path = repo_root / rel_path
        text = _read_script_text(path)
        shebang = _script_shebang(text)
        direct_python_targets = _extract_direct_python_targets(rel_path, text, shebang)
        direct_shell_targets = _extract_direct_shell_targets(text)
        meta[rel_path] = {
            "shebang": shebang,
            "python_shebang": shebang.startswith("#!/usr/bin/env python"),
            "direct_python_targets": direct_python_targets,
            "direct_shell_targets": [item for item in direct_shell_targets if item != rel_path],
        }
    return meta


def _resolve_python_owners(
    rel_path: str,
    meta: Dict[str, Dict[str, object]],
    cache: Dict[str, Set[str]],
    stack: Set[str],
) -> Set[str]:
    if rel_path in cache:
        return set(cache[rel_path])
    if rel_path in stack:
        return set()
    stack.add(rel_path)
    entry = meta.get(rel_path) or {}
    owners: Set[str] = set(entry.get("direct_python_targets") or [])
    for target in entry.get("direct_shell_targets") or []:
        if target in meta:
            owners.update(_resolve_python_owners(target, meta, cache, stack))
    stack.remove(rel_path)
    cache[rel_path] = set(owners)
    return set(owners)


def _runtime_classification(rel_path: str, *, python_shebang: bool, owners: List[str]) -> str:
    if rel_path.endswith(".py"):
        return "python_entrypoint"
    if python_shebang:
        return "python_entrypoint"
    if rel_path.startswith("hooks/") and not owners:
        return "hook_shell_only"
    return "legacy_shell_wrapper"


def _build_payload(repo_root: Path) -> Dict[str, object]:
    entrypoints = _collect_entrypoints(repo_root)
    usage = _scan_consumers(repo_root, entrypoints)
    meta = _build_wrapper_meta(repo_root, entrypoints)
    resolved_cache: Dict[str, Set[str]] = {}
    items: List[Dict[str, object]] = []

    for rel_path in entrypoints:
        abs_path = repo_root / rel_path
        canonical_replacement_path = None
        if rel_path.startswith("tools/"):
            canonical_replacement_path = _extract_canonical_replacement(abs_path)
        classification, core_api, migration_deferred = _classify_entrypoint(rel_path, canonical_replacement_path)
        consumers = usage.get(rel_path, [])
        grouped = _group_consumers(consumers)

        entry_meta = meta.get(rel_path) or {}
        direct_shell_targets = list(entry_meta.get("direct_shell_targets") or [])
        unresolved_shell_targets = sorted(target for target in direct_shell_targets if target not in meta)
        owners = sorted(_resolve_python_owners(rel_path, meta, resolved_cache, set()))
        runtime_classification = _runtime_classification(
            rel_path,
            python_shebang=bool(entry_meta.get("python_shebang")),
            owners=owners,
        )
        primary_owner = owners[0] if len(owners) == 1 else None

        items.append(
            {
                "path": rel_path,
                "classification": classification,
                "runtime_classification": runtime_classification,
                "core_api": core_api,
                "migration_deferred": migration_deferred,
                "canonical_replacement_path": canonical_replacement_path,
                "python_owner_path": primary_owner,
                "python_owner_paths": owners,
                "python_owner_count": len(owners),
                "python_owner_resolution": "none" if not owners else ("single" if len(owners) == 1 else "multiple"),
                "direct_python_targets": list(entry_meta.get("direct_python_targets") or []),
                "shell_targets": direct_shell_targets,
                "unresolved_shell_targets": unresolved_shell_targets,
                "consumers": consumers,
                "consumer_count": len(consumers),
                "consumers_by_type": grouped,
                "consumer_types": sorted(grouped.keys()),
            }
        )
    return {
        "schema": "aidd.tools_inventory.v3",
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
        lines.append(f"- runtime_classification: {entry.get('runtime_classification', '')}")
        lines.append(f"- python_owner_path: {entry.get('python_owner_path')}")
        owners = entry.get("python_owner_paths") or []
        if owners:
            lines.append(f"- python_owner_paths ({len(owners)}):")
            for owner in owners:
                lines.append(f"  - {owner}")
        if entry.get("core_api"):
            lines.append("- core_api: true")
        if entry.get("migration_deferred"):
            lines.append("- migration_deferred: true")
        if entry.get("canonical_replacement_path"):
            lines.append(f"- canonical_replacement_path: {entry.get('canonical_replacement_path')}")
        shell_targets = entry.get("shell_targets") or []
        if shell_targets:
            lines.append("- shell_targets:")
            for target in shell_targets:
                lines.append(f"  - {target}")
        unresolved = entry.get("unresolved_shell_targets") or []
        if unresolved:
            lines.append("- unresolved_shell_targets:")
            for target in unresolved:
                lines.append(f"  - {target}")
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
        repo_root = _repo_root()
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
