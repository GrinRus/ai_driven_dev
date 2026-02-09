#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Dict, List


def parse_frontmatter(text: str) -> Dict[str, str | list[str]]:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}
    data: Dict[str, str | list[str]] = {}
    current_list_key: str | None = None
    for line in lines[1:]:
        if line.strip() == "---":
            break
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.startswith("-"):
            if not current_list_key or not isinstance(data.get(current_list_key), list):
                continue
            item = stripped.lstrip("-").strip().strip('"').strip("'")
            if item:
                data[current_list_key].append(item)
            continue
        current_list_key = None
        if ":" not in stripped:
            continue
        key, value = stripped.split(":", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if value == "":
            data[key] = []
            current_list_key = key
        else:
            data[key] = value
    return data


def load_frontmatter(path: Path) -> Dict[str, str | list[str]]:
    try:
        return parse_frontmatter(path.read_text(encoding="utf-8"))
    except OSError:
        return {}


def _normalize_path(path: str) -> str:
    if path.startswith("./"):
        return path[2:]
    return path


def build_bundle(root: Path) -> Dict[str, object]:
    manifest_path = root / ".claude-plugin" / "plugin.json"
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))

    skills_raw = payload.get("skills") or []
    agents_raw = payload.get("agents") or []

    skills: List[Dict[str, str]] = []
    for entry in sorted(skills_raw):
        rel = _normalize_path(entry)
        path = root / rel
        fm = load_frontmatter(path)
        skills.append(
            {
                "path": rel,
                "name": str(fm.get("name", "")),
                "lang": str(fm.get("lang", "")),
                "prompt_version": str(fm.get("prompt_version", "")),
                "source_version": str(fm.get("source_version", "")),
                "user_invocable": str(fm.get("user-invocable", "")),
                "disable_model_invocation": str(fm.get("disable-model-invocation", "")),
            }
        )

    agents: List[Dict[str, str]] = []
    for entry in sorted(agents_raw):
        rel = _normalize_path(entry)
        path = root / rel
        fm = load_frontmatter(path)
        agents.append(
            {
                "path": rel,
                "name": str(fm.get("name", "")),
                "lang": str(fm.get("lang", "")),
                "prompt_version": str(fm.get("prompt_version", "")),
                "source_version": str(fm.get("source_version", "")),
            }
        )

    return {
        "schema": "aidd.entrypoints.bundle.v1",
        "skills": skills,
        "agents": agents,
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate entrypoints bundle from plugin manifest.")
    parser.add_argument(
        "--root",
        default=Path(__file__).resolve().parents[1],
        type=Path,
        help="Repository root containing .claude-plugin/plugin.json",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Output path (default: tests/repo_tools/entrypoints-bundle.txt)",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    root = args.root.resolve()
    bundle = build_bundle(root)
    output = Path(args.output) if args.output else root / "tests" / "repo_tools" / "entrypoints-bundle.txt"
    output.write_text(json.dumps(bundle, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
