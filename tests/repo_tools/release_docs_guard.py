#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Iterable

INTERNAL_MARKER = "INTERNAL/DEV-ONLY"
VALID_GROUPS = {"public_release_docs", "runtime_contract_docs", "internal_dev_docs"}
SEMVER_HEADING_RE = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*) - \d{4}-\d{2}-\d{2}$")
TOKEN_BOUNDARY = r"[A-Za-z0-9_./-]"


def _parse_manifest(path: Path) -> dict[str, list[str]]:
    groups: dict[str, list[str]] = {name: [] for name in VALID_GROUPS}
    current: str | None = None
    for lineno, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw.strip()
        if not line or line == "---" or line.startswith("#"):
            continue
        if line.endswith(":") and not line.startswith("- "):
            group = line[:-1].strip()
            if group not in VALID_GROUPS:
                raise ValueError(f"{path.as_posix()}:{lineno}: unknown group `{group}`")
            current = group
            continue
        if line.startswith("- "):
            if current is None:
                raise ValueError(f"{path.as_posix()}:{lineno}: list item without a group")
            value = line[2:].strip().strip("'").strip('"')
            if not value:
                raise ValueError(f"{path.as_posix()}:{lineno}: empty list item")
            groups[current].append(value)
            continue
        raise ValueError(f"{path.as_posix()}:{lineno}: unsupported syntax `{raw}`")

    for key, values in groups.items():
        if not values:
            raise ValueError(f"{path.as_posix()}: group `{key}` must be non-empty")
    return groups


def _has_wildcards(value: str) -> bool:
    return any(ch in value for ch in "*?[")


def _resolve_entries(root: Path, entries: Iterable[str]) -> tuple[dict[str, Path], list[str]]:
    resolved: dict[str, Path] = {}
    errors: list[str] = []
    for entry in entries:
        if _has_wildcards(entry):
            matches = sorted(p for p in root.glob(entry) if p.is_file())
            if not matches:
                errors.append(f"manifest pattern has no matches: `{entry}`")
                continue
            for match in matches:
                rel = match.relative_to(root).as_posix()
                resolved[rel] = match
            continue

        target = root / entry
        if not target.is_file():
            errors.append(f"manifest path is missing: `{entry}`")
            continue
        resolved[entry] = target
    return resolved, errors


def _section_bounds(lines: list[str], heading: str) -> tuple[int, int] | None:
    start = -1
    for idx, line in enumerate(lines):
        if line.strip() == heading:
            start = idx
            break
    if start < 0:
        return None
    end = len(lines)
    for idx in range(start + 1, len(lines)):
        if lines[idx].startswith("## "):
            end = idx
            break
    return start, end


def _subsection_bounds(lines: list[str], start: int, end: int, heading: str) -> tuple[int, int] | None:
    sub_start = -1
    for idx in range(start + 1, end):
        if lines[idx].strip() == heading:
            sub_start = idx
            break
    if sub_start < 0:
        return None
    sub_end = end
    for idx in range(sub_start + 1, end):
        if lines[idx].startswith("### "):
            sub_end = idx
            break
    return sub_start, sub_end


def _token_line_hits(lines: list[str], token: str) -> list[int]:
    pattern = re.compile(
        rf"(?<!{TOKEN_BOUNDARY}){re.escape(token)}(?!{TOKEN_BOUNDARY})"
    )
    hits: list[int] = []
    for idx, line in enumerate(lines, start=1):
        if pattern.search(line):
            hits.append(idx)
    return hits


def _validate_readme(
    *,
    path: Path,
    docs_heading: str,
    internal_tokens: set[str],
) -> list[str]:
    errors: list[str] = []
    lines = path.read_text(encoding="utf-8").splitlines()

    bounds = _section_bounds(lines, docs_heading)
    if bounds is None:
        return [f"{path.as_posix()}: missing `{docs_heading}` section"]

    section_start, section_end = bounds
    public_bounds = _subsection_bounds(lines, section_start, section_end, "### Public docs")
    if public_bounds is None:
        errors.append(f"{path.as_posix()}: missing `### Public docs` subsection")
        return errors

    internal_bounds = _subsection_bounds(lines, section_start, section_end, "### Internal/Maintainer docs")
    if internal_bounds is None:
        errors.append(f"{path.as_posix()}: missing `### Internal/Maintainer docs` subsection")
        return errors

    public_start, public_end = public_bounds
    internal_start, internal_end = internal_bounds
    if not (public_start < internal_start):
        errors.append(
            f"{path.as_posix()}: expected `### Public docs` before `### Internal/Maintainer docs`"
        )
        return errors

    for token in sorted(internal_tokens):
        hits = _token_line_hits(lines, token)
        if not hits:
            continue
        for lineno in hits:
            if public_start + 1 <= lineno <= public_end:
                errors.append(
                    f"{path.as_posix()}:{lineno}: internal doc `{token}` appears in Public docs"
                )
            if not (internal_start + 1 <= lineno <= internal_end):
                if lineno < internal_start + 1 or lineno > internal_end:
                    errors.append(
                        f"{path.as_posix()}:{lineno}: internal doc `{token}` must be only in Internal/Maintainer docs"
                    )
    return errors


