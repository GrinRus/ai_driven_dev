from __future__ import annotations

import argparse
import sys
from pathlib import Path

from tools import runtime

REQUIRED_SCHEMA = "aidd.arch_profile.v1"
REQUIRED_HEADINGS = [
    "## Style / Pattern",
    "## Modules / Layers",
    "## Allowed dependencies",
    "## Invariants",
    "## Interface pointers (API / DB / Events)",
    "## Skills enabled (AIDD)",
    "## Repo conventions",
]


def _parse_front_matter(text: str) -> dict[str, str]:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}
    data: dict[str, str] = {}
    for line in lines[1:]:
        if line.strip() == "---":
            break
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        data[key.strip()] = value.strip()
    return data


def _resolve_profile_path(path_arg: str | None) -> Path:
    if path_arg:
        return Path(path_arg)
    try:
        _, project_root = runtime.resolve_roots(Path.cwd(), create=False)
        return project_root / "docs" / "architecture" / "profile.md"
    except FileNotFoundError:
        return Path("aidd/docs/architecture/profile.md")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate AIDD architecture profile.")
    parser.add_argument("--path", help="Path to architecture profile markdown.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    profile_path = _resolve_profile_path(args.path)
    if not profile_path.exists():
        print(f"[arch-profile] missing profile: {profile_path}")
        return 1

    text = profile_path.read_text(encoding="utf-8")
    front = _parse_front_matter(text)
    schema = front.get("schema", "")
    if schema != REQUIRED_SCHEMA:
        print(f"[arch-profile] invalid schema: {schema!r} (expected {REQUIRED_SCHEMA})")
        return 1

    missing = [heading for heading in REQUIRED_HEADINGS if heading not in text]
    if missing:
        print(f"[arch-profile] missing sections: {', '.join(missing)}")
        return 1

    print(f"[arch-profile] ok: {profile_path}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
