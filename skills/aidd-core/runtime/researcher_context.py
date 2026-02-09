#!/usr/bin/env python3
"""Collect and export context for the Researcher agent."""

from __future__ import annotations

import argparse
import ast
import datetime as _dt
import json
import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, Iterator, List, Optional, Sequence, Tuple

from aidd_runtime.feature_ids import resolve_aidd_root, resolve_identifiers


_DEFAULT_CONFIG = Path("config") / "conventions.json"
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
_LANG_SUFFIXES: Dict[str, Tuple[str, ...]] = {
    "py": (".py",),
    "kt": (".kt",),
    "kts": (".kts",),
    "java": (".java",),
}
_DEFAULT_LANGS: Tuple[str, ...] = ("py", "kt", "kts", "java")
_DEFAULT_KEYWORD_MIN_LEN = 3
_DEFAULT_KEYWORD_MAX_COUNT = 25
_DEFAULT_KEYWORD_SHORT_WHITELIST = {"kt", "kts", "js", "ts"}
_DEFAULT_STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "by",
    "for",
    "from",
    "how",
    "if",
    "in",
    "is",
    "it",
    "its",
    "of",
    "on",
    "or",
    "that",
    "the",
    "this",
    "to",
    "we",
    "with",
    "без",
    "в",
    "во",
    "все",
    "для",
    "если",
    "и",
    "или",
    "как",
    "не",
    "на",
    "но",
    "по",
    "при",
    "с",
    "со",
    "то",
    "это",
}
_DEFAULT_IGNORE_DIRS = {
    ".git",
    ".gradle",
    ".idea",
    ".venv",
    "aidd",
    "build",
    "dist",
    "node_modules",
    "out",
    "output",
    "target",
    "vendor",
}

_CAMEL_SPLIT_RE = re.compile(r"([a-z0-9])([A-Z])")
_TOKEN_SPLIT_RE = re.compile(r"[^\w]+", re.UNICODE)
_DOD_RE = re.compile(r"\bdod\s*:\s*(.+)", re.IGNORECASE)


def _utc_timestamp() -> str:
    return _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _normalize_ignore_dirs(values: Any) -> set[str]:
    if not values:
        return set()
    if isinstance(values, (list, tuple, set)):
        items = values
    else:
        items = [values]
    return {str(item).strip().lower() for item in items if str(item).strip()}



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


def _extract_non_negotiables(text: Optional[str]) -> tuple[Optional[str], List[str]]:
    if not text:
        return text, []
    match = _DOD_RE.search(text)
    if not match:
        return text, []
    remainder = text[: match.start()].strip()
    payload = (match.group(1) or "").strip()
    return remainder or None, [payload] if payload else []


def _tokenize_text(value: str) -> List[str]:
    if not value:
        return []
    cleaned = _CAMEL_SPLIT_RE.sub(r"\1 \2", value)
    cleaned = cleaned.replace("_", " ").replace("-", " ").replace("/", " ")
    tokens = [token.strip() for token in _TOKEN_SPLIT_RE.split(cleaned) if token.strip()]
    return tokens


def _normalize_stopwords(raw: Iterable[str]) -> set[str]:
    stopwords: set[str] = set()
    for item in raw:
        token = (str(item) or "").strip().lower()
        if token:
            stopwords.add(token)
    return stopwords


def _normalize_keywords(
    values: Iterable[str],
    *,
    stopwords: set[str],
    min_len: int,
    short_whitelist: set[str],
    max_count: int,
) -> List[str]:
    tokens: List[str] = []
    for raw in values:
        raw_text = (raw or "").strip()
        if not raw_text:
            continue
        for token in _tokenize_text(raw_text):
            lowered = token.lower()
            if not lowered:
                continue
            if lowered in stopwords:
                continue
            if len(lowered) < min_len and lowered not in short_whitelist:
                continue
            tokens.append(lowered)
    tokens = _unique(tokens)
    if max_count > 0 and len(tokens) > max_count:
        tokens = tokens[:max_count]
    return tokens


def _identifier_tokens(ticket: str, slug_hint: Optional[str]) -> List[str]:
    sources = [ticket]
    if slug_hint:
        sources.append(slug_hint)
    tokens: List[str] = []
    for source in sources:
        normalized = (source or "").strip()
        if not normalized:
            continue
        if normalized not in tokens:
            tokens.append(normalized)
        for token in _tokenize_text(normalized):
            lowered = token.strip().lower()
            if lowered and lowered not in tokens:
                tokens.append(lowered)
    return _unique(tokens)


def _norm_token_list(values: Iterable[str]) -> List[str]:
    items: List[str] = []
    for raw in values:
        text = str(raw).strip().lower()
        if text:
            items.append(text)
    return items


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


