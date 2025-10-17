#!/usr/bin/env python3
"""Collect and export context for the Researcher agent."""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, Iterator, List, Optional, Sequence, Tuple


_DEFAULT_CONFIG = Path("config") / "conventions.json"
_ACTIVE_FEATURE_FILE = Path("docs") / ".active_feature"
_REPORT_DIR = Path("reports") / "research"
_ALLOWED_SUFFIXES = {
    ".kt",
    ".kts",
    ".java",
    ".py",
    ".md",
    ".rst",
    ".yml",
    ".yaml",
    ".json",
}
_MAX_MATCHES = 24
_MAX_FILE_BYTES = 512 * 1024


def _unique(items: Iterable[str]) -> List[str]:
    seen: set[str] = set()
    result: List[str] = []
    for raw in items:
        item = (raw or "").strip()
        if not item or item in seen:
            continue
        seen.add(item)
        result.append(item)
    return result


def _slug_tokens(slug: str) -> List[str]:
    separators = ("-", "_", " ", "/")
    tokens = [slug]
    value = slug
    for sep in separators:
        value = value.replace(sep, " ")
    for token in value.split():
        token = token.strip().lower()
        if token and token not in tokens:
            tokens.append(token)
    return _unique(tokens)


def _normalise_rel(path: str, root: Optional[Path] = None) -> str:
    candidate = Path(path.strip())
    if not candidate.is_absolute():
        return candidate.as_posix().lstrip("./")
    if root is None:
        return candidate.as_posix()
    try:
        return candidate.relative_to(root).as_posix()
    except ValueError:
        return candidate.as_posix()


def _read_text_sample(path: Path) -> Optional[str]:
    try:
        data = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None
    lines = data.splitlines()
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("#"):
            return stripped.lstrip("# ").strip()
    return None


def _extract_status(path: Path) -> Optional[str]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError):
        return None
    for line in lines:
        if line.lower().startswith("status:"):
            return line.split(":", 1)[1].strip()
    return None


@dataclass
class Scope:
    slug: str
    tags: List[str] = field(default_factory=list)
    paths: List[str] = field(default_factory=list)
    docs: List[str] = field(default_factory=list)
    keywords: List[str] = field(default_factory=list)


