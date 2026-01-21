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

from tools.feature_ids import resolve_identifiers, resolve_project_root


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
_CALLGRAPH_LANGS = {"kt", "kts", "java"}
_DEFAULT_GRAPH_LIMIT = 300
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
_GRAPH_MODES = {"auto", "focus", "full"}
_INSTALL_HINT = "INSTALL_HINT: python3 -m pip install tree_sitter_language_pack"

_CAMEL_SPLIT_RE = re.compile(r"([a-z0-9])([A-Z])")
_TOKEN_SPLIT_RE = re.compile(r"[^\w]+", re.UNICODE)
_DOD_RE = re.compile(r"\bdod\s*:\s*(.+)", re.IGNORECASE)


def _utc_timestamp() -> str:
    return _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


_CALL_GRAPH_FULL_COLS: Tuple[str, ...] = (
    "caller",
    "callee",
    "file",
    "line",
    "language",
    "caller_raw",
)
_TRIM_WARNING_RE = re.compile(r"(?:^|\s)call graph trimmed to \d+ edges\.?")


def _columnar_call_graph(edges: List[Dict[str, Any]], imports: List[Dict[str, Any]]) -> Dict[str, Any]:
    cols = list(_CALL_GRAPH_FULL_COLS)
    rows = [
        [
            edge.get("caller"),
            edge.get("callee"),
            edge.get("file"),
            edge.get("line"),
            edge.get("language"),
            edge.get("caller_raw"),
        ]
        for edge in edges
    ]
    return {
        "schema": "aidd.call-graph.v1",
        "generated_at": _utc_timestamp(),
        "cols": cols,
        "rows": rows,
        "imports": imports,
    }


def _select_graph_edges(
    graph: Dict[str, Any],
    graph_mode: str,
    graph_limit: int,
) -> Tuple[List[Dict[str, Any]], str]:
    edges_full = graph.get("edges_full")
    if edges_full is None:
        edges_full = graph.get("edges") or []
    edges_focus = graph.get("edges") or []
    if graph_mode == "full":
        return list(edges_full), "full"
    if graph_mode == "focus":
        return list(edges_focus), "focus"
    if len(edges_full) <= graph_limit:
        return list(edges_full), "full"
    return list(edges_focus), "focus"


def _strip_trim_warning(warning: str) -> str:
    if not warning:
        return ""
    cleaned = _TRIM_WARNING_RE.sub("", warning)
    cleaned = re.sub(r"\s{2,}", " ", cleaned)
    return cleaned.strip()


