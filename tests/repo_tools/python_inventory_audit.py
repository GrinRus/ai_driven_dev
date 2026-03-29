#!/usr/bin/env python3
"""Build a machine-readable inventory for repository Python files."""

from __future__ import annotations

import argparse
import ast
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Sequence

ROOT = Path(__file__).resolve().parents[2]
SCAN_ROOTS = ("skills", "hooks", "aidd_runtime", "tests")
TEXT_EXTENSIONS = {".py", ".sh", ".md", ".json", ".yaml", ".yml", ".txt"}
CI_COMMAND_GLOBS = (
    ".github/workflows/**/*.yml",
    ".github/workflows/**/*.yaml",
    "tests/repo_tools/**/*.sh",
    "tests/repo_tools/**/*.py",
    "skills/*/SKILL.md",
    "agents/**/*.md",
    "commands/**/*.md",
)


@dataclass
class FileInventory:
    path: str
    role: str
    entrypoint: bool
    invocation: str
    direct_imports: List[str]
    incoming_refs_count: int
    covered_by_tests: bool
    used_in_ci_or_commands: bool
    status: str
    status_reason: str


def _iter_python_files(root: Path) -> List[Path]:
    files: List[Path] = []
    for scan_root in SCAN_ROOTS:
        base = root / scan_root
        if not base.is_dir():
            continue
        for path in base.rglob("*.py"):
            if "__pycache__" in path.parts:
                continue
            if path.is_file():
                files.append(path.resolve())
    return sorted(set(files))


def _role_for(rel: Path) -> str:
    parts = rel.parts
    if not parts:
        return "library"
    if parts[0] == "tests":
        if len(parts) >= 2 and parts[1] == "repo_tools":
            return "repo_tool"
        return "test"
    if parts[0] == "hooks":
        return "entrypoint" if len(parts) == 2 else "library"
    if len(parts) >= 4 and parts[0] == "skills" and parts[2] == "runtime":
        return "entrypoint" if len(parts) == 4 else "library"
    return "library"


def _is_entrypoint(role: str) -> bool:
    return role == "entrypoint"


def _parse_direct_imports(path: Path) -> List[str]:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except Exception:
        return []

    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                name = str(alias.name or "").strip()
                if name:
                    modules.add(name)
        elif isinstance(node, ast.ImportFrom):
            level = int(getattr(node, "level", 0) or 0)
            if node.module:
                modules.add("." * level + node.module)
            elif level:
                modules.add("." * level)
    return sorted(modules)


def _iter_text_files(root: Path) -> Iterable[Path]:
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if any(part in {".git", ".venv", "node_modules", "__pycache__"} for part in path.parts):
            continue
        if path.suffix.lower() in TEXT_EXTENSIONS:
            yield path


def _load_text_index(root: Path) -> Dict[str, str]:
    payload: Dict[str, str] = {}
    for path in _iter_text_files(root):
        rel = path.relative_to(root).as_posix()
        try:
            payload[rel] = path.read_text(encoding="utf-8")
        except Exception:
            continue
    return payload


def _collect_ci_command_refs(root: Path, text_index: Dict[str, str]) -> Dict[str, List[str]]:
    files: List[Path] = []
    for glob_pattern in CI_COMMAND_GLOBS:
        files.extend(path for path in root.glob(glob_pattern) if path.is_file())

    refs: Dict[str, List[str]] = {}
    for path in sorted(set(files)):
        rel = path.relative_to(root).as_posix()
        text = text_index.get(rel)
        if text is None:
            try:
                text = path.read_text(encoding="utf-8")
            except Exception:
                continue
        refs[rel] = [text]
    return refs


def _incoming_ref_count(target_rel: str, text_index: Dict[str, str]) -> int:
    count = 0
    for rel, text in text_index.items():
        if rel == target_rel:
            continue
        if target_rel in text:
            count += 1
    return count


def _is_covered_by_tests(path: Path, rel: Path, role: str, tests_text: str, test_files: Sequence[Path]) -> bool:
    if role in {"test", "repo_tool"}:
        return True

    rel_text = rel.as_posix()
    module_name = ".".join(rel.with_suffix("").parts)
    if rel_text in tests_text or module_name in tests_text:
        return True

    stem = path.stem
    expected = f"test_{stem}.py"
    return any(candidate.name == expected for candidate in test_files)


