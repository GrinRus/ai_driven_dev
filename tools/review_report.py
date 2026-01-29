from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from tools import runtime

_STATUS_ALIASES = {
    "ready": "READY",
    "pass": "READY",
    "ok": "READY",
    "ship": "READY",
    "warn": "WARN",
    "warning": "WARN",
    "needs_fixes": "WARN",
    "needs-fixes": "WARN",
    "needs fixes": "WARN",
    "revise": "WARN",
    "blocked": "BLOCKED",
    "fail": "BLOCKED",
    "error": "BLOCKED",
    "blocker": "BLOCKED",
}


def _normalize_status(value: object) -> str:
    raw = str(value or "").strip().lower()
    if not raw:
        return ""
    normalized = _STATUS_ALIASES.get(raw, raw)
    return str(normalized).strip().upper()


def _inflate_columnar(section: object) -> List[Dict]:
    if not isinstance(section, dict):
        return []
    cols = section.get("cols")
    rows = section.get("rows")
    if not isinstance(cols, list) or not isinstance(rows, list):
        return []
    items: List[Dict] = []
    for row in rows:
        if not isinstance(row, list):
            continue
        record: Dict[str, Any] = {}
        for idx, col in enumerate(cols):
            if idx >= len(row):
                break
            record[str(col)] = row[idx]
        if record:
            items.append(record)
    return items


