#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Iterable

SEMVER_RE = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")
TAG_RE = re.compile(r"^v(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")


def _as_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path.as_posix()}: expected top-level JSON object")
    return payload


def _iter_errors(root: Path, tag: str | None) -> Iterable[str]:
    plugin_path = root / ".claude-plugin" / "plugin.json"
    marketplace_path = root / ".claude-plugin" / "marketplace.json"
    changelog_path = root / "CHANGELOG.md"

    if not plugin_path.exists():
        yield f"missing manifest: {plugin_path.as_posix()}"
        return
    if not marketplace_path.exists():
        yield f"missing manifest: {marketplace_path.as_posix()}"
        return

    try:
        plugin_payload = _load_json(plugin_path)
    except Exception as exc:  # pragma: no cover - defensive
        yield f"failed to parse {plugin_path.as_posix()}: {exc}"
        return
    try:
        marketplace_payload = _load_json(marketplace_path)
    except Exception as exc:  # pragma: no cover - defensive
        yield f"failed to parse {marketplace_path.as_posix()}: {exc}"
        return

    plugin_name = _as_text(plugin_payload.get("name"))
    plugin_version = _as_text(plugin_payload.get("version"))
    if not plugin_name:
        yield f"{plugin_path.as_posix()}: `name` is required"
    if not SEMVER_RE.match(plugin_version):
        yield f"{plugin_path.as_posix()}: `version` must match X.Y.Z (got `{plugin_version}`)"

    entries = marketplace_payload.get("plugins")
    if not isinstance(entries, list) or not entries:
        yield f"{marketplace_path.as_posix()}: `plugins` must be a non-empty array"
        return

    plugin_entry: dict[str, Any] | None = None
    for item in entries:
        if not isinstance(item, dict):
            continue
        if _as_text(item.get("name")) == plugin_name:
            plugin_entry = item
            break
    if plugin_entry is None:
        yield (
            f"{marketplace_path.as_posix()}: plugin `{plugin_name}` is missing in `plugins[]`"
        )
        return

    market_version = _as_text(plugin_entry.get("version"))
    source = plugin_entry.get("source")
    source_ref = ""
    if isinstance(source, dict):
        source_ref = _as_text(source.get("ref"))

    if not SEMVER_RE.match(market_version):
        yield (
            f"{marketplace_path.as_posix()}: plugin `version` must match X.Y.Z "
            f"(got `{market_version}`)"
        )
    if plugin_version and market_version and plugin_version != market_version:
        yield (
            f"version mismatch: plugin.json={plugin_version}, "
            f"marketplace.json={market_version}"
        )

    if not TAG_RE.match(source_ref):
        yield (
            f"{marketplace_path.as_posix()}: `source.ref` must be immutable tag vX.Y.Z "
            f"(got `{source_ref}`)"
        )
    expected_ref = f"v{plugin_version}" if plugin_version else ""
    if source_ref and expected_ref and source_ref != expected_ref:
        yield (
            f"release ref mismatch: expected `{expected_ref}` from plugin version, "
            f"got `{source_ref}`"
        )

    if tag:
        normalized = tag.strip()
        if normalized.startswith("refs/tags/"):
            normalized = normalized.removeprefix("refs/tags/")
        if not TAG_RE.match(normalized):
            yield f"tag must match vX.Y.Z (got `{tag}`)"
        if expected_ref and normalized != expected_ref:
            yield (
                f"tag mismatch: tag `{normalized}` does not match manifest version "
                f"`{plugin_version}`"
            )
        if not changelog_path.exists():
            yield f"missing changelog: {changelog_path.as_posix()}"
        else:
            text = changelog_path.read_text(encoding="utf-8")
            heading_re = re.compile(
                rf"^##\s+{re.escape(plugin_version)}(?:\s+-|\s*$)",
                re.MULTILINE,
            )
            if not heading_re.search(text):
                yield (
                    f"{changelog_path.as_posix()}: missing release heading for "
                    f"`{plugin_version}`"
                )


def _infer_tag() -> str | None:
    if os.getenv("GITHUB_REF_TYPE") == "tag":
        return _as_text(os.getenv("GITHUB_REF_NAME") or os.getenv("GITHUB_REF"))
    github_ref = _as_text(os.getenv("GITHUB_REF"))
    if github_ref.startswith("refs/tags/"):
        return github_ref
    return None


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate release parity for plugin manifests and tag/changelog."
    )
    parser.add_argument("--root", default=".", help="Repository root path.")
    parser.add_argument(
        "--tag",
        default=None,
        help="Release tag (vX.Y.Z). If omitted, inferred from GitHub tag env when available.",
    )
    args = parser.parse_args()

    root = Path(args.root).resolve()
    tag = args.tag if args.tag is not None else _infer_tag()
    errors = list(_iter_errors(root=root, tag=tag))
    if errors:
        for err in errors:
            print(f"[release-guard] {err}", file=sys.stderr)
        return 1

    if tag:
        normalized = tag.removeprefix("refs/tags/")
        print(f"[release-guard] OK (tag={normalized})")
    else:
        print("[release-guard] OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