def _emit_call_graph_warning(prefix: str, warning: Optional[str]) -> None:
    if not warning:
        return
    if "tree-sitter" not in warning.lower():
        return
    print(f"{prefix} {_INSTALL_HINT}", file=sys.stderr)
    print(f"{prefix} WARN: {warning}", file=sys.stderr)


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

    def call_graph_settings(self) -> Dict[str, Any]:
        settings = self._settings.get("call_graph")
        return settings if isinstance(settings, dict) else {}

    def ast_grep_settings(self) -> Dict[str, Any]:
        settings = self._settings.get("ast_grep")
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
            rel = Path(root).relative_to(base)
            if len(rel.parts) > max_depth:
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

        doc_infos, doc_roots = self._describe_docs(scope.docs)
        search_roots.extend(doc_roots)
        scope.invalid_paths = _unique(invalid_paths)
        return path_infos, doc_infos, search_roots

    def write_targets(self, scope: Scope) -> Path:
        report_dir = self.root / _REPORT_DIR
        report_dir.mkdir(parents=True, exist_ok=True)
        payload = {
            "ticket": scope.ticket,
            "slug": scope.slug_hint or scope.ticket,
            "slug_hint": scope.slug_hint,
            "generated_at": _utc_timestamp(),
            "config_source": os.path.relpath(self.config_path, self.root) if self.config_path.exists() else None,
            "tags": scope.tags,
            "paths": scope.paths,
            "paths_discovered": scope.paths_discovered,
            "invalid_paths": scope.invalid_paths,
            "docs": scope.docs,
            "keywords": scope.keywords,
            "keywords_raw": scope.keywords_raw,
            "non_negotiables": scope.non_negotiables,
        }
        target_path = report_dir / f"{scope.ticket}-targets.json"
        target_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        return target_path

    def collect_context(self, scope: Scope, *, limit: int = _MAX_MATCHES) -> Dict[str, Any]:
        path_infos, doc_infos, search_roots = self._resolve_search_roots(scope)
        matches = self._scan_matches(search_roots, scope.keywords, limit=limit)
        code_index: List[Dict[str, Any]] = []
        reuse_candidates: List[Dict[str, Any]] = []
        profile = self._build_project_profile(scope, matches)

        return {
            "ticket": scope.ticket,
            "slug": scope.slug_hint or scope.ticket,
            "slug_hint": scope.slug_hint,
            "generated_at": _utc_timestamp(),
            "config_source": os.path.relpath(self.config_path, self.root) if self.config_path.exists() else None,
            "tags": scope.tags,
            "keywords": scope.keywords,
            "keywords_raw": scope.keywords_raw,
            "paths": path_infos,
            "paths_discovered": scope.paths_discovered,
            "invalid_paths": scope.invalid_paths,
            "docs": doc_infos,
            "matches": matches,
            "code_index": code_index,
            "reuse_candidates": reuse_candidates,
            "profile": profile,
            "manual_notes": scope.manual_notes,
            "non_negotiables": scope.non_negotiables,
        }

    def write_context(self, scope: Scope, context: Dict[str, Any], *, output: Optional[Path] = None) -> Path:
        report_dir = self.root / _REPORT_DIR
        report_dir.mkdir(parents=True, exist_ok=True)
        target_path = output or (report_dir / f"{scope.ticket}-context.json")
        target_path = _normalize_output_path(self.root, target_path)
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_text(json.dumps(context, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        return target_path

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
        tests_detected, tests_evidence, suggested_test_tasks = self._detect_tests()
        profile = {
            "is_new_project": len(matches) == 0,
            "src_layers": self._detect_src_layers(),
            "tests_detected": tests_detected,
            "tests_evidence": tests_evidence,
            "suggested_test_tasks": suggested_test_tasks,
            "config_detected": self._detect_configs(),
            "logging_artifacts": self._detect_logging_artifacts(),
            "recommendations": [],
        }
        profile["recommendations"] = self._baseline_recommendations(profile, scope)
        return profile

    def _detect_src_layers(self, limit: int = 8) -> List[str]:
        candidates = [self._paths_base / "src"]
        if self._paths_base != self.root:
            candidates.append(self.root / "src")
        src_dir = next((candidate for candidate in candidates if candidate.exists()), None)
        if not src_dir:
            return []
        layers: List[str] = []
        for child in sorted(src_dir.iterdir()):
            if not child.is_dir():
                continue
            layers.append(self._rel_to_base(child))
            if len(layers) >= limit:
                break
        return layers

    def _detect_tests(self) -> Tuple[bool, List[str], List[str]]:
        evidence: List[str] = []
        suggested_tasks: List[str] = []
        patterns = [
            "**/src/test",
            "**/src/tests",
            "**/test",
            "**/tests",
            "**/spec",
            "**/specs",
            "**/__tests__",
        ]
        roots = [self._paths_base]
        if self._paths_base != self.root:
            roots.append(self.root)
        for root in roots:
            if not root.exists():
                continue
            for pattern in patterns:
                try:
                    iterator = root.glob(pattern)
                except OSError:
                    continue
                for candidate in iterator:
                    if not candidate.exists():
                        continue
                    if self._is_excluded_test_path(candidate):
                        continue
                    evidence.append(self._rel_to_base(candidate))
                    if len(evidence) >= 12:
                        break
                if len(evidence) >= 12:
                    break
            if len(evidence) >= 12:
                break

        try:
            from tools.test_settings_defaults import detect_build_tools

            build_tools = detect_build_tools(self._paths_base if self._paths_base.exists() else self.root)
        except Exception:
            build_tools = set()
        if "gradle" in build_tools:
            suggested_tasks.append("./gradlew test")
        if "npm" in build_tools:
            suggested_tasks.append("npm test")
        if "python" in build_tools:
            suggested_tasks.append("pytest")
        if "go" in build_tools:
            suggested_tasks.append("go test ./...")
        if "rust" in build_tools:
            suggested_tasks.append("cargo test")
        if "dotnet" in build_tools:
            suggested_tasks.append("dotnet test")

        return bool(evidence), _unique(evidence), _unique(suggested_tasks)

    def _is_excluded_test_path(self, path: Path) -> bool:
        excluded_roots = {
            "docs",
            "reports",
            ".cache",
            ".git",
            "aidd",
            "node_modules",
            ".venv",
            "venv",
            "vendor",
            "dist",
            "build",
            "out",
            "target",
        }
        for base in (self._paths_base, self.root):
            try:
                rel = path.relative_to(base)
                parts = rel.parts
                if not parts:
                    return False
                if parts[0] in excluded_roots:
                    return True
                return False
            except ValueError:
                continue
        return False

    def _detect_configs(self) -> bool:
        candidates = [
            self._paths_base / "config",
            self._paths_base / "configs",
            self._paths_base / "settings",
            self._paths_base / "src" / "main" / "resources",
        ]
        if self._paths_base != self.root:
            candidates.extend(
                [
                    self.root / "config",
                    self.root / "configs",
                    self.root / "settings",
                    self.root / "src" / "main" / "resources",
                ]
            )
        for candidate in candidates:
            if candidate.exists():
                return True
        return False

    def _detect_logging_artifacts(self, limit: int = 5) -> List[str]:
        tokens = ("logback", "logging", "logger", "log4j")
        candidates: List[str] = []
        search_roots = [
            self._paths_base / "config",
            self._paths_base / "configs",
            self._paths_base / "src",
        ]
        if self._paths_base != self.root:
            search_roots.extend(
                [
                    self.root / "config",
                    self.root / "configs",
                    self.root / "src",
                ]
            )
        for root in search_roots:
            if not root.exists():
                continue
            try:
                iterator = root.rglob("*")
            except OSError:
                continue
            for path in iterator:
                if len(candidates) >= limit:
                    break
                if not path.is_file():
                    continue
                lowered = path.name.lower()
                if any(token in lowered for token in tokens):
                    candidates.append(self._rel_to_base(path))
            if len(candidates) >= limit:
                break
        return candidates

    def _baseline_recommendations(self, profile: Dict[str, Any], scope: Scope) -> List[str]:
        recommendations: List[str] = []
        defaults = self._settings.get("defaults", {})
        default_paths = [item for item in defaults.get("paths", []) if isinstance(item, str) and item.strip()]
        default_docs = [item for item in defaults.get("docs", []) if isinstance(item, str) and item.strip()]
        default_keywords = [item for item in defaults.get("keywords", []) if isinstance(item, str) and item.strip()]

        if profile["is_new_project"] and default_paths:
            recommendations.append(
                "Создайте базовые директории для разработки: " + ", ".join(default_paths)
            )
        if profile["is_new_project"] and default_docs:
            recommendations.append(
                "Подготовьте документацию по умолчанию: " + ", ".join(default_docs)
            )
        if profile["is_new_project"] and default_keywords:
            recommendations.append(
                "Добавьте ключевые термины в код/доки: " + ", ".join(default_keywords[:5])
            )
        if not profile["tests_detected"]:
            recommendations.append("Добавьте tests/ или src/test для smoke-покрытия.")
        if not profile["config_detected"]:
            recommendations.append("Создайте config/ или settings/ с базовыми конфигурациями.")
        if not profile["logging_artifacts"]:
            recommendations.append("Настройте логирование (logback/logging.yaml) для наблюдаемости.")

        if scope.manual_notes:
            recommendations.append("Проверьте ручные заметки исследователя и перенесите их в отчёт.")

        return _unique(recommendations)

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

    def _auto_detect_tags(self, scope: Scope) -> List[str]:
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
                if marker_path.exists() or any(marker_text in candidate for candidate in path_candidates):
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
                rel = self._rel_to_base(file_path)
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

    def _iter_callgraph_files(self, roots: Sequence[Path], languages: Sequence[str]) -> List[Path]:
        exts: set[str] = set()
        for lang in languages:
            exts.update(_LANG_SUFFIXES.get(lang, ()))
        files: List[Path] = []
        for root in roots:
            iterator: Iterable[Path]
            if root.is_dir():
                iterator = root.rglob("*")
            else:
                iterator = [root]
            for path in iterator:
                if not path.is_file():
                    continue
                if path.suffix.lower() not in exts:
                    continue
                files.append(path)
        return files

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
        allowed_langs = {lang.lower() for lang in (languages or _DEFAULT_LANGS)}
        code_index = self._collect_code_index(roots, allowed_langs)
        reuse_candidates = self._score_reuse_candidates(code_index, keywords, limit=limit)
        if reuse_only:
            return [], reuse_candidates
        return code_index, reuse_candidates

    def collect_call_graph(
        self,
        scope: Scope,
        *,
        roots: Sequence[Path],
        languages: Sequence[str],
        engine_name: str = "auto",
        engine: Optional["_CallGraphEngine"] = None,
        graph_filter: Optional[str] = None,
        graph_limit: int = _DEFAULT_GRAPH_LIMIT,
    ) -> Dict[str, Any]:
        callgraph_langs = [lang for lang in languages if lang in _CALLGRAPH_LANGS]
        files = self._iter_callgraph_files(roots, callgraph_langs)
        base: Dict[str, Any] = {
            "engine": engine_name,
            "supported_languages": [],
            "edges": [],
            "imports": [],
            "edges_full": [],
        }
        if not files or not callgraph_langs:
            base["warning"] = "call graph disabled or no supported files"
            return base
        if engine_name == "none":
            base["warning"] = "call graph disabled (graph-engine none)"
            return base

        selected_engine = engine or _load_callgraph_engine(engine_name)
        if selected_engine is None:
            base["warning"] = "call graph engine not available"
            return base
        result = selected_engine.build(files) or {}
        result.setdefault("engine", selected_engine.name)
        result.setdefault("supported_languages", list(selected_engine.supported_languages))
        edges = result.get("edges") or []
        imports = result.get("imports") or []

        focus_filter = graph_filter or ""
        trimmed_edges = edges
        trimmed = False
        if focus_filter:
            try:
                regex = re.compile(focus_filter, re.IGNORECASE)
                trimmed_edges = [
                    edge
                    for edge in edges
                    if regex.search(edge.get("file", ""))
                    or regex.search(str(edge.get("caller", "")))
                    or regex.search(str(edge.get("callee", "")))
                ]
            except re.error:
                trimmed_edges = edges
        if graph_limit and len(trimmed_edges) > graph_limit:
            trimmed_edges = trimmed_edges[:graph_limit]
            trimmed = True

        result["edges_full"] = edges
        result["edges"] = trimmed_edges
        result["imports"] = imports
        if trimmed:
            warning = (result.get("warning") or "").strip()
            suffix = f"call graph trimmed to {graph_limit} edges."
            result["warning"] = f"{warning} {suffix}".strip()
        return result

    def _collect_code_index(self, roots: Sequence[Path], allowed_langs: set[str]) -> List[Dict[str, Any]]:
        index: List[Dict[str, Any]] = []
        for root in roots:
            iterator: Iterable[Path]
            if root.is_dir():
                iterator = self._iter_code_files(root, allowed_langs)
            else:
                iterator = [root]
            for path in iterator:
                lang = _language_for_path(path)
                if not lang or lang not in allowed_langs:
                    continue
                summary = self._summarise_code_file(path, lang)
                if summary:
                    index.append(summary)
        return index

    def _iter_code_files(self, root: Path, allowed_langs: set[str]) -> Iterator[Path]:
        try:
            for path in root.rglob("*"):
                if not path.is_file():
                    continue
                lang = _language_for_path(path)
                if not lang or lang not in allowed_langs:
                    continue
                yield path
        except OSError:
            return iter(())

    def _summarise_code_file(self, path: Path, lang: str) -> Optional[Dict[str, Any]]:
        try:
            data = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            return None
        if len(data.encode("utf-8")) > _MAX_FILE_BYTES:
            return None

        imports: List[str] = []
        symbols: List[Dict[str, Any]] = []
        if lang == "py":
            imports, symbols = _extract_python_summary(data)
        else:
            imports, symbols = _extract_generic_summary(data, lang)

        has_tests = _is_test_path(path)
        rel_path = self._rel_to_base(path)
        return {
            "path": rel_path,
            "language": lang,
            "imports": imports,
            "symbols": symbols,
            "has_tests": has_tests,
        }

    def _score_reuse_candidates(
        self, code_index: Sequence[Dict[str, Any]], keywords: Sequence[str], *, limit: int = _MAX_MATCHES
    ) -> List[Dict[str, Any]]:
        tokens = [kw.strip().lower() for kw in keywords if kw]
        if not tokens:
            tokens = []
        candidates: List[Dict[str, Any]] = []
        for entry in code_index:
            path = entry.get("path", "")
            language = entry.get("language", "")
            has_tests = bool(entry.get("has_tests"))
            symbols = entry.get("symbols") or []
            imports = entry.get("imports") or []
            symbol_tokens = [s.get("name", "") for s in symbols]
            score = 0
            lower_path = path.lower()
            for token in tokens:
                if token in lower_path:
                    score += 2
                if any(token in (sym or "").lower() for sym in symbol_tokens):
                    score += 3
                if any(token in (imp or "").lower() for imp in imports):
                    score += 1
            if has_tests:
                score += 1
            if score == 0 and tokens:
                continue
            candidates.append(
                {
                    "path": path,
                    "language": language,
                    "score": score,
                    "has_tests": has_tests,
                    "top_symbols": symbol_tokens[:3],
                    "imports": imports[:5],
                }
            )
        candidates.sort(key=lambda item: item.get("score", 0), reverse=True)
        return candidates[:limit]


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


def _parse_graph_filter(value: Optional[str], fallback: str) -> str:
    if value is None or not value.strip():
        return fallback
    return value.strip()


def _parse_graph_engine(value: Optional[str]) -> str:
    if not value:
        return "auto"
    normalized = value.strip().lower()
    if normalized not in {"auto", "none", "ts"}:
        return "auto"
    return normalized


def _parse_graph_mode(value: Optional[str]) -> str:
    if not value:
        return "auto"
    normalized = value.strip().lower()
    if normalized not in _GRAPH_MODES:
        return "auto"
    return normalized


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


class _CallGraphEngine:
    name: str
    supported_languages: set[str]
    supported_extensions: set[str]

    def build(self, files: Sequence[Path]) -> Dict[str, Any]:  # pragma: no cover - interface
        raise NotImplementedError


class _TreeSitterEngine(_CallGraphEngine):
    def __init__(self) -> None:
        self.name = "tree-sitter"
        self.supported_languages = {"java", "kt", "kts"}
        self.supported_extensions = {".java", ".kt", ".kts"}
        self._parser_loader = None
        self._load_error: Optional[str] = None
        try:
            from tree_sitter_language_pack import get_parser  # type: ignore

            self._parser_loader = get_parser
        except Exception as exc:  # pragma: no cover - optional dependency
            self._load_error = f"tree-sitter not available: {exc}"

    def _parser_for_suffix(self, suffix: str):
        if not self._parser_loader:
            return None
        if suffix == ".java":
            return self._parser_loader("java")
        if suffix in {".kt", ".kts"}:
            try:
                return self._parser_loader("kotlin")
            except Exception:
                return None
        return None

    def build(self, files: Sequence[Path]) -> Dict[str, Any]:
        if self._load_error or not self._parser_loader:
            return {"edges": [], "imports": [], "warning": self._load_error or "tree-sitter unavailable"}

        edges: List[Dict[str, Any]] = []
        imports: List[Dict[str, Any]] = []
        for path in files:
            suffix = path.suffix.lower()
            parser = self._parser_for_suffix(suffix)
            if parser is None:
                continue
            try:
                source = path.read_bytes()
            except OSError:
                continue
            try:
                tree = parser.parse(source)
            except Exception:
                continue
            imports.extend(self._ts_imports(path, source))
            edges.extend(self._ts_edges(path, source, tree))
        return {"edges": edges, "imports": imports}

    def _ts_imports(self, path: Path, source: bytes) -> List[Dict[str, Any]]:
        # simple text-based import extraction to avoid grammar coupling
        lines = source.decode("utf-8", errors="ignore").splitlines()
        collected: List[Dict[str, Any]] = []
        imports: List[str] = []
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("import "):
                imports.append(stripped.replace("import ", "", 1).strip("; ").strip())
        if imports:
            collected.append({"file": path.as_posix(), "imports": imports})
        return collected

    def _ts_edges(self, path: Path, source: bytes, tree: Any) -> List[Dict[str, Any]]:
        text = source.decode("utf-8", errors="ignore")
        edges: List[Dict[str, Any]] = []
        package = ""
        for line in text.splitlines():
            stripped = line.strip()
            if stripped.startswith("package "):
                package = stripped.replace("package", "", 1).strip().strip(";")
                break

        def node_text(node: Any) -> str:
            return text[node.start_byte : node.end_byte]

        callers: List[Dict[str, Any]] = []

        def walk(node: Any, parents: List[Any]) -> None:
            node_type = getattr(node, "type", "")
            if node_type in {"class_declaration", "object_declaration", "class_body", "interface_declaration"}:
                # record container scope
                name = ""
                for child in node.children:
                    if child.type in {"identifier", "type_identifier", "simple_identifier"}:
                        name = node_text(child).strip()
                        break
                container_fqn = ".".join(filter(None, [package, name])) if name else package
                callers.append({"container": name, "fqn": container_fqn})
            if node_type in {
                "method_declaration",
                "constructor_declaration",
                "function_declaration",
            }:
                name = ""
                for child in node.children:
                    if child.type in {"identifier", "simple_identifier"}:
                        name = node_text(child).strip()
                        break
                caller_id = name or "<anonymous>"
                container_fqn = None
                for parent in reversed(callers):
                    if "fqn" in parent and parent["fqn"]:
                        container_fqn = parent["fqn"]
                        break
                caller_fqn = ".".join(filter(None, [container_fqn or package, caller_id]))
                callers.append({"id": caller_id, "name": caller_id, "fqn": caller_fqn})
            if node_type in {"method_invocation", "call_expression"}:
                callee = ""
                for child in node.children:
                    if child.type in {"identifier", "simple_identifier"}:
                        callee = node_text(child).strip()
                        break
                caller = None
                for parent in reversed(callers):
                    if "id" in parent:
                        caller = parent
                        break
                edges.append(
                    {
                        "caller": (caller.get("fqn") or caller.get("id")) if caller else None,
                        "caller_raw": caller.get("id") if caller else None,
                        "callee": callee or None,
                        "file": path.as_posix(),
                        "line": getattr(node, "start_point", (0, 0))[0] + 1,
                        "language": "java" if path.suffix.lower() == ".java" else "kotlin",
                    }
                )
            for child in getattr(node, "children", []):
                walk(child, parents + [node])
            # pop scopes when leaving node
            if node_type in {
                "method_declaration",
                "constructor_declaration",
                "function_declaration",
                "class_declaration",
                "object_declaration",
                "interface_declaration",
                "class_body",
            }:
                if callers:
                    callers.pop()

        walk(tree.root_node, [])
        return edges


def _load_callgraph_engine(engine_name: str) -> Optional[_CallGraphEngine]:
    if engine_name == "none":
        return None
    if engine_name in {"auto", "ts"}:
        engine = _TreeSitterEngine()
        return engine
    return None


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Prepare context for the Researcher agent.")
    parser.add_argument("--config", help="Path to conventions JSON with researcher section.")
    parser.add_argument(
        "--ticket",
        "--slug",
        dest="ticket",
        help="Ticket identifier to analyse (defaults to docs/.active_ticket or legacy .active_feature).",
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
        help="Collect code symbols/imports/tests alongside keyword matches (enables call graph unless --graph-engine none).",
    )
    parser.add_argument("--reuse-only", action="store_true", help="Skip keyword matches and focus on reuse candidates.")
    parser.add_argument("--langs", help="Comma-separated list of languages to scan (py,kt,kts,java).")
    parser.add_argument(
        "--call-graph",
        action="store_true",
        help=(
            "Build call/import graph for supported languages. Deprecated: graph is built automatically in deep-code "
            "unless --graph-engine none; use --graph-mode to control focus/full."
        ),
    )
    parser.add_argument(
        "--graph-engine",
        choices=["auto", "none", "ts"],
        default="auto",
        help="Engine for call graph: auto (tree-sitter when available), none (disable), ts (force tree-sitter).",
    )
    parser.add_argument(
        "--graph-langs",
        help="Comma-separated list of languages for call graph (supports kt,kts,java; others ignored).",
    )
    parser.add_argument(
        "--graph-filter",
        help="Regex to keep only matching call graph edges (matches file/caller/callee). Defaults to ticket/keywords.",
    )
    parser.add_argument(
        "--graph-limit",
        type=int,
        default=_DEFAULT_GRAPH_LIMIT,
        help=f"Maximum number of call graph edges to keep in focused graph (default: {_DEFAULT_GRAPH_LIMIT}).",
    )
    parser.add_argument(
        "--graph-mode",
        choices=["auto", "focus", "full"],
        default="auto",
        help="Graph selection for context: auto (full if small), focus (filter+limit), full (no filter/limit).",
    )
    parser.add_argument(
        "--auto",
        action="store_true",
        help="Automation-friendly mode for /feature-dev-aidd:idea-new integrations (prints warnings on empty matches).",
    )
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    root = resolve_project_root(Path.cwd())
    if not root.exists():
        parser.error(f"project root does not exist: {root}")

    identifiers = resolve_identifiers(root, ticket=args.ticket, slug_hint=args.slug_hint)
    ticket = identifiers.resolved_ticket
    if not ticket:
        parser.error("feature ticket is required (--ticket) or set docs/.active_ticket first.")

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
    graph_languages = _parse_langs(getattr(args, "graph_langs", None))
    graph_engine = _parse_graph_engine(getattr(args, "graph_engine", None))
    graph_mode = _parse_graph_mode(getattr(args, "graph_mode", None))
    auto_filter = "|".join(_unique(scope.keywords + [scope.ticket]))
    graph_filter = _parse_graph_filter(getattr(args, "graph_filter", None), fallback=auto_filter)
    raw_limit = getattr(args, "graph_limit", _DEFAULT_GRAPH_LIMIT)
    try:
        graph_limit = int(raw_limit)
    except (TypeError, ValueError):
        graph_limit = _DEFAULT_GRAPH_LIMIT
    if graph_limit <= 0:
        graph_limit = _DEFAULT_GRAPH_LIMIT

    deep_code_enabled = bool(args.deep_code)
    call_graph_requested = bool(args.call_graph)
    if args.auto:
        if deep_code_enabled or call_graph_requested:
            auto_profile = "graph-scan"
            auto_reason = "explicit flags"
        else:
            callgraph_files = builder._iter_callgraph_files(search_roots, list(_CALLGRAPH_LANGS))
            if callgraph_files:
                auto_profile = "graph-scan"
                auto_reason = "kt/kts/java detected"
                deep_code_enabled = True
                call_graph_requested = True
            else:
                auto_profile = "fast-scan"
                auto_reason = "no kt/kts/java detected"
                deep_code_enabled = False
                call_graph_requested = False
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
    graph_enabled = graph_engine != "none"
    should_build_graph = graph_enabled and (call_graph_requested or deep_code_enabled)
    context["call_graph"] = []
    context["import_graph"] = []
    context["call_graph_engine"] = graph_engine
    context["call_graph_supported_languages"] = []
    context["call_graph_filter"] = graph_filter
    context["call_graph_limit"] = graph_limit
    context["call_graph_warning"] = ""
    if should_build_graph:
        graph = builder.collect_call_graph(
            scope,
            roots=search_roots,
            languages=graph_languages or languages or list(_CALLGRAPH_LANGS),
            engine_name=graph_engine,
            graph_filter=graph_filter,
            graph_limit=graph_limit,
        )
        selected_edges, selected_mode = _select_graph_edges(graph, graph_mode, graph_limit)
        context["call_graph"] = selected_edges
        context["import_graph"] = graph.get("imports", [])
        context["call_graph_engine"] = graph.get("engine", graph_engine)
        context["call_graph_supported_languages"] = graph.get("supported_languages", [])
        warning = graph.get("warning") or ""
        if selected_mode == "full":
            warning = _strip_trim_warning(warning)
        context["call_graph_warning"] = warning
        _emit_call_graph_warning("[researcher]", warning)

        full_edges = graph.get("edges_full")
        if full_edges is None:
            full_edges = graph.get("edges") or []
        full_path = Path(args.output or f"aidd/reports/research/{ticket}-call-graph-full.json")
        full_path = _normalize_output_path(root, full_path)
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_payload = {"edges": full_edges, "imports": graph.get("imports", [])}
        full_path.write_text(json.dumps(full_payload, indent=2), encoding="utf-8")
        context["call_graph_full_path"] = os.path.relpath(full_path, root)
        columnar_path = full_path.with_suffix(".cjson")
        try:
            columnar_payload = _columnar_call_graph(
                full_payload.get("edges", []),
                full_payload.get("imports", []),
            )
            columnar_path.write_text(json.dumps(columnar_payload, indent=2), encoding="utf-8")
            context["call_graph_full_columnar_path"] = os.path.relpath(columnar_path, root)
        except OSError:
            pass
    elif graph_engine == "none" and (call_graph_requested or deep_code_enabled):
        context["call_graph_warning"] = "call graph disabled (graph-engine none)"
    context["auto_mode"] = bool(args.auto)
    match_count = len(context["matches"])
    if match_count == 0:
        print(
            f"[researcher] WARN: 0 matches for {ticket} → сузить paths/keywords или graph-only.",
            file=sys.stderr,
        )
    if args.dry_run:
        print(json.dumps(context, indent=2, ensure_ascii=False))
        return 0

    output_override = Path(args.output) if args.output else None
    output_path = builder.write_context(scope, context, output=output_override)
    rel_output = output_path.relative_to(root).as_posix()
    pack_path = None
    try:
        from tools import reports_pack as _reports_pack

        pack_path = _reports_pack.write_research_context_pack(output_path, root=root)
        try:
            rel_pack = pack_path.relative_to(root).as_posix()
        except ValueError:
            rel_pack = pack_path.as_posix()
        print(f"[researcher] pack saved to {rel_pack}.")
    except Exception as exc:
        print(f"[researcher] WARN: failed to generate pack: {exc}", file=sys.stderr)
    full_edges_count = 0
    if context.get("call_graph_full_path"):
        try:
            full_payload = json.loads((root / context["call_graph_full_path"]).read_text(encoding="utf-8"))
            full_edges_count = len(full_payload.get("edges") or [])
        except Exception:
            full_edges_count = 0
    message = f"[researcher] context saved to {rel_output} ({match_count} matches"
    if deep_code_enabled:
        reuse_count = len(context.get("reuse_candidates") or [])
        message += f", {reuse_count} reuse candidates"
    if should_build_graph:
        graph_edges = len(context.get("call_graph") or [])
        message += f", {graph_edges} call edges (full: {full_edges_count})"
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