def _stable_finding_id(prefix: str, *parts: object) -> str:
    digest = hashlib.sha1()
    digest.update(prefix.encode("utf-8"))
    for part in parts:
        normalized = " ".join(str(part or "").strip().split())
        digest.update(b"|")
        digest.update(normalized.encode("utf-8"))
    return digest.hexdigest()[:12]


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create/update review report with findings (stored in aidd/reports/reviewer/<ticket>.json).",
    )
    parser.add_argument(
        "--ticket",
        dest="ticket",
        help="Ticket identifier to use (defaults to docs/.active_ticket).",
    )
    parser.add_argument(
        "--slug-hint",
        dest="slug_hint",
        help="Optional slug hint override for report metadata.",
    )
    parser.add_argument(
        "--branch",
        help="Optional branch override for metadata.",
    )
    parser.add_argument(
        "--report",
        help="Optional report path override (default: aidd/reports/reviewer/<ticket>.json).",
    )
    parser.add_argument(
        "--findings",
        help="JSON list of findings or JSON object containing findings.",
    )
    parser.add_argument(
        "--findings-file",
        help="Path to JSON file containing findings list or full report payload.",
    )
    parser.add_argument(
        "--status",
        help="Review status label to store (READY|WARN|BLOCKED).",
    )
    parser.add_argument(
        "--summary",
        help="Optional summary for the review report.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    _, target = runtime.require_workflow_root()

    context = runtime.resolve_feature_context(
        target,
        ticket=getattr(args, "ticket", None),
        slug_hint=getattr(args, "slug_hint", None),
    )
    ticket = (context.resolved_ticket or "").strip()
    slug_hint = (context.slug_hint or ticket or "").strip()
    if not ticket:
        raise ValueError("feature ticket is required; pass --ticket or set docs/.active_ticket via /feature-dev-aidd:idea-new.")

    branch = args.branch or runtime.detect_branch(target)

    def _fmt(text: str) -> str:
        return (
            text.replace("{ticket}", ticket)
            .replace("{slug}", slug_hint or ticket)
            .replace("{branch}", branch or "")
        )

    report_template = args.report or runtime.review_report_template(target)
    report_text = _fmt(report_template)
    report_path = runtime.resolve_path_for_target(Path(report_text), target)

    if args.findings and args.findings_file:
        raise ValueError("use --findings or --findings-file (not both)")

    input_payload = None
    if args.findings_file:
        try:
            input_payload = json.loads(Path(args.findings_file).read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSON in --findings-file: {exc}") from exc
    elif args.findings:
        try:
            input_payload = json.loads(args.findings)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSON for --findings: {exc}") from exc
    elif not args.status and not args.summary:
        raise ValueError("provide --findings or --findings-file, or update --status/--summary")

    def _extract_findings(raw: object) -> List[Dict]:
        if raw is None:
            return []
        if isinstance(raw, dict) and "findings" in raw:
            raw = raw.get("findings")
        if isinstance(raw, dict) and raw.get("cols") and raw.get("rows"):
            raw = _inflate_columnar(raw)
        if isinstance(raw, dict):
            if any(key in raw for key in ("title", "severity", "details", "recommendation", "scope", "id")):
                raw = [raw]
            else:
                return []
        if isinstance(raw, list):
            return [entry for entry in raw if isinstance(entry, dict)]
        return []

    existing_payload: Dict[str, Any] = {}
    existing_findings: List[Dict] = []
    if report_path.exists():
        try:
            existing_payload = json.loads(report_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            existing_payload = {}
    if isinstance(existing_payload, dict):
        existing_findings = _extract_findings(existing_payload.get("findings"))

    def _normalize_signature_text(value: object) -> str:
        return " ".join(str(value or "").strip().split()).lower()

    def _extract_title(entry: Dict, fallback: Optional[Dict[str, Any]] = None) -> str:
        title = entry.get("title") or entry.get("summary") or entry.get("message") or entry.get("details")
        if not title and fallback:
            title = fallback.get("title")
        return str(title or "").strip() or "issue"

    def _extract_scope(entry: Dict, fallback: Optional[Dict[str, Any]] = None) -> str:
        scope = entry.get("scope")
        if not scope and fallback:
            scope = fallback.get("scope")
        return str(scope or "").strip()

    def _normalize_signature(entry: Dict, fallback: Optional[Dict[str, Any]] = None) -> str:
        parts = [
            _normalize_signature_text(_extract_title(entry, fallback)),
            _normalize_signature_text(_extract_scope(entry, fallback)),
            _normalize_signature_text(entry.get("details") or entry.get("recommendation") or entry.get("message") or ""),
        ]
        return "|".join(parts)

    def _stable_id(entry: Dict, fallback: Optional[Dict[str, Any]] = None) -> str:
        return _stable_finding_id("review", _extract_title(entry, fallback), _extract_scope(entry, fallback))

    def _merge_findings(existing: List[Dict], incoming: List[Dict]) -> List[Dict]:
        merged: List[Dict] = []
        by_signature = {
            _normalize_signature(item): item
            for item in existing
            if isinstance(item, dict)
        }
        for entry in incoming:
            if not isinstance(entry, dict):
                continue
            signature = _normalize_signature(entry)
            fallback = by_signature.get(signature)
            item = dict(entry)
            if not item.get("id"):
                item["id"] = _stable_id(item, fallback)
            merged.append(item)
        return merged

    new_findings: List[Dict] = []
    if input_payload is not None:
        new_findings = _extract_findings(input_payload)
        new_findings = _merge_findings(existing_findings, new_findings)

    now = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    record: Dict[str, Any] = existing_payload if isinstance(existing_payload, dict) else {}
    record.update(
        {
            "ticket": ticket,
            "slug": slug_hint or ticket,
            "kind": "review",
            "stage": "review",
            "updated_at": now,
        }
    )
    if branch:
        record["branch"] = branch
    record.setdefault("generated_at", now)
    if args.status:
        record["status"] = _normalize_status(args.status)
    if args.summary:
        record["summary"] = str(args.summary).strip()
    if new_findings:
        record["findings"] = new_findings
    elif "findings" in record:
        record["findings"] = record.get("findings") or []

    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    rel_report = runtime.rel_path(report_path, target)
    print(f"[aidd] review report saved to {rel_report}.")
    runtime.maybe_sync_index(target, ticket, slug_hint or None, reason="review-report")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
