#!/usr/bin/env python3
"""Build a review pack from reviewer report."""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

from aidd_runtime import runtime
from aidd_runtime.io_utils import dump_yaml, parse_front_matter, utc_timestamp

DEFAULT_REVIEWER_MARKER = "aidd/reports/reviewer/{ticket}/{scope_key}.tests.json"


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""


def load_loop_pack_meta(root: Path, ticket: str) -> Tuple[str, str, str]:
    stored_ticket = runtime.read_active_ticket(root)
    stored_item = runtime.read_active_work_item(root)
    if not stored_ticket or stored_ticket != ticket or not stored_item:
        return "", "", ""
    scope_key = runtime.resolve_scope_key(stored_item, ticket)
    pack_path = root / "reports" / "loops" / ticket / f"{scope_key}.loop.pack.md"
    if not pack_path.exists():
        return "", "", ""
    front = parse_front_matter(read_text(pack_path))
    work_item_id = front.get("work_item_id", "")
    work_item_key = front.get("work_item_key", "") or stored_item
    scope_key = front.get("scope_key", "") or scope_key
    return work_item_id, work_item_key, scope_key


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
    for key in ("summary", "title", "message", "details", "recommendation"):
        value = entry.get(key)
        if value:
            return normalize_text(value)
    return "n/a"


def normalize_links(entry: Dict[str, object]) -> List[str]:
    links = entry.get("links")
    if isinstance(links, list):
        return [str(item).strip() for item in links if str(item).strip()]
    link = entry.get("link") or entry.get("path") or entry.get("file")
    if link:
        return [str(link).strip()]
    return []


def normalize_finding(entry: Dict[str, object]) -> Dict[str, object]:
    entry_id = str(entry.get("id") or "").strip() or "n/a"
    severity = normalize_severity(entry.get("severity"))
    blocking = entry.get("blocking") is True or severity in {"blocker", "critical", "blocking"}
    return {
        "id": entry_id,
        "summary": finding_summary(entry),
        "severity": severity,
        "blocking": blocking,
        "scope": str(entry.get("scope") or "").strip(),
        "links": normalize_links(entry),
    }


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


