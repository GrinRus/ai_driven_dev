#!/usr/bin/env python3
"""Validate implement/review/qa output contract and read budget/order."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from aidd_runtime import ast_index
from aidd_runtime import context_quality
from aidd_runtime import gates
from aidd_runtime import memory_common
from aidd_runtime import runtime
from aidd_runtime import stage_lexicon
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
_REASON_CODE_RE = re.compile(r"reason_code\s*=\s*([a-z0-9_:-]+)", re.IGNORECASE)
AST_REASON_CODES = {
    ast_index.REASON_BINARY_MISSING,
    ast_index.REASON_INDEX_MISSING,
    ast_index.REASON_TIMEOUT,
    ast_index.REASON_JSON_INVALID,
    ast_index.REASON_FALLBACK_RG,
}


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


def _is_memory_pack(path: str) -> bool:
    normalized = path.replace("\\", "/")
    return normalized.startswith("aidd/reports/memory/") and normalized.endswith(".pack.json")


def _is_ast_pack(path: str) -> bool:
    normalized = path.replace("\\", "/")
    return normalized.startswith("aidd/reports/research/") and normalized.endswith("-ast.pack.json")


def _extract_reason_codes(reason: str) -> List[str]:
    if not reason:
        return []
    found = {match.group(1).strip().lower() for match in _REASON_CODE_RE.finditer(reason)}
    lowered = reason.lower()
    for code in AST_REASON_CODES:
        if code in lowered:
            found.add(code)
    return sorted(found)


def _ast_next_action(ticket: str, reason_code: str) -> str:
    code = str(reason_code or "").strip().lower()
    if code == ast_index.REASON_BINARY_MISSING:
        return "Install ast-index and run `ast-index rebuild` in workspace root."
    if code == ast_index.REASON_INDEX_MISSING:
        return "Run `ast-index rebuild` in workspace root and rerun the stage."
    if code == ast_index.REASON_TIMEOUT:
        return f"Rerun `python3 ${{CLAUDE_PLUGIN_ROOT}}/skills/researcher/runtime/research.py --ticket {ticket} --auto` after increasing ast_index.timeout_s."
    if code == ast_index.REASON_JSON_INVALID:
        return "Update ast-index to a version that supports `--format json` and rebuild index."
    return f"python3 ${{CLAUDE_PLUGIN_ROOT}}/skills/researcher/runtime/research.py --ticket {ticket} --auto"


def _memory_autoslice_hint(ticket: str, stage: str, scope_key: str) -> str:
    return (
        "python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-memory/runtime/memory_autoslice.py "
        f"--ticket {ticket} --stage {stage} --scope-key {scope_key}"
    )


def _load_memory_slice_gate(target: Path) -> Dict[str, object]:
    try:
        config = gates.load_gates_config(target)
    except Exception:
        config = {}
    memory_cfg = config.get("memory") if isinstance(config.get("memory"), dict) else {}
    raw_mode = str(memory_cfg.get("slice_enforcement") or "warn").strip().lower()
    mode = raw_mode if raw_mode in {"off", "warn", "hard"} else "warn"
    raw_stages = memory_cfg.get("enforce_stages")
    if isinstance(raw_stages, list):
        stages = [
            stage_lexicon.resolve_stage_name(str(item).strip())
            for item in raw_stages
            if str(item).strip()
        ]
        stages = [stage for stage in stages if stage]
    else:
        stages = ["research", "plan", "review-spec", "implement", "review", "qa"]
    try:
        max_age = max(1, int(memory_cfg.get("max_slice_age_minutes") or 240))
    except (TypeError, ValueError):
        max_age = 240
    return {
        "mode": mode,
        "stages": stages,
        "max_slice_age_minutes": max_age,
    }


def _memory_manifest_rel_path(target: Path, ticket: str, stage: str, scope_key: str) -> str:
    manifest_path = memory_common.memory_slices_manifest_path(target, ticket, stage, scope_key)
    return runtime.rel_path(manifest_path, target)


def _parse_timestamp(raw: object) -> Optional[dt.datetime]:
    value = str(raw or "").strip()
    if not value:
        return None
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    try:
        parsed = dt.datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt.timezone.utc)
    return parsed.astimezone(dt.timezone.utc)


def _manifest_age_minutes(path: Path) -> Optional[float]:
    if not path.exists():
        return None
    payload: Dict[str, object] = {}
    try:
        parsed = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(parsed, dict):
            payload = parsed
    except Exception:
        payload = {}
    ts_value = payload.get("updated_at") or payload.get("generated_at")
    ts = _parse_timestamp(ts_value)
    if ts is None:
        try:
            ts = dt.datetime.fromtimestamp(path.stat().st_mtime, tz=dt.timezone.utc)
        except OSError:
            return None
    now = dt.datetime.now(dt.timezone.utc)
    delta = now - ts
    return max(0.0, delta.total_seconds() / 60.0)


def _manifest_is_valid(path: Path) -> bool:
    if not path.exists():
        return False
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return False
    if not isinstance(payload, dict):
        return False
    return str(payload.get("schema") or "").strip() == "aidd.memory.slices.manifest.v1"


def _find_index(entries: List[Dict[str, str]], predicate) -> int:
    for idx, entry in enumerate(entries):
        if predicate(entry):
            return idx
    return -1


def _matches_expected_read_path(target: Path, *, raw_path: str, expected_rel: str) -> bool:
    candidate = str(raw_path or "").strip().replace("\\", "/")
    if not candidate:
        return False
    if candidate == expected_rel:
        return True
    try:
        resolved = runtime.resolve_path_for_target(Path(candidate), target)
        return runtime.rel_path(resolved, target) == expected_rel
    except Exception:
        return False


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
    payload = _status_summary._load_stage_result(stage_result_path, stage)
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
    max_read_items: int = 8,
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
    memory_idx = _find_index(read_entries, lambda item: _is_memory_pack(item.get("path") or ""))
    ast_idx = _find_index(read_entries, lambda item: _is_ast_pack(item.get("path") or ""))
    full_read_idx = _find_index(read_entries, lambda item: _is_full_doc(item.get("path") or ""))

    memory_gate = _load_memory_slice_gate(target)
    memory_policy_mode = str(memory_gate.get("mode") or "warn")
    memory_enforce_stages = {
        stage_lexicon.resolve_stage_name(item) for item in (memory_gate.get("stages") or [])
    }
    memory_enforced = memory_policy_mode != "off" and stage in memory_enforce_stages
    memory_manifest_expected = _memory_manifest_rel_path(target, ticket, stage, scope_key)
    memory_manifest_idx = _find_index(
        read_entries,
        lambda item: _matches_expected_read_path(
            target,
            raw_path=str(item.get("path") or ""),
            expected_rel=memory_manifest_expected,
        ),
    )
    memory_manifest_path = runtime.resolve_path_for_target(Path(memory_manifest_expected), target)
    memory_manifest_exists = _manifest_is_valid(memory_manifest_path)
    memory_manifest_age = _manifest_age_minutes(memory_manifest_path) if memory_manifest_exists else None
    try:
        memory_max_age = int(memory_gate.get("max_slice_age_minutes") or 240)
    except (TypeError, ValueError):
        memory_max_age = 240
    memory_blocked_reason = ""
    memory_next_action = ""
    if memory_enforced:
        if memory_manifest_idx < 0:
            warnings.append("memory_slice_missing")
        if not memory_manifest_exists:
            warnings.append("memory_slice_manifest_missing")
        if memory_manifest_age is not None and memory_manifest_age > float(memory_max_age):
            warnings.append("memory_slice_stale")
        if full_read_idx >= 0 and (memory_manifest_idx < 0 or memory_manifest_idx > full_read_idx):
            warnings.append("memory_slice_missing")
        if memory_policy_mode == "hard":
            if "memory_slice_stale" in warnings:
                memory_blocked_reason = "memory_slice_stale"
            elif "memory_slice_manifest_missing" in warnings:
                memory_blocked_reason = "memory_slice_manifest_missing"
            elif "memory_slice_missing" in warnings:
                memory_blocked_reason = "memory_slice_missing"
            if memory_blocked_reason:
                memory_next_action = _memory_autoslice_hint(ticket, stage, scope_key)

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
        if context_idx >= 0 and memory_idx >= 0 and context_idx < memory_idx:
            warnings.append("read_order_context_before_memory")
        if ast_idx >= 0 and loop_idx >= 0 and ast_idx < loop_idx:
            warnings.append("read_order_ast_before_loop")
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
        if loop_idx >= 0 and review_idx >= 0 and review_idx < loop_idx:
            warnings.append("read_order_review_before_loop")
        if context_idx >= 0 and loop_idx >= 0 and context_idx < loop_idx:
            warnings.append("read_order_context_before_loop")
        if context_idx >= 0 and review_idx >= 0 and context_idx < review_idx:
            warnings.append("read_order_context_before_review")
        if context_idx >= 0 and memory_idx >= 0 and context_idx < memory_idx:
            warnings.append("read_order_context_before_memory")
        if context_idx >= 0 and memory_manifest_idx >= 0 and context_idx < memory_manifest_idx:
            warnings.append("read_order_context_before_memory_slice")

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
    ast_required = False
    try:
        ast_cfg = ast_index.load_ast_index_config(target)
        ast_required = bool(ast_cfg.required) and str(ast_cfg.mode).strip().lower() != "off"
    except Exception:
        ast_required = False
    ast_reason_codes: list[str] = []
    for entry in read_entries:
        reason_codes = _extract_reason_codes(entry.get("reason") or "")
        for code in reason_codes:
            if code in AST_REASON_CODES:
                ast_reason_codes.append(code)
    ast_reason_codes = sorted(set(ast_reason_codes))
    ast_blocked_reason = ""
    ast_next_action = ""
    if ast_reason_codes:
        if ast_required:
            warnings.append("ast_index_required_fallback")
            ast_blocked_reason = ast_reason_codes[0]
            ast_next_action = _ast_next_action(ticket, ast_blocked_reason)
        else:
            warnings.append("ast_index_fallback_warn")

    blocked_reason = memory_blocked_reason or ast_blocked_reason
    status = "blocked" if blocked_reason else ("warn" if warnings or missing else "ok")
    reason_code = blocked_reason if blocked_reason else ("output_contract_warn" if status == "warn" else "")
    next_action = memory_next_action if memory_blocked_reason else ast_next_action
    payload = {
        "schema": "aidd.output_contract.v1",
        "ticket": ticket,
        "stage": stage,
        "scope_key": scope_key,
        "work_item_key": work_item_key or None,
        "log_path": runtime.rel_path(log_path, target) if log_path else "",
        "stage_result_path": stage_result_rel,
        "status": status,
        "reason_code": reason_code,
        "missing_fields": missing,
        "warnings": sorted(set(warnings)),
        "status_output": status_output,
        "status_expected": expected_status,
        "read_log": read_entries,
        "actions_log": fields.get("actions_log", ""),
        "ast_required": ast_required,
        "ast_reason_codes": ast_reason_codes,
        "memory_slice_policy_mode": memory_policy_mode,
        "memory_slice_enforced": memory_enforced,
        "memory_slice_manifest_expected": memory_manifest_expected,
        "memory_slice_manifest_read": memory_manifest_idx >= 0,
        "memory_slice_manifest_exists": memory_manifest_exists,
        "memory_slice_manifest_age_minutes": None if memory_manifest_age is None else round(memory_manifest_age, 3),
        "memory_slice_max_age_minutes": memory_max_age,
        "next_action": next_action,
    }
    try:
        context_quality.update_from_output_contract(
            target,
            ticket=ticket,
            read_entries=read_entries,
            status=str(payload.get("status") or ""),
            reason_code=str(payload.get("reason_code") or ""),
            ast_reason_codes=ast_reason_codes,
            warnings=payload.get("warnings") or [],
        )
    except Exception:
        pass
    return payload


def parse_args(argv: List[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate output contract for implement/review/qa.")
    parser.add_argument("--ticket", help="Ticket identifier (defaults to docs/.active.json).")
    parser.add_argument("--slug-hint", help="Optional slug hint override.")
    parser.add_argument("--stage", required=True, choices=("implement", "review", "qa"))
    parser.add_argument("--scope-key", help="Optional scope key override.")
    parser.add_argument("--work-item-key", help="Optional work item key override.")
    parser.add_argument("--log", dest="log_path", required=True, help="Path to command output log.")
    parser.add_argument("--stage-result", help="Optional stage_result path override.")
    parser.add_argument("--max-read-items", type=int, default=8, help="Max entries allowed in AIDD:READ_LOG.")
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
