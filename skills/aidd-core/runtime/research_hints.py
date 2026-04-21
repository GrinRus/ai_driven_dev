from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Sequence


RESEARCH_HINTS_HEADING = "AIDD:RESEARCH_HINTS"
_EMPTY_VALUES = {"", "-", "none", "n/a", "na", "tbd"}
_ALIASES = {
    "paths": {"paths", "path", "пути", "путь"},
    "keywords": {"keywords", "keyword", "ключевые слова", "ключевые", "ключи"},
    "notes": {"notes", "note", "заметки", "заметка", "notes/details"},
}
_EXAMPLE_SUFFIX_RE = re.compile(r"\(\s*(?:e\.?g\.?|for example|например)\b.*\)$", re.IGNORECASE)
_PLACEHOLDER_RE = re.compile(r"^<[^>]+>$")
_TOKEN_SPLIT_RE = re.compile(r"[\s,:]+")


@dataclass(frozen=True)
class ResearchHints:
    paths: List[str]
    keywords: List[str]
    notes: List[str]

    def has_scope(self) -> bool:
        return bool(self.paths or self.keywords)


def _unique(values: Iterable[str]) -> List[str]:
    seen: set[str] = set()
    out: List[str] = []
    for raw in values:
        value = str(raw or "").strip()
        if not value or value in seen:
            continue
        seen.add(value)
        out.append(value)
    return out


def _extract_markdown_section(text: str, heading: str) -> str:
    lines = text.splitlines()
    needle = f"## {heading}".lower()
    start_idx = -1
    for idx, line in enumerate(lines):
        if line.strip().lower().startswith(needle):
            start_idx = idx + 1
            break
    if start_idx < 0:
        return ""
    end_idx = len(lines)
    for idx in range(start_idx, len(lines)):
        if lines[idx].startswith("## "):
            end_idx = idx
            break
    return "\n".join(lines[start_idx:end_idx]).strip()


def _normalize_label(raw: str) -> str:
    cleaned = raw.strip().strip("`").replace("**", "")
    cleaned = re.sub(r"\s+", " ", cleaned).strip().lower()
    for field, aliases in _ALIASES.items():
        if cleaned in aliases:
            return field
    return ""


def _normalize_scalar(raw: str) -> str:
    value = str(raw or "").strip()
    value = _EXAMPLE_SUFFIX_RE.sub("", value).strip()
    value = value.strip("`").strip()
    if _PLACEHOLDER_RE.fullmatch(value):
        return ""
    if value.lower() in _EMPTY_VALUES:
        return ""
    return value


def _split_tokens(raw: str, *, lowercase: bool = False, is_path: bool = False) -> List[str]:
    value = _normalize_scalar(raw)
    if not value:
        return []
    tokens: List[str] = []
    for token in _TOKEN_SPLIT_RE.split(value):
        cleaned = token.strip().strip("`").strip()
        if not cleaned:
            continue
        if _PLACEHOLDER_RE.fullmatch(cleaned):
            continue
        if cleaned.lower() in _EMPTY_VALUES:
            continue
        if is_path:
            cleaned = cleaned.replace("\\", "/")
            cleaned = cleaned.lstrip("./").rstrip("/")
            cleaned = cleaned or "."
        if lowercase:
            cleaned = cleaned.lower()
        tokens.append(cleaned)
    return _unique(tokens)


def _split_notes(raw: str) -> List[str]:
    value = _normalize_scalar(raw)
    if not value:
        return []
    parts = re.split(r"[;\n]+", value)
    notes = [part.strip().strip("`") for part in parts if part.strip()]
    return _unique(notes)


def parse_research_hints(text: str) -> ResearchHints:
    section = _extract_markdown_section(text, RESEARCH_HINTS_HEADING)
    if not section:
        return ResearchHints(paths=[], keywords=[], notes=[])

    paths: List[str] = []
    keywords: List[str] = []
    notes: List[str] = []
    for line in section.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        normalized = re.sub(r"^[-*+]\s+", "", stripped).strip()
        normalized = normalized.replace("**", "")
        if ":" not in normalized:
            continue
        label_raw, value_raw = normalized.split(":", 1)
        field = _normalize_label(label_raw)
        if not field:
            continue
        if field == "paths":
            paths.extend(_split_tokens(value_raw, is_path=True))
        elif field == "keywords":
            keywords.extend(_split_tokens(value_raw, lowercase=True))
        else:
            notes.extend(_split_notes(value_raw))
    return ResearchHints(
        paths=_unique(paths),
        keywords=_unique(keywords),
        notes=_unique(notes),
    )


def load_research_hints(root: Path, ticket: str) -> ResearchHints:
    prd_path = root / "docs" / "prd" / f"{ticket}.prd.md"
    if not prd_path.exists():
        return ResearchHints(paths=[], keywords=[], notes=[])
    try:
        text = prd_path.read_text(encoding="utf-8")
    except OSError:
        return ResearchHints(paths=[], keywords=[], notes=[])
    return parse_research_hints(text)


def merge_unique(*groups: Sequence[str]) -> List[str]:
    merged: List[str] = []
    for group in groups:
        for raw in group:
            value = str(raw or "").strip()
            if not value:
                continue
            merged.append(value)
    return _unique(merged)
