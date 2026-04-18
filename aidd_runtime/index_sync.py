#!/usr/bin/env python3
"""Generate derived ticket index files."""

from __future__ import annotations

import argparse
import datetime as dt
import json
from contextlib import suppress
import re
from pathlib import Path
from typing import Dict, Iterable, List, Optional

import os
import sys


def _ensure_plugin_root_on_path() -> None:
    env_root = os.environ.get("CLAUDE_PLUGIN_ROOT", "").strip()
    if env_root:
        root = Path(env_root).resolve()
        if (root / "aidd_runtime").is_dir():
            if str(root) not in sys.path:
                sys.path.insert(0, str(root))
            return

    probe = Path(__file__).resolve()
    for parent in (probe.parent, *probe.parents):
        if (parent / "aidd_runtime").is_dir():
            os.environ.setdefault("CLAUDE_PLUGIN_ROOT", str(parent))
            if str(parent) not in sys.path:
                sys.path.insert(0, str(parent))
            return


_ensure_plugin_root_on_path()

from aidd_runtime import runtime
from aidd_runtime import artifact_truth
from aidd_runtime.prd_review_section import extract_prd_review_section

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
OPEN_ITEM_PREFIX_RE = re.compile(r"^(?:[-*+]\s+|\d+\.\s+)")
CHECKBOX_PREFIX_RE = re.compile(r"^\[[ xX]\]\s*")
NONE_VALUES = {"none", "нет", "n/a", "na"}


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


def _normalize_section_item(line: str) -> str:
    normalized = OPEN_ITEM_PREFIX_RE.sub("", line.strip())
    normalized = CHECKBOX_PREFIX_RE.sub("", normalized).strip()
    if normalized.startswith("`") and normalized.endswith("`") and len(normalized) > 1:
        normalized = normalized[1:-1].strip()
    if normalized.startswith("**") and normalized.endswith("**") and len(normalized) > 3:
        normalized = normalized[2:-2].strip()
    if normalized.startswith("__") and normalized.endswith("__") and len(normalized) > 3:
        normalized = normalized[2:-2].strip()
    return normalized


def _extract_open_questions(md: str) -> List[str]:
    collected: List[str] = []
    for raw in _extract_section(md, "AIDD:OPEN_QUESTIONS"):
        stripped = raw.strip()
        if not stripped or stripped.startswith(">"):
            continue
        normalized = _normalize_section_item(stripped)
        if not normalized or normalized.casefold() in NONE_VALUES:
            continue
        collected.append(stripped)
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
        content = prd_path.read_text(encoding="utf-8")
    except OSError:
        return ""
    _, status, _ = extract_prd_review_section(content, normalize_status=lambda value: value.strip().lower())
    return status


def _collect_events(root: Path, ticket: str, limit: int = EVENTS_LIMIT) -> List[Dict[str, object]]:
    path = root / "reports" / "events" / f"{ticket}.jsonl"
    if not path.exists():
        return []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    events: List[Dict[str, object]] = []
    for raw in lines:
        if not raw.strip():
            continue
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            events.append(payload)
    policy = artifact_truth.load_artifact_truth_config(root)
    events = artifact_truth.collapse_events(events, enabled=bool(policy.get("collapse_event_noise", True)))
    if limit <= 0:
        return []
    return events[-max(limit, 0):]


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
        with suppress(json.JSONDecodeError):
            payload = json.loads(prd_path.read_text(encoding="utf-8"))
            record = {
                "name": "prd-review",
                "status": payload.get("status") or "",
                "path": _rel_path(root, prd_path),
            }
            if prd_doc_status:
                record["doc_status"] = prd_doc_status
            checks.append(record)

    qa_path = _find_report_variant(root / "reports" / "qa" / f"{ticket}.json")
    if qa_path:
        with suppress(json.JSONDecodeError):
            payload = json.loads(qa_path.read_text(encoding="utf-8"))
            checks.append(
                {
                    "name": "qa",
                    "status": payload.get("status") or "",
                    "path": _rel_path(root, qa_path),
                }
            )

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
    open_questions = _extract_open_questions(tasklist_text)
    open_questions_source = "tasklist"
    if not open_questions:
        open_questions = _extract_open_questions(prd_text)
        if open_questions:
            open_questions_source = "prd:aidd_open_questions"
    if not open_questions:
        open_questions_source = "none"
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

    reports = _collect_reports(root, ticket)
    truth = artifact_truth.evaluate_artifact_truth(
        root,
        ticket,
        tasklist_text=tasklist_text,
        actual_reports=reports,
    )

    return {
        "schema": SCHEMA,
        "ticket": ticket,
        "slug": slug,
        "stage": _detect_stage(root),
        "updated": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "summary": summary,
        "artifacts": _collect_artifacts(root, ticket),
        "reports": reports,
        "next3": next3,
        "open_questions": open_questions,
        "open_questions_source": open_questions_source,
        "risks_top5": risks_top5,
        "checks": _collect_checks(root, ticket),
        "context_pack": context_pack,
        "events": _collect_events(root, ticket),
        "doc_statuses": truth.get("doc_statuses") or {},
        "expected_reports": truth.get("expected_reports") or [],
        "missing_expected_reports": truth.get("missing_expected_reports") or [],
        "truth_checks": truth.get("truth_checks") or [],
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
