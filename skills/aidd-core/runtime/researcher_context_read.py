#!/usr/bin/env python3
"""Read-budget and reuse-ranking helpers for researcher context."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, Iterable, Iterator, List, Optional, Sequence, Tuple

from aidd_runtime import researcher_context as core


def scan_matches(
    builder,
    roots: Sequence[Path],
    keywords: Sequence[str],
    *,
    limit: int = core._MAX_MATCHES,
) -> List[Dict[str, Any]]:
    matches: List[Dict[str, Any]] = []
    seen: set[Tuple[str, str, int]] = set()
    tokens = [kw.strip().lower() for kw in keywords if kw]
    if not tokens:
        return matches

    for root in roots:
        if root.is_dir():
            iterator = iter_files(builder, root)
        else:
            iterator = iter([root])
        for file_path in iterator:
            rel = builder._rel_to_base(file_path)
            try:
                data = file_path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            if len(data.encode("utf-8")) > core._MAX_FILE_BYTES:
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


def iter_files(builder, root: Path) -> Iterator[Path]:
    try:
        base_root = root
        if builder._is_ignored_root(base_root):
            return
        for base, dirs, files in os.walk(root):
            dirs[:] = [name for name in dirs if name.lower() not in builder._ignore_dirs]
            if builder._is_ignored_path(Path(base), base=base_root):
                dirs[:] = []
                continue
            for name in files:
                path = Path(base) / name
                if builder._is_ignored_path(path, base=base_root):
                    continue
                if path.suffix.lower() in core._ALLOWED_SUFFIXES:
                    yield path
    except OSError:
        return


def collect_deep_context(
    builder,
    scope: "core.Scope",
    *,
    roots: Sequence[Path],
    keywords: Sequence[str],
    languages: Sequence[str],
    reuse_only: bool = False,
    limit: int = core._MAX_MATCHES,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    _ = scope
    allowed_langs = {lang.lower() for lang in (languages or core._DEFAULT_LANGS)}
    code_index = collect_code_index(builder, roots, allowed_langs)
    reuse_candidates = score_reuse_candidates(builder, code_index, keywords, limit=limit)
    if reuse_only:
        return [], reuse_candidates
    return code_index, reuse_candidates


def collect_code_index(builder, roots: Sequence[Path], allowed_langs: set[str]) -> List[Dict[str, Any]]:
    index: List[Dict[str, Any]] = []
    for root in roots:
        iterator: Iterable[Path]
        if root.is_dir():
            iterator = iter_code_files(builder, root, allowed_langs)
        else:
            iterator = [root]
        for path in iterator:
            lang = core._language_for_path(path)
            if not lang or lang not in allowed_langs:
                continue
            summary = summarise_code_file(builder, path, lang)
            if summary:
                index.append(summary)
    return index


def iter_code_files(builder, root: Path, allowed_langs: set[str]) -> Iterator[Path]:
    try:
        base_root = root
        if builder._is_ignored_root(base_root):
            return
        for base, dirs, files in os.walk(root):
            dirs[:] = [name for name in dirs if name.lower() not in builder._ignore_dirs]
            if builder._is_ignored_path(Path(base), base=base_root):
                dirs[:] = []
                continue
            for name in files:
                path = Path(base) / name
                if builder._is_ignored_path(path, base=base_root):
                    continue
                lang = core._language_for_path(path)
                if not lang or lang not in allowed_langs:
                    continue
                yield path
    except OSError:
        return


def summarise_code_file(builder, path: Path, lang: str) -> Optional[Dict[str, Any]]:
    try:
        data = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None
    if len(data.encode("utf-8")) > core._MAX_FILE_BYTES:
        return None

    imports: List[str] = []
    symbols: List[Dict[str, Any]] = []
    if lang == "py":
        imports, symbols = core._extract_python_summary(data)
    else:
        imports, symbols = core._extract_generic_summary(data, lang)

    has_tests = core._is_test_path(path)
    rel_path = builder._rel_to_base(path)
    return {
        "path": rel_path,
        "language": lang,
        "imports": imports,
        "symbols": symbols,
        "has_tests": has_tests,
    }


def score_reuse_candidates(
    builder,
    code_index: Sequence[Dict[str, Any]],
    keywords: Sequence[str],
    *,
    limit: int = core._MAX_MATCHES,
) -> List[Dict[str, Any]]:
    _ = builder
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
