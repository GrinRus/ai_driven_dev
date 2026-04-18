from __future__ import annotations

import re
from typing import Iterable, List, Sequence, Tuple


def extract_marker_source(line: str, *, inline_path_re: re.Pattern[str]) -> str:
    text = str(line or "").strip()
    if not text:
        return "inline"
    match = inline_path_re.search(text)
    if match:
        return match.group("path").strip()
    return "inline"


def is_marker_noise_source(
    source: str,
    line: str,
    *,
    noise_section_hints: Sequence[str],
    noise_placeholders: Sequence[str],
) -> bool:
    source_lower = str(source or "").strip().lower()
    stripped = str(line or "").strip()
    line_lower = stripped.lower()
    if any(hint in line_lower for hint in noise_section_hints):
        return True
    if any(token in line_lower for token in noise_placeholders):
        return True
    if stripped.startswith(">"):
        return True
    if (stripped.startswith("- `") or stripped.startswith("* `")) and (
        "id=review:" in line_lower or "id_review_" in line_lower
    ):
        return True
    if "`" in stripped and ("id=review:" in line_lower or "id_review_" in line_lower):
        return True
    if ("канонический формат" in line_lower or "canonical format" in line_lower) and (
        "id=review:" in line_lower or "id_review_" in line_lower
    ):
        return True
    if "aidd/docs/tasklist/templates/" in source_lower or "aidd/docs/tasklist/templates/" in line_lower:
        return True
    return (
        source_lower.endswith(".bak")
        or source_lower.endswith(".tmp")
        or ".bak:" in source_lower
        or ".tmp:" in source_lower
        or ".bak" in line_lower
        or ".tmp" in line_lower
    )


def scan_marker_semantics(
    entries: Iterable[Tuple[str, str]],
    *,
    semantic_tokens: Sequence[str],
    inline_path_re: re.Pattern[str],
    noise_section_hints: Sequence[str],
    noise_placeholders: Sequence[str],
) -> Tuple[List[str], List[str]]:
    signal: List[str] = []
    noise: List[str] = []
    seen_signal: set[str] = set()
    seen_noise: set[str] = set()
    for source_name, text in entries:
        for raw_line in str(text or "").splitlines():
            line = raw_line.strip()
            if not line:
                continue
            line_lower = line.lower()
            if not any(token in line_lower for token in semantic_tokens):
                continue
            marker_source = extract_marker_source(line, inline_path_re=inline_path_re)
            item = f"{source_name}:{marker_source}"
            if is_marker_noise_source(
                marker_source,
                line,
                noise_section_hints=noise_section_hints,
                noise_placeholders=noise_placeholders,
            ):
                if item not in seen_noise:
                    seen_noise.add(item)
                    noise.append(item)
                continue
            if item not in seen_signal:
                seen_signal.add(item)
                signal.append(item)
    return signal, noise
