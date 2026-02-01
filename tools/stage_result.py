#!/usr/bin/env python3
"""Write a machine-readable stage result."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Iterable, List, Optional, Tuple

from tools import runtime
from tools.io_utils import dump_yaml, utc_timestamp

DEFAULT_REVIEWER_MARKER = "aidd/reports/reviewer/{ticket}/{scope_key}.json"


def _split_items(values: Iterable[str] | None) -> List[str]:
    items: List[str] = []
    if not values:
        return items
    for raw in values:
        if raw is None:
            continue
        for part in str(raw).replace(",", " ").split():
            part = part.strip()
            if part:
                items.append(part)
    return items


def _dedupe(items: Iterable[str]) -> List[str]:
    seen = set()
    deduped: List[str] = []
    for item in items:
        key = item.strip()
        if not key or key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Write stage result (aidd.stage_result.v1).")
    parser.add_argument("--ticket", help="Ticket identifier (defaults to docs/.active_ticket).")
    parser.add_argument("--slug-hint", help="Optional slug hint override.")
    parser.add_argument("--stage", required=True, choices=("implement", "review", "qa"))
    parser.add_argument("--result", required=True, choices=("blocked", "continue", "done"))
    parser.add_argument("--scope-key", help="Optional scope key override.")
    parser.add_argument("--work-item-key", help="Optional work item key override.")
    parser.add_argument("--reason", default="", help="Optional human-readable reason.")
    parser.add_argument("--reason-code", default="", help="Optional machine-readable reason code.")
    parser.add_argument("--artifact", action="append", help="Artifact path (repeatable).")
    parser.add_argument("--artifacts", action="append", help="Artifacts list (comma/space separated).")
    parser.add_argument("--evidence-link", action="append", help="Evidence link (repeatable).")
    parser.add_argument("--evidence-links", action="append", help="Evidence links list (comma/space separated).")
    parser.add_argument("--producer", default="command", help="Producer label (default: command).")
    parser.add_argument("--format", choices=("json", "yaml"), help="Emit structured output to stdout.")
    return parser.parse_args(argv)


def _reviewer_requirements(
    target: Path,
    *,
    ticket: str,
    slug_hint: Optional[str],
    scope_key: str,
) -> Tuple[bool, bool, str]:
    config = runtime.load_gates_config(target)
    reviewer_cfg = config.get("reviewer") if isinstance(config, dict) else None
    if not isinstance(reviewer_cfg, dict):
        reviewer_cfg = {}
    if reviewer_cfg.get("enabled") is False:
        return False, False, ""
    marker_template = str(
        reviewer_cfg.get("marker")
        or reviewer_cfg.get("tests_marker")
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
        return False, False, ""
    try:
        payload = json.loads(marker_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return False, False, runtime.rel_path(marker_path, target)
    field_name = str(
        reviewer_cfg.get("tests_field")
        or reviewer_cfg.get("field")
        or "tests"
    )
    marker_value = str(payload.get(field_name) or "").strip().lower()
    required_values = reviewer_cfg.get("required_values")
    if required_values is None:
        required_values = reviewer_cfg.get("requiredValues") or ["required"]
    if not isinstance(required_values, list):
        required_values = [required_values]
    required_values = [str(value).strip().lower() for value in required_values if str(value).strip()]
    if marker_value and marker_value in required_values:
        return True, True, runtime.rel_path(marker_path, target)
    return False, False, runtime.rel_path(marker_path, target)


def _tests_policy(
    target: Path,
    *,
    ticket: str,
    slug_hint: Optional[str],
    scope_key: str,
) -> Tuple[bool, bool, str]:
    config = runtime.load_gates_config(target)
    mode = str(config.get("tests_required", "disabled") if isinstance(config, dict) else "disabled").strip().lower()
    require = mode in {"soft", "hard"}
    block = mode == "hard"
    reviewer_required, reviewer_block, marker_source = _reviewer_requirements(
        target,
        ticket=ticket,
        slug_hint=slug_hint,
        scope_key=scope_key,
    )
    if reviewer_required:
        require = True
        block = reviewer_block or block
    return require, block, marker_source


def _resolve_tests_evidence(
    target: Path,
    *,
    ticket: str,
    scope_key: str,
    stage: str,
) -> Tuple[Optional[str], Optional[str]]:
    from tools.reports import tests_log as _tests_log

    stages = [stage]
    if stage == "review":
        stages.append("implement")
    entry, path = _tests_log.latest_entry(target, ticket, scope_key, stages=stages)
    if not path or not path.exists():
        return None, None
    rel_path = runtime.rel_path(path, target)
    entry_id = str(entry.get("updated_at") or entry.get("ts") or "") if entry else ""
    return rel_path, entry_id


def main(argv: list[str] | None = None) -> int:
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

    if stage in {"implement", "review"} and not work_item_key:
        raise ValueError("work_item_key is required for implement/review stage results")

    artifacts = _dedupe(_split_items(args.artifact) + _split_items(args.artifacts))
    evidence_links = _dedupe(_split_items(args.evidence_link) + _split_items(args.evidence_links))
    producer = (args.producer or "command").strip()
    result = (args.result or "").strip().lower()
    requested_result = result
    reason = (args.reason or "").strip()
    reason_code = (args.reason_code or "").strip()

    tests_required, tests_block, marker_source = _tests_policy(
        target,
        ticket=ticket,
        slug_hint=context.slug_hint,
        scope_key=scope_key,
    )
    tests_link, tests_entry = _resolve_tests_evidence(
        target,
        ticket=ticket,
        scope_key=scope_key,
        stage=stage,
    )
    if tests_link:
        evidence_links.append(tests_link)
    if tests_required and not tests_link and not reason_code:
        reason_code = "missing_test_evidence"
        if not reason:
            reason = "tests evidence required but not found"
    if tests_required and tests_block and not tests_link:
        result = "blocked"

    if marker_source and marker_source not in evidence_links:
        evidence_links.append(marker_source)

    payload = {
        "schema": "aidd.stage_result.v1",
        "ticket": ticket,
        "stage": stage,
        "scope_key": scope_key,
        "result": result,
        "requested_result": requested_result,
        "reason": reason,
        "reason_code": reason_code,
        "work_item_key": work_item_key or None,
        "artifacts": artifacts,
        "evidence_links": evidence_links,
        "updated_at": utc_timestamp(),
        "producer": producer,
    }

    output_dir = target / "reports" / "loops" / ticket / scope_key
    output_dir.mkdir(parents=True, exist_ok=True)
    result_path = output_dir / f"stage.{stage}.result.json"
    result_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    rel_path = runtime.rel_path(result_path, target)
    if args.format:
        output = json.dumps(payload, ensure_ascii=False, indent=2) if args.format == "json" else "\n".join(dump_yaml(payload))
        print(output)
        print(f"[stage-result] saved {rel_path}", file=sys.stderr)
        return 0

    print(f"[stage-result] saved {rel_path}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
