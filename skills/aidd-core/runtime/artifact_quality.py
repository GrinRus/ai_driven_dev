from __future__ import annotations

import re
from pathlib import Path
from typing import Iterable, List, Tuple

from aidd_runtime import runtime
from aidd_runtime.io_utils import utc_timestamp

_STATUS_LINE_RE = re.compile(r"^\s*status\s*:\s*([A-Za-z][A-Za-z0-9_-]*)", re.IGNORECASE)
_HEADING_RE = re.compile(r"^\s*##\s+(.+?)\s*$")
_BULLET_RE = re.compile(r"^\s*-\s+(.+?)\s*$")

_PLACEHOLDER_TOKEN_RE = re.compile(r"<[A-Za-z0-9_./:-]{2,120}>")
_TEMPLATE_LEAK_RULES: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("template_prd_header", re.compile(r"PRD\s+[—-]\s+Шаблон", re.IGNORECASE)),
    ("template_status_draft", re.compile(r"^\s*Status:\s*draft\b", re.IGNORECASE | re.MULTILINE)),
    ("template_owner_placeholder", re.compile(r"^\s*Owner:\s*<name/team>\s*$", re.IGNORECASE | re.MULTILINE)),
    (
        "template_status_hint",
        re.compile(r"^\s*#\s*Status:\s*PENDING\|READY\|WARN\|BLOCKED\s*$", re.IGNORECASE | re.MULTILINE),
    ),
    ("template_stage_goal", re.compile(r"<stage-specific goal>", re.IGNORECASE)),
)

_PSEUDO_PATH_SEGMENT_RE = re.compile(r"^(?:domain|adapter|mcp)(?:/(?:domain|adapter|mcp))*$", re.IGNORECASE)
_ALLOWED_PATH_TOKEN_RE = re.compile(r"^[A-Za-z0-9_./*?{}:-]+$")
_REPORT_PATH_RE = re.compile(r"^aidd/reports/[A-Za-z0-9_./-]+$")


def detect_template_leakage(text: str) -> List[str]:
    content = str(text or "")
    markers: List[str] = []
    for code, rule in _TEMPLATE_LEAK_RULES:
        if rule.search(content):
            markers.append(code)
    if _PLACEHOLDER_TOKEN_RE.search(content):
        markers.append("template_placeholder_token")
    return sorted(set(markers))


def has_template_leakage(text: str) -> bool:
    return bool(detect_template_leakage(text))


def detect_status_drift(text: str) -> List[str]:
    lines = str(text or "").splitlines()
    top_status = ""
    review_statuses: List[Tuple[str, str]] = []
    current_heading = ""
    for line in lines:
        heading_match = _HEADING_RE.match(line)
        if heading_match:
            current_heading = heading_match.group(1).strip()
            continue
        status_match = _STATUS_LINE_RE.match(line)
        if not status_match:
            continue
        value = status_match.group(1).strip().upper()
        if not top_status:
            top_status = value
        if current_heading and "review" in current_heading.lower():
            review_statuses.append((current_heading, value))

    if not top_status:
        return []
    drift: List[str] = []
    for heading, value in review_statuses:
        if value != top_status:
            drift.append(f"{heading}:{value}!={top_status}")
    return sorted(set(drift))


def _clean_line(value: str) -> str:
    text = str(value or "").strip()
    if text.startswith("`") and text.endswith("`"):
        text = text[1:-1].strip()
    return text


def _section_lines(text: str, heading: str) -> List[str]:
    lines = str(text or "").splitlines()
    in_section = False
    selected: List[str] = []
    target = heading.strip().lower()
    for raw in lines:
        heading_match = _HEADING_RE.match(raw)
        if heading_match:
            value = heading_match.group(1).strip().lower()
            if in_section:
                break
            in_section = value == target
            continue
        if in_section:
            selected.append(raw)
    return selected


def _first_bullet(lines: Iterable[str]) -> str:
    for raw in lines:
        match = _BULLET_RE.match(raw)
        if not match:
            continue
        value = _clean_line(match.group(1))
        if value:
            return value
    return ""


def _extract_scalar(text: str, key: str) -> str:
    pattern = re.compile(rf"^\s*{re.escape(key)}\s*:\s*(.+)$", re.IGNORECASE | re.MULTILINE)
    match = pattern.search(str(text or ""))
    if not match:
        return ""
    return _clean_line(match.group(1))


def _extract_inline_list(text: str, key: str) -> List[str]:
    lines = str(text or "").splitlines()
    items: List[str] = []
    pattern = re.compile(rf"^\s*{re.escape(key)}\s*:\s*$", re.IGNORECASE)
    in_list = False
    for raw in lines:
        if pattern.match(raw):
            in_list = True
            continue
        if in_list and _HEADING_RE.match(raw):
            break
        if not in_list:
            continue
        match = _BULLET_RE.match(raw)
        if not match:
            if raw.strip():
                break
            continue
        value = _clean_line(match.group(1))
        if value:
            items.append(value)
    return items


