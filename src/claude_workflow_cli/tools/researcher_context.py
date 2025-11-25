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

from claude_workflow_cli.feature_ids import resolve_identifiers


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


def _utc_timestamp() -> str:
    return _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


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


def _identifier_tokens(ticket: str, slug_hint: Optional[str]) -> List[str]:
    separators = ("-", "_", " ", "/")
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
        value = normalized
        for sep in separators:
            value = value.replace(sep, " ")
        for token in value.split():
            lowered = token.strip().lower()
            if lowered and lowered not in tokens:
                tokens.append(lowered)
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
    ticket: str
    slug_hint: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    paths: List[str] = field(default_factory=list)
    docs: List[str] = field(default_factory=list)
    keywords: List[str] = field(default_factory=list)
    manual_notes: List[str] = field(default_factory=list)


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

    def build_scope(self, ticket: str, slug_hint: Optional[str] = None) -> Scope:
        ticket_value = (ticket or "").strip()
        if not ticket_value:
            raise ValueError("ticket must be a non-empty string")
        hint_value = (slug_hint or "").strip() or None
        settings = self._settings
        defaults = settings.get("defaults", {})
        default_paths = defaults.get("paths", ["src"])
        default_docs = defaults.get("docs", ["docs"])
        default_keywords = defaults.get("keywords", [])

        tags = self._resolve_tags(ticket_value, hint_value)
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
            ticket=ticket_value,
            slug_hint=hint_value,
            tags=tags,
            paths=_norm_all(list(default_paths) + list(tag_paths)),
            docs=_norm_all(list(default_docs) + list(tag_docs)),
            keywords=_unique(default_keywords + tag_keywords + _identifier_tokens(ticket_value, hint_value)),
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
        if extra_notes:
            scope.manual_notes = _unique(scope.manual_notes + [note for note in extra_notes if note])
        return scope

    def describe_targets(self, scope: Scope) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Path]]:
        return self._resolve_search_roots(scope)

    def _resolve_search_roots(self, scope: Scope) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Path]]:
        search_roots: List[Path] = []
        path_infos: List[Dict[str, Any]] = []
        for rel in scope.paths:
            info, path_obj = self._describe_path(rel)
            path_infos.append(info)
            if path_obj is not None:
                search_roots.append(path_obj)

        doc_infos, doc_roots = self._describe_docs(scope.docs)
        search_roots.extend(doc_roots)
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
            "docs": scope.docs,
            "keywords": scope.keywords,
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
            "paths": path_infos,
            "docs": doc_infos,
            "matches": matches,
            "code_index": code_index,
            "reuse_candidates": reuse_candidates,
            "profile": profile,
            "manual_notes": scope.manual_notes,
        }

    def write_context(self, scope: Scope, context: Dict[str, Any], *, output: Optional[Path] = None) -> Path:
        report_dir = self.root / _REPORT_DIR
        report_dir.mkdir(parents=True, exist_ok=True)
        target_path = output or (report_dir / f"{scope.ticket}-context.json")
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

    def _build_project_profile(self, scope: Scope, matches: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
        profile = {
            "is_new_project": len(matches) == 0,
            "src_layers": self._detect_src_layers(),
            "tests_detected": self._detect_tests(),
            "config_detected": self._detect_configs(),
            "logging_artifacts": self._detect_logging_artifacts(),
            "recommendations": [],
        }
        profile["recommendations"] = self._baseline_recommendations(profile, scope)
        return profile

    def _detect_src_layers(self, limit: int = 8) -> List[str]:
        src_dir = self.root / "src"
        if not src_dir.exists():
            return []
        layers: List[str] = []
        for child in sorted(src_dir.iterdir()):
            if not child.is_dir():
                continue
            layers.append(child.relative_to(self.root).as_posix())
            if len(layers) >= limit:
                break
        return layers

    def _detect_tests(self) -> bool:
        candidates = [
            self.root / "tests",
            self.root / "test",
            self.root / "src" / "test",
            self.root / "src" / "tests",
        ]
        for candidate in candidates:
            if candidate.exists():
                return True
        return False

    def _detect_configs(self) -> bool:
        candidates = [
            self.root / "config",
            self.root / "configs",
            self.root / "settings",
            self.root / "src" / "main" / "resources",
        ]
        for candidate in candidates:
            if candidate.exists():
                return True
        return False

    def _detect_logging_artifacts(self, limit: int = 5) -> List[str]:
        tokens = ("logback", "logging", "logger", "log4j")
        candidates: List[str] = []
        search_roots = [
            self.root / "config",
            self.root / "configs",
            self.root / "src",
        ]
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
                    try:
                        rel = path.relative_to(self.root).as_posix()
                    except ValueError:
                        rel = path.as_posix()
                    candidates.append(rel)
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
        if not files or not callgraph_langs:
            return {
                "engine": engine_name,
                "supported_languages": [],
                "edges": [],
                "imports": [],
                "warning": "call graph disabled or no supported files",
            }

        selected_engine = engine or _load_callgraph_engine(engine_name)
        if selected_engine is None:
            return {
                "engine": engine_name,
                "supported_languages": [],
                "edges": [],
                "imports": [],
                "warning": "call graph engine not available",
            }
        result = selected_engine.build(files)
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
            result["warning"] = (result.get("warning") or "") + f" call graph trimmed to {graph_limit} edges."
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
        try:
            rel_path = path.relative_to(self.root).as_posix()
        except ValueError:
            rel_path = path.as_posix()
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
                callers.append({"container": name})
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
                callers.append({"id": caller_id, "name": caller_id})
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
                        "caller": caller["id"] if caller else None,
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
        if engine._parser_loader is None:
            if engine_name == "ts":
                return None
            return None
        return engine
    return None


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Prepare context for the Researcher agent.")
    parser.add_argument("--target", default=".", help="Project root (default: current directory).")
    parser.add_argument("--config", help="Path to conventions JSON with researcher section.")
    parser.add_argument(
        "--ticket",
        "--slug",
        "--feature",
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
    parser.add_argument("--output", help="Override output path for context JSON (default: reports/research/<ticket>-context.json).")
    parser.add_argument("--targets-only", action="store_true", help="Only refresh targets JSON, skip scanning sources.")
    parser.add_argument("--dry-run", action="store_true", help="Run without writing files; prints context JSON to stdout.")
    parser.add_argument("--deep-code", action="store_true", help="Collect code symbols/imports/tests alongside keyword matches.")
    parser.add_argument("--reuse-only", action="store_true", help="Skip keyword matches and focus on reuse candidates.")
    parser.add_argument("--langs", help="Comma-separated list of languages to scan (py,kt,kts,java).")
    parser.add_argument("--call-graph", action="store_true", help="Build call/import graph for supported languages.")
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
        "--auto",
        action="store_true",
        help="Automation-friendly mode for /idea-new integrations (prints warnings on empty matches).",
    )
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    root = Path(args.target).resolve()
    if not root.exists():
        parser.error(f"target directory does not exist: {root}")

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
    auto_filter = "|".join(_unique(scope.keywords + [scope.ticket]))
    graph_filter = _parse_graph_filter(getattr(args, "graph_filter", None), fallback=auto_filter)
    raw_limit = getattr(args, "graph_limit", _DEFAULT_GRAPH_LIMIT)
    try:
        graph_limit = int(raw_limit)
    except (TypeError, ValueError):
        graph_limit = _DEFAULT_GRAPH_LIMIT
    if graph_limit <= 0:
        graph_limit = _DEFAULT_GRAPH_LIMIT

    context = builder.collect_context(scope, limit=args.limit)
    if args.deep_code:
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
    if getattr(args, "call_graph", False):
        graph_filter = _parse_graph_filter(getattr(args, "graph_filter", None), fallback=auto_filter)
        graph_limit = int(getattr(args, "graph_limit", _DEFAULT_GRAPH_LIMIT) or _DEFAULT_GRAPH_LIMIT)
        graph = builder.collect_call_graph(
            scope,
            roots=search_roots,
            languages=graph_languages or languages or list(_CALLGRAPH_LANGS),
            engine_name=graph_engine,
            graph_filter=graph_filter,
            graph_limit=graph_limit,
        )
        context["call_graph"] = graph.get("edges", [])
        context["import_graph"] = graph.get("imports", [])
        context["call_graph_engine"] = graph.get("engine", graph_engine)
        context["call_graph_supported_languages"] = graph.get("supported_languages", [])
        if graph.get("edges_full") is not None:
            full_path = Path(args.output or f"reports/research/{ticket}-call-graph-full.json")
            if not full_path.is_absolute():
                full_path = root / full_path
            full_path.parent.mkdir(parents=True, exist_ok=True)
            full_payload = {"edges": graph.get("edges_full", []), "imports": graph.get("imports", [])}
            full_path.write_text(json.dumps(full_payload, indent=2), encoding="utf-8")
            context["call_graph_full_path"] = os.path.relpath(full_path, root)
        context["call_graph_filter"] = graph_filter
        context["call_graph_limit"] = graph_limit
        if graph.get("warning"):
            context["call_graph_warning"] = graph.get("warning")
    else:
        context["call_graph"] = []
        context["import_graph"] = []
        context["call_graph_engine"] = graph_engine
        context["call_graph_supported_languages"] = []
    context["auto_mode"] = bool(args.auto)
    match_count = len(context["matches"])
    if match_count == 0:
        print(
            f"[researcher] 0 matches found for {ticket} — зафиксируйте baseline и статус pending в docs/research/{ticket}.md."
        )
    if args.dry_run:
        print(json.dumps(context, indent=2, ensure_ascii=False))
        return 0

    output_override = Path(args.output) if args.output else None
    output_path = builder.write_context(scope, context, output=output_override)
    rel_output = output_path.relative_to(root).as_posix()
    full_edges_count = 0
    if context.get("call_graph_full_path"):
        try:
            full_payload = json.loads((root / context["call_graph_full_path"]).read_text(encoding="utf-8"))
            full_edges_count = len(full_payload.get("edges") or [])
        except Exception:
            full_edges_count = 0
    message = f"[researcher] context saved to {rel_output} ({match_count} matches"
    if args.deep_code:
        reuse_count = len(context.get("reuse_candidates") or [])
        message += f", {reuse_count} reuse candidates"
    if getattr(args, "call_graph", False):
        graph_edges = len(context.get("call_graph") or [])
        message += f", {graph_edges} call edges (full: {full_edges_count})"
    message += ")."
    print(message)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
