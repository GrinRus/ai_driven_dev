#!/usr/bin/env python3
"""Lightweight PRD review helper for Claude workflow.

The script inspects docs/prd/<ticket>.prd.md, looks for the dedicated
`## PRD Review` section, checks status/action items and surfaces obvious
placeholders (TODO/TBD/<...>) that must be resolved before development.

It produces a structured JSON report that can be stored in reports/prd/
and optionally prints a concise human-readable summary.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Iterable, List, Optional

from claude_workflow_cli.feature_ids import resolve_identifiers
from claude_workflow_cli.paths import AiddRootError, require_aidd_root


def detect_project_root(target: Optional[Path] = None) -> Path:
    base = target or Path.cwd()
    return require_aidd_root(base)
DEFAULT_STATUS = "pending"
APPROVED_STATUSES = {"ready"}
BLOCKING_TOKENS = {"blocked", "reject"}
PLACEHOLDER_PATTERN = re.compile(r"<[^>]+>")
REVIEW_SECTION_HEADER = "## PRD Review"


@dataclass
class Finding:
    severity: str  # critical | major | minor
    title: str
    details: str


@dataclass
class Report:
    ticket: str
    slug: str
    status: str
    recommended_status: str
    findings: List[Finding]
    action_items: List[str]
    generated_at: str

    def to_dict(self) -> dict:
        payload = asdict(self)
        payload["findings"] = [asdict(item) for item in self.findings]
        return payload


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Perform lightweight PRD review heuristics."
    )
    parser.add_argument(
        "--target",
        default=".",
        help="Workspace root (default: current; workflow lives in ./aidd).",
    )
    parser.add_argument(
        "--ticket",
        help="Feature ticket to analyse (defaults to docs/.active_ticket).",
    )
    parser.add_argument(
        "--slug",
        "--slug-hint",
        dest="slug_hint",
        help="Optional slug hint override (defaults to docs/.active_feature when available).",
    )
    parser.add_argument(
        "--prd",
        type=Path,
        help="Explicit path to PRD file. Defaults to docs/prd/<ticket>.prd.md.",
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
    return parser.parse_args(argv)


def _read_optional_text(path: Path) -> Optional[str]:
    try:
        value = path.read_text(encoding="utf-8").strip()
    except OSError:
        return None
    return value or None


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

    ticket_file = root / "docs" / ".active_ticket"
    slug_file = root / "docs" / ".active_feature"
    ticket_value = _read_optional_text(ticket_file)
    slug_value = _read_optional_text(slug_file)
    if ticket_value:
        return ticket_value, slug_value or ticket_value
    if slug_value:
        return slug_value, slug_value
    return "", ""


def locate_prd(root: Path, ticket: str, explicit: Optional[Path]) -> Path:
    if explicit:
        return explicit
    return root / "docs" / "prd" / f"{ticket}.prd.md"


def extract_review_section(content: str) -> tuple[str, List[str]]:
    """Return status string and action items from the PRD Review section."""
    lines = content.splitlines()
    status = DEFAULT_STATUS
    action_items: List[str] = []
    inside_section = False

    for line in lines:
        if line.strip().startswith("## "):
            inside_section = line.strip() == REVIEW_SECTION_HEADER
            continue
        if not inside_section:
            continue

        stripped = line.strip()
        if stripped.lower().startswith("status:"):
            status = stripped.split(":", 1)[1].strip().lower() or DEFAULT_STATUS
        elif stripped.startswith("- ["):
            action_items.append(stripped)
    return status, action_items


def collect_placeholders(content: str) -> Iterable[str]:
    for line in content.splitlines():
        trimmed = line.strip()
        if not trimmed:
            continue
        if "TODO" in trimmed or "TBD" in trimmed:
            yield trimmed
            continue
        if PLACEHOLDER_PATTERN.search(trimmed):
            yield trimmed


def analyse_prd(slug: str, prd_path: Path, *, ticket: Optional[str] = None) -> Report:
    try:
        content = prd_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        raise SystemExit(f"[prd-review] PRD not found: {prd_path}")

    status, action_items = extract_review_section(content)
    findings: List[Finding] = []

    placeholder_hits = list(collect_placeholders(content))
    for item in placeholder_hits:
        findings.append(
            Finding(
                severity="major",
                title="Найдены заглушки в PRD",
                details=item,
            )
        )

    if status not in APPROVED_STATUSES and not placeholder_hits and not action_items:
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

    recomputed_status = status
    if status in BLOCKING_TOKENS:
        recomputed_status = "blocked"
    elif action_items:
        recomputed_status = "pending"
    elif status not in APPROVED_STATUSES:
        recomputed_status = status or DEFAULT_STATUS

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
    try:
        root = detect_project_root(Path(args.target))
    except AiddRootError as exc:
        print(f"[prd-review] {exc}", file=sys.stderr)
        return 2
    ticket, slug_hint = detect_feature(root, getattr(args, "ticket", None), getattr(args, "slug_hint", None))
    if not ticket:
        print(
            "[prd-review] Cannot determine feature ticket. "
            "Pass --ticket or create docs/.active_ticket (legacy fallback: docs/.active_feature).",
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
    if not output_path.is_absolute():
        output_path = root / output_path
    output_path.write_text(json.dumps(report.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    rel = output_path.relative_to(root) if output_path.is_relative_to(root) else output_path
    print(f"[prd-review] report saved to {rel}", file=sys.stderr)
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    args = parse_args(argv)
    return run(args)


if __name__ == "__main__":
    raise SystemExit(main())