def _validate_internal_markers(paths: dict[str, Path]) -> list[str]:
    errors: list[str] = []
    for rel, full in sorted(paths.items()):
        if full.suffix.lower() != ".md":
            continue
        head = "\n".join(full.read_text(encoding="utf-8").splitlines()[:8])
        if INTERNAL_MARKER not in head:
            errors.append(f"{rel}: missing `{INTERNAL_MARKER}` marker in first lines")
    return errors


def _validate_changelog(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    errors: list[str] = []

    if "## Unreleased" not in lines:
        errors.append(f"{path.as_posix()}: missing `## Unreleased` heading")

    h2 = re.findall(r"^##\s+(.+)$", text, flags=re.MULTILINE)
    if not h2:
        return [f"{path.as_posix()}: no H2 headings found"]
    if h2[0] != "Unreleased":
        errors.append(f"{path.as_posix()}: first H2 heading must be `Unreleased`")
    for heading in h2[1:]:
        if not SEMVER_HEADING_RE.match(heading):
            errors.append(
                f"{path.as_posix()}: invalid release heading `{heading}`; expected `X.Y.Z - YYYY-MM-DD`"
            )

    if re.search(r"^###\s+", text, flags=re.MULTILINE):
        errors.append(f"{path.as_posix()}: minimal semver changelog must not use H3 sections")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate public/internal documentation split for release navigation."
    )
    parser.add_argument("--root", default=".", help="Repository root")
    parser.add_argument(
        "--manifest",
        default="docs/release-docs-manifest.yaml",
        help="Path to release docs manifest (YAML subset)",
    )
    args = parser.parse_args()

    root = Path(args.root).resolve()
    manifest_path = (root / args.manifest).resolve()
    if not manifest_path.is_file():
        print(f"[release-docs-guard] missing manifest: {manifest_path.as_posix()}", file=sys.stderr)
        return 1

    try:
        groups = _parse_manifest(manifest_path)
    except ValueError as exc:
        print(f"[release-docs-guard] {exc}", file=sys.stderr)
        return 1

    public_docs, public_errors = _resolve_entries(root, groups["public_release_docs"])
    runtime_docs, runtime_errors = _resolve_entries(root, groups["runtime_contract_docs"])
    internal_docs, internal_errors = _resolve_entries(root, groups["internal_dev_docs"])

    errors: list[str] = []
    errors.extend(public_errors)
    errors.extend(runtime_errors)
    errors.extend(internal_errors)

    overlap = (set(public_docs) | set(runtime_docs)) & set(internal_docs)
    for path in sorted(overlap):
        errors.append(f"manifest overlap: `{path}` cannot be both public/runtime and internal")

    readme_ru = root / "README.md"
    readme_en = root / "README.en.md"
    if not readme_ru.is_file():
        errors.append("README.md is required")
    if not readme_en.is_file():
        errors.append("README.en.md is required")

    internal_tokens = set(internal_docs.keys())
    if readme_ru.is_file():
        errors.extend(
            _validate_readme(
                path=readme_ru,
                docs_heading="## Документация",
                internal_tokens=internal_tokens,
            )
        )
    if readme_en.is_file():
        errors.extend(
            _validate_readme(
                path=readme_en,
                docs_heading="## Documentation",
                internal_tokens=internal_tokens,
            )
        )

    errors.extend(_validate_internal_markers(internal_docs))

    changelog = root / "CHANGELOG.md"
    if not changelog.is_file():
        errors.append("CHANGELOG.md is required")
    else:
        errors.extend(_validate_changelog(changelog))

    if errors:
        for item in errors:
            print(f"[release-docs-guard] {item}", file=sys.stderr)
        return 1

    print(
        "[release-docs-guard] OK "
        f"(public={len(public_docs)}, runtime={len(runtime_docs)}, internal={len(internal_docs)})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