class ResearcherContextBuilder:
    """Builds file/doc scopes and extracts keyword matches for Researcher."""

    def __init__(self, root: Path, config_path: Optional[Path] = None) -> None:
        self.root = root.resolve()
        base_config = config_path or (_DEFAULT_CONFIG if _DEFAULT_CONFIG.is_absolute() else self.root / _DEFAULT_CONFIG)
        self.config_path = base_config.resolve()
        self._settings = self._load_settings()

    def _load_settings(self) -> Dict[str, Any]:
        if not self.config_path.exists():
            return {}
        try:
            raw = json.loads(self.config_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        section = raw.get("researcher", {})
        return section if isinstance(section, dict) else {}

    def build_scope(self, slug: str) -> Scope:
        settings = self._settings
        defaults = settings.get("defaults", {})
        default_paths = defaults.get("paths", ["src"])
        default_docs = defaults.get("docs", ["docs"])
        default_keywords = defaults.get("keywords", [])

        tags = self._resolve_tags(slug)
        tag_paths: List[str] = []
        tag_docs: List[str] = []
        tag_keywords: List[str] = []
        tags_config = settings.get("tags", {})
        for tag in tags:
            info = tags_config.get(tag, {})
            tag_paths.extend(info.get("paths", []))
            tag_docs.extend(info.get("docs", []))
            tag_keywords.extend(info.get("keywords", []))

        def _norm_all(values: Sequence[str]) -> List[str]:
            return _unique([_normalise_rel(item, self.root) for item in values])

        scope = Scope(
            slug=slug,
            tags=tags,
            paths=_norm_all(list(default_paths) + list(tag_paths)),
            docs=_norm_all(list(default_docs) + list(tag_docs)),
            keywords=_unique(default_keywords + tag_keywords + _slug_tokens(slug)),
        )
        return scope

    def extend_scope(
        self,
        scope: Scope,
        *,
        extra_paths: Optional[Iterable[str]] = None,
        extra_keywords: Optional[Iterable[str]] = None,
    ) -> Scope:
        if extra_paths:
            normalised = []
            for item in extra_paths:
                raw = (item or "").strip()
                if not raw:
                    continue
                path_obj = Path(raw)
                if path_obj.is_absolute():
                    try:
                        rel = path_obj.relative_to(self.root).as_posix()
                    except ValueError:
                        rel = path_obj.as_posix()
                else:
                    rel = _normalise_rel(raw, self.root)
                normalised.append(rel)
            scope.paths = _unique(scope.paths + normalised)
        if extra_keywords:
            scope.keywords = _unique(scope.keywords + [item.strip().lower() for item in extra_keywords])
        return scope

    def write_targets(self, scope: Scope) -> Path:
        report_dir = self.root / _REPORT_DIR
        report_dir.mkdir(parents=True, exist_ok=True)
        payload = {
            "slug": scope.slug,
            "generated_at": _dt.datetime.utcnow().isoformat(timespec="seconds") + "Z",
            "config_source": os.path.relpath(self.config_path, self.root) if self.config_path.exists() else None,
            "tags": scope.tags,
            "paths": scope.paths,
            "docs": scope.docs,
            "keywords": scope.keywords,
        }
        target_path = report_dir / f"{scope.slug}-targets.json"
        target_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        return target_path

    def collect_context(self, scope: Scope, *, limit: int = _MAX_MATCHES) -> Dict[str, Any]:
        search_roots: List[Path] = []
        path_infos: List[Dict[str, Any]] = []
        for rel in scope.paths:
            info, path_obj = self._describe_path(rel)
            path_infos.append(info)
            if path_obj is not None:
                search_roots.append(path_obj)

        doc_infos, doc_roots = self._describe_docs(scope.docs)
        search_roots.extend(doc_roots)

        matches = self._scan_matches(search_roots, scope.keywords, limit=limit)

        return {
            "slug": scope.slug,
            "generated_at": _dt.datetime.utcnow().isoformat(timespec="seconds") + "Z",
            "config_source": os.path.relpath(self.config_path, self.root) if self.config_path.exists() else None,
            "tags": scope.tags,
            "keywords": scope.keywords,
            "paths": path_infos,
            "docs": doc_infos,
            "matches": matches,
        }

    def write_context(self, scope: Scope, context: Dict[str, Any], *, output: Optional[Path] = None) -> Path:
        report_dir = self.root / _REPORT_DIR
        report_dir.mkdir(parents=True, exist_ok=True)
        target_path = output or (report_dir / f"{scope.slug}-context.json")
        if not target_path.is_absolute():
            target_path = self.root / target_path
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_text(json.dumps(context, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        return target_path

    def _describe_path(self, rel: str) -> Tuple[Dict[str, Any], Optional[Path]]:
        raw_path = Path(rel)
        if raw_path.is_absolute():
            abs_path = raw_path
            try:
                rel_path = abs_path.relative_to(self.root).as_posix()
            except ValueError:
                rel_path = abs_path.as_posix()
        else:
            rel_path = raw_path.as_posix().lstrip("./")
            abs_path = (self.root / raw_path).resolve()
        info: Dict[str, Any] = {
            "path": rel_path,
            "exists": abs_path.exists(),
            "type": "directory" if abs_path.is_dir() else ("file" if abs_path.is_file() else "missing"),
        }
        search_root: Optional[Path] = None
        if abs_path.exists():
            search_root = abs_path
            if abs_path.is_dir():
                info["sample"] = self._sample_files(abs_path)
            else:
                info["sample"] = [rel_path]
        return info, search_root

    def _describe_docs(self, docs: Sequence[str]) -> Tuple[List[Dict[str, Any]], List[Path]]:
        infos: List[Dict[str, Any]] = []
        roots: List[Path] = []
        for raw in docs:
            raw_path = Path(raw)
            if raw_path.is_absolute():
                abs_path = raw_path
                try:
                    rel_path = abs_path.relative_to(self.root).as_posix()
                except ValueError:
                    rel_path = abs_path.as_posix()
            else:
                rel_path = raw_path.as_posix().lstrip("./")
                abs_path = (self.root / raw_path).resolve()
            if abs_path.is_dir():
                doc_files = sorted(p for p in abs_path.glob("*.md"))
                if not doc_files:
                    infos.append(
                        {
                            "path": rel_path,
                            "exists": abs_path.exists(),
                            "type": "directory",
                            "sample": [],
                        }
                    )
                    continue
                for doc in doc_files:
                    rel_doc = doc.relative_to(self.root).as_posix()
                    info = {
                        "path": rel_doc,
                        "exists": True,
                        "type": "file",
                        "title": _read_text_sample(doc),
                        "status": _extract_status(doc),
                    }
                    infos.append(info)
                    roots.append(doc)
            else:
                info = {
                    "path": rel_path,
                    "exists": abs_path.exists(),
                    "type": "file" if abs_path.exists() else "missing",
                }
                if abs_path.exists():
                    info["title"] = _read_text_sample(abs_path)
                    info["status"] = _extract_status(abs_path)
                    roots.append(abs_path)
                infos.append(info)
        return infos, roots

    def _sample_files(self, directory: Path, limit: int = 6) -> List[str]:
        samples: List[str] = []
        try:
            iterator = (p for p in sorted(directory.rglob("*")) if p.is_file())
        except OSError:
            return samples
        for path in iterator:
            samples.append(path.relative_to(self.root).as_posix())
            if len(samples) >= limit:
                break
        return samples

    def _resolve_tags(self, slug: str) -> List[str]:
        settings = self._settings
        features = settings.get("features", {})
        tags_from_config = features.get(slug, [])
        tags = [tag for tag in tags_from_config if isinstance(tag, str)]
        if tags:
            return _unique(tags)
        available_tags = settings.get("tags", {})
        tokens = _slug_tokens(slug)
        for token in tokens:
            lowered = token.lower()
            if lowered in available_tags and lowered not in tags:
                tags.append(lowered)
        return _unique(tags)

    def _scan_matches(
        self,
        roots: Sequence[Path],
        keywords: Sequence[str],
        *,
        limit: int = _MAX_MATCHES,
    ) -> List[Dict[str, Any]]:
        matches: List[Dict[str, Any]] = []
        seen: set[Tuple[str, str, int]] = set()
        tokens = [kw.strip().lower() for kw in keywords if kw]
        if not tokens:
            return matches

        for root in roots:
            if root.is_dir():
                iterator = self._iter_files(root)
            else:
                iterator = iter([root])
            for file_path in iterator:
                rel = file_path.relative_to(self.root).as_posix()
                try:
                    data = file_path.read_text(encoding="utf-8")
                except (OSError, UnicodeDecodeError):
                    continue
                if len(data.encode("utf-8")) > _MAX_FILE_BYTES:
                    continue
                lowered = data.lower()
                lines = data.splitlines()
                for token in tokens:
                    idx = lowered.find(token)
                    if idx == -1:
                        continue
                    line_num = lowered[:idx].count("\n")
                    snippet = "\n".join(lines[max(0, line_num - 1) : min(len(lines), line_num + 2)])
                    key = (rel, token, line_num)
                    if key in seen:
                        continue
                    matches.append(
                        {
                            "token": token,
                            "file": rel,
                            "line": line_num + 1,
                            "snippet": snippet,
                        }
                    )
                    seen.add(key)
                    if len(matches) >= limit:
                        return matches
        return matches

    def _iter_files(self, root: Path) -> Iterator[Path]:
        try:
            for path in root.rglob("*"):
                if path.is_file() and path.suffix.lower() in _ALLOWED_SUFFIXES:
                    yield path
        except OSError:
            return iter(())


def _parse_paths(value: Optional[str]) -> List[str]:
    if not value:
        return []
    items = []
    for chunk in value.split(":"):
        chunk = chunk.strip()
        if not chunk:
            continue
        items.append(chunk)
    return items


def _parse_keywords(value: Optional[str]) -> List[str]:
    if not value:
        return []
    items = []
    for chunk in value.split(","):
        token = chunk.strip().lower()
        if token:
            items.append(token)
    return items


def _read_active_slug(root: Path) -> Optional[str]:
    slug_path = root / _ACTIVE_FEATURE_FILE
    if not slug_path.exists():
        return None
    return slug_path.read_text(encoding="utf-8").strip() or None


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Prepare context for the Researcher agent.")
    parser.add_argument("--target", default=".", help="Project root (default: current directory).")
    parser.add_argument("--config", help="Path to conventions JSON with researcher section.")
    parser.add_argument("--slug", "--feature", dest="slug", help="Feature slug to analyse (defaults to active feature).")
    parser.add_argument("--paths", help="Colon-separated list of additional paths to scan.")
    parser.add_argument("--keywords", help="Comma-separated list of extra keywords.")
    parser.add_argument("--limit", type=int, default=_MAX_MATCHES, help="Maximum number of code/document matches to capture.")
    parser.add_argument("--output", help="Override output path for context JSON (default: reports/research/<slug>-context.json).")
    parser.add_argument("--targets-only", action="store_true", help="Only refresh targets JSON, skip scanning sources.")
    parser.add_argument("--dry-run", action="store_true", help="Run without writing files; prints context JSON to stdout.")
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    root = Path(args.target).resolve()
    if not root.exists():
        parser.error(f"target directory does not exist: {root}")

    slug = args.slug or _read_active_slug(root)
    if not slug:
        parser.error("feature slug is required (--slug) or set docs/.active_feature first.")

    config_path = Path(args.config).resolve() if args.config else None
    builder = ResearcherContextBuilder(root, config_path=config_path)
    scope = builder.build_scope(slug)
    scope = builder.extend_scope(
        scope,
        extra_paths=_parse_paths(args.paths),
        extra_keywords=_parse_keywords(args.keywords),
    )

    targets_path = builder.write_targets(scope)
    rel_targets = targets_path.relative_to(root).as_posix()
    print(f"[researcher] targets saved to {rel_targets} ({len(scope.paths)} paths, {len(scope.docs)} docs).")

    if args.targets_only:
        return 0

    context = builder.collect_context(scope, limit=args.limit)
    if args.dry_run:
        print(json.dumps(context, indent=2, ensure_ascii=False))
        return 0

    output_path = builder.write_context(scope, context, output=Path(args.output) if args.output else None)
    rel_output = output_path.relative_to(root).as_posix()
    print(f"[researcher] context saved to {rel_output} ({len(context['matches'])} matches).")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
