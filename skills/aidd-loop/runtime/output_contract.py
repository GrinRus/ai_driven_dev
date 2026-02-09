#!/usr/bin/env python3
"""Validate implement/review/qa output contract and read budget/order."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from aidd_runtime import runtime
from aidd_runtime import status_summary as _status_summary


REQUIRED_FIELDS = {
    "status",
    "work_item_key",
    "artifacts",
    "tests",
    "blockers",
    "next_actions",
    "read_log",
}

FULL_DOC_PREFIXES = (
    "aidd/docs/prd/",
    "aidd/docs/plan/",
    "aidd/docs/tasklist/",
    "aidd/docs/research/",
    "aidd/docs/spec/",
)


def _normalize_line(line: str) -> str:
    return line.strip()


def _parse_fields(text: str) -> Dict[str, str]:
    fields: Dict[str, str] = {}
    patterns = {
        "status": re.compile(r"^Status:\s*(.+)$", re.IGNORECASE),
        "work_item_key": re.compile(r"^Work item key:\s*(.+)$", re.IGNORECASE),
        "artifacts": re.compile(r"^Artifacts updated:\s*(.+)$", re.IGNORECASE),
        "tests": re.compile(r"^Tests:\s*(.+)$", re.IGNORECASE),
        "blockers": re.compile(r"^Blockers/Handoff:\s*(.+)$", re.IGNORECASE),
        "next_actions": re.compile(r"^Next actions:\s*(.+)$", re.IGNORECASE),
        "read_log": re.compile(r"^AIDD:READ_LOG:\s*(.+)$", re.IGNORECASE),
        "actions_log": re.compile(r"^AIDD:ACTIONS_LOG:\s*(.+)$", re.IGNORECASE),
    }
    for raw in text.splitlines():
        line = _normalize_line(raw)
        for key, pattern in patterns.items():
            match = pattern.match(line)
            if match:
                fields[key] = match.group(1).strip()
    return fields


def _parse_read_log(raw: str) -> List[Dict[str, str]]:
    if not raw:
        return []
    parts = [part.strip() for part in raw.split(";") if part.strip()]
    if not parts:
        parts = [raw.strip()]
    entries: List[Dict[str, str]] = []
    for part in parts:
        cleaned = part.lstrip("-").strip()
        reason = ""
        path = cleaned
        match = re.search(r"\(reason:\s*([^)]+)\)", cleaned, re.IGNORECASE)
        if match:
            reason = match.group(1).strip()
            path = cleaned[: match.start()].strip()
        entries.append({"path": path, "reason": reason})
    return entries


def _reason_allows_full_doc(reason: str) -> bool:
    lowered = reason.lower()
    return any(
        token in lowered
        for token in ("missing field", "missing_fields", "missing-fields", "excerpt missing", "missing excerpt")
    )


def _is_full_doc(path: str) -> bool:
    normalized = path.replace("\\", "/")
    return any(normalized.startswith(prefix) for prefix in FULL_DOC_PREFIXES)


def _is_report_path(path: str) -> bool:
    normalized = path.replace("\\", "/")
    return normalized.startswith("aidd/reports/")


def _find_index(entries: List[Dict[str, str]], predicate) -> int:
    for idx, entry in enumerate(entries):
        if predicate(entry):
            return idx
    return -1


def _expected_status(
    target: Path,
    *,
    ticket: str,
    stage: str,
    scope_key: str,
    work_item_key: str,
    stage_result_path: Optional[Path] = None,
) -> Tuple[str, str]:
    if stage_result_path is None:
        stage_result_path = target / "reports" / "loops" / ticket / scope_key / f"stage.{stage}.result.json"
    payload = _status_summary._load_stage_result(stage_result_path)
    if not payload:
        return "", runtime.rel_path(stage_result_path, target)
    status = _status_summary._status_from_result(stage, payload)
    return status, runtime.rel_path(stage_result_path, target)


def check_output_contract(
    *,
    target: Path,
    ticket: str,
    stage: str,
    scope_key: str,
    work_item_key: str,
    log_path: Path,
    stage_result_path: Optional[Path] = None,
    max_read_items: int = 3,
) -> Dict[str, object]:
    text = log_path.read_text(encoding="utf-8", errors="replace") if log_path.exists() else ""
    fields = _parse_fields(text)
    missing = sorted(REQUIRED_FIELDS - set(fields.keys()))
    warnings: List[str] = []

    read_entries = _parse_read_log(fields.get("read_log", ""))
    if not read_entries:
        warnings.append("read_log_missing")
    if max_read_items and len(read_entries) > max_read_items:
        warnings.append("read_log_too_long")

    for entry in read_entries:
        path = entry.get("path") or ""
        reason = entry.get("reason") or ""
        if _is_full_doc(path) and not _reason_allows_full_doc(reason):
            warnings.append("full_doc_without_missing_fields")
        if not _is_report_path(path) and not _is_full_doc(path):
            warnings.append("non_pack_read_log_entry")

    loop_idx = _find_index(read_entries, lambda item: ".loop.pack." in (item.get("path") or ""))
    review_idx = _find_index(read_entries, lambda item: "review.latest.pack" in (item.get("path") or ""))
    context_idx = _find_index(read_entries, lambda item: "/reports/context/" in (item.get("path") or ""))

    if stage in {"implement", "review"}:
        actions_value = str(fields.get("actions_log") or "").strip()
        if not actions_value:
            warnings.append("actions_log_missing")
        elif actions_value.lower() == "n/a":
            warnings.append("actions_log_invalid")
        else:
            actions_path = runtime.resolve_path_for_target(Path(actions_value), target)
            if not actions_path.exists():
                warnings.append("actions_log_path_missing")
        if loop_idx < 0:
            warnings.append("read_order_missing_loop_pack")
        if review_idx >= 0 and loop_idx >= 0 and review_idx < loop_idx:
            warnings.append("read_order_review_before_loop")
        if context_idx >= 0 and loop_idx >= 0 and context_idx < loop_idx:
            warnings.append("read_order_context_before_loop")
        if context_idx >= 0 and review_idx >= 0 and context_idx < review_idx:
            warnings.append("read_order_context_before_review")
    elif stage == "qa":
        actions_value = str(fields.get("actions_log") or "").strip()
        if not actions_value:
            warnings.append("actions_log_missing")
        elif actions_value.lower() == "n/a":
            warnings.append("actions_log_invalid")
        else:
            actions_path = runtime.resolve_path_for_target(Path(actions_value), target)
            if not actions_path.exists():
                warnings.append("actions_log_path_missing")
        if context_idx < 0:
            warnings.append("read_order_missing_context_pack")
        elif context_idx != 0:
            warnings.append("read_order_context_not_first")

    expected_status, stage_result_rel = _expected_status(
        target,
        ticket=ticket,
        stage=stage,
        scope_key=scope_key,
        work_item_key=work_item_key,
        stage_result_path=stage_result_path,
    )
    status_output = fields.get("status", "")
    if expected_status and status_output and expected_status.upper() != status_output.strip().upper():
        warnings.append("status_mismatch_stage_result")

    status = "warn" if warnings or missing else "ok"
    return {
        "schema": "aidd.output_contract.v1",
        "ticket": ticket,
        "stage": stage,
        "scope_key": scope_key,
        "work_item_key": work_item_key or None,
        "log_path": runtime.rel_path(log_path, target) if log_path else "",
        "stage_result_path": stage_result_rel,
        "status": status,
        "reason_code": "output_contract_warn" if status == "warn" else "",
        "missing_fields": missing,
        "warnings": sorted(set(warnings)),
        "status_output": status_output,
        "status_expected": expected_status,
        "read_log": read_entries,
        "actions_log": fields.get("actions_log", ""),
    }


def parse_args(argv: List[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate output contract for implement/review/qa.")
    parser.add_argument("--ticket", help="Ticket identifier (defaults to docs/.active.json).")
    parser.add_argument("--slug-hint", help="Optional slug hint override.")
    parser.add_argument("--stage", required=True, choices=("implement", "review", "qa"))
    parser.add_argument("--scope-key", help="Optional scope key override.")
    parser.add_argument("--work-item-key", help="Optional work item key override.")
    parser.add_argument("--log", dest="log_path", required=True, help="Path to command output log.")
    parser.add_argument("--stage-result", help="Optional stage_result path override.")
    parser.add_argument("--max-read-items", type=int, default=3, help="Max entries allowed in AIDD:READ_LOG.")
    parser.add_argument("--format", choices=("json", "text"), default="json")
    return parser.parse_args(argv)


def main(argv: List[str] | None = None) -> int:
    args = parse_args(argv)
    _, target = runtime.require_workflow_root()
    ticket, context = runtime.require_ticket(
        target,
        ticket=getattr(args, "ticket", None),
        slug_hint=getattr(args, "slug_hint", None),
    )
    stage = (args.stage or "").strip().lower()
    work_item_key = (args.work_item_key or "").strip()
    if stage in {"implement", "review"} and not work_item_key:
        work_item_key = runtime.read_active_work_item(target)
    scope_key = (args.scope_key or "").strip()
    if not scope_key:
        if stage == "qa":
            scope_key = runtime.resolve_scope_key("", ticket)
        else:
            scope_key = runtime.resolve_scope_key(work_item_key, ticket)

    log_path = runtime.resolve_path_for_target(Path(args.log_path), target)
    stage_result_path = runtime.resolve_path_for_target(Path(args.stage_result), target) if args.stage_result else None

    payload = check_output_contract(
        target=target,
        ticket=ticket,
        stage=stage,
        scope_key=scope_key,
        work_item_key=work_item_key,
        log_path=log_path,
        stage_result_path=stage_result_path,
        max_read_items=int(args.max_read_items),
    )
    if args.format == "text":
        print(f"[output-contract] status={payload.get('status')} log={payload.get('log_path')}")
        if payload.get("warnings"):
            print("warnings:")
            for warning in payload.get("warnings"):
                print(f"- {warning}")
        if payload.get("missing_fields"):
            print("missing_fields:")
            for missing in payload.get("missing_fields"):
                print(f"- {missing}")
    else:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
