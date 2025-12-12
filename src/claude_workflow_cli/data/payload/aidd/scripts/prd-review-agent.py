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
import os
import re
import sys
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Iterable, List, Optional

REPO_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_SRC = Path.cwd() / "src"
for candidate in (REPO_ROOT / "src", WORKSPACE_SRC):
    if candidate.is_dir():
        candidate_str = str(candidate)
        if candidate_str not in sys.path:
            sys.path.insert(0, candidate_str)

try:
    from claude_workflow_cli.feature_ids import resolve_identifiers  # type: ignore
except ImportError:  # pragma: no cover - fallback for standalone usage
    resolve_identifiers = None  # type: ignore

def detect_project_root() -> Path:
    """Prefer the plugin root (aidd) even if workspace-level docs/ exist."""
    cwd = Path.cwd().resolve()
    env_root = os.getenv("CLAUDE_PLUGIN_ROOT")
    project_root = os.getenv("CLAUDE_PROJECT_DIR")
    candidates = []
    if env_root:
        candidates.append(Path(env_root).expanduser().resolve())
    if cwd.name == "aidd":
        candidates.append(cwd)
    candidates.append(cwd / "aidd")
    candidates.append(cwd)
    if project_root:
        candidates.append(Path(project_root).expanduser().resolve())
    for candidate in candidates:
        docs_dir = candidate / "docs"
        if docs_dir.is_dir():
            return candidate
    return cwd


ROOT_DIR = detect_project_root()
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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Perform lightweight PRD review heuristics."
    )
    parser.add_argument(
        "--ticket",
        help="Feature ticket to analyse (defaults to docs/.active_ticket).",
    )
    parser.add_argument(
        "--slug",
        help="Legacy slug hint override (defaults to docs/.active_feature when available).",
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
    return parser.parse_args()


def _read_optional_text(path: Path) -> Optional[str]:
    try:
        value = path.read_text(encoding="utf-8").strip()
    except OSError:
        return None
    return value or None


def detect_feature(ticket_arg: Optional[str], slug_arg: Optional[str]) -> tuple[str, str]:
    ticket_candidate = (ticket_arg or "").strip() or None
    slug_candidate = (slug_arg or "").strip() or None

    if resolve_identifiers is not None:
        identifiers = resolve_identifiers(ROOT_DIR, ticket=ticket_candidate, slug_hint=slug_candidate)
        ticket_resolved = (identifiers.resolved_ticket or "").strip()
        slug_resolved = (identifiers.slug_hint or "").strip()
        if ticket_resolved:
            return ticket_resolved, slug_resolved or ticket_resolved

    if ticket_candidate:
        return ticket_candidate, slug_candidate or ticket_candidate

    ticket_file = ROOT_DIR / "docs" / ".active_ticket"
    slug_file = ROOT_DIR / "docs" / ".active_feature"
    ticket_value = _read_optional_text(ticket_file)
    slug_value = _read_optional_text(slug_file)
    if ticket_value:
        return ticket_value, slug_value or ticket_value
    if slug_value:
        return slug_value, slug_value
    return "", ""


def locate_prd(ticket: str, explicit: Optional[Path]) -> Path:
    if explicit:
        return explicit
    return ROOT_DIR / "docs" / "prd" / f"{ticket}.prd.md"


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


def main() -> None:
    args = parse_args()
    ticket, slug_hint = detect_feature(getattr(args, "ticket", None), getattr(args, "slug", None))
    if not ticket:
        raise SystemExit(
            "[prd-review] Cannot determine feature ticket. "
            "Pass --ticket or create docs/.active_ticket (legacy fallback: docs/.active_feature)."
        )

    slug = slug_hint or ticket
    prd_path = locate_prd(ticket, args.prd)
    report = analyse_prd(slug, prd_path, ticket=ticket)

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
