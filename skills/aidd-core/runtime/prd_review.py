#!/usr/bin/env python3
"""Lightweight PRD review helper for Claude workflow.

The script inspects docs/prd/<ticket>.prd.md, looks for the dedicated
`## PRD Review` section, checks status/action items and surfaces obvious
placeholders (TODO/TBD/<...>) that must be resolved before development.

It produces a structured JSON report that can be stored in aidd/reports/prd/
and optionally prints a concise human-readable summary.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import sys
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Iterable, List, Optional

from aidd_runtime.feature_ids import resolve_aidd_root, resolve_identifiers


def detect_project_root(target: Optional[Path] = None) -> Path:
    base = target or Path.cwd()
    return resolve_aidd_root(base)
DEFAULT_STATUS = "pending"
APPROVED_STATUSES = {"ready"}
BLOCKING_TOKENS = {"blocked", "reject"}
PLACEHOLDER_PATTERN = re.compile(r"<[^>]+>")
REVIEW_SECTION_HEADER = "## PRD Review"


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


def _stable_id(prefix: str, *parts: str) -> str:
    digest = hashlib.sha1()
    digest.update(prefix.encode("utf-8"))
    digest.update(b"|")
    for part in parts:
        digest.update(_normalize_id_text(str(part)).encode("utf-8"))
        digest.update(b"|")
    return digest.hexdigest()[:12]


@dataclass
class Finding:
    severity: str  # critical | major | minor
    title: str
    details: str
    id: str = ""

    def __post_init__(self) -> None:
        if not self.id:
            self.id = _stable_id("prd", self.severity, self.title, self.details)


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
        "--ticket",
        help="Feature ticket to analyse (defaults to docs/.active.json).",
    )
    parser.add_argument(
        "--slug",
        "--slug-hint",
        dest="slug_hint",
        help="Optional slug hint override (defaults to docs/.active.json when available).",
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
    root = detect_project_root()
    ticket, slug_hint = detect_feature(root, getattr(args, "ticket", None), getattr(args, "slug_hint", None))
    if not ticket:
        print(
            "[prd-review] Cannot determine feature ticket. "
            "Pass --ticket or create docs/.active.json.",
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
        try:
            output_path.unlink()
        except OSError:
            pass
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    args = parse_args(argv)
    return run(args)


if __name__ == "__main__":
    raise SystemExit(main())
