#!/usr/bin/env python3
"""Lightweight PRD review helper for Claude workflow.

The script inspects aidd/docs/prd/<ticket>.prd.md, looks for the dedicated
`## PRD Review` section (including numbered `## <N>. PRD Review` variants),
checks status/action items and surfaces obvious placeholders (TODO/TBD/<...>)
that must be resolved before development.

It produces a structured JSON report that can be stored in aidd/reports/prd/
and optionally prints a concise human-readable summary.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import sys
from contextlib import suppress
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Iterable, List, Optional

try:
    from aidd_runtime._bootstrap import ensure_repo_root
except ImportError:  # pragma: no cover - direct script execution
    from _bootstrap import ensure_repo_root

ensure_repo_root(__file__)

from aidd_runtime import id_utils  # noqa: E402
from aidd_runtime import runtime  # noqa: E402
from aidd_runtime.feature_ids import resolve_aidd_root, resolve_identifiers  # noqa: E402
from aidd_runtime.prd_review_section import (  # noqa: E402
    extract_prd_review_section,
    is_markdown_h2,
    is_prd_review_header,
)


def detect_project_root(target: Optional[Path] = None) -> Path:
    base = target or Path.cwd()
    return resolve_aidd_root(base)
DEFAULT_STATUS = "pending"
APPROVED_STATUSES = {"ready"}
BLOCKING_TOKENS = {"blocked", "reject"}
STATUS_ALIASES = {
    "ready_for_implementation": "ready",
    "ready-for-implementation": "ready",
}
PLACEHOLDER_PATTERN = re.compile(r"<[^>]+>")
TODO_TBD_PATTERN = re.compile(r"\b(?:TODO|TBD)\b", re.IGNORECASE)
HTML_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)
FENCE_MARKER_RE = re.compile(r"^\s*(```+|~~~+)")
INLINE_CODE_RE = re.compile(r"`[^`\n]*`")
NARRATIVE_TBD_PLACEHOLDER_RE = re.compile(
    r"\bcontain(?:s)?\s+tbd\s+placeholders\b",
    re.IGNORECASE,
)
RESOLVED_TBD_RE = re.compile(
    r"\btbd\b\s*(?:[-:]\s*)?(?:resolved|fixed|closed|done)\b",
    re.IGNORECASE,
)
OPEN_ACTION_ITEM_RE = re.compile(r"^- \[\s\]", re.IGNORECASE)
AIDD_OPEN_QUESTIONS_HEADING = "## AIDD:OPEN_QUESTIONS"
AIDD_ANSWERS_HEADING = "## AIDD:ANSWERS"
NARRATIVE_OPEN_QUESTIONS_HEADING = "## 10. Открытые вопросы"
Q_RE = re.compile(r"\bQ(\d+)\b")
COMPACT_ANSWER_RE = re.compile(r'\bQ(\d+)\s*=\s*(?:"([^"\n]+)"|([^\s;,#`]+))')
INVALID_ANSWER_VALUES = {"tbd", "todo", "none", "нет", "n/a", "na", "empty", "unknown", "-", "?"}
NONE_VALUES = {"none", "нет", "n/a", "na"}
OPEN_ITEM_PREFIX_RE = re.compile(r"^(?:[-*+]\s+|\d+\.\s+)")
CHECKBOX_PREFIX_RE = re.compile(r"^\[[ xX]\]\s*")
MARKDOWN_HEADING_RE = re.compile(r"^\s{0,3}#{1,6}\s+\S")
COMPACT_ANSWER_INSTRUCTION_RE = re.compile(
    r"(compact\s+формат|q<n>\s*=\s*<token>|q<n>\s*=\s*\"[^\"]+\")",
    re.IGNORECASE,
)
PLACEHOLDER_FIELD_RE = re.compile(
    r"^(?:[-*+]\s+|\d+\.\s+)?(?:\[[ xX]\]\s*)?"
    r"(?:\*\*[^*]+\*\*|[A-Za-zА-Яа-я0-9_./() -]{1,80})\s*:\s*<[^>]+>"
)
PLACEHOLDER_ARROW_RE = re.compile(
    r"^(?:[-*+]\s+|\d+\.\s+)?<[^>]+>\s*→\s*<[^>]+>(?:\s*→\s*<[^>]+>)*$"
)
EXAMPLE_PLACEHOLDER_RE = re.compile(
    r"(?:^|[\s`])(?:/feature-dev-aidd:[^\s]+|python3\s+\$\{CLAUDE_PLUGIN_ROOT\}/skills/[^\s]+|aidd/[^\s`]+)"
    r".*<[^>]+>",
    re.IGNORECASE,
)
PLACEHOLDER_TOKEN_RE = re.compile(r"<[^>\n]+>")


def _normalize_output_path(root: Path, path: Path) -> Path:
    if path.is_absolute():
        return path.resolve()
    parts = path.parts
    if parts and parts[0] == ".":
        path = Path(*parts[1:])
        parts = path.parts
    if parts and parts[0] == "aidd" and root.name == "aidd":
        path = Path(*parts[1:])
    return (root / path).resolve()


def _rel_path(root: Path, path: Path) -> str:
    try:
        rel = path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()
    if root.name == "aidd":
        return f"aidd/{rel}"
    return rel


def _normalize_id_text(value: str) -> str:
    return " ".join(str(value).strip().split())


def _normalize_review_status(status: str) -> str:
    value = str(status or "").strip().lower()
    if not value:
        return DEFAULT_STATUS
    return STATUS_ALIASES.get(value, value)


@dataclass
class Finding:
    severity: str  # critical | major | minor
    title: str
    details: str
    id: str = ""

    def __post_init__(self) -> None:
        if not self.id:
            self.id = id_utils.stable_id(
                "prd",
                _normalize_id_text(self.severity),
                _normalize_id_text(self.title),
                _normalize_id_text(self.details),
            )


@dataclass
class Report:
    ticket: str
    slug: str
    status: str
    recommended_status: str
    findings: List[Finding]
    action_items: List[str]
    generated_at: str
    open_questions_count: int = 0
    answers_format: str = "compact_q_values"
    narrative_vs_structured_mismatch: bool = False
    canonical_prd_path: str = ""

    def to_dict(self) -> dict:
        payload = asdict(self)
        payload["findings"] = [asdict(item) for item in self.findings]
        return payload


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Perform lightweight PRD review heuristics."
    )
    parser.add_argument(
        "--ticket",
        help="Feature ticket to analyse (defaults to aidd/docs/.active.json).",
    )
    parser.add_argument(
        "--slug",
        "--slug-hint",
        dest="slug_hint",
        help="Optional slug hint override (defaults to aidd/docs/.active.json when available).",
    )
    parser.add_argument(
        "--prd",
        type=Path,
        help="Explicit path to PRD file. Defaults to aidd/docs/prd/<ticket>.prd.md.",
    )
    parser.add_argument(
        "--report",
        type=Path,
        help="Optional path to store JSON report. Directories are created automatically.",
    )
    parser.add_argument(
        "--emit-text",
        action="store_true",
        help="Print a human-readable summary in addition to JSON output.",
    )
    parser.add_argument(
        "--stdout-format",
        choices=("json", "text", "auto"),
        default="auto",
        help="Format for stdout output (default: auto). Auto prints text when --emit-text is used.",
    )
    parser.add_argument(
        "--emit-patch",
        action="store_true",
        help="Emit RFC6902 patch file when a previous report exists.",
    )
    parser.add_argument(
        "--pack-only",
        action="store_true",
        help="Remove JSON report after writing pack sidecar.",
    )
    parser.add_argument(
        "--require-ready",
        action="store_true",
        help="Return non-zero when recommended_status is not ready.",
    )
    parser.add_argument(
        "--docs-only",
        action="store_true",
        help="Enable docs-only rewrite mode for this invocation.",
    )
    return parser.parse_args(argv)


def detect_feature(root: Path, ticket_arg: Optional[str], slug_arg: Optional[str]) -> tuple[str, str]:
    ticket_candidate = (ticket_arg or "").strip() or None
    slug_candidate = (slug_arg or "").strip() or None

    identifiers = resolve_identifiers(root, ticket=ticket_candidate, slug_hint=slug_candidate)
    ticket_resolved = (identifiers.resolved_ticket or "").strip()
    slug_resolved = (identifiers.slug_hint or "").strip()
    if ticket_resolved:
        return ticket_resolved, slug_resolved or ticket_resolved

    if ticket_candidate:
        return ticket_candidate, slug_candidate or ticket_candidate

    return "", ""


def locate_prd(root: Path, ticket: str, explicit: Optional[Path]) -> Path:
    if explicit:
        return explicit
    return root / "docs" / "prd" / f"{ticket}.prd.md"


def extract_review_section(content: str) -> tuple[str, List[str]]:
    """Return status string and action items from the PRD Review section."""
    _, status, action_items = extract_prd_review_section(
        content,
        normalize_status=_normalize_review_status,
    )
    if not status:
        status = DEFAULT_STATUS
    return status, action_items


def _extract_section(text: str, heading_prefix: str) -> str:
    lines = text.splitlines()
    start_idx = -1
    needle = heading_prefix.strip().lower()
    for idx, line in enumerate(lines):
        if line.strip().lower().startswith(needle):
            start_idx = idx + 1
            break
    if start_idx < 0:
        return ""
    end_idx = len(lines)
    for idx in range(start_idx, len(lines)):
        if MARKDOWN_HEADING_RE.match(lines[idx]):
            end_idx = idx
            break
    return "\n".join(lines[start_idx:end_idx]).strip()


def _normalize_open_item(line: str) -> str:
    normalized = OPEN_ITEM_PREFIX_RE.sub("", line.strip())
    normalized = CHECKBOX_PREFIX_RE.sub("", normalized).strip()
    if normalized.startswith("`") and normalized.endswith("`") and len(normalized) > 1:
        normalized = normalized[1:-1].strip()
    if normalized.startswith("**") and normalized.endswith("**") and len(normalized) > 3:
        normalized = normalized[2:-2].strip()
    return normalized


def _collect_open_question_count(section: str) -> int:
    if not section:
        return 0
    q_numbers: set[int] = set()
    generic_items = 0
    for raw_line in section.splitlines():
        stripped = raw_line.strip()
        if not stripped or stripped.startswith(">"):
            continue
        normalized = _normalize_open_item(stripped)
        if not normalized:
            continue
        if normalized.lower() in NONE_VALUES:
            continue
        local_numbers = [int(match.group(1)) for match in Q_RE.finditer(normalized)]
        if local_numbers:
            q_numbers.update(local_numbers)
            continue
        generic_items += 1
    if q_numbers:
        return len(q_numbers)
    return generic_items


def _detect_answers_format(section: str) -> str:
    raw_payload = (section or "").strip()
    payload_lines: list[str] = []
    in_fence = False
    fence_marker = ""
    for raw in (section or "").splitlines():
        stripped = raw.strip()
        fence_match = FENCE_MARKER_RE.match(raw)
        if fence_match:
            marker = str(fence_match.group(1) or "")[:3]
            if not in_fence:
                in_fence = True
                fence_marker = marker
            elif marker == fence_marker:
                in_fence = False
                fence_marker = ""
            continue
        if in_fence:
            continue
        if not stripped or stripped.startswith(">"):
            continue
        if stripped.startswith("<!--") or stripped.endswith("-->"):
            continue
        if stripped.startswith("`") and stripped.endswith("`") and len(stripped) > 1:
            continue
        payload_lines.append(raw)
    payload = "\n".join(payload_lines).strip()
    if not payload:
        return "invalid" if raw_payload else "compact_q_values"
    compact_answers: dict[int, str] = {}
    for match in COMPACT_ANSWER_RE.finditer(payload):
        try:
            number = int(match.group(1))
        except ValueError:
            continue
        if number <= 0:
            continue
        value = str((match.group(2) if match.group(2) is not None else match.group(3)) or "").strip().lower()
        if value in INVALID_ANSWER_VALUES:
            return "invalid"
        if value.startswith("<") and value.endswith(">"):
            return "invalid"
        if "<" in value or ">" in value:
            return "invalid"
        compact_answers[number] = value
    if not compact_answers:
        return "invalid"
    return "compact_q_values"


def _strip_inline_code(text: str) -> str:
    return INLINE_CODE_RE.sub("", text)


def _looks_like_placeholder_example(line: str) -> bool:
    lowered = line.lower()
    if EXAMPLE_PLACEHOLDER_RE.search(line):
        return True
    if ("например" in lowered or "example" in lowered) and not (
        _matches_placeholder_standalone(line)
        or PLACEHOLDER_FIELD_RE.match(line)
        or PLACEHOLDER_ARROW_RE.match(line)
    ):
        return True
    return False


def _matches_placeholder_standalone(line: str) -> bool:
    value = CHECKBOX_PREFIX_RE.sub("", OPEN_ITEM_PREFIX_RE.sub("", line.strip())).strip()
    if not value:
        return False

    match = PLACEHOLDER_TOKEN_RE.match(value)
    if match is None:
        return False

    pos = match.end()
    length = len(value)
    while pos < length:
        while pos < length and value[pos].isspace():
            pos += 1
        if pos >= length:
            break

        char = value[pos]
        if char in ".,;:":
            pos += 1
            continue
        if char in {"→", "|"}:
            pos += 1
            while pos < length and value[pos].isspace():
                pos += 1
            match = PLACEHOLDER_TOKEN_RE.match(value, pos)
            if match is None:
                return False
            pos = match.end()
            continue
        return False

    return True


def _is_actionable_placeholder_line(line: str) -> bool:
    if _matches_placeholder_standalone(line):
        return True
    if PLACEHOLDER_FIELD_RE.match(line):
        return True
    if PLACEHOLDER_ARROW_RE.match(line):
        return True
    normalized = line.lstrip()
    if normalized.startswith(("- ", "* ", "+ ")) and PLACEHOLDER_PATTERN.search(line):
        return not _looks_like_placeholder_example(line)
    return False


def collect_placeholders(content: str) -> Iterable[str]:
    sanitized = HTML_COMMENT_RE.sub(" ", content)
    inside_review_section = False
    inside_answers_section = False
    inside_fence = False
    fence_marker = ""
    for line in sanitized.splitlines():
        fence_match = FENCE_MARKER_RE.match(line)
        if fence_match:
            marker = str(fence_match.group(1) or "")[:3]
            if not inside_fence:
                inside_fence = True
                fence_marker = marker
            elif marker == fence_marker:
                inside_fence = False
                fence_marker = ""
            continue
        if inside_fence:
            continue
        if is_markdown_h2(line):
            inside_review_section = is_prd_review_header(line)
            inside_answers_section = line.strip().lower().startswith(AIDD_ANSWERS_HEADING.lower())
            continue
        if inside_review_section:
            continue
        trimmed = line.strip()
        if not trimmed:
            continue
        # Ignore instructional compact-format examples in AIDD:ANSWERS blockquotes.
        if (
            inside_answers_section
            and trimmed.startswith(">")
            and COMPACT_ANSWER_INSTRUCTION_RE.search(trimmed)
        ):
            continue
        if RESOLVED_TBD_RE.search(trimmed):
            continue
        if NARRATIVE_TBD_PLACEHOLDER_RE.search(trimmed):
            continue
        if TODO_TBD_PATTERN.search(trimmed):
            yield trimmed
            continue
        stripped = _strip_inline_code(trimmed).strip()
        if not stripped:
            continue
        if PLACEHOLDER_PATTERN.search(stripped) and _is_actionable_placeholder_line(stripped):
            yield trimmed


def analyse_prd(slug: str, prd_path: Path, *, ticket: Optional[str] = None) -> Report:
    try:
        content = prd_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        raise SystemExit(f"[prd-review] PRD not found: {prd_path}")

    status, action_items = extract_review_section(content)
    findings: List[Finding] = []
    open_action_items = [item for item in action_items if OPEN_ACTION_ITEM_RE.match(item)]
    aidd_open_section = _extract_section(content, AIDD_OPEN_QUESTIONS_HEADING)
    aidd_answers_section = _extract_section(content, AIDD_ANSWERS_HEADING)
    narrative_open_section = _extract_section(content, NARRATIVE_OPEN_QUESTIONS_HEADING)
    open_questions_count = _collect_open_question_count(aidd_open_section)
    narrative_open_questions_count = _collect_open_question_count(narrative_open_section)
    narrative_vs_structured_mismatch = bool(
        narrative_open_questions_count and narrative_open_questions_count != open_questions_count
    )
    answers_format = _detect_answers_format(aidd_answers_section)

    placeholder_hits = list(collect_placeholders(content))
    for item in placeholder_hits:
        findings.append(
            Finding(
                severity="major",
                title="Найдены заглушки в PRD",
                details=item,
            )
        )
    if open_questions_count > 0:
        findings.append(
            Finding(
                severity="major",
                title="Незакрытые AIDD:OPEN_QUESTIONS",
                details=f"Осталось открытых вопросов: {open_questions_count}",
            )
        )
    if answers_format == "invalid":
        findings.append(
            Finding(
                severity="major",
                title="AIDD:ANSWERS в невалидном формате",
                details="AIDD:ANSWERS должен быть в compact формате `Q<N>=<value>` без TBD/пустых значений.",
            )
        )

    if status not in APPROVED_STATUSES and not placeholder_hits and not open_action_items:
        findings.append(
            Finding(
                severity="minor",
                title="Статус PRD Review не обновлён",
                details="Укажите Status: READY после ревью.",
            )
        )

    if status in BLOCKING_TOKENS:
        findings.append(
            Finding(
                severity="critical",
                title="PRD Review помечен как BLOCKED",
                details="Закройте блокеры перед разработкой.",
            )
        )

    has_critical_findings = any(item.severity == "critical" for item in findings)
    has_major_findings = any(item.severity == "major" for item in findings)
    if status in BLOCKING_TOKENS or has_critical_findings:
        recomputed_status = "blocked"
    elif has_major_findings or open_action_items or status not in APPROVED_STATUSES:
        recomputed_status = "pending"
    else:
        recomputed_status = "ready"

    generated_at = (
        dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    )

    return Report(
        ticket=ticket or slug,
        slug=slug,
        status=status or DEFAULT_STATUS,
        recommended_status=recomputed_status,
        findings=findings,
        action_items=action_items,
        generated_at=generated_at,
        open_questions_count=open_questions_count,
        answers_format=answers_format,
        narrative_vs_structured_mismatch=narrative_vs_structured_mismatch,
        canonical_prd_path=prd_path.as_posix(),
    )


def print_text_report(report: Report) -> None:
    header = f"[prd-review] slug={report.slug} status={report.status} recommended={report.recommended_status}"
    print(header)
    if report.action_items:
        print(f"- незакрытые action items ({len(report.action_items)}):")
        for item in report.action_items:
            print(f"  • {item}")
    if report.findings:
        print(f"- findings ({len(report.findings)}):")
        for finding in report.findings:
            print(f"  • [{finding.severity}] {finding.title} — {finding.details}")


def run(args: argparse.Namespace) -> int:
    root = detect_project_root()
    ticket, slug_hint = detect_feature(root, getattr(args, "ticket", None), getattr(args, "slug_hint", None))
    if not ticket:
        print(
            "[prd-review] Cannot determine feature ticket. "
            "Pass --ticket or create aidd/docs/.active.json.",
            file=sys.stderr,
        )
        return 1

    slug = slug_hint or ticket
    prd_path = locate_prd(root, ticket, args.prd)
    try:
        report = analyse_prd(slug, prd_path, ticket=ticket)
    except SystemExit as exc:
        message = str(exc)
        if message:
            print(message, file=sys.stderr)
        return 1

    if args.emit_text or args.stdout_format in ("text", "auto"):
        print_text = args.emit_text or args.stdout_format == "text"
    else:
        print_text = False

    if print_text:
        print_text_report(report)

    should_emit_json = (args.stdout_format in ("json", "auto") and not print_text) or args.stdout_format == "json"
    if should_emit_json:
        print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2))

    output_path = args.report
    if output_path is None:
        output_path = root / "reports" / "prd" / f"{ticket}.json"
    output_path = _normalize_output_path(root, output_path)

    previous_payload = None
    if args.emit_patch and output_path.exists():
        try:
            previous_payload = json.loads(output_path.read_text(encoding="utf-8"))
        except Exception:
            previous_payload = None

    output_path.write_text(json.dumps(report.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    rel = _rel_path(root, output_path)
    print(f"[prd-review] report saved to {rel}", file=sys.stderr)
    try:
        from aidd_runtime.reports import events as _events

        _events.append_event(
            root,
            ticket=ticket,
            slug_hint=slug,
            event_type="prd-review",
            status=report.status,
            report_path=Path(rel),
            source="aidd prd-review",
        )
    except Exception as exc:
        print(f"[prd-review] WARN: failed to log event: {exc}", file=sys.stderr)
    pack_path = None
    try:
        from aidd_runtime import reports_pack

        pack_path = reports_pack.write_prd_pack(output_path, root=root)
    except Exception as exc:
        print(f"[prd-review] WARN: failed to generate pack: {exc}", file=sys.stderr)

    if args.emit_patch and previous_payload is not None:
        try:
            from aidd_runtime import json_patch as _json_patch

            patch_ops = _json_patch.diff(previous_payload, report.to_dict())
            patch_path = output_path.with_suffix(".patch.json")
            patch_path.write_text(
                json.dumps(patch_ops, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
        except Exception as exc:
            print(f"[prd-review] WARN: failed to emit patch: {exc}", file=sys.stderr)

    pack_only = bool(args.pack_only or os.getenv("AIDD_PACK_ONLY", "").strip() == "1")
    if pack_only and pack_path and pack_path.exists():
        same_target = False
        try:
            same_target = output_path.resolve() == pack_path.resolve()
        except OSError:
            same_target = output_path == pack_path
        if not same_target:
            with suppress(OSError):
                output_path.unlink()
    docs_only_mode = runtime.docs_only_mode_requested(explicit=getattr(args, "docs_only", False))
    if getattr(args, "require_ready", False) and report.recommended_status != "ready" and not docs_only_mode:
        print(
            "[prd-review] ERROR: report is not ready "
            f"(reason_code=review_not_ready, recommended_status={report.recommended_status})",
            file=sys.stderr,
        )
        return 2
    if getattr(args, "require_ready", False) and report.recommended_status != "ready" and docs_only_mode:
        print(
            "[prd-review] WARN: docs-only rewrite mode bypasses review_not_ready gate "
            f"(recommended_status={report.recommended_status}).",
            file=sys.stderr,
        )
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    args = parse_args(argv)
    return run(args)


if __name__ == "__main__":
    raise SystemExit(main())