def _context_read_log_entries(text: str) -> List[str]:
    entries: List[str] = []
    for raw in _section_lines(text, "AIDD:READ_LOG"):
        match = _BULLET_RE.match(raw)
        if not match:
            continue
        value = _clean_line(match.group(1))
        if not value:
            continue
        if "(reason:" in value.lower():
            value = value.split("(", 1)[0].strip()
        if value:
            entries.append(value)
    return entries


def _compact_join(values: Iterable[str], *, limit: int) -> str:
    items: List[str] = []
    for raw in values:
        value = _clean_line(raw)
        if not value or value in items:
            continue
        items.append(value)
        if len(items) >= limit:
            break
    return ", ".join(items)


def _sanitize_context_items(
    values: Iterable[str],
    *,
    path_like: bool = False,
    max_items: int = 0,
) -> List[str]:
    cleaned: List[str] = []
    for raw in values:
        value = _clean_line(raw)
        if not value:
            continue
        if has_template_leakage(value):
            continue
        if path_like and not _is_path_token_plausible(value):
            continue
        if value in cleaned:
            continue
        cleaned.append(value)
        if max_items > 0 and len(cleaned) >= max_items:
            break
    return cleaned


def render_context_pack_excerpt(text: str, *, max_lines: int, max_chars: int) -> str:
    content = str(text or "").strip()
    if not content:
        return ""
    markers = detect_template_leakage(content)
    stage = _extract_scalar(content, "stage")
    generated_at = _extract_scalar(content, "generated_at")
    read_next = _extract_inline_list(content, "read_next")
    action = _first_bullet(_section_lines(content, "What to do now"))
    read_log_count = len(_context_read_log_entries(content))

    lines: List[str] = []
    if markers:
        lines.append(f"- contamination_detected: {', '.join(markers)}")
    if stage:
        lines.append(f"- stage: {stage}")
    if generated_at:
        lines.append(f"- generated_at: {generated_at}")
    if read_next:
        lines.append(f"- read_next: {_compact_join(read_next, limit=3)}")
    if read_log_count:
        lines.append(f"- read_log_items: {read_log_count}")
    if action:
        lines.append(f"- next_action: {action}")
    if not lines:
        fallback: List[str] = []
        for raw in content.splitlines():
            line = _clean_line(raw)
            if not line:
                continue
            if line.startswith("#"):
                continue
            fallback.append(line)
            if len(fallback) >= max(max_lines, 3):
                break
        if fallback:
            lines.append(f"- context_pack_excerpt: {fallback[0]}")
            for item in fallback[1:]:
                lines.append(f"- {item}")
        else:
            lines.append("- context_pack_summary: n/a")

    if max_lines > 0:
        lines = lines[:max_lines]
    rendered = "\n".join(lines).strip()
    if max_chars > 0 and len(rendered) > max_chars:
        rendered = rendered[:max_chars].rstrip()
    return rendered


def _default_context_read_next(root: Path, ticket: str) -> List[str]:
    candidates = [
        root / "docs" / "tasklist" / f"{ticket}.md",
        root / "docs" / "plan" / f"{ticket}.md",
        root / "docs" / "prd" / f"{ticket}.prd.md",
        root / "docs" / "index" / f"{ticket}.json",
    ]
    values = [runtime.rel_path(path, root) for path in candidates if path.exists()]
    values.extend(_default_pack_sources(root, ticket))
    return values[:8]


def _default_pack_sources(root: Path, ticket: str) -> List[str]:
    reports_root = root / "reports"
    if not reports_root.exists():
        return []
    names = (f"{ticket}.pack.json", f"{ticket}-")
    values: List[str] = []
    for path in sorted(reports_root.rglob("*.pack.json")):
        filename = path.name
        if filename == names[0] or filename.startswith(names[1]):
            rel = runtime.rel_path(path, root)
            if rel not in values:
                values.append(rel)
        if len(values) >= 12:
            break
    return values


def _default_context_links(root: Path, ticket: str) -> List[str]:
    candidates = [
        root / "docs" / "prd" / f"{ticket}.prd.md",
        root / "docs" / "plan" / f"{ticket}.md",
        root / "docs" / "tasklist" / f"{ticket}.md",
        root / "docs" / "index" / f"{ticket}.json",
        root / "reports" / "qa" / f"{ticket}.json",
        root / "reports" / "prd" / f"{ticket}.json",
        root / "reports" / "context" / f"{ticket}.pack.md",
    ]
    values = [runtime.rel_path(path, root) for path in candidates if path.exists()]
    for pack_path in _default_pack_sources(root, ticket):
        if pack_path not in values:
            values.append(pack_path)
    return values[:16]


