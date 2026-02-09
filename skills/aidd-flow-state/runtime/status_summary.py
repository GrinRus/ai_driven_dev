#!/usr/bin/env python3
"""Summarize stage result status for implement/review/qa."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Dict, Optional

from aidd_runtime import runtime


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Summarize stage result status for a ticket.")
    parser.add_argument("--ticket", help="Ticket identifier (defaults to docs/.active.json).")
    parser.add_argument("--slug-hint", help="Optional slug hint override.")
    parser.add_argument("--stage", choices=("implement", "review", "qa"), help="Stage name to summarize.")
    parser.add_argument("--scope-key", help="Optional scope key override.")
    parser.add_argument("--work-item-key", help="Optional work item key override.")
    parser.add_argument("--format", choices=("json",), help="Emit structured output to stdout.")
    return parser.parse_args(argv)


def _load_stage_result(path: Path) -> Optional[Dict[str, object]]:
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    if str(payload.get("schema") or "") != "aidd.stage_result.v1":
        return None
    return payload


def _status_from_result(stage: str, payload: Dict[str, object]) -> str:
    result = str(payload.get("result") or "").strip().lower()
    verdict = str(payload.get("verdict") or "").strip().upper()
    if stage == "review" and verdict in {"SHIP", "REVISE", "BLOCKED"}:
        if verdict == "SHIP":
            return "READY"
        if verdict == "REVISE":
            return "WARN"
        return "BLOCKED"
    if result == "done":
        return "READY"
    if result == "continue":
        return "WARN"
    return "BLOCKED"


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    _, target = runtime.require_workflow_root()
    ticket, context = runtime.require_ticket(
        target,
        ticket=getattr(args, "ticket", None),
        slug_hint=getattr(args, "slug_hint", None),
    )
    stage = (args.stage or "").strip().lower()
    if not stage:
        stage = runtime.read_active_stage(target)
    if stage not in {"implement", "review", "qa"}:
        raise ValueError("stage is required (implement|review|qa)")

    work_item_key = (args.work_item_key or "").strip()
    if stage in {"implement", "review"} and not work_item_key:
        work_item_key = runtime.read_active_work_item(target)

    scope_key = (args.scope_key or "").strip()
    if not scope_key:
        if stage == "qa":
            scope_key = runtime.resolve_scope_key("", ticket)
        else:
            scope_key = runtime.resolve_scope_key(work_item_key, ticket)

    result_path = target / "reports" / "loops" / ticket / scope_key / f"stage.{stage}.result.json"
    payload = _load_stage_result(result_path)
    if not payload:
        summary = {
            "schema": "aidd.status_summary.v1",
            "ticket": ticket,
            "stage": stage,
            "scope_key": scope_key,
            "work_item_key": work_item_key or None,
            "status": "BLOCKED",
            "result": "blocked",
            "reason_code": "stage_result_missing",
            "reason": "stage result missing or invalid",
            "stage_result_path": runtime.rel_path(result_path, target),
        }
        if args.format == "json":
            print(json.dumps(summary, ensure_ascii=False, indent=2))
            return 1
        print(f"Status: {summary['status']}")
        print(f"Stage: {stage}")
        print(f"Work item key: {work_item_key or 'n/a'}")
        print(f"Scope key: {scope_key or 'n/a'}")
        print(f"Reason code: {summary['reason_code']}")
        print(f"Reason: {summary['reason']}")
        print(f"Stage result: {summary['stage_result_path']}")
        return 1

    status = _status_from_result(stage, payload)
    reason_code = str(payload.get("reason_code") or "").strip()
    reason = str(payload.get("reason") or "").strip()

    tests_summary = ""
    tests_reason_code = ""
    tests_log_rel = ""
    try:
        from aidd_runtime.reports import tests_log as _tests_log

        stages = [stage]
        if stage == "review":
            stages.append("implement")
        summary, summary_reason_code, tests_path, _entry = _tests_log.summarize_tests(
            target,
            ticket,
            scope_key,
            stages=stages,
        )
        tests_summary = summary
        tests_reason_code = summary_reason_code
        if tests_path and tests_path.exists():
            tests_log_rel = runtime.rel_path(tests_path, target)
    except Exception:
        pass

    summary = {
        "schema": "aidd.status_summary.v1",
        "ticket": ticket,
        "stage": stage,
        "scope_key": scope_key,
        "work_item_key": work_item_key or None,
        "status": status,
        "result": str(payload.get("result") or ""),
        "verdict": str(payload.get("verdict") or "") or None,
        "reason_code": reason_code or None,
        "reason": reason or None,
        "tests": {
            "summary": tests_summary or None,
            "reason_code": tests_reason_code or None,
            "log_path": tests_log_rel or None,
        },
        "stage_result_path": runtime.rel_path(result_path, target),
    }

    if args.format == "json":
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return 0

    print(f"Status: {status}")
    print(f"Stage: {stage}")
    print(f"Work item key: {work_item_key or 'n/a'}")
    print(f"Scope key: {scope_key or 'n/a'}")
    result_line = str(payload.get("result") or "").strip().lower() or "n/a"
    verdict = str(payload.get("verdict") or "").strip().upper()
    if verdict:
        result_line = f"{result_line} (verdict={verdict})"
    print(f"Stage result: {result_line}")
    if reason_code:
        print(f"Reason code: {reason_code}")
    if reason:
        print(f"Reason: {reason}")
    if tests_summary:
        tests_line = f"{tests_summary}"
        if tests_reason_code:
            tests_line += f" (reason_code={tests_reason_code})"
        if tests_log_rel:
            tests_line += f" log={tests_log_rel}"
        print(f"Tests: {tests_line}")
    else:
        print("Tests: n/a")
    print(f"Stage result path: {runtime.rel_path(result_path, target)}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
