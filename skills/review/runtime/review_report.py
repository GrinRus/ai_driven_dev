from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from aidd_runtime import runtime

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


def _strip_updated_at(payload: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(payload, dict):
        return {}
    cleaned = dict(payload)
    cleaned.pop("updated_at", None)
    return cleaned


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


def _normalize_severity(value: object) -> str:
    raw = str(value or "").strip().lower()
    return raw or "unknown"


def _extract_summary(entry: Dict[str, Any], fallback: Optional[Dict[str, Any]] = None) -> str:
    for key in ("summary", "title", "message", "details", "recommendation"):
        value = entry.get(key)
        if value:
            return str(value).strip()
    if fallback:
        return _extract_summary(fallback, None)
    return ""


def _extract_links(entry: Dict[str, Any], fallback: Optional[Dict[str, Any]] = None) -> List[str]:
    links = entry.get("links")
    if isinstance(links, list):
        return [str(item).strip() for item in links if str(item).strip()]
    link = entry.get("link") or entry.get("path") or entry.get("file")
    if link:
        return [str(link).strip()]
    if fallback:
        return _extract_links(fallback, None)
    return []


def _normalize_blocking(entry: Dict[str, Any], severity: str) -> bool:
    if entry.get("blocking") is True:
        return True
    if severity in {"blocker", "critical", "blocking"}:
        return True
    return False


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create/update review report with findings (stored in aidd/reports/reviewer/<ticket>/<scope_key>.json).",
    )
    parser.add_argument(
        "--ticket",
        dest="ticket",
        help="Ticket identifier to use (defaults to docs/.active.json).",
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
        help="Optional report path override (default: aidd/reports/reviewer/<ticket>/<scope_key>.json).",
    )
    parser.add_argument(
        "--scope-key",
        help="Optional scope key override (default: derived from work item).",
    )
    parser.add_argument(
        "--work-item-key",
        help="Optional work item key override (iteration_id=... / id=...).",
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
    parser.add_argument(
        "--fix-plan",
        help="Optional JSON object with structured fix plan.",
    )
    parser.add_argument(
        "--fix-plan-file",
        help="Path to JSON file containing structured fix plan.",
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
        raise ValueError("feature ticket is required; pass --ticket or set docs/.active.json via /feature-dev-aidd:idea-new.")

    branch = args.branch or runtime.detect_branch(target)
    work_item_key = (args.work_item_key or runtime.read_active_work_item(target)).strip()
    scope_key = (args.scope_key or runtime.resolve_scope_key(work_item_key, ticket)).strip()
    if not work_item_key:
        raise ValueError("work_item_key is required for review reports (run loop-pack first)")

    def _fmt(text: str) -> str:
        return (
            text.replace("{ticket}", ticket)
            .replace("{slug}", slug_hint or ticket)
            .replace("{branch}", branch or "")
            .replace("{scope_key}", scope_key or runtime.resolve_scope_key(ticket, ticket))
        )

    report_template = args.report or runtime.review_report_template(target)
    if "{scope_key}" not in report_template:
        print(
            "[aidd] WARN: review report template missing {scope_key}; falling back to default template.",
            file=sys.stderr,
        )
        report_template = runtime.DEFAULT_REVIEW_REPORT
    report_text = _fmt(report_template)
    report_path = runtime.resolve_path_for_target(Path(report_text), target)

    if args.findings and args.findings_file:
        raise ValueError("use --findings or --findings-file (not both)")
    if args.fix_plan and args.fix_plan_file:
        raise ValueError("use --fix-plan or --fix-plan-file (not both)")

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

    def _looks_like_report_payload(payload: Dict[str, Any]) -> bool:
        kind = str(payload.get("kind") or "").strip().lower()
        stage = str(payload.get("stage") or "").strip().lower()
        if kind == "review" or stage == "review":
            return True
        if "findings" in payload or "blocking_findings_count" in payload:
            return True
        return False

    existing_payload: Dict[str, Any] = {}
    existing_findings: List[Dict] = []
    existing_updated_at = ""
    if report_path.exists():
        try:
            existing_payload = json.loads(report_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            existing_payload = {}
    if isinstance(existing_payload, dict):
        existing_updated_at = str(existing_payload.get("updated_at") or "")
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

    def _normalize_findings(items: List[Dict]) -> List[Dict]:
        normalized: List[Dict] = []
        for entry in items:
            if not isinstance(entry, dict):
                continue
            item = dict(entry)
            summary = _extract_summary(item)
            if not summary:
                summary = "n/a"
            item["summary"] = summary
            severity = _normalize_severity(item.get("severity"))
            item["severity"] = severity
            scope = str(item.get("scope") or "").strip()
            if scope:
                item["scope"] = scope
            links = _extract_links(item)
            item["links"] = links
            item["blocking"] = _normalize_blocking(item, severity)
            normalized.append(item)
        return normalized

    fix_plan_payload = None
    if args.fix_plan_file:
        try:
            fix_plan_payload = json.loads(Path(args.fix_plan_file).read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSON in --fix-plan-file: {exc}") from exc
    elif args.fix_plan:
        try:
            fix_plan_payload = json.loads(args.fix_plan)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSON for --fix-plan: {exc}") from exc
    elif isinstance(input_payload, dict):
        fix_plan_payload = input_payload.get("fix_plan") or input_payload.get("fixPlan")

    new_findings: List[Dict] = []
    if input_payload is not None:
        new_findings = _extract_findings(input_payload)
        new_findings = _merge_findings(existing_findings, new_findings)

    now = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    record: Dict[str, Any] = dict(existing_payload) if isinstance(existing_payload, dict) else {}
    record.update(
        {
            "ticket": ticket,
            "slug": slug_hint or ticket,
            "kind": "review",
            "stage": "review",
            "scope_key": scope_key,
            "work_item_key": work_item_key,
        }
    )
    if branch:
        record["branch"] = branch
    record.setdefault("generated_at", now)
    if args.status:
        record["status"] = _normalize_status(args.status)
    if args.summary:
        record["summary"] = str(args.summary).strip()
    if fix_plan_payload is not None:
        record["fix_plan"] = fix_plan_payload
    if "tests_summary" not in record:
        try:
            from aidd_runtime.reports import tests_log as _tests_log

            summary, reason_code, tests_path, _entry = _tests_log.summarize_tests(
                target,
                ticket,
                scope_key,
                stages=["review", "implement"],
            )
            record["tests_summary"] = summary
            if reason_code:
                record.setdefault("tests_reason_code", reason_code)
            if tests_path and tests_path.exists():
                record.setdefault("tests_log_path", runtime.rel_path(tests_path, target))
        except Exception:
            pass
    findings_payload: List[Dict] = []
    if new_findings:
        findings_payload = _normalize_findings(new_findings)
    elif "findings" in record:
        findings_payload = _normalize_findings(record.get("findings") or [])
    if findings_payload:
        record["findings"] = findings_payload
    elif "findings" in record:
        record["findings"] = []

    if "findings" in record:
        record["blocking_findings_count"] = sum(
            1 for entry in record.get("findings") or [] if isinstance(entry, dict) and entry.get("blocking")
        )

    record.pop("updated_at", None)
    existing_compare = _strip_updated_at(existing_payload)
    record_compare = _strip_updated_at(record)
    changed = record_compare != existing_compare or not report_path.exists()
    if not existing_updated_at and not changed:
        changed = True

    if changed:
        record["updated_at"] = now
        report_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            report_path.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        except OSError as exc:
            raise RuntimeError("BLOCKED: review_report_write_failed") from exc
    else:
        record["updated_at"] = existing_updated_at or now

    rel_report = runtime.rel_path(report_path, target)
    if changed:
        print(f"[aidd] review report saved to {rel_report}.")
    else:
        print(f"[aidd] review report unchanged ({rel_report}).")
    runtime.maybe_sync_index(target, ticket, slug_hint or None, reason="review-report")

    def _ensure_reviewer_marker() -> None:
        config = runtime.load_gates_config(target)
        reviewer_cfg = config.get("reviewer") if isinstance(config, dict) else None
        if not isinstance(reviewer_cfg, dict):
            reviewer_cfg = {}
        marker_template = str(
            reviewer_cfg.get("tests_marker")
            or reviewer_cfg.get("marker")
            or runtime.DEFAULT_REVIEW_REPORT.replace(".json", ".tests.json")
        )
        marker_path = runtime.reviewer_marker_path(
            target,
            marker_template,
            ticket,
            slug_hint,
            scope_key=scope_key,
        )
        if marker_path.exists():
            return
        field_name = str(
            reviewer_cfg.get("tests_field")
            or reviewer_cfg.get("field")
            or "tests"
        )
        optional_values = reviewer_cfg.get("optional_values") or ["optional", "skipped", "not-required"]
        if not isinstance(optional_values, list):
            optional_values = [optional_values]
        status_value = str(optional_values[0]) if optional_values else "optional"
        payload = {
            "ticket": ticket,
            "slug": slug_hint or ticket,
            field_name: status_value,
            "updated_at": now,
        }
        marker_path.parent.mkdir(parents=True, exist_ok=True)
        marker_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    _ensure_reviewer_marker()

    active_work_item = runtime.read_active_work_item(target).strip()
    if active_work_item and active_work_item == work_item_key:
        loop_pack_path = target / "reports" / "loops" / ticket / f"{scope_key}.loop.pack.md"
        pack_path = target / "reports" / "loops" / ticket / scope_key / "review.latest.pack.md"
        if not loop_pack_path.exists():
            raise RuntimeError("BLOCKED: review_report_write_failed")
        if changed or not pack_path.exists():
            try:
                from aidd_runtime import review_pack as review_pack_module

                review_pack_module.main(["--ticket", ticket])
            except Exception as exc:
                raise RuntimeError("BLOCKED: review_report_write_failed") from exc
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