def _is_used_in_ci_or_commands(target_rel: str, ci_refs: Dict[str, List[str]]) -> bool:
    for blobs in ci_refs.values():
        for text in blobs:
            if target_rel in text:
                return True
    return False


def _status_for(*, entrypoint: bool, incoming_refs_count: int, used_in_ci_or_commands: bool) -> tuple[str, str]:
    if entrypoint:
        return "active", "runtime/hook entrypoint"
    if incoming_refs_count == 0 and not used_in_ci_or_commands:
        return "candidate_dead", "no incoming refs, not entrypoint, not used in CI/commands"
    if incoming_refs_count == 0 and used_in_ci_or_commands:
        return "keep", "no incoming refs, but referenced by CI/commands"
    return "active", "referenced by repository code/docs"


def _build_inventory(root: Path) -> Dict[str, object]:
    py_files = _iter_python_files(root)
    text_index = _load_text_index(root)
    ci_refs = _collect_ci_command_refs(root, text_index)

    tests_files = sorted((root / "tests").rglob("*.py")) if (root / "tests").is_dir() else []
    tests_text = "\n".join(
        text_index.get(path.relative_to(root).as_posix(), "")
        for path in tests_files
        if path.is_file()
    )

    rows: List[FileInventory] = []
    for path in py_files:
        rel = path.relative_to(root)
        rel_text = rel.as_posix()
        role = _role_for(rel)
        entrypoint = _is_entrypoint(role)
        incoming_refs_count = _incoming_ref_count(rel_text, text_index)
        used_in_ci_or_commands = _is_used_in_ci_or_commands(rel_text, ci_refs)
        covered_by_tests = _is_covered_by_tests(path, rel, role, tests_text, tests_files)
        status, status_reason = _status_for(
            entrypoint=entrypoint,
            incoming_refs_count=incoming_refs_count,
            used_in_ci_or_commands=used_in_ci_or_commands,
        )

        rows.append(
            FileInventory(
                path=rel_text,
                role=role,
                entrypoint=entrypoint,
                invocation=f"python3 {rel_text}" if entrypoint else "",
                direct_imports=_parse_direct_imports(path),
                incoming_refs_count=incoming_refs_count,
                covered_by_tests=covered_by_tests,
                used_in_ci_or_commands=used_in_ci_or_commands,
                status=status,
                status_reason=status_reason,
            )
        )

    role_counts: Dict[str, int] = {}
    status_counts: Dict[str, int] = {}
    for row in rows:
        role_counts[row.role] = role_counts.get(row.role, 0) + 1
        status_counts[row.status] = status_counts.get(row.status, 0) + 1

    return {
        "schema": "aidd.python_inventory.v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "root": root.as_posix(),
        "summary": {
            "total_files": len(rows),
            "roles": role_counts,
            "statuses": status_counts,
        },
        "files": [asdict(row) for row in rows],
    }


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build Python inventory audit report.")
    parser.add_argument("--root", default=str(ROOT), help="Repository root (default: current repository root).")
    parser.add_argument("--out", help="Optional output JSON path.")
    parser.add_argument(
        "--print-candidates",
        action="store_true",
        help="Print candidate_dead entries to stdout.",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    root = Path(args.root).resolve()
    report = _build_inventory(root)

    out_path = Path(args.out).resolve() if args.out else None
    if out_path is not None:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    summary = report["summary"]
    print(
        "[python-inventory-audit] "
        f"files={summary['total_files']} "
        f"roles={json.dumps(summary['roles'], ensure_ascii=False, sort_keys=True)} "
        f"statuses={json.dumps(summary['statuses'], ensure_ascii=False, sort_keys=True)}"
    )

    if args.print_candidates:
        for row in report["files"]:
            if row.get("status") == "candidate_dead":
                print(f"[python-inventory-audit] CANDIDATE: {row['path']} ({row['status_reason']})")

    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
