#!/usr/bin/env python3
"""Build a review pack from reviewer report."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

from tools import runtime


def _utc_timestamp() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""


def parse_front_matter(text: str) -> Dict[str, str]:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}
    data: Dict[str, str] = {}
    for line in lines[1:]:
        if line.strip() == "---":
            break
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        data[key.strip()] = value.strip()
    return data


def load_loop_pack_meta(root: Path, ticket: str) -> Tuple[str, str]:
    active_ticket = (root / "docs" / ".active_ticket")
    active_work_item = (root / "docs" / ".active_work_item")
    try:
        stored_ticket = active_ticket.read_text(encoding="utf-8").strip()
    except OSError:
        stored_ticket = ""
    try:
        stored_item = active_work_item.read_text(encoding="utf-8").strip()
    except OSError:
        stored_item = ""
    if not stored_ticket or stored_ticket != ticket or not stored_item:
        return "", ""
    pack_path = root / "reports" / "loops" / ticket / f"{stored_item}.loop.pack.md"
    if not pack_path.exists():
        return "", ""
    front = parse_front_matter(read_text(pack_path))
    return front.get("work_item_id", ""), front.get("work_item_key", "")


def inflate_columnar(section: object) -> List[Dict[str, object]]:
    if not isinstance(section, dict):
        return []
    cols = section.get("cols")
    rows = section.get("rows")
    if not isinstance(cols, list) or not isinstance(rows, list):
        return []
    items: List[Dict[str, object]] = []
    for row in rows:
        if not isinstance(row, list):
            continue
        record: Dict[str, object] = {}
        for idx, col in enumerate(cols):
            if idx >= len(row):
                break
            record[str(col)] = row[idx]
        if record:
            items.append(record)
    return items


def extract_findings(payload: Dict[str, object]) -> List[Dict[str, object]]:
    findings = payload.get("findings")
    if isinstance(findings, dict) and findings.get("cols") and findings.get("rows"):
        return inflate_columnar(findings)
    if isinstance(findings, dict):
        return [findings]
    if isinstance(findings, list):
        return [item for item in findings if isinstance(item, dict)]
    return []


def normalize_text(value: object) -> str:
    return " ".join(str(value or "").strip().split())


def finding_summary(entry: Dict[str, object]) -> str:
    for key in ("recommendation", "title", "summary", "message", "details"):
        value = entry.get(key)
        if value:
            return normalize_text(value)
    return "n/a"


def dedupe_findings(findings: List[Dict[str, object]]) -> List[Dict[str, object]]:
    seen: set[str] = set()
    deduped: List[Dict[str, object]] = []
    for entry in findings:
        entry_id = normalize_text(entry.get("id")) if entry.get("id") else ""
        signature = entry_id or normalize_text(
            "|".join(
                [
                    normalize_text(entry.get("title") or entry.get("summary") or entry.get("message") or ""),
                    normalize_text(entry.get("scope") or ""),
                    normalize_text(entry.get("details") or entry.get("recommendation") or ""),
                ]
            )
        )
        if not signature or signature in seen:
            continue
        seen.add(signature)
        deduped.append(entry)
    return deduped


def normalize_severity(value: object) -> str:
    raw = str(value or "").strip().lower()
    return raw or "unknown"


SEVERITY_ORDER = {
    "critical": 0,
    "blocker": 0,
    "major": 1,
    "high": 1,
    "medium": 2,
    "minor": 3,
    "low": 4,
    "info": 5,
    "unknown": 6,
}


def sort_findings(findings: List[Dict[str, object]]) -> List[Dict[str, object]]:
    def sort_key(item: Dict[str, object]) -> Tuple[int, str]:
        severity = normalize_severity(item.get("severity"))
        return (SEVERITY_ORDER.get(severity, 6), str(item.get("id") or item.get("title") or ""))

    return sorted(findings, key=sort_key)


def verdict_from_status(status: str, findings: List[Dict[str, object]]) -> str:
    status = status.strip().lower()
    if status == "ready":
        return "SHIP"
    if status == "blocked":
        return "BLOCKED"
    if status == "warn":
        return "REVISE"
    if findings:
        return "REVISE"
    return "BLOCKED"


def render_pack(
    *,
    ticket: str,
    verdict: str,
    updated_at: str,
    work_item_id: str,
    work_item_key: str,
    findings: List[Dict[str, object]],
    next_actions: List[str],
    review_report: str,
    handoff_ids: List[str],
) -> str:
    lines: List[str] = [
        "---",
        "schema: aidd.review_pack.v1",
        f"updated_at: {updated_at}",
        f"ticket: {ticket}",
        f"work_item_id: {work_item_id}",
        f"work_item_key: {work_item_key}",
        f"verdict: {verdict}",
        "---",
        "",
        f"# Review Pack — {ticket}",
        "",
        "## Verdict",
        f"- {verdict}",
        "",
        "## Top findings",
    ]
    if findings:
        for entry in findings:
            entry_id = str(entry.get("id") or "n/a")
            severity = normalize_severity(entry.get("severity"))
            requirement = finding_summary(entry)
            lines.append(f"- {entry_id} [{severity}] {requirement}")
    else:
        lines.append("- none")
    lines.extend(
        [
            "",
            "## Next actions",
        ]
    )
    if next_actions:
        for action in next_actions:
            lines.append(f"- {action}")
    else:
        lines.append("- none")
    lines.extend(
        [
            "",
            "## References",
            f"- review_report: {review_report}",
        ]
    )
    if handoff_ids:
        lines.append("- handoff_ids:")
        for item_id in handoff_ids:
            lines.append(f"  - {item_id}")
    return "\n".join(lines).rstrip() + "\n"


def dump_yaml(data: object, indent: int = 0) -> List[str]:
    lines: List[str] = []
    prefix = " " * indent
    if isinstance(data, dict):
        for key, value in data.items():
            if isinstance(value, (dict, list)):
                lines.append(f"{prefix}{key}:")
                lines.extend(dump_yaml(value, indent + 2))
            else:
                lines.append(f"{prefix}{key}: {json.dumps(value)}")
    elif isinstance(data, list):
        for item in data:
            if isinstance(item, (dict, list)):
                lines.append(f"{prefix}-")
                lines.extend(dump_yaml(item, indent + 2))
            else:
                lines.append(f"{prefix}- {json.dumps(item)}")
    else:
        lines.append(f"{prefix}{json.dumps(data)}")
    return lines


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate review pack from reviewer report.")
    parser.add_argument("--ticket", help="Ticket identifier to use (defaults to docs/.active_ticket).")
    parser.add_argument("--slug-hint", help="Optional slug hint override.")
    parser.add_argument("--format", choices=("json", "yaml"), help="Emit structured output to stdout.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    _, target = runtime.require_workflow_root()
    context = runtime.resolve_feature_context(target, ticket=args.ticket, slug_hint=args.slug_hint)
    ticket = (context.resolved_ticket or "").strip()
    if not ticket:
        raise ValueError("feature ticket is required; pass --ticket or set docs/.active_ticket via /feature-dev-aidd:idea-new.")

    report_path = target / "reports" / "reviewer" / f"{ticket}.json"
    if not report_path.exists():
        raise FileNotFoundError(f"review report not found at {runtime.rel_path(report_path, target)}")

    payload = json.loads(report_path.read_text(encoding="utf-8"))
    findings = dedupe_findings(extract_findings(payload))
    findings = sort_findings(findings)[:5]
    verdict = verdict_from_status(str(payload.get("status") or ""), findings)
    updated_at = _utc_timestamp()
    work_item_id, work_item_key = load_loop_pack_meta(target, ticket)
    if not work_item_id or not work_item_key:
        raise FileNotFoundError(
            "loop pack metadata not found (run loop-pack and ensure .active_work_item is set)"
        )

    handoff_ids: List[str] = []
    for entry in findings:
        item_id = entry.get("id")
        if item_id:
            handoff_ids.append(str(item_id))
    handoff_ids = list(dict.fromkeys(handoff_ids))[:5]

    next_actions: List[str] = []
    for entry in findings:
        action = entry.get("recommendation") or entry.get("title") or entry.get("summary") or entry.get("message") or entry.get("details")
        if action:
            next_actions.append(" ".join(str(action).split()))
    next_actions = list(dict.fromkeys(next_actions))[:5]

    pack_text = render_pack(
        ticket=ticket,
        verdict=verdict,
        updated_at=updated_at,
        work_item_id=work_item_id,
        work_item_key=work_item_key,
        findings=findings,
        next_actions=next_actions,
        review_report=runtime.rel_path(report_path, target),
        handoff_ids=handoff_ids,
    )

    output_dir = target / "reports" / "loops" / ticket
    output_dir.mkdir(parents=True, exist_ok=True)
    pack_path = output_dir / "review.latest.pack.md"
    pack_path.write_text(pack_text, encoding="utf-8")
    rel_path = runtime.rel_path(pack_path, target)

    structured = {
        "schema": "aidd.review_pack.v1",
        "updated_at": updated_at,
        "ticket": ticket,
        "work_item_id": work_item_id,
        "work_item_key": work_item_key,
        "verdict": verdict,
        "path": rel_path,
        "review_report": runtime.rel_path(report_path, target),
        "findings": findings,
        "next_actions": next_actions,
        "handoff_ids": handoff_ids,
    }

    if args.format:
        output = json.dumps(structured, ensure_ascii=False, indent=2) if args.format == "json" else "\n".join(dump_yaml(structured))
        print(output)
        print(f"[review-pack] saved {rel_path} (verdict={verdict})", file=sys.stderr)
        return 0

    print(f"[review-pack] saved {rel_path} (verdict={verdict})")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
