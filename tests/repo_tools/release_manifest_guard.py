#!/usr/bin/env python3
"""Release and manifest governance guard."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path


SEMVER_RE = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")
TAG_RE = re.compile(r"^v(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")


def _load_json(path: Path) -> dict:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"[release-manifest-guard] invalid JSON {path}: {exc}", file=sys.stderr)
        raise SystemExit(2)
    if not isinstance(payload, dict):
        print(f"[release-manifest-guard] JSON root must be object: {path}", file=sys.stderr)
        raise SystemExit(2)
    return payload


def _as_str(value: object) -> str:
    return str(value).strip() if value is not None else ""


def _should_check_remote_tags() -> bool:
    return _as_str(os.getenv("GITHUB_ACTIONS", "")).lower() == "true" or _as_str(
        os.getenv("AIDD_RELEASE_CHECK_REMOTE_TAG", "")
    ) == "1"


def _remote_tag_exists(root: Path, tag: str) -> tuple[bool, str]:
    try:
        result = subprocess.run(
            ["git", "ls-remote", "--exit-code", "--tags", "origin", f"refs/tags/{tag}"],
            cwd=root,
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError as exc:
        return False, str(exc)
    details = (result.stderr or result.stdout or "").strip()
    return result.returncode == 0, details


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate manifest parity and release/tag governance.")
    parser.add_argument("--root", default=".", help="Repository root")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    plugin_path = root / ".claude-plugin" / "plugin.json"
    marketplace_path = root / ".claude-plugin" / "marketplace.json"

    plugin = _load_json(plugin_path)
    marketplace = _load_json(marketplace_path)

    errors: list[str] = []
    marketplace_refs: set[str] = set()

    plugin_version = _as_str(plugin.get("version"))
    if not SEMVER_RE.match(plugin_version):
        errors.append(f"plugin version must be semver (MAJOR.MINOR.PATCH), got {plugin_version!r}")

    plugins = marketplace.get("plugins")
    if not isinstance(plugins, list) or not plugins:
        errors.append("marketplace plugins[] must be non-empty")
        plugins = []

    marketplace_versions: set[str] = set()
    for idx, item in enumerate(plugins):
        if not isinstance(item, dict):
            errors.append(f"plugins[{idx}] must be object")
            continue
        version = _as_str(item.get("version"))
        ref = _as_str((item.get("source") or {}).get("ref") if isinstance(item.get("source"), dict) else "")
        if version:
            marketplace_versions.add(version)
            if not SEMVER_RE.match(version):
                errors.append(f"plugins[{idx}].version must be semver, got {version!r}")
        else:
            errors.append(f"plugins[{idx}].version is required")

        if not ref:
            errors.append(f"plugins[{idx}].source.ref is required")
        elif not TAG_RE.match(ref):
            errors.append(
                f"plugins[{idx}].source.ref must be semver tag (vX.Y.Z) for stable channel; got {ref!r}"
            )
        else:
            marketplace_refs.add(ref)

    if plugin_version and marketplace_versions and len(marketplace_versions) == 1:
        only = next(iter(marketplace_versions))
        if only != plugin_version:
            errors.append(f"version mismatch: plugin.json={plugin_version}, marketplace={only}")
    elif len(marketplace_versions) > 1:
        errors.append(f"multiple marketplace versions found: {sorted(marketplace_versions)}")

    github_ref = _as_str(os.getenv("GITHUB_REF", ""))
    github_ref_name = _as_str(os.getenv("GITHUB_REF_NAME", ""))
    tag_name = github_ref_name if TAG_RE.match(github_ref_name) else ""
    if not tag_name and github_ref.startswith("refs/tags/"):
        candidate = github_ref.rsplit("/", 1)[-1]
        if TAG_RE.match(candidate):
            tag_name = candidate

    if tag_name:
        tag_version = tag_name[1:]
        if plugin_version != tag_version:
            errors.append(
                f"release tag/version mismatch: tag={tag_name}, plugin.json version={plugin_version}"
            )
        for idx, item in enumerate(plugins):
            if not isinstance(item, dict):
                continue
            source = item.get("source") if isinstance(item.get("source"), dict) else {}
            ref = _as_str(source.get("ref") if isinstance(source, dict) else "")
            if ref != tag_name:
                errors.append(
                    f"release tag build requires plugins[{idx}].source.ref == {tag_name!r}, got {ref!r}"
                )
    if not errors and _should_check_remote_tags():
        for ref in sorted(marketplace_refs):
            exists, details = _remote_tag_exists(root, ref)
            if not exists:
                suffix = f": {details}" if details else ""
                errors.append(f"marketplace source.ref tag {ref!r} not found on origin{suffix}")

    if errors:
        for error in errors:
            print(f"[release-manifest-guard] {error}", file=sys.stderr)
        return 2

    print("[release-manifest-guard] OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