def _normalize_output_path(root: Path, path: Path) -> Path:
    if path.is_absolute():
        return path
    parts = path.parts
    if parts and parts[0] == ".":
        path = Path(*parts[1:])
        parts = path.parts
    if parts and parts[0] == "aidd" and root.name == "aidd":
        path = Path(*parts[1:])
    return root / path


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
    ticket: str
    slug_hint: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    paths: List[str] = field(default_factory=list)
    paths_discovered: List[str] = field(default_factory=list)
    invalid_paths: List[str] = field(default_factory=list)
    docs: List[str] = field(default_factory=list)
    keywords: List[str] = field(default_factory=list)
    keywords_raw: List[str] = field(default_factory=list)
    non_negotiables: List[str] = field(default_factory=list)
    manual_notes: List[str] = field(default_factory=list)


class ResearcherContextBuilder:
    """Builds file/doc scopes and extracts keyword matches for Researcher."""

    def __init__(
        self,
        root: Path,
        config_path: Optional[Path] = None,
        *,
        paths_relative: Optional[str] = None,
    ) -> None:
        self.root = root.resolve()
        self.workspace_root = self.root.parent if self.root.name == "aidd" else self.root
        base_config = config_path or (_DEFAULT_CONFIG if _DEFAULT_CONFIG.is_absolute() else self.root / _DEFAULT_CONFIG)
        self.config_path = base_config.resolve()
        self._settings = self._load_settings()
        ignore_dirs = _normalize_ignore_dirs(self._settings.get("ignore_dirs"))
        self._ignore_dirs = ignore_dirs or set(_DEFAULT_IGNORE_DIRS)
        default_mode = "workspace" if self.root.name == "aidd" else "aidd"
        config_mode = default_mode
        defaults = self._settings.get("defaults", {})
        if isinstance(defaults, dict) and defaults.get("workspace_relative") is False:
            config_mode = "aidd"
        elif isinstance(defaults, dict) and defaults.get("workspace_relative") is True:
            config_mode = "workspace"
        chosen = (paths_relative or "").strip().lower()
        if chosen in {"workspace", "aidd"}:
            config_mode = chosen
        self._paths_base = self.workspace_root if config_mode == "workspace" else self.root
        self._paths_relative_mode = config_mode

    def _is_ignored_path(self, path: Path, *, base: Optional[Path] = None) -> bool:
        ignore = self._ignore_dirs
        if not ignore:
            return False
        parts: Tuple[str, ...]
        if base:
            try:
                parts = path.relative_to(base).parts
            except ValueError:
                parts = path.parts
        else:
            parts = path.parts
        return any(part.lower() in ignore for part in parts)

    def _is_ignored_root(self, path: Path) -> bool:
        name = path.name.lower()
        if name != "aidd":
            return name in self._ignore_dirs
        return path.resolve() != self.root.resolve()

    @property
    def paths_relative_mode(self) -> str:
        return self._paths_relative_mode

    def _rel_to_base(self, path: Path) -> str:
        for base in (self._paths_base, self.root):
            try:
                return path.relative_to(base).as_posix()
            except ValueError:
                continue
        return path.as_posix()

    def _load_settings(self) -> Dict[str, Any]:
        if not self.config_path.exists():
            return {}
        try:
            raw = json.loads(self.config_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        section = raw.get("researcher", {})
        return section if isinstance(section, dict) else {}

    def _keyword_settings(self) -> Dict[str, Any]:
        settings = self._settings.get("keyword_settings")
        return settings if isinstance(settings, dict) else {}

    def build_scope(self, ticket: str, slug_hint: Optional[str] = None) -> Scope:
        ticket_value = (ticket or "").strip()
        if not ticket_value:
            raise ValueError("ticket must be a non-empty string")
        hint_value = (slug_hint or "").strip() or None
        cleaned_hint, non_negotiables = _extract_non_negotiables(hint_value)
        settings = self._settings
        defaults = settings.get("defaults", {})
        default_paths = defaults.get("paths", ["src"])
        default_docs = defaults.get("docs", ["docs"])
        default_keywords = defaults.get("keywords", [])

        tags = self._resolve_tags(ticket_value, cleaned_hint)
        tag_paths, tag_docs, tag_keywords = self._collect_tag_payload(tags)

        def _norm_all(values: Sequence[str]) -> List[str]:
            return _unique([_normalise_rel(item, self._paths_base) for item in values])

        keyword_settings = self._keyword_settings()
        min_len = int(keyword_settings.get("min_len", _DEFAULT_KEYWORD_MIN_LEN))
        max_count = int(keyword_settings.get("max_count", _DEFAULT_KEYWORD_MAX_COUNT))
        short_whitelist = set(
            _normalize_stopwords(keyword_settings.get("short_whitelist", _DEFAULT_KEYWORD_SHORT_WHITELIST))
        )
        stopwords = set(_DEFAULT_STOPWORDS)
        stopwords.update(_normalize_stopwords(keyword_settings.get("stopwords", [])))

        raw_keywords: List[str] = []
        raw_keywords.extend([item for item in default_keywords if isinstance(item, str)])
        raw_keywords.extend([item for item in tag_keywords if isinstance(item, str)])
        raw_keywords.append(ticket_value)
        if hint_value:
            raw_keywords.append(hint_value)

        normalise_sources: List[str] = []
        normalise_sources.extend([item for item in default_keywords if isinstance(item, str)])
        normalise_sources.extend([item for item in tag_keywords if isinstance(item, str)])
        normalise_sources.append(ticket_value)
        if cleaned_hint:
            normalise_sources.append(cleaned_hint)

        keywords = _normalize_keywords(
            normalise_sources,
            stopwords=stopwords,
            min_len=max(1, min_len),
            short_whitelist=short_whitelist or _DEFAULT_KEYWORD_SHORT_WHITELIST,
            max_count=max_count,
        )

        scope = Scope(
            ticket=ticket_value,
            slug_hint=hint_value,
            tags=tags,
            paths=_norm_all(list(default_paths) + list(tag_paths)),
            docs=_norm_all(list(default_docs) + list(tag_docs)),
            keywords=keywords,
            keywords_raw=_unique([item.strip() for item in raw_keywords if isinstance(item, str) and item.strip()]),
            non_negotiables=non_negotiables,
        )
        scope = self._discover_paths(scope)
        auto_tags = self._auto_detect_tags(scope)
        if auto_tags:
            added_tags = [tag for tag in auto_tags if tag not in scope.tags]
            scope.tags = _unique(scope.tags + auto_tags)
            if added_tags:
                extra_paths, extra_docs, extra_keywords = self._collect_tag_payload(added_tags)
                refresh_paths = False
                if extra_paths:
                    scope.paths = _unique(scope.paths + _norm_all(extra_paths))
                if extra_docs:
                    scope.docs = _unique(scope.docs + _norm_all(extra_docs))
                if extra_keywords:
                    raw_added = [
                        item.strip()
                        for item in extra_keywords
                        if isinstance(item, str) and item.strip()
                    ]
                    if raw_added:
                        scope.keywords_raw = _unique(scope.keywords_raw + raw_added)
                        normalise_sources.extend(raw_added)
                        scope.keywords = _normalize_keywords(
                            normalise_sources,
                            stopwords=stopwords,
                            min_len=max(1, min_len),
                            short_whitelist=short_whitelist or _DEFAULT_KEYWORD_SHORT_WHITELIST,
                            max_count=max_count,
                        )
                        refresh_paths = True
                if refresh_paths:
                    scope = self._discover_paths(scope)
        return scope

    def extend_scope(
        self,
        scope: Scope,
        *,
        extra_paths: Optional[Iterable[str]] = None,
        extra_keywords: Optional[Iterable[str]] = None,
        extra_notes: Optional[Iterable[str]] = None,
    ) -> Scope:
        if extra_paths:
            normalised = []
            for item in extra_paths:
                raw = (item or "").strip()
                if not raw:
                    continue
                path_obj = Path(raw)
                if path_obj.is_absolute():
                    rel = self._rel_to_base(path_obj)
                else:
                    rel = _normalise_rel(raw, self._paths_base)
                normalised.append(rel)
            scope.paths = _unique(scope.paths + normalised)
        if extra_keywords:
            raw_items = [item.strip() for item in extra_keywords if item and item.strip()]
            scope.keywords_raw = _unique(scope.keywords_raw + raw_items)
            keyword_settings = self._keyword_settings()
            min_len = int(keyword_settings.get("min_len", _DEFAULT_KEYWORD_MIN_LEN))
            max_count = int(keyword_settings.get("max_count", _DEFAULT_KEYWORD_MAX_COUNT))
            short_whitelist = set(
                _normalize_stopwords(keyword_settings.get("short_whitelist", _DEFAULT_KEYWORD_SHORT_WHITELIST))
            )
            stopwords = set(_DEFAULT_STOPWORDS)
            stopwords.update(_normalize_stopwords(keyword_settings.get("stopwords", [])))
            scope.keywords = _unique(
                scope.keywords
                + _normalize_keywords(
                    raw_items,
                    stopwords=stopwords,
                    min_len=max(1, min_len),
                    short_whitelist=short_whitelist or _DEFAULT_KEYWORD_SHORT_WHITELIST,
                    max_count=max_count,
                )
            )
        if extra_notes:
            scope.manual_notes = _unique(scope.manual_notes + [note for note in extra_notes if note])
        return scope

    def sync_scope_paths(self, scope: Scope, paths: Iterable[str]) -> Scope:
        normalised: List[str] = []
        for item in paths:
            raw = (item or "").strip()
            if not raw:
                continue
            path_obj = Path(raw)
            if path_obj.is_absolute():
                rel = self._rel_to_base(path_obj)
            else:
                rel = _normalise_rel(raw, self._paths_base)
            normalised.append(rel)
        if not normalised:
            return scope
        scope.paths = _unique(normalised)
        scope.paths_discovered = []
        scope.invalid_paths = []

        base_tags = self._resolve_tags(scope.ticket, scope.slug_hint)
        scope.tags = base_tags
        auto_tags = self._auto_detect_tags(scope, strict_paths=True)
        if auto_tags:
            scope.tags = _unique(scope.tags + auto_tags)

        settings = self._settings
        defaults = settings.get("defaults", {})
        default_docs = defaults.get("docs", ["docs"])
        _, tag_docs, tag_keywords = self._collect_tag_payload(scope.tags)

        def _norm_all(values: Sequence[str]) -> List[str]:
            return _unique([_normalise_rel(item, self._paths_base) for item in values])

        scope.docs = _norm_all(list(default_docs) + list(tag_docs))

        keyword_settings = self._keyword_settings()
        min_len = int(keyword_settings.get("min_len", _DEFAULT_KEYWORD_MIN_LEN))
        max_count = int(keyword_settings.get("max_count", _DEFAULT_KEYWORD_MAX_COUNT))
        short_whitelist = set(
            _normalize_stopwords(keyword_settings.get("short_whitelist", _DEFAULT_KEYWORD_SHORT_WHITELIST))
        )
        stopwords = set(_DEFAULT_STOPWORDS)
        stopwords.update(_normalize_stopwords(keyword_settings.get("stopwords", [])))

        default_keywords = defaults.get("keywords", [])
        hint_value = (scope.slug_hint or "").strip() or None
        cleaned_hint, _ = _extract_non_negotiables(hint_value)
        raw_keywords: List[str] = []
        raw_keywords.extend([item for item in default_keywords if isinstance(item, str)])
        raw_keywords.extend([item for item in tag_keywords if isinstance(item, str)])
        raw_keywords.append(scope.ticket)
        if hint_value:
            raw_keywords.append(hint_value)

        normalise_sources: List[str] = []
        normalise_sources.extend([item for item in default_keywords if isinstance(item, str)])
        normalise_sources.extend([item for item in tag_keywords if isinstance(item, str)])
        normalise_sources.append(scope.ticket)
        if cleaned_hint:
            normalise_sources.append(cleaned_hint)

        scope.keywords = _normalize_keywords(
            normalise_sources,
            stopwords=stopwords,
            min_len=max(1, min_len),
            short_whitelist=short_whitelist or _DEFAULT_KEYWORD_SHORT_WHITELIST,
            max_count=max_count,
        )
        scope.keywords_raw = _unique([item.strip() for item in raw_keywords if isinstance(item, str) and item.strip()])
        return scope

    def _discover_paths(self, scope: Scope) -> Scope:
        settings = self._settings.get("path_discovery", {})
        max_discovered = int(settings.get("max_discovered", 12)) if isinstance(settings, dict) else 12
        keywords = [kw for kw in scope.keywords if kw]
        discovered: List[str] = []
        if keywords:
            discovered.extend(self._discover_paths_from_gradle(keywords, max_discovered=max_discovered))
            if len(discovered) < max_discovered:
                discovered.extend(
                    self._discover_paths_from_keywords(
                        keywords,
                        max_discovered=max_discovered - len(discovered),
                    )
                )
        scope.paths_discovered = _unique(scope.paths_discovered + discovered)
        if scope.paths_discovered:
            scope.paths = _unique(scope.paths + scope.paths_discovered)
        return scope

    def _discover_paths_from_gradle(self, keywords: Sequence[str], *, max_discovered: int) -> List[str]:
        if max_discovered <= 0:
            return []
        modules: List[str] = []
        settings_files = list(self._paths_base.rglob("settings.gradle")) + list(
            self._paths_base.rglob("settings.gradle.kts")
        )
        settings_files = [path for path in settings_files if not self._is_ignored_path(path, base=self._paths_base)]
        include_re = re.compile(r"include\s*\(([^)]*)\)", re.IGNORECASE)
        include_line_re = re.compile(r"^\s*include\s+(.+)$", re.IGNORECASE | re.MULTILINE)
        quoted_re = re.compile(r"['\"]([^'\"]+)['\"]")

        def normalize_module(raw: str) -> str:
            cleaned = raw.strip()
            if not cleaned:
                return ""
            if cleaned.startswith(":"):
                cleaned = cleaned[1:]
            cleaned = cleaned.replace(":", "/").strip("/")
            return cleaned

        def collect_from_chunk(chunk: str) -> None:
            for match in quoted_re.findall(chunk or ""):
                module = normalize_module(match)
                if module:
                    modules.append(module)

        for settings_path in settings_files[:5]:
            try:
                data = settings_path.read_text(encoding="utf-8")
            except OSError:
                continue
            for match in include_re.finditer(data):
                collect_from_chunk(match.group(1))
            for match in include_line_re.finditer(data):
                collect_from_chunk(match.group(1))
        if not modules:
            return []
        matches: List[str] = []
        for module in modules:
            lowered = module.lower()
            if not any(kw in lowered for kw in keywords):
                continue
            candidate = self._paths_base / module
            if candidate.exists():
                matches.append(self._rel_to_base(candidate))
            if len(matches) >= max_discovered:
                break
        return matches

    def _discover_paths_from_keywords(self, keywords: Sequence[str], *, max_discovered: int) -> List[str]:
        if max_discovered <= 0:
            return []
        matches: List[str] = []
        base = self._paths_base
        max_depth = 4
        for root, dirs, _ in os.walk(base):
            dirs[:] = [name for name in dirs if name.lower() not in self._ignore_dirs]
            rel = Path(root).relative_to(base)
            if len(rel.parts) > max_depth:
                dirs[:] = []
                continue
            if self._is_ignored_path(Path(root), base=base):
                dirs[:] = []
                continue
            for name in list(dirs):
                lowered = name.lower()
                if any(kw in lowered for kw in keywords):
                    candidate = Path(root) / name
                    matches.append(self._rel_to_base(candidate))
                    if len(matches) >= max_discovered:
                        return matches
        return matches

    def describe_targets(self, scope: Scope) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Path]]:
        return self._resolve_search_roots(scope)

    def resolve_path_roots(self, scope: Scope) -> List[Path]:
        roots: List[Path] = []
        for rel in scope.paths:
            _, path_obj = self._describe_path(rel)
            if path_obj is not None:
                roots.append(path_obj)
        return roots

    def _resolve_search_roots(self, scope: Scope) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Path]]:
        search_roots: List[Path] = []
        path_infos: List[Dict[str, Any]] = []
        invalid_paths: List[str] = []
        for rel in scope.paths:
            info, path_obj = self._describe_path(rel)
            path_infos.append(info)
            if path_obj is not None:
                search_roots.append(path_obj)
            if not info.get("exists", False):
                invalid_paths.append(info.get("path") or rel)

        if scope.paths_discovered:
            valid_paths = [info.get("path") for info in path_infos if info.get("exists")]
            scope.paths = _unique([path for path in valid_paths if path])
            path_infos = [info for info in path_infos if info.get("exists")]

        doc_infos, doc_roots = self._describe_docs(scope.docs)
        search_roots.extend(doc_roots)
        scope.invalid_paths = _unique(invalid_paths)
        return path_infos, doc_infos, search_roots

    def write_targets(self, scope: Scope) -> Path:
        from aidd_runtime import researcher_context_pack as _pack

        return _pack.write_targets(self, scope)

    def write_rlm_targets(
        self,
        ticket: str,
        *,
        targets_mode: str | None = None,
        rlm_paths: list[str] | None = None,
    ) -> Path:
        from aidd_runtime import rlm_targets
        from aidd_runtime.rlm_config import load_rlm_settings

        settings = load_rlm_settings(self.root)
        payload = rlm_targets.build_targets(
            self.root,
            ticket,
            settings=settings,
            targets_mode=targets_mode,
            paths_override=rlm_paths,
            base_root=self._paths_base,
        )
        report_dir = self.root / _REPORT_DIR
        report_dir.mkdir(parents=True, exist_ok=True)
        target_path = report_dir / f"{ticket}-rlm-targets.json"
        target_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        return target_path

    def collect_context(self, scope: Scope, *, limit: int = _MAX_MATCHES) -> Dict[str, Any]:
        from aidd_runtime import researcher_context_pack as _pack

        return _pack.collect_context(self, scope, limit=limit)

    def write_context(self, scope: Scope, context: Dict[str, Any], *, output: Optional[Path] = None) -> Path:
        from aidd_runtime import researcher_context_pack as _pack

        return _pack.write_context(self, scope, context, output=output)

    def _describe_path(self, rel: str) -> Tuple[Dict[str, Any], Optional[Path]]:
        raw_path = Path(rel)
        if raw_path.is_absolute():
            abs_path = raw_path
        else:
            abs_path = (self._paths_base / raw_path).resolve()
            if not abs_path.exists() and self._paths_base != self.root:
                alt_path = (self.root / raw_path).resolve()
                if alt_path.exists():
                    abs_path = alt_path
        rel_path = self._rel_to_base(abs_path)
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
            else:
                abs_path = (self._paths_base / raw_path).resolve()
                if not abs_path.exists() and self._paths_base != self.root:
                    alt_path = (self.root / raw_path).resolve()
                    if alt_path.exists():
                        abs_path = alt_path
            rel_path = self._rel_to_base(abs_path)
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
                    rel_doc = self._rel_to_base(doc)
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
            samples.append(self._rel_to_base(path))
            if len(samples) >= limit:
                break
        return samples

    def _build_project_profile(self, scope: Scope, matches: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
        from aidd_runtime import researcher_context_pack as _pack

        return _pack.build_project_profile(self, scope, matches)

    def _detect_src_layers(self, limit: int = 8) -> List[str]:
        from aidd_runtime import researcher_context_pack as _pack

        return _pack.detect_src_layers(self, limit=limit)

    def _detect_tests(self) -> Tuple[bool, List[str], List[str]]:
        from aidd_runtime import researcher_context_pack as _pack

        return _pack.detect_tests(self)

    def _is_excluded_test_path(self, path: Path) -> bool:
        from aidd_runtime import researcher_context_pack as _pack

        return _pack.is_excluded_test_path(self, path)

    def _detect_configs(self) -> bool:
        from aidd_runtime import researcher_context_pack as _pack

        return _pack.detect_configs(self)

    def _detect_logging_artifacts(self, limit: int = 5) -> List[str]:
        from aidd_runtime import researcher_context_pack as _pack

        return _pack.detect_logging_artifacts(self, limit=limit)

    def _baseline_recommendations(self, profile: Dict[str, Any], scope: Scope) -> List[str]:
        from aidd_runtime import researcher_context_pack as _pack

        return _pack.baseline_recommendations(self, profile, scope)

    def _resolve_tags(self, ticket: str, slug_hint: Optional[str]) -> List[str]:
        settings = self._settings
        features = settings.get("features", {})
        tags: List[str] = []
        for key in (ticket, slug_hint):
            if not key:
                continue
            config_tags = features.get(key, [])
            tags.extend(tag for tag in config_tags if isinstance(tag, str))
        if tags:
            return _unique(tags)
        available_tags = settings.get("tags", {})
        tokens = _identifier_tokens(ticket, slug_hint)
        for token in tokens:
            lowered = token.lower()
            if lowered in available_tags and lowered not in tags:
                tags.append(lowered)
        return _unique(tags)

    def _collect_tag_payload(self, tags: Sequence[str]) -> Tuple[List[str], List[str], List[str]]:
        settings = self._settings
        tags_config = settings.get("tags", {})
        tag_paths: List[str] = []
        tag_docs: List[str] = []
        tag_keywords: List[str] = []
        for tag in tags:
            info = tags_config.get(tag, {})
            if not isinstance(info, dict):
                continue
            tag_paths.extend([item for item in info.get("paths", []) if isinstance(item, str)])
            tag_docs.extend([item for item in info.get("docs", []) if isinstance(item, str)])
            tag_keywords.extend([item for item in info.get("keywords", []) if isinstance(item, str)])
        return tag_paths, tag_docs, tag_keywords

    def _auto_detect_tags(self, scope: Scope, *, strict_paths: bool = False) -> List[str]:
        settings = self._settings
        auto_cfg = settings.get("auto_tags", {})
        if not isinstance(auto_cfg, dict):
            return []
        slug_text = " ".join(item for item in [scope.ticket, scope.slug_hint] if item).lower()
        token_set = set(_norm_token_list(_identifier_tokens(scope.ticket, scope.slug_hint)))
        path_candidates = [item for item in (scope.paths + scope.paths_discovered) if item]
        detected: List[str] = []
        for tag, raw in auto_cfg.items():
            if tag in scope.tags or not isinstance(raw, dict):
                continue
            keywords = _norm_token_list(raw.get("slug_keywords") or raw.get("keywords") or [])
            if keywords:
                if any(keyword in token_set for keyword in keywords) or any(keyword in slug_text for keyword in keywords):
                    detected.append(tag)
                    continue
            markers = raw.get("path_markers") or raw.get("paths") or []
            if isinstance(markers, str):
                markers = [markers]
            for marker in markers:
                marker_text = str(marker).strip()
                if not marker_text:
                    continue
                marker_path = Path(marker_text)
                if not marker_path.is_absolute():
                    marker_path = self._paths_base / marker_text
                if (not strict_paths and marker_path.exists()) or any(
                    marker_text in candidate for candidate in path_candidates
                ):
                    detected.append(tag)
                    break
        return _unique(detected)

    def _scan_matches(
        self,
        roots: Sequence[Path],
        keywords: Sequence[str],
        *,
        limit: int = _MAX_MATCHES,
    ) -> List[Dict[str, Any]]:
        from aidd_runtime import researcher_context_read as _read

        return _read.scan_matches(self, roots, keywords, limit=limit)

    def _iter_files(self, root: Path) -> Iterator[Path]:
        from aidd_runtime import researcher_context_read as _read

        yield from _read.iter_files(self, root)

    def collect_deep_context(
        self,
        scope: Scope,
        *,
        roots: Sequence[Path],
        keywords: Sequence[str],
        languages: Sequence[str],
        reuse_only: bool = False,
        limit: int = _MAX_MATCHES,
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        from aidd_runtime import researcher_context_read as _read

        return _read.collect_deep_context(
            self,
            scope,
            roots=roots,
            keywords=keywords,
            languages=languages,
            reuse_only=reuse_only,
            limit=limit,
        )

    def _collect_code_index(self, roots: Sequence[Path], allowed_langs: set[str]) -> List[Dict[str, Any]]:
        from aidd_runtime import researcher_context_read as _read

        return _read.collect_code_index(self, roots, allowed_langs)

    def _iter_code_files(self, root: Path, allowed_langs: set[str]) -> Iterator[Path]:
        from aidd_runtime import researcher_context_read as _read

        yield from _read.iter_code_files(self, root, allowed_langs)

    def _summarise_code_file(self, path: Path, lang: str) -> Optional[Dict[str, Any]]:
        from aidd_runtime import researcher_context_read as _read

        return _read.summarise_code_file(self, path, lang)

    def _score_reuse_candidates(
        self, code_index: Sequence[Dict[str, Any]], keywords: Sequence[str], *, limit: int = _MAX_MATCHES
    ) -> List[Dict[str, Any]]:
        from aidd_runtime import researcher_context_read as _read

        return _read.score_reuse_candidates(self, code_index, keywords, limit=limit)


def _parse_paths(value: Optional[str]) -> List[str]:
    if not value:
        return []
    items = []
    for chunk in re.split(r"[,:]", value):
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


def _parse_notes(values: Optional[Iterable[str]], root: Path) -> List[str]:
    if not values:
        return []
    notes: List[str] = []
    stdin_payload: Optional[str] = None
    for raw in values:
        value = (raw or "").strip()
        if not value:
            continue
        if value == "-":
            if stdin_payload is None:
                stdin_payload = sys.stdin.read()
            payload = (stdin_payload or "").strip()
            if payload:
                notes.append(payload)
            continue
        if value.startswith("@"):
            note_path = Path(value[1:])
            if not note_path.is_absolute():
                note_path = (root / note_path).resolve()
            try:
                payload = note_path.read_text(encoding="utf-8").strip()
            except (OSError, UnicodeDecodeError):
                continue
            if payload:
                notes.append(payload)
            continue
        notes.append(value)
    return notes


def _language_for_path(path: Path) -> Optional[str]:
    suffix = path.suffix.lower()
    for lang, suffixes in _LANG_SUFFIXES.items():
        if suffix in suffixes:
            return lang
    return None


def _parse_langs(value: Optional[str]) -> List[str]:
    if not value:
        return []
    langs: List[str] = []
    for chunk in value.split(","):
        token = chunk.strip().lower()
        if token and token not in langs:
            langs.append(token)
    return langs


def _is_test_path(path: Path) -> bool:
    lowered = [part.lower() for part in path.parts]
    return any("test" in part for part in lowered)


def _extract_python_summary(data: str) -> Tuple[List[str], List[Dict[str, Any]]]:
    imports: List[str] = []
    symbols: List[Dict[str, Any]] = []
    try:
        tree = ast.parse(data)
    except SyntaxError:
        return imports, symbols
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            name = ""
            if isinstance(node, ast.Import):
                name = ", ".join(alias.name for alias in node.names)
            else:
                module = node.module or ""
                name = module if not node.names else f"{module}: " + ", ".join(alias.name for alias in node.names)
            if name:
                imports.append(name)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            signature_parts = [arg.arg for arg in node.args.args]
            signature = f"({', '.join(signature_parts)})"
            symbols.append({"name": node.name, "kind": "function", "line": node.lineno, "signature": signature})
        elif isinstance(node, ast.ClassDef):
            bases = [getattr(base, "id", "") or getattr(base, "attr", "") for base in node.bases]
            base_sig = f" extends {', '.join([b for b in bases if b])}" if bases else ""
            symbols.append({"name": node.name, "kind": "class", "line": node.lineno, "signature": base_sig})
    return imports[:20], symbols[:30]


_GENERIC_CLASS_RE = re.compile(r"\b(class|interface|object)\s+([A-Za-z_][\w<>]*)")
_GENERIC_FUNC_RE = re.compile(r"\bfun\s+([A-Za-z_][\w<>]*)\s*\(([^)]*)\)|\b(?:public|protected|private)?\s*(?:static\s+)?(?:[\w<>]+)\s+([A-Za-z_]\w*)\s*\(([^)]*)\)")


def _extract_generic_summary(data: str, lang: str) -> Tuple[List[str], List[Dict[str, Any]]]:
    imports: List[str] = []
    symbols: List[Dict[str, Any]] = []
    for line in data.splitlines():
        stripped = line.strip()
        if stripped.startswith("import "):
            imports.append(stripped.replace("import ", "").strip())
    for match in _GENERIC_CLASS_RE.finditer(data):
        name = match.group(2)
        symbols.append({"name": name, "kind": "class", "line": _line_for_index(data, match.start())})
    for match in _GENERIC_FUNC_RE.finditer(data):
        func_name = match.group(1) or match.group(3)
        params = match.group(2) or match.group(4) or ""
        symbols.append(
            {
                "name": func_name,
                "kind": "function",
                "line": _line_for_index(data, match.start()),
                "signature": f"({params})",
            }
        )
    return imports[:20], symbols[:30]


def _line_for_index(data: str, index: int) -> int:
    return data.count("\n", 0, index) + 1


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Prepare context for the Researcher agent.")
    parser.add_argument("--config", help="Path to conventions JSON with researcher section.")
    parser.add_argument(
        "--ticket",
        "--slug",
        dest="ticket",
        help="Ticket identifier to analyse (defaults to docs/.active.json).",
    )
    parser.add_argument(
        "--slug-hint",
        dest="slug_hint",
        help="Optional slug hint override used for templates and keywords.",
    )
    parser.add_argument("--paths", help="Colon-separated list of additional paths to scan.")
    parser.add_argument("--keywords", help="Comma-separated list of extra keywords.")
    parser.add_argument(
        "--note",
        dest="notes",
        action="append",
        help="Free-form note or @path to include in the context; use '-' to read stdin once.",
    )
    parser.add_argument("--limit", type=int, default=_MAX_MATCHES, help="Maximum number of code/document matches to capture.")
    parser.add_argument(
        "--output",
        help="Override output path for context JSON (default: aidd/reports/research/<ticket>-context.json).",
    )
    parser.add_argument(
        "--pack-only",
        action="store_true",
        help="Remove JSON report after writing pack sidecar.",
    )
    parser.add_argument("--targets-only", action="store_true", help="Only refresh targets JSON, skip scanning sources.")
    parser.add_argument("--dry-run", action="store_true", help="Run without writing files; prints context JSON to stdout.")
    parser.add_argument(
        "--deep-code",
        action="store_true",
        help="Collect code symbols/imports/tests alongside keyword matches.",
    )
    parser.add_argument("--reuse-only", action="store_true", help="Skip keyword matches and focus on reuse candidates.")
    parser.add_argument("--langs", help="Comma-separated list of languages to scan (py,kt,kts,java).")
    parser.add_argument(
        "--auto",
        action="store_true",
        help="Automation-friendly mode for /feature-dev-aidd:idea-new integrations (prints warnings on empty matches).",
    )
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    root = resolve_aidd_root(Path.cwd())
    if not root.exists():
        parser.error(f"project root does not exist: {root}")

    identifiers = resolve_identifiers(root, ticket=args.ticket, slug_hint=args.slug_hint)
    ticket = identifiers.resolved_ticket
    if not ticket:
        parser.error("feature ticket is required (--ticket) or set docs/.active.json first.")

    config_path = Path(args.config).resolve() if args.config else None
    builder = ResearcherContextBuilder(root, config_path=config_path)
    scope = builder.build_scope(ticket, slug_hint=identifiers.slug_hint)
    scope = builder.extend_scope(
        scope,
        extra_paths=_parse_paths(args.paths),
        extra_keywords=_parse_keywords(args.keywords),
        extra_notes=_parse_notes(args.notes, root),
    )
    _, _, search_roots = builder.describe_targets(scope)

    targets_path = builder.write_targets(scope)
    rel_targets = targets_path.relative_to(root).as_posix()
    print(f"[researcher] targets saved to {rel_targets} ({len(scope.paths)} paths, {len(scope.docs)} docs).")

    if args.targets_only:
        return 0

    languages = _parse_langs(args.langs)
    deep_code_enabled = bool(args.deep_code)
    if args.auto:
        auto_profile = "deep-scan" if deep_code_enabled else "fast-scan"
        auto_reason = "explicit --deep-code" if deep_code_enabled else "no --deep-code"
        print(f"[researcher] auto profile: {auto_profile} ({auto_reason}).")

    context = builder.collect_context(scope, limit=args.limit)
    if deep_code_enabled:
        code_index, reuse_candidates = builder.collect_deep_context(
            scope,
            roots=search_roots,
            keywords=scope.keywords,
            languages=languages or _DEFAULT_LANGS,
            reuse_only=args.reuse_only,
            limit=args.limit,
        )
        context["code_index"] = code_index
        context["reuse_candidates"] = reuse_candidates
        context["deep_mode"] = True
    else:
        context["deep_mode"] = False
    context["auto_mode"] = bool(args.auto)
    match_count = len(context["matches"])
    if match_count == 0:
        print(f"[researcher] WARN: 0 matches for {ticket} → сузить paths/keywords.", file=sys.stderr)
    if args.dry_run:
        print(json.dumps(context, indent=2, ensure_ascii=False))
        return 0

    output_override = Path(args.output) if args.output else None
    output_path = builder.write_context(scope, context, output=output_override)
    rel_output = output_path.relative_to(root).as_posix()
    pack_path = None
    try:
        from aidd_runtime import reports_pack as _reports_pack

        pack_path = _reports_pack.write_research_context_pack(output_path, root=root)
        try:
            rel_pack = pack_path.relative_to(root).as_posix()
        except ValueError:
            rel_pack = pack_path.as_posix()
        print(f"[researcher] pack saved to {rel_pack}.")
    except Exception as exc:
        print(f"[researcher] WARN: failed to generate pack: {exc}", file=sys.stderr)
    message = f"[researcher] context saved to {rel_output} ({match_count} matches"
    if deep_code_enabled:
        reuse_count = len(context.get("reuse_candidates") or [])
        message += f", {reuse_count} reuse candidates"
    message += ")."
    print(message)
    pack_only = bool(getattr(args, "pack_only", False) or os.getenv("AIDD_PACK_ONLY", "").strip() == "1")
    if pack_only and pack_path and pack_path.exists():
        try:
            output_path.unlink()
        except OSError:
            pass
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
