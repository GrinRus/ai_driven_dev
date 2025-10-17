#!/usr/bin/env python3
"""Lightweight PRD review helper for Claude workflow.

The script inspects docs/prd/<slug>.prd.md, looks for the dedicated
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

ROOT_DIR = Path.cwd()
DEFAULT_STATUS = "pending"
APPROVED_STATUSES = {"approved"}
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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Perform lightweight PRD review heuristics."
    )
    parser.add_argument("--slug", help="Feature slug to analyse (defaults to docs/.active_feature).")
    parser.add_argument(
        "--prd",
        type=Path,
        help="Explicit path to PRD file. Defaults to docs/prd/<slug>.prd.md.",
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
    return parser.parse_args()


def detect_slug(explicit: Optional[str]) -> Optional[str]:
    if explicit:
        value = explicit.strip()
        return value or None
    slug_path = ROOT_DIR / "docs" / ".active_feature"
    if not slug_path.exists():
        return None
    try:
        raw = slug_path.read_text(encoding="utf-8").strip()
    except OSError:
        return None
    return raw or None


def locate_prd(slug: str, explicit: Optional[Path]) -> Path:
    if explicit:
        return explicit
    return ROOT_DIR / "docs" / "prd" / f"{slug}.prd.md"


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


def analyse_prd(slug: str, prd_path: Path) -> Report:
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
                details="Укажите Status: approved после ревью.",
            )
        )

    if status in BLOCKING_TOKENS:
        findings.append(
            Finding(
                severity="critical",
                title="PRD Review помечен как blocked",
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

    return Report(
        slug=slug,
        status=status or DEFAULT_STATUS,
        recommended_status=recomputed_status,
        findings=findings,
        action_items=action_items,
        generated_at=dt.datetime.utcnow().isoformat(timespec="seconds") + "Z",
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


def main() -> None:
    args = parse_args()
    slug = detect_slug(args.slug)
    if not slug:
        raise SystemExit("[prd-review] Cannot determine feature slug. Pass --slug or create docs/.active_feature.")

    prd_path = locate_prd(slug, args.prd)
    report = analyse_prd(slug, prd_path)

    if args.emit_text or args.stdout_format in ("text", "auto"):
        print_text = args.emit_text or args.stdout_format == "text"
    else:
        print_text = False

    if print_text:
        print_text_report(report)

    should_emit_json = (args.stdout_format in ("json", "auto") and not print_text) or args.stdout_format == "json"
    if should_emit_json:
        print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2))

    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
