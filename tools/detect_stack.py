from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

IGNORED_DIRS = {"aidd", ".git", "node_modules", ".venv"}

MARKERS: Dict[str, Tuple[str, ...]] = {
    "node": ("package.json", "pnpm-lock.yaml", "yarn.lock", "package-lock.json"),
    "python": ("pyproject.toml", "requirements.txt", "setup.py", "Pipfile", "Pipfile.lock"),
    "gradle": ("build.gradle", "build.gradle.kts", "settings.gradle", "settings.gradle.kts"),
    "maven": ("pom.xml",),
    "go": ("go.mod",),
    "rust": ("Cargo.toml",),
    "dotnet": (".sln",),
}

SKILL_MAP: Dict[str, List[str]] = {
    "node": ["testing-node", "formatting", "dev-run"],
    "python": ["testing-pytest", "formatting", "dev-run"],
    "gradle": ["testing-gradle", "formatting", "dev-run"],
    "maven": ["formatting", "dev-run"],
    "go": ["formatting", "dev-run"],
    "rust": ["formatting", "dev-run"],
    "dotnet": ["formatting", "dev-run"],
}


def _iter_files(root: Path) -> Iterable[Path]:
    for current, dirs, files in os.walk(root):
        rel = Path(current).resolve().relative_to(root)
        if rel.parts and rel.parts[0] in IGNORED_DIRS:
            dirs[:] = []
            continue
        dirs[:] = [d for d in dirs if d not in IGNORED_DIRS]
        for name in files:
            yield Path(current) / name


def detect_stack(root: Path) -> Dict[str, object]:
    root = root.resolve()
    detected: Dict[str, List[str]] = {key: [] for key in MARKERS}
    for path in _iter_files(root):
        for stack, markers in MARKERS.items():
            for marker in markers:
                if marker.startswith(".") and path.name.endswith(marker):
                    detected[stack].append(path.relative_to(root).as_posix())
                    break
                if path.name == marker:
                    detected[stack].append(path.relative_to(root).as_posix())
                    break

    stack_hint: List[str] = [stack for stack, paths in detected.items() if paths]
    enabled_skills: List[str] = []
    for stack in stack_hint:
        enabled_skills.extend(SKILL_MAP.get(stack, []))

    def dedupe(items: List[str]) -> List[str]:
        seen = set()
        ordered: List[str] = []
        for item in items:
            if item in seen:
                continue
            seen.add(item)
            ordered.append(item)
        return ordered

    return {
        "stack_hint": dedupe(stack_hint),
        "enabled_skills": dedupe(enabled_skills),
        "detected": {k: v for k, v in detected.items() if v},
        "root": root.as_posix(),
    }


def _split_front_matter(text: str) -> Tuple[List[str], List[str]]:
    lines = text.splitlines(keepends=True)
    if not lines or not lines[0].strip().startswith("---"):
        return [], lines
    for idx in range(1, len(lines)):
        if lines[idx].strip() == "---":
            return lines[: idx + 1], lines[idx + 1 :]
    return [], lines


def _merge_list(existing: List[str], new: List[str]) -> List[str]:
    merged = []
    seen = set()
    for item in existing + new:
        item = item.strip()
        if not item or item in seen:
            continue
        seen.add(item)
        merged.append(item)
    return merged


def _parse_list_block(lines: List[str], key: str) -> List[str]:
    prefix = f"{key}:"
    items: List[str] = []
    capture = False
    for line in lines:
        if line.startswith(prefix):
            capture = True
            inline = line[len(prefix) :].strip()
            if inline.startswith("[") and inline.endswith("]"):
                raw = inline.strip("[]")
                items.extend([part.strip().strip("\"") for part in raw.split(",") if part.strip()])
            continue
        if capture:
            if line.startswith("  -"):
                items.append(line.replace("-", "", 1).strip())
                continue
            break
    return items


def _replace_list_block(lines: List[str], key: str, items: List[str]) -> List[str]:
    prefix = f"{key}:"
    output: List[str] = []
    i = 0
    replaced = False
    while i < len(lines):
        line = lines[i]
        if line.startswith(prefix):
            replaced = True
            output.append(f"{key}:\n")
            for item in items:
                output.append(f"  - {item}\n")
            i += 1
            while i < len(lines) and lines[i].startswith("  -"):
                i += 1
            continue
        output.append(line)
        i += 1
    if not replaced:
        output.append(f"{key}:\n")
        for item in items:
            output.append(f"  - {item}\n")
    return output


def update_profile(profile_path: Path, detection: Dict[str, object], *, force: bool = False) -> bool:
    if not profile_path.exists():
        print(f"[detect-stack] profile not found: {profile_path}")
        return False

    stack_hint = list(detection.get("stack_hint", []))
    enabled_skills = list(detection.get("enabled_skills", []))
    if not stack_hint and not enabled_skills:
        return False

    text = profile_path.read_text(encoding="utf-8")
    front, body = _split_front_matter(text)
    if not front:
        print(f"[detect-stack] missing front-matter: {profile_path}")
        return False

    front_lines = front[1:-1]
    existing_stack = _parse_list_block(front_lines, "stack_hint")
    existing_skills = _parse_list_block(front_lines, "enabled_skills")

    merged_stack = _merge_list(existing_stack, stack_hint)
    merged_skills = _merge_list(existing_skills, enabled_skills)

    if not force and merged_stack == existing_stack and merged_skills == existing_skills:
        return False

    updated_lines = _replace_list_block(front_lines, "stack_hint", merged_stack)
    updated_lines = _replace_list_block(updated_lines, "enabled_skills", merged_skills)

    updated = ["---\n", *updated_lines, "---\n", *body]
    profile_path.write_text("".join(updated), encoding="utf-8")
    return True


def _render_summary(payload: Dict[str, object]) -> str:
    stacks = ", ".join(payload.get("stack_hint", []) or []) or "none"
    skills = ", ".join(payload.get("enabled_skills", []) or []) or "none"
    return f"stack_hint={stacks}; enabled_skills={skills}"


def _render_yaml(payload: Dict[str, object]) -> str:
    lines = ["schema: aidd.detect_stack.v1"]
    for key in ("stack_hint", "enabled_skills"):
        items = payload.get(key, []) or []
        lines.append(f"{key}:")
        for item in items:
            lines.append(f"  - {item}")
    detected = payload.get("detected", {}) or {}
    lines.append("detected:")
    for stack, paths in detected.items():
        lines.append(f"  {stack}:")
        for path in paths:
            lines.append(f"    - {path}")
    return "\n".join(lines) + "\n"


def parse_args(argv: List[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Detect stack markers for AIDD init.")
    parser.add_argument("--root", default=".", help="Workspace root to scan.")
    parser.add_argument("--format", choices=("json", "yaml"), help="Structured output format.")
    return parser.parse_args(argv)


def main(argv: List[str] | None = None) -> int:
    args = parse_args(argv)
    payload = detect_stack(Path(args.root))
    if args.format == "json":
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        print(_render_summary(payload), file=os.sys.stderr)
    elif args.format == "yaml":
        print(_render_yaml(payload), end="")
        print(_render_summary(payload), file=os.sys.stderr)
    else:
        print(_render_summary(payload))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