def build_clean_context_pack(root: Path, ticket: str, *, existing_text: str = "", contamination: Iterable[str] | None = None) -> str:
    stage = runtime.read_active_stage(root) or "unknown"
    generated_at = utc_timestamp()
    contamination_markers = [item for item in (contamination or []) if str(item).strip()]

    # Hard-replace path: when contamination is detected, rebuild from structured sources only.
    if contamination_markers:
        read_next = _default_context_read_next(root, ticket)
        links = _default_context_links(root, ticket)
        read_log = [f"aidd/reports/context/{ticket}.pack.md"]
    else:
        read_next = _extract_inline_list(existing_text, "read_next") or _default_context_read_next(root, ticket)
        links = _extract_inline_list(existing_text, "artefact_links") or _default_context_links(root, ticket)
        read_log = _context_read_log_entries(existing_text) or [f"aidd/reports/context/{ticket}.pack.md"]

    read_next = _sanitize_context_items(read_next, path_like=True, max_items=5) or _default_context_read_next(root, ticket)[:5]
    links = _sanitize_context_items(links, path_like=True, max_items=10) or _default_context_links(root, ticket)[:10]
    read_log = _sanitize_context_items(read_log, path_like=True, max_items=5) or [f"aidd/reports/context/{ticket}.pack.md"]

    what_to_do = _first_bullet(_section_lines(existing_text, "What to do now"))
    if not what_to_do or has_template_leakage(what_to_do):
        what_to_do = "Update next stage handoff using canonical reports only."
    user_note = _first_bullet(_section_lines(existing_text, "User note")) or "n/a"
    if has_template_leakage(user_note):
        user_note = "n/a"

    lines = [
        f"# AIDD Context Pack — {stage}",
        "",
        f"ticket: {ticket}",
        f"stage: {stage}",
        "agent: stage-chain",
        f"generated_at: {generated_at}",
        "read_next:",
    ]
    lines.extend([f"- {_clean_line(item)}" for item in read_next[:5] if _clean_line(item)])
    if lines[-1] == "read_next:":
        lines.append("- n/a")
    lines.append("artefact_links:")
    lines.extend([f"- {_clean_line(item)}" for item in links[:10] if _clean_line(item)])
    if lines[-1] == "artefact_links:":
        lines.append("- n/a")
    lines.extend(
        [
            "",
            "## AIDD:READ_LOG",
        ]
    )
    lines.extend([f"- {_clean_line(item)} (reason: context-pack-compact)" for item in read_log[:5] if _clean_line(item)])
    if lines[-1] == "## AIDD:READ_LOG":
        lines.append("- n/a")
    lines.extend(
        [
            "",
            "## What to do now",
            f"- {what_to_do}",
            "",
            "## User note",
            f"- {user_note}",
        ]
    )
    if contamination_markers:
        lines.extend(
            [
                "",
                "## Repair telemetry",
                f"- quality_repair: hard_replace",
                f"- contamination_markers: {', '.join(sorted(set(contamination_markers)))}",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def repair_context_pack_if_contaminated(root: Path, ticket: str, context_path: Path) -> Tuple[bool, List[str]]:
    if not context_path.exists():
        return False, []
    try:
        existing = context_path.read_text(encoding="utf-8")
    except OSError:
        return False, []
    markers = detect_template_leakage(existing)
    if not markers:
        return False, []
    repaired = build_clean_context_pack(root, ticket, existing_text=existing, contamination=markers)
    # Hard replace policy for contaminated context artifacts.
    context_path.unlink(missing_ok=True)
    context_path.parent.mkdir(parents=True, exist_ok=True)
    context_path.write_text(repaired, encoding="utf-8")
    return True, markers


def _is_path_token_plausible(value: str) -> bool:
    token = str(value or "").strip()
    if not token:
        return False
    if "<" in token or ">" in token:
        return False
    if not _ALLOWED_PATH_TOKEN_RE.match(token):
        return False
    normalized = token.strip("./").lower()
    if _PSEUDO_PATH_SEGMENT_RE.match(normalized):
        return False
    return True


def normalize_expected_report_paths(values: Iterable[str]) -> Tuple[List[str], List[str]]:
    normalized: List[str] = []
    dropped: List[str] = []
    for raw in values:
        value = str(raw or "").strip()
        if not value:
            continue
        if not _is_path_token_plausible(value):
            dropped.append(value)
            continue
        if not _REPORT_PATH_RE.match(value):
            dropped.append(value)
            continue
        if value not in normalized:
            normalized.append(value)
    return normalized, dropped


def filter_plausible_paths(values: Iterable[str]) -> Tuple[List[str], List[str]]:
    kept: List[str] = []
    dropped: List[str] = []
    for raw in values:
        value = str(raw or "").strip()
        if not value:
            continue
        if _is_path_token_plausible(value):
            if value not in kept:
                kept.append(value)
        else:
            dropped.append(value)
    return kept, dropped