def _reviewer_requirements(
    target: Path,
    *,
    ticket: str,
    slug_hint: Optional[str],
    scope_key: str,
) -> Tuple[bool, bool]:
    config = runtime.load_gates_config(target)
    reviewer_cfg = config.get("reviewer") if isinstance(config, dict) else None
    if not isinstance(reviewer_cfg, dict):
        reviewer_cfg = {}
    if reviewer_cfg.get("enabled") is False:
        return False, False
    marker_template = str(
        reviewer_cfg.get("tests_marker")
        or DEFAULT_REVIEWER_MARKER
    )
    marker_path = runtime.reviewer_marker_path(
        target,
        marker_template,
        ticket,
        slug_hint,
        scope_key=scope_key,
    )
    if not marker_path.exists():
        return False, False
    try:
        payload = json.loads(marker_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return False, False
    field_name = str(
        reviewer_cfg.get("tests_field")
        or "tests"
    )
    marker_value = str(payload.get(field_name) or "").strip().lower()
    required_values = reviewer_cfg.get("required_values") or ["required"]
    if not isinstance(required_values, list):
        required_values = [required_values]
    required_values = [str(value).strip().lower() for value in required_values if str(value).strip()]
    if marker_value and marker_value in required_values:
        return True, True
    return False, False


def _tests_policy(
    target: Path,
    *,
    ticket: str,
    slug_hint: Optional[str],
    scope_key: str,
) -> Tuple[bool, bool]:
    config = runtime.load_gates_config(target)
    mode = str(config.get("tests_required", "disabled") if isinstance(config, dict) else "disabled").strip().lower()
    require = mode in {"soft", "hard"}
    block = mode == "hard"
    reviewer_required, reviewer_block = _reviewer_requirements(
        target,
        ticket=ticket,
        slug_hint=slug_hint,
        scope_key=scope_key,
    )
    if reviewer_required:
        require = True
        block = reviewer_block or block
    return require, block


def _tests_entry_has_evidence(entry: Optional[Dict[str, object]]) -> bool:
    if not isinstance(entry, dict):
        return False
    status = str(entry.get("status") or "").strip().lower()
    return status in {"pass", "fail"}


def parse_loop_pack_boundaries(loop_pack_path: Path) -> Dict[str, List[str]]:
    boundaries: Dict[str, List[str]] = {"allowed_paths": [], "forbidden_paths": []}
    if not loop_pack_path.exists():
        return boundaries
    lines = read_text(loop_pack_path).splitlines()
    if not lines or lines[0].strip() != "---":
        return boundaries
    current_list: Optional[str] = None
    in_front = False
    for raw in lines:
        line = raw.rstrip()
        if line.strip() == "---":
            if not in_front:
                in_front = True
                continue
            break
        if not in_front:
            continue
        stripped = line.strip()
        if stripped == "boundaries:":
            current_list = None
            continue
        if stripped == "allowed_paths:":
            current_list = "allowed_paths"
            continue
        if stripped == "forbidden_paths:":
            current_list = "forbidden_paths"
            continue
        if current_list and stripped.startswith("-"):
            value = stripped[1:].strip()
            if value and value != "[]":
                boundaries[current_list].append(value)
    return boundaries


def _normalize_list(raw: object) -> List[str]:
    if raw is None:
        return []
    if isinstance(raw, str):
        items = [raw]
    elif isinstance(raw, list):
        items = raw
    else:
        return []
    return [str(item).strip() for item in items if str(item).strip()]


def normalize_fix_plan(
    raw: object,
    *,
    findings: List[Dict[str, object]],
    boundaries: Dict[str, List[str]],
    review_report: str,
    loop_pack: str,
    missing_tests: bool = False,
) -> Dict[str, object]:
    plan: Dict[str, object] = {}
    if isinstance(raw, dict):
        plan.update(raw)
    steps = _normalize_list(plan.get("steps"))
    commands = _normalize_list(plan.get("commands"))
    tests = _normalize_list(plan.get("tests"))
    expected_paths = _normalize_list(plan.get("expected_paths") or plan.get("expectedPaths"))
    acceptance_check = str(plan.get("acceptance_check") or plan.get("acceptanceCheck") or "").strip()
    links = _normalize_list(plan.get("links"))
    fixes = _normalize_list(plan.get("fixes"))

    blocking_ids = [str(entry.get("id") or "").strip() for entry in findings if entry.get("blocking")]
    blocking_ids = [item for item in blocking_ids if item]
    priority_ids = blocking_ids or [str(entry.get("id") or "").strip() for entry in findings if entry.get("id")]
    priority_ids = [item for item in priority_ids if item]
    for finding_id in blocking_ids:
        if finding_id not in fixes:
            fixes.append(finding_id)
    if not fixes and priority_ids:
        fixes = list(priority_ids)

    if not steps:
        for finding_id in priority_ids:
            steps.append(f"Fix finding {finding_id} (see review report)")

    if missing_tests:
        tests_step = "Run required tests (see AIDD:TEST_EXECUTION)"
        if not any(
            "test" in str(step).lower() or "aidd:test_execution" in str(step).lower()
            for step in steps
        ):
            steps.append(tests_step)

    if not tests:
        tests.append("see AIDD:TEST_EXECUTION")

    if not expected_paths:
        expected_paths = boundaries.get("allowed_paths", [])

    if not acceptance_check:
        if blocking_ids:
            acceptance_check = "Blocking findings resolved: " + ", ".join(blocking_ids)
        elif priority_ids:
            acceptance_check = "Findings resolved: " + ", ".join(priority_ids)
        else:
            acceptance_check = "Findings resolved and review can ship."

    if review_report and review_report not in links:
        links.append(review_report)
    if loop_pack and loop_pack not in links:
        links.append(loop_pack)

    return {
        "steps": steps,
        "commands": commands,
        "tests": tests,
        "expected_paths": expected_paths,
        "acceptance_check": acceptance_check,
        "links": links,
        "fixes": fixes,
    }


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
    review_report_updated_at: str,
    work_item_id: str,
    work_item_key: str,
    scope_key: str,
    findings: List[Dict[str, object]],
    next_actions: List[str],
    review_report: str,
    handoff_ids: List[str],
    blocking_findings_count: int,
    handoff_ids_added: List[str],
    next_recommended_work_item: str,
    evidence_links: List[str],
    fix_plan: Optional[Dict[str, object]] = None,
) -> str:
    lines: List[str] = [
        "---",
        "schema: aidd.review_pack.v2",
        f"updated_at: {updated_at}",
        f"review_report_updated_at: {review_report_updated_at or 'none'}",
        f"ticket: {ticket}",
        f"work_item_id: {work_item_id}",
        f"work_item_key: {work_item_key}",
        f"scope_key: {scope_key}",
        f"verdict: {verdict}",
        f"blocking_findings_count: {blocking_findings_count}",
        "handoff_ids_added:",
    ]
    if handoff_ids_added:
        lines.extend([f"  - {item_id}" for item_id in handoff_ids_added])
    else:
        lines.append("  - []")
    lines.append(f"next_recommended_work_item: {next_recommended_work_item or 'none'}")
    lines.append("evidence_links:")
    if evidence_links:
        lines.extend([f"  - {link}" for link in evidence_links])
    else:
        lines.append("  - []")
    lines.extend(
        [
            "---",
            "",
            f"# Review Pack — {ticket}",
            "",
            "## Verdict",
            f"- {verdict}",
            "",
            "## Operational summary",
            f"- blocking_findings_count: {blocking_findings_count}",
            f"- next_recommended_work_item: {next_recommended_work_item or 'none'}",
            "",
            "## Findings",
        ]
    )
    if findings:
        for entry in findings:
            entry_id = str(entry.get("id") or "n/a")
            severity = normalize_severity(entry.get("severity"))
            summary = str(entry.get("summary") or "")
            blocking = "true" if entry.get("blocking") else "false"
            scope = str(entry.get("scope") or "")
            links = entry.get("links") if isinstance(entry.get("links"), list) else []
            lines.append(f"- id: {entry_id}")
            if summary:
                lines.append(f"  - summary: {summary}")
            lines.append(f"  - severity: {severity}")
            lines.append(f"  - blocking: {blocking}")
            if scope:
                lines.append(f"  - scope: {scope}")
            if links:
                lines.append("  - links:")
                for link in links:
                    lines.append(f"    - {link}")
    else:
        lines.append("- none")

    if fix_plan:
        lines.extend(
            [
                "",
                "## Fix Plan",
                "- steps:",
            ]
        )
        for idx, step in enumerate(fix_plan.get("steps", []), start=1):
            lines.append(f"  - {idx}. {step}")
        lines.append("- commands:")
        for cmd in fix_plan.get("commands", []):
            lines.append(f"  - {cmd}")
        lines.append("- tests:")
        for test in fix_plan.get("tests", []):
            lines.append(f"  - {test}")
        lines.append("- expected_paths:")
        for path in fix_plan.get("expected_paths", []):
            lines.append(f"  - {path}")
        acceptance_check = str(fix_plan.get("acceptance_check") or "")
        if acceptance_check:
            lines.append(f"- acceptance_check: {acceptance_check}")
        links = fix_plan.get("links", [])
        if links:
            lines.append("- links:")
            for link in links:
                lines.append(f"  - {link}")
        fixes = fix_plan.get("fixes", [])
        if fixes:
            lines.append("- fixes:")
            for item_id in fixes:
                lines.append(f"  - finding_id={item_id}")
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
    if evidence_links:
        lines.append("- evidence_links:")
        for link in evidence_links:
            lines.append(f"  - {link}")
    return "\n".join(lines).rstrip() + "\n"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate review pack from reviewer report.")
    parser.add_argument("--ticket", help="Ticket identifier to use (defaults to docs/.active.json).")
    parser.add_argument("--slug-hint", help="Optional slug hint override.")
    parser.add_argument("--format", choices=("json", "yaml"), help="Emit structured output to stdout.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    _, target = runtime.require_workflow_root()
    context = runtime.resolve_feature_context(target, ticket=args.ticket, slug_hint=args.slug_hint)
    ticket = (context.resolved_ticket or "").strip()
    if not ticket:
        raise ValueError("feature ticket is required; pass --ticket or set docs/.active.json via /feature-dev-aidd:idea-new.")

    work_item_id, work_item_key, scope_key = load_loop_pack_meta(target, ticket)
    if not work_item_id or not work_item_key:
        raise FileNotFoundError("loop pack metadata not found (run loop-pack and ensure active work_item is set)")
    if not scope_key:
        scope_key = runtime.resolve_scope_key(work_item_key, ticket)

    report_template = runtime.review_report_template(target)
    slug_hint = (context.slug_hint or ticket or "").strip()
    report_text = (
        str(report_template)
        .replace("{ticket}", ticket)
        .replace("{slug}", slug_hint or ticket)
        .replace("{scope_key}", scope_key)
    )
    report_path = runtime.resolve_path_for_target(Path(report_text), target)
    if not report_path.exists():
        raise FileNotFoundError(f"review report not found at {runtime.rel_path(report_path, target)}")

    payload = json.loads(report_path.read_text(encoding="utf-8"))
    report_updated_at = str(payload.get("updated_at") or payload.get("generated_at") or "")
    findings_raw = extract_findings(payload)
    tests_required, tests_block = _tests_policy(
        target,
        ticket=ticket,
        slug_hint=slug_hint,
        scope_key=scope_key,
    )
    tests_entry = None
    try:
        from aidd_runtime.reports import tests_log as _tests_log

        tests_entry, tests_path = _tests_log.latest_entry(
            target,
            ticket,
            scope_key,
            stages=["review", "implement"],
            statuses=("pass", "fail"),
        )
    except Exception:
        tests_entry = None

    tests_evidence = _tests_entry_has_evidence(tests_entry)
    missing_tests = tests_required and not tests_evidence
    findings = [normalize_finding(entry) for entry in findings_raw]
    verdict = verdict_from_status(str(payload.get("status") or ""), findings)
    if missing_tests:
        if tests_block:
            verdict = "BLOCKED"
        elif verdict != "BLOCKED":
            verdict = "REVISE"
    updated_at = utc_timestamp()

    handoff_ids: List[str] = []
    for entry in findings:
        item_id = entry.get("id")
        if item_id:
            handoff_ids.append(str(item_id))
    handoff_ids = list(dict.fromkeys(handoff_ids))[:5]
    handoff_ids_added = list(handoff_ids)

    blocking_findings_count = sum(1 for entry in findings if entry.get("blocking"))

    next_actions: List[str] = []
    for entry in findings_raw:
        action = entry.get("recommendation") or entry.get("title") or entry.get("summary") or entry.get("message") or entry.get("details")
        if action:
            next_actions.append(" ".join(str(action).split()))
    next_actions = list(dict.fromkeys(next_actions))[:5]

    next_recommended_work_item = work_item_key if verdict == "REVISE" else ""
    evidence_links: List[str] = [runtime.rel_path(report_path, target)]
    try:
        from aidd_runtime.reports import tests_log as _tests_log

        tests_entry, tests_path = _tests_log.latest_entry(
            target,
            ticket,
            scope_key,
            stages=["review", "implement"],
            statuses=("pass", "fail"),
        )
        if tests_path and tests_path.exists():
            evidence_links.append(runtime.rel_path(tests_path, target))
    except Exception:
        pass
    evidence_links = list(dict.fromkeys(evidence_links))

    tests_summary = ""
    tests_reason_code = ""
    tests_log_rel = ""
    try:
        from aidd_runtime.reports import tests_log as _tests_log

        summary, reason_code, tests_path, _entry = _tests_log.summarize_tests(
            target,
            ticket,
            scope_key,
            stages=["review", "implement"],
        )
        tests_summary = summary
        tests_reason_code = reason_code
        if tests_path and tests_path.exists():
            tests_log_rel = runtime.rel_path(tests_path, target)
    except Exception:
        pass

    loop_pack_path = target / "reports" / "loops" / ticket / f"{scope_key}.loop.pack.md"
    boundaries = parse_loop_pack_boundaries(loop_pack_path)
    fix_plan_raw = None
    if isinstance(payload, dict):
        fix_plan_raw = payload.get("fix_plan") or payload.get("fixPlan")
    fix_plan = None
    fix_plan_json = ""
    if verdict == "REVISE":
        fix_plan = normalize_fix_plan(
            fix_plan_raw,
            findings=findings,
            boundaries=boundaries,
            review_report=runtime.rel_path(report_path, target),
            loop_pack=runtime.rel_path(loop_pack_path, target) if loop_pack_path.exists() else "",
            missing_tests=missing_tests,
        )

    output_dir = target / "reports" / "loops" / ticket / scope_key
    output_dir.mkdir(parents=True, exist_ok=True)

    if verdict == "REVISE" and fix_plan:
        fix_plan_path = output_dir / "review.fix_plan.json"
        fix_plan_json = runtime.rel_path(fix_plan_path, target)
        evidence_links = list(dict.fromkeys([*evidence_links, fix_plan_json]))

    pack_text = render_pack(
        ticket=ticket,
        verdict=verdict,
        updated_at=updated_at,
        review_report_updated_at=report_updated_at,
        work_item_id=work_item_id,
        work_item_key=work_item_key,
        scope_key=scope_key,
        findings=findings,
        next_actions=next_actions,
        review_report=runtime.rel_path(report_path, target),
        handoff_ids=handoff_ids,
        blocking_findings_count=blocking_findings_count,
        handoff_ids_added=handoff_ids_added,
        next_recommended_work_item=next_recommended_work_item,
        evidence_links=evidence_links,
        fix_plan=fix_plan,
    )

    pack_path = output_dir / "review.latest.pack.md"
    pack_path.write_text(pack_text, encoding="utf-8")
    rel_path = runtime.rel_path(pack_path, target)

    if verdict == "REVISE" and fix_plan:
        fix_plan_payload = {
            "schema": "aidd.review_fix_plan.v1",
            "updated_at": updated_at,
            "ticket": ticket,
            "work_item_key": work_item_key,
            "scope_key": scope_key,
            "fix_plan": fix_plan,
        }
        fix_plan_path.write_text(json.dumps(fix_plan_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    structured = {
        "schema": "aidd.review_pack.v2",
        "updated_at": updated_at,
        "review_report_updated_at": report_updated_at,
        "ticket": ticket,
        "work_item_id": work_item_id,
        "work_item_key": work_item_key,
        "scope_key": scope_key,
        "verdict": verdict,
        "path": rel_path,
        "review_report": runtime.rel_path(report_path, target),
        "findings": findings,
        "next_actions": next_actions,
        "handoff_ids": handoff_ids,
        "blocking_findings_count": blocking_findings_count,
        "handoff_ids_added": handoff_ids_added,
        "next_recommended_work_item": next_recommended_work_item,
        "evidence_links": evidence_links,
        "fix_plan": fix_plan,
        "fix_plan_json": fix_plan_json,
        "tests_summary": tests_summary,
        "tests_reason_code": tests_reason_code,
        "tests_log_path": tests_log_rel,
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
