#!/usr/bin/env python3
"""Write a machine-readable stage result."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Iterable, List, Optional, Tuple

from aidd_runtime import gates
from aidd_runtime import runtime
from aidd_runtime.io_utils import dump_yaml, parse_front_matter, utc_timestamp

DEFAULT_REVIEWER_MARKER = "aidd/reports/reviewer/{ticket}/{scope_key}.tests.json"


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


def _append_misc_link(links: dict, value: str) -> None:
    if not value:
        return
    misc = links.get("links")
    if not isinstance(misc, list):
        misc = []
    if value not in misc:
        misc.append(value)
    links["links"] = misc


def _parse_evidence_links(values: Iterable[str] | None) -> dict:
    links: dict[str, object] = {}
    extras: List[str] = []
    for item in _split_items(values):
        if "=" in item:
            key, value = item.split("=", 1)
            key = key.strip()
            value = value.strip()
            if key and value:
                links[key] = value
                continue
        extras.append(item)
    if extras:
        links["links"] = _dedupe(extras)
    return links


def _latest_stream_log(root: Path, ticket: str) -> Optional[Path]:
    log_dir = root / "reports" / "loops" / ticket
    if not log_dir.exists():
        return None
    candidates = sorted(log_dir.glob("cli.loop-*.stream.log"))
    if not candidates:
        return None
    return candidates[-1]


def _stream_jsonl_for(stream_log: Path) -> Optional[Path]:
    name = stream_log.name
    if not name.endswith(".stream.log"):
        return None
    candidate = stream_log.with_name(name[: -len(".stream.log")] + ".stream.jsonl")
    if candidate.exists():
        return candidate
    return None


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Write stage result (aidd.stage_result.v1).")
    parser.add_argument("--ticket", help="Ticket identifier (defaults to docs/.active.json).")
    parser.add_argument("--slug-hint", help="Optional slug hint override.")
    parser.add_argument("--stage", required=True, choices=("implement", "review", "qa"))
    parser.add_argument("--result", required=True, choices=("blocked", "continue", "done"))
    parser.add_argument("--scope-key", help="Optional scope key override.")
    parser.add_argument("--work-item-key", help="Optional work item key override.")
    parser.add_argument("--allow-missing-work-item", action="store_true", help="Allow missing work_item_key on early BLOCKED results.")
    parser.add_argument("--reason", default="", help="Optional human-readable reason.")
    parser.add_argument("--reason-code", default="", help="Optional machine-readable reason code.")
    parser.add_argument("--verdict", default="", help="Optional verdict for review stage (SHIP|REVISE|BLOCKED).")
    parser.add_argument("--error", action="append", help="Error string (repeatable).")
    parser.add_argument("--errors", action="append", help="Errors list (comma/space separated).")
    parser.add_argument("--artifact", action="append", help="Artifact path (repeatable).")
    parser.add_argument("--artifacts", action="append", help="Artifacts list (comma/space separated).")
    parser.add_argument("--evidence-link", action="append", help="Evidence link (repeatable, supports key=path).")
    parser.add_argument("--evidence-links", action="append", help="Evidence links list (comma/space separated, supports key=path).")
    parser.add_argument("--producer", default="command", help="Producer label (default: command).")
    parser.add_argument("--format", choices=("json", "yaml"), help="Emit structured output to stdout.")
    return parser.parse_args(argv)


def _reviewer_requirements(
    target: Path,
    *,
    ticket: str,
    slug_hint: Optional[str],
    scope_key: str,
) -> Tuple[bool, bool, bool, str]:
    config = runtime.load_gates_config(target)
    reviewer_cfg = config.get("reviewer") if isinstance(config, dict) else None
    if not isinstance(reviewer_cfg, dict):
        reviewer_cfg = {}
    if reviewer_cfg.get("enabled") is False:
        return False, False, False, ""
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
        return False, False, False, ""
    try:
        payload = json.loads(marker_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return False, False, False, runtime.rel_path(marker_path, target)
    field_name = str(
        reviewer_cfg.get("tests_field")
        or "tests"
    )
    marker_value = str(payload.get(field_name) or "").strip().lower()
    required_values = reviewer_cfg.get("required_values") or ["required"]
    if not isinstance(required_values, list):
        required_values = [required_values]
    required_values = [str(value).strip().lower() for value in required_values if str(value).strip()]
    optional_values = reviewer_cfg.get("optional_values") or ["optional", "skipped", "not-required"]
    if not isinstance(optional_values, list):
        optional_values = [optional_values]
    optional_values = [str(value).strip().lower() for value in optional_values if str(value).strip()]
    optional_overrides = set(optional_values + ["not-required", "not_required", "none"])
    if marker_value and marker_value in required_values:
        return True, True, False, runtime.rel_path(marker_path, target)
    if marker_value and marker_value in optional_overrides:
        return False, False, True, runtime.rel_path(marker_path, target)
    return False, False, False, runtime.rel_path(marker_path, target)


def _tests_policy(
    target: Path,
    *,
    ticket: str,
    slug_hint: Optional[str],
    scope_key: str,
    stage: str,
) -> Tuple[bool, bool, str]:
    config = runtime.load_gates_config(target)
    mode = str(config.get("tests_required", "disabled") if isinstance(config, dict) else "disabled").strip().lower()
    require = mode in {"soft", "hard"}
    block = mode == "hard"

    stage_policy = gates.resolve_stage_tests_policy(config if isinstance(config, dict) else {}, stage)
    if stage_policy == "none":
        return False, False, ""
    if stage_policy == "full":
        require = True
        block = True
    elif stage_policy == "targeted":
        require = True

    reviewer_required, reviewer_block, reviewer_not_required, marker_source = _reviewer_requirements(
        target,
        ticket=ticket,
        slug_hint=slug_hint,
        scope_key=scope_key,
    )
    if reviewer_not_required:
        return False, False, marker_source
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
) -> Tuple[Optional[str], bool, Optional[dict]]:
    from aidd_runtime.reports import tests_log as _tests_log

    stages = [stage]
    if stage == "review":
        stages.append("implement")
    entry, path = _tests_log.latest_entry(
        target,
        ticket,
        scope_key,
        stages=stages,
        statuses=("pass", "fail"),
    )
    if entry and path and path.exists():
        return runtime.rel_path(path, target), True, entry
    entry, path = _tests_log.latest_entry(
        target,
        ticket,
        scope_key,
        stages=stages,
        statuses=None,
    )
    if not path or not path.exists():
        return None, False, None
    return runtime.rel_path(path, target), False, entry


def _load_review_pack_verdict(target: Path, ticket: str, scope_key: str) -> str:
    pack_path = target / "reports" / "loops" / ticket / scope_key / "review.latest.pack.md"
    if not pack_path.exists():
        return ""
    front = parse_front_matter(pack_path.read_text(encoding="utf-8"))
    verdict = str(front.get("verdict") or "").strip().upper()
    return verdict if verdict in {"SHIP", "REVISE", "BLOCKED"} else ""


def _load_qa_report_status(target: Path, ticket: str) -> str:
    report_path = target / "reports" / "qa" / f"{ticket}.json"
    if not report_path.exists():
        return ""
    try:
        payload = json.loads(report_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return ""
    status = str(payload.get("status") or "").strip().upper()
    return status if status in {"READY", "WARN", "BLOCKED"} else ""


def _review_context_pack_placeholder(target: Path, ticket: str) -> bool:
    pack_path = target / "reports" / "context" / f"{ticket}.pack.md"
    if not pack_path.exists():
        return False
    try:
        content = pack_path.read_text(encoding="utf-8")
    except OSError:
        return False
    return "<stage-specific goal>" in content


def _normalize_work_item_key(value: str) -> str:
    raw = str(value or "").strip()
    if raw.startswith("id="):
        suffix = raw[3:]
        if suffix.startswith("iteration_id="):
            return suffix
        if suffix.startswith("iteration_id_"):
            return f"iteration_id={suffix[len('iteration_id_'):]}"
    return raw


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    _, target = runtime.require_workflow_root()
    ticket, context = runtime.require_ticket(
        target,
        ticket=getattr(args, "ticket", None),
        slug_hint=getattr(args, "slug_hint", None),
    )

    stage = (args.stage or "").strip().lower()
    work_item_key = _normalize_work_item_key(args.work_item_key or "")
    if stage in {"implement", "review"} and not work_item_key:
        work_item_key = _normalize_work_item_key(runtime.read_active_work_item(target))
    scope_key = (args.scope_key or "").strip()
    if stage in {"implement", "review"} and work_item_key:
        scope_key = runtime.resolve_scope_key(work_item_key, ticket)
    if not scope_key:
        if stage == "qa":
            scope_key = runtime.resolve_scope_key("", ticket)
        else:
            scope_key = runtime.resolve_scope_key(work_item_key, ticket)

    if stage in {"implement", "review"}:
        if work_item_key and not runtime.is_valid_work_item_key(work_item_key):
            raise ValueError("work_item_key must match iteration_id=<id> or id=<id> (no composite keys)")
        if not work_item_key and not args.allow_missing_work_item:
            raise ValueError("work_item_key is required for implement/review stage results")

    artifacts = _dedupe(_split_items(args.artifact) + _split_items(args.artifacts))
    errors = _dedupe(_split_items(args.error) + _split_items(args.errors))
    evidence_links = _parse_evidence_links(_split_items(args.evidence_link) + _split_items(args.evidence_links))
    producer = (args.producer or "command").strip()
    result = (args.result or "").strip().lower()
    requested_result = result
    reason = (args.reason or "").strip()
    reason_code = (args.reason_code or "").strip().lower()
    verdict = (args.verdict or "").strip().upper()
    explicit_blocked_review = stage == "review" and (requested_result == "blocked" or verdict == "BLOCKED")

    tests_required, tests_block, marker_source = _tests_policy(
        target,
        ticket=ticket,
        slug_hint=context.slug_hint,
        scope_key=scope_key,
        stage=stage,
    )
    pack_verdict = ""
    context_pack_missing = False
    context_pack_placeholder = False
    if stage == "review":
        pack_verdict = _load_review_pack_verdict(target, ticket, scope_key)
        context_pack_path = target / "reports" / "context" / f"{ticket}.pack.md"
        if not context_pack_path.exists():
            context_pack_missing = True
        else:
            context_pack_placeholder = _review_context_pack_placeholder(target, ticket)
    qa_report_status = ""
    if stage == "qa":
        qa_report_status = _load_qa_report_status(target, ticket)
    tests_link, tests_evidence, tests_entry = _resolve_tests_evidence(
        target,
        ticket=ticket,
        scope_key=scope_key,
        stage=stage,
    )
    if tests_link:
        evidence_links.setdefault("tests_log", tests_link)
    no_tests_code = ""
    if tests_required:
        no_tests_code = "no_tests_hard" if tests_block else "no_tests_soft"
    if tests_required and not tests_link:
        try:
            from aidd_runtime.reports import tests_log as _tests_log

            _tests_log.append_log(
                target,
                ticket=ticket,
                slug_hint=context.slug_hint or ticket,
                stage=stage,
                scope_key=scope_key,
                work_item_key=work_item_key or None,
                profile="none",
                tasks=None,
                filters=None,
                exit_code=None,
                log_path=None,
                status="skipped",
                reason_code=no_tests_code or "no_tests",
                reason="tests evidence missing",
                details={"stage_result": True},
                source="stage-result",
                cwd=str(target),
            )
            tests_link = runtime.rel_path(_tests_log.tests_log_path(target, ticket, scope_key), target)
            evidence_links.setdefault("tests_log", tests_link)
        except Exception:
            pass
    skip_reason_code = ""
    skip_reason = ""
    tests_failed = False
    tests_entry_status = ""
    if tests_entry:
        tests_entry_status = str(tests_entry.get("status") or "").strip().lower()
        if tests_entry_status == "fail":
            tests_failed = True
    if tests_entry and not tests_evidence:
        if tests_entry_status in {"skipped", "not-run", "skip"}:
            skip_reason_code = str(tests_entry.get("reason_code") or "").strip().lower() or "tests_skipped"
            skip_reason = str(tests_entry.get("reason") or "").strip()
            if not skip_reason:
                details = tests_entry.get("details")
                if isinstance(details, dict):
                    skip_reason = str(details.get("reason") or "").strip()
    if tests_required and not tests_evidence:
        if not reason_code or reason_code in {skip_reason_code or "", "missing_test_evidence"}:
            reason_code = no_tests_code or "missing_test_evidence"
            if not reason:
                reason = "tests evidence required but not found"
        if skip_reason and reason and skip_reason not in reason:
            reason = f"{reason}; {skip_reason}"
    missing_tests = tests_required and not tests_evidence
    docs_only_skip = skip_reason_code == "docs_only"
    tests_reason_codes = {"missing_test_evidence", "no_tests_soft", "no_tests_hard"}
    if skip_reason_code:
        tests_reason_codes.add(skip_reason_code)
    tests_reason = bool(reason_code and reason_code in tests_reason_codes)
    if missing_tests:
        if tests_block and not docs_only_skip:
            result = "blocked"
            if stage == "review":
                verdict = "BLOCKED"
        elif tests_reason:
            if stage == "review":
                if not explicit_blocked_review:
                    result = "continue"
                    verdict = "REVISE"
            elif stage == "implement" and result == "blocked":
                result = "continue"
            elif stage == "qa" and result == "blocked":
                result = "done"

    warn_reason_codes = {
        "out_of_scope_warn",
        "no_boundaries_defined_warn",
        "auto_boundary_extend_warn",
        "review_context_pack_placeholder_warn",
        "fast_mode_warn",
        "output_contract_warn",
    }
    if reason_code in warn_reason_codes and result == "blocked":
        result = "continue"

    if stage == "qa" and qa_report_status:
        if qa_report_status == "BLOCKED":
            result = "blocked"
        elif qa_report_status in {"READY", "WARN"} and result == "blocked" and not missing_tests:
            result = "done"
        if qa_report_status == "BLOCKED":
            if reason_code in {"", "manual_skip"}:
                reason_code = "qa_blocked"
                if not reason:
                    reason = "qa report blocked"
        elif qa_report_status == "WARN":
            if (not reason_code or reason_code == "manual_skip") and not missing_tests:
                reason_code = "qa_warn"
                if not reason:
                    reason = "qa report warn"

    if stage == "qa" and tests_failed:
        result = "blocked"
        if reason_code != "qa_tests_failed":
            if reason:
                if "qa tests failed" not in reason:
                    reason = f"{reason}; qa tests failed"
            else:
                reason = "qa tests failed"
            reason_code = "qa_tests_failed"

    if stage == "review" and context_pack_missing:
        result = "blocked"
        reason_code = "review_context_pack_missing"
        if not reason:
            reason = "review context pack missing"
        verdict = "BLOCKED"
        pack_verdict = ""
    elif stage == "review" and context_pack_placeholder:
        placeholder_reason = "review_context_pack_placeholder_warn"
        if not reason:
            reason = "review context pack placeholder found"
        elif "review context pack placeholder found" not in reason:
            reason = f"{reason}; review context pack placeholder found"
        reason_code = placeholder_reason
        if result == "done":
            result = "continue"
        elif reason_code == placeholder_reason and result == "blocked":
            result = "continue"

    if stage == "review":
        if pack_verdict:
            verdict = pack_verdict
        elif explicit_blocked_review and reason_code not in warn_reason_codes:
            verdict = "BLOCKED"
        if not verdict:
            if result == "done":
                verdict = "SHIP"
            elif result == "continue":
                verdict = "REVISE"
            elif result == "blocked":
                verdict = "BLOCKED"
        if verdict == "SHIP":
            result = "done"
        elif verdict == "REVISE":
            result = "continue"
        elif verdict == "BLOCKED":
            result = "blocked"

    if marker_source and marker_source != evidence_links.get("reviewer_marker"):
        evidence_links["reviewer_marker"] = marker_source

    if stage == "review":
        report_template = runtime.review_report_template(target)
        report_rel = (
            str(report_template)
            .replace("{ticket}", ticket)
            .replace("{slug}", (context.slug_hint or ticket))
            .replace("{scope_key}", scope_key)
        )
        report_path = runtime.resolve_path_for_target(Path(report_rel), target)
        if report_path.exists():
            evidence_links.setdefault("review_report", runtime.rel_path(report_path, target))
        pack_path = target / "reports" / "loops" / ticket / scope_key / "review.latest.pack.md"
        if pack_path.exists():
            evidence_links.setdefault("review_pack", runtime.rel_path(pack_path, target))
        fix_plan_path = target / "reports" / "loops" / ticket / scope_key / "review.fix_plan.json"
        if fix_plan_path.exists():
            evidence_links.setdefault("fix_plan_json", runtime.rel_path(fix_plan_path, target))
    if stage == "qa":
        qa_report_path = target / "reports" / "qa" / f"{ticket}.json"
        if qa_report_path.exists():
            evidence_links.setdefault("qa_report", runtime.rel_path(qa_report_path, target))
        qa_pack_path = qa_report_path.with_suffix(".pack.json")
        if qa_pack_path.exists():
            evidence_links.setdefault("qa_pack", runtime.rel_path(qa_pack_path, target))

    if stage != "qa":
        if "cli_log" not in evidence_links:
            stream_log = _latest_stream_log(target, ticket)
            if stream_log:
                evidence_links["cli_log"] = runtime.rel_path(stream_log, target)
                if "cli_stream" not in evidence_links:
                    stream_jsonl = _stream_jsonl_for(stream_log)
                    if stream_jsonl:
                        evidence_links["cli_stream"] = runtime.rel_path(stream_jsonl, target)
        elif "cli_stream" not in evidence_links:
            cli_log_value = str(evidence_links.get("cli_log") or "")
            if cli_log_value:
                cli_log_path = runtime.resolve_path_for_target(Path(cli_log_value), target)
                stream_jsonl = _stream_jsonl_for(cli_log_path)
                if stream_jsonl:
                    evidence_links["cli_stream"] = runtime.rel_path(stream_jsonl, target)

    if not evidence_links:
        evidence_links = {}

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
        "verdict": verdict or None,
        "artifacts": artifacts,
        "errors": errors,
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
