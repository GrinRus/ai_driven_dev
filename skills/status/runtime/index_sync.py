#!/usr/bin/env python3
"""Generate derived ticket index files."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
from pathlib import Path
from typing import Dict, Iterable, List, Optional

from aidd_runtime import runtime

SCHEMA = "aidd.ticket.v1"
EVENTS_LIMIT = 5
REQUIRED_FIELDS = [
    "schema",
    "ticket",
    "slug",
    "stage",
    "updated",
    "summary",
    "artifacts",
    "reports",
    "next3",
    "open_questions",
    "risks_top5",
    "checks",
]

SECTION_RE = re.compile(r"^##\s+(AIDD:[A-Z0-9_]+)\b", re.IGNORECASE)
HEADING_RE = re.compile(r"^##\s+")


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""


def _extract_section(md: str, name: str) -> List[str]:
    lines = md.splitlines()
    start = None
    target = name.strip().lower()
    for idx, line in enumerate(lines):
        match = SECTION_RE.match(line.strip())
        if match and match.group(1).strip().lower() == target:
            start = idx + 1
            break
    if start is None:
        return []
    collected: List[str] = []
    for line in lines[start:]:
        if HEADING_RE.match(line):
            break
        if line.strip():
            collected.append(line.strip())
    return collected


def _first_nonempty(lines: Iterable[str]) -> str:
    for line in lines:
        value = line.strip("- ").strip()
        if value:
            return value
    return ""


def _detect_stage(root: Path) -> str:
    return runtime.read_active_stage(root)


def _rel_path(root: Path, path: Path) -> str:
    rel = path.relative_to(root).as_posix()
    if root.name == "aidd":
        return f"aidd/{rel}"
    return rel


def _collect_reports(root: Path, ticket: str) -> List[str]:
    reports = []
    candidates = [
        root / "reports" / "research" / f"{ticket}-rlm-targets.json",
        root / "reports" / "research" / f"{ticket}-rlm-manifest.json",
        root / "reports" / "research" / f"{ticket}-rlm.nodes.jsonl",
        root / "reports" / "research" / f"{ticket}-rlm.links.jsonl",
        root / "reports" / "prd" / f"{ticket}.json",
        root / "reports" / "qa" / f"{ticket}.json",
    ]
    candidates.append(root / "reports" / "research" / f"{ticket}-rlm.pack.json")
    candidates.append(root / "reports" / "research" / f"{ticket}-rlm.worklist.pack.json")
    candidates.append(root / "reports" / "prd" / f"{ticket}.pack.json")
    candidates.append(root / "reports" / "qa" / f"{ticket}.pack.json")
    candidates.append(root / "reports" / "context" / f"{ticket}.pack.md")

    reviewer_dir = root / "reports" / "reviewer" / ticket
    if reviewer_dir.exists():
        candidates.extend(sorted(reviewer_dir.glob("*.json")))
    else:
        candidates.append(root / "reports" / "reviewer" / f"{ticket}.json")

    tests_dir = root / "reports" / "tests" / ticket
    if tests_dir.exists():
        candidates.extend(sorted(tests_dir.glob("*.jsonl")))
    else:
        candidates.append(root / "reports" / "tests" / f"{ticket}.jsonl")
    for path in candidates:
        if path.exists():
            reports.append(_rel_path(root, path))
    return reports


def _read_prd_review_status(root: Path, ticket: str) -> str:
    prd_path = root / "docs" / "prd" / f"{ticket}.prd.md"
    if not prd_path.exists():
        return ""
    try:
        lines = prd_path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return ""
    inside = False
    for raw in lines:
        stripped = raw.strip()
        if stripped.startswith("## "):
            inside = stripped == "## PRD Review"
            continue
        if not inside:
            continue
        lower = stripped.lower()
        if lower.startswith("status:"):
            return stripped.split(":", 1)[1].strip().lower()
    return ""


def _collect_events(root: Path, ticket: str, limit: int = EVENTS_LIMIT) -> List[Dict[str, object]]:
    path = root / "reports" / "events" / f"{ticket}.jsonl"
    if not path.exists():
        return []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    events: List[Dict[str, object]] = []
    for raw in reversed(lines):
        if not raw.strip():
            continue
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            events.append(payload)
        if len(events) >= max(limit, 0):
            break
    return list(reversed(events))


def _find_report_variant(report_path: Path) -> Optional[Path]:
    if report_path.exists():
        return report_path
    if report_path.suffix == ".json":
        candidate = report_path.with_suffix(".pack.json")
        if candidate.exists():
            return candidate
    return None


def _collect_artifacts(root: Path, ticket: str) -> List[str]:
    artifacts = []
    candidates = [
        root / "docs" / "prd" / f"{ticket}.prd.md",
        root / "docs" / "plan" / f"{ticket}.md",
        root / "docs" / "research" / f"{ticket}.md",
        root / "docs" / "spec" / f"{ticket}.spec.yaml",
        root / "docs" / "tasklist" / f"{ticket}.md",
    ]
    for path in candidates:
        if path.exists():
            artifacts.append(_rel_path(root, path))
    return artifacts


def _collect_checks(root: Path, ticket: str) -> List[Dict[str, str]]:
    checks: List[Dict[str, str]] = []
    prd_doc_status = _read_prd_review_status(root, ticket)
    prd_path = _find_report_variant(root / "reports" / "prd" / f"{ticket}.json")
    if prd_path:
        try:
            payload = json.loads(prd_path.read_text(encoding="utf-8"))
            record = {
                "name": "prd-review",
                "status": payload.get("status") or "",
                "path": _rel_path(root, prd_path),
            }
            if prd_doc_status:
                record["doc_status"] = prd_doc_status
            checks.append(record)
        except json.JSONDecodeError:
            pass

    qa_path = _find_report_variant(root / "reports" / "qa" / f"{ticket}.json")
    if qa_path:
        try:
            payload = json.loads(qa_path.read_text(encoding="utf-8"))
            checks.append({
                "name": "qa",
                "status": payload.get("status") or "",
                "path": _rel_path(root, qa_path),
            })
        except json.JSONDecodeError:
            pass

    reviewer_path = root / "reports" / "reviewer" / f"{ticket}.json"
    if reviewer_path.exists():
        checks.append({
            "name": "reviewer-tests",
            "status": "present",
            "path": _rel_path(root, reviewer_path),
        })
    return checks


def build_index(root: Path, ticket: str, slug: str) -> Dict[str, object]:
    tasklist_path = root / "docs" / "tasklist" / f"{ticket}.md"
    prd_path = root / "docs" / "prd" / f"{ticket}.prd.md"

    tasklist_text = _read_text(tasklist_path)
    prd_text = _read_text(prd_path)

    next3 = _extract_section(tasklist_text, "AIDD:NEXT_3")
    open_questions = _extract_section(tasklist_text, "AIDD:OPEN_QUESTIONS")
    if not open_questions:
        open_questions = _extract_section(prd_text, "AIDD:OPEN_QUESTIONS")
    risks_top5 = _extract_section(tasklist_text, "AIDD:RISKS")
    if not risks_top5:
        risks_top5 = _extract_section(prd_text, "AIDD:RISKS")

    context_pack = _extract_section(tasklist_text, "AIDD:CONTEXT_PACK")
    summary = _first_nonempty(context_pack)
    if not summary:
        for line in prd_text.splitlines():
            if line.startswith("# "):
                summary = line.strip("# ").strip()
                break
    if not summary:
        summary = f"{ticket}"

    return {
        "schema": SCHEMA,
        "ticket": ticket,
        "slug": slug,
        "stage": _detect_stage(root),
        "updated": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "summary": summary,
        "artifacts": _collect_artifacts(root, ticket),
        "reports": _collect_reports(root, ticket),
        "next3": next3,
        "open_questions": open_questions,
        "risks_top5": risks_top5,
        "checks": _collect_checks(root, ticket),
        "context_pack": context_pack,
        "events": _collect_events(root, ticket),
    }


def write_index(root: Path, ticket: str, slug: str, *, output: Optional[Path] = None) -> Path:
    index_dir = root / "docs" / "index"
    index_dir.mkdir(parents=True, exist_ok=True)
    path = output or (index_dir / f"{ticket}.json")
    payload = build_index(root, ticket, slug)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Generate/update ticket index file.")
    parser.add_argument("--ticket", help="Ticket identifier (defaults to docs/.active.json).")
    parser.add_argument("--slug-hint", dest="slug_hint", help="Optional slug hint override.")
    parser.add_argument("--slug", help="Optional slug override used in the index file.")
    parser.add_argument("--output", help="Optional output path override.")
    args = parser.parse_args(argv)

    _, root = runtime.require_workflow_root()
    ticket, context = runtime.require_ticket(
        root,
        ticket=getattr(args, "ticket", None),
        slug_hint=getattr(args, "slug_hint", None),
    )
    slug = (args.slug or context.slug_hint or ticket).strip()
    output = Path(args.output) if args.output else None
    if output is not None:
        output = runtime.resolve_path_for_target(output, root)
    index_path = write_index(root, ticket, slug, output=output)
    rel = runtime.rel_path(index_path, root)
    print(f"[aidd] index saved to {rel}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
