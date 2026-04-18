#!/usr/bin/env python3
"""Stage-result and review-pack handlers for loop-step."""

from __future__ import annotations

import datetime as dt
import io
import json
import re
import sys
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from typing import Dict, List, Tuple

from aidd_runtime import runtime
from aidd_runtime import stage_result_contract
from aidd_runtime.io_utils import parse_front_matter
from aidd_runtime import loop_step as core

_ITERATION_SCOPE_ALIAS_RE = re.compile(r"^[IM]\d+$", re.IGNORECASE)
_ITERATION_SCOPE_CANONICAL_RE = re.compile(r"^iteration_id_([IM]\d+)$", re.IGNORECASE)


def stage_result_path(root: Path, ticket: str, scope_key: str, stage: str) -> Path:
    return root / "reports" / "loops" / ticket / scope_key / f"stage.{stage}.result.json"


def _parse_stage_result(path: Path, stage: str) -> Tuple[Dict[str, object] | None, str]:
    if not path.exists():
        return None, "missing"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None, "invalid-json"
    return stage_result_contract.normalize_stage_result_payload(payload, stage)


def _canonical_scope_key(value: str) -> str:
    raw = runtime.sanitize_scope_key(value or "")
    if not raw:
        return ""
    canonical_match = _ITERATION_SCOPE_CANONICAL_RE.match(raw)
    if canonical_match:
        return f"iteration_id_{canonical_match.group(1).upper()}"
    if _ITERATION_SCOPE_ALIAS_RE.match(raw):
        return f"iteration_id_{raw.upper()}"
    return raw


def _candidate_scope(path: Path, payload: Dict[str, object] | None) -> Tuple[str, str]:
    raw = str((payload or {}).get("scope_key") or "").strip() or path.parent.name
    canonical = _canonical_scope_key(raw)
    return raw, canonical


def _scope_status(status: str, scope_raw: str, scope_canonical: str) -> str:
    base = status or "ok"
    if scope_raw and scope_canonical and scope_raw != scope_canonical:
        return f"{base}(scope={scope_raw},canonical={scope_canonical})"
    if scope_raw:
        return f"{base}(scope={scope_raw})"
    return base


def _result_status(payload: Dict[str, object]) -> str:
    result = str(payload.get("result") or "").strip().lower()
    requested = stage_result_contract.normalize_requested_result(payload.get("requested_result"))
    effective = stage_result_contract.effective_stage_result(payload)
    details = [f"result={result or 'unknown'}"]
    if requested:
        details.append(f"requested={requested}")
    if effective and effective != result:
        details.append(f"effective={effective}")
    reason_code = str(payload.get("reason_code") or "").strip().lower()
    if reason_code:
        details.append(f"reason_code={reason_code}")
    return "ok(" + ",".join(details) + ")"


def _select_candidate(
    candidates: List[Tuple[Path, Dict[str, object], str, str]],
    *,
    expected_scope_key: str,
) -> Tuple[Path, Dict[str, object], str, str]:
    expected_raw = str(expected_scope_key or "").strip()
    expected_canonical = _canonical_scope_key(expected_raw)

    pool = list(candidates)
    if expected_raw:
        scoped = []
        for item in pool:
            _path, _payload, scope_raw, scope_canonical = item
            if scope_raw == expected_raw:
                scoped.append(item)
                continue
            if expected_canonical and scope_canonical == expected_canonical:
                scoped.append(item)
        if scoped:
            pool = scoped

    canonical_iteration = [
        item
        for item in pool
        if item[2] == item[3] and item[3].startswith("iteration_id_")
    ]
    if canonical_iteration:
        return canonical_iteration[0]
    return pool[0]


def _collect_stage_result_candidates(root: Path, ticket: str, stage: str) -> List[Path]:
    base = root / "reports" / "loops" / ticket
    if not base.exists():
        return []
    return sorted(
        base.rglob(f"stage.{stage}.result.json"),
        key=lambda candidate: candidate.stat().st_mtime if candidate.exists() else 0.0,
        reverse=True,
    )


def _in_window(path: Path, *, started_at: float | None, finished_at: float | None, tolerance_seconds: float = 5.0) -> bool:
    if started_at is None or finished_at is None:
        return True
    if not path.exists():
        return False
    mtime = path.stat().st_mtime
    return (started_at - tolerance_seconds) <= mtime <= (finished_at + tolerance_seconds)


def _stage_result_diagnostics(candidates: List[Tuple[Path, str]], *, selected: Path | None = None) -> str:
    if not candidates:
        return "candidates=none"
    parts: List[str] = []
    for index, (path, status) in enumerate(candidates[:6]):
        role = "preferred" if index == 0 else "fallback"
        marker = "selected" if selected and path == selected else "candidate"
        timestamp = "n/a"
        if path.exists():
            timestamp = dt.datetime.fromtimestamp(path.stat().st_mtime, tz=dt.timezone.utc).isoformat()
        status_value = status or "ok"
        parts.append(f"{role}:{marker}:{path.as_posix()}:{status_value}@{timestamp}")
    return "candidates=" + ", ".join(parts)


def load_stage_result(
    root: Path,
    ticket: str,
    scope_key: str,
    stage: str,
    *,
    started_at: float | None = None,
    finished_at: float | None = None,
) -> Tuple[Dict[str, object] | None, Path, str, str, str, str]:
    preferred_path = stage_result_path(root, ticket, scope_key, stage)
    preferred_payload, preferred_error = _parse_stage_result(preferred_path, stage)
    if preferred_payload is not None:
        return preferred_payload, preferred_path, "", "", "", ""

    preferred_scope_raw, preferred_scope_canonical = _candidate_scope(preferred_path, None)
    diagnostics: List[Tuple[Path, str]] = [
        (preferred_path, _scope_status(preferred_error, preferred_scope_raw, preferred_scope_canonical))
    ]
    validated: List[Tuple[Path, Dict[str, object], str, str]] = []
    for candidate in _collect_stage_result_candidates(root, ticket, stage):
        if candidate == preferred_path:
            continue
        payload, status = _parse_stage_result(candidate, stage)
        scope_raw, scope_canonical = _candidate_scope(candidate, payload)
        status_value = status
        if payload is not None and not status_value:
            status_value = _result_status(payload)
        diagnostics.append((candidate, _scope_status(status_value, scope_raw, scope_canonical)))
        if payload is None:
            continue
        validated.append((candidate, payload, scope_raw, scope_canonical))

    fresh: List[Tuple[Path, Dict[str, object], str, str]] = []
    for item in validated:
        path = item[0]
        if _in_window(path, started_at=started_at, finished_at=finished_at):
            fresh.append(item)
    selected_pool = fresh or validated
    if not selected_pool:
        return (
            None,
            preferred_path,
            "stage_result_missing_or_invalid",
            "",
            "",
            _stage_result_diagnostics(diagnostics, selected=None),
        )

    selected_path, selected_payload, selected_scope_raw, selected_scope_canonical = _select_candidate(
        selected_pool,
        expected_scope_key=scope_key,
    )
    selected_scope = selected_scope_canonical or selected_scope_raw or selected_path.parent.name
    selected_payload = dict(selected_payload)
    if selected_scope:
        selected_payload["scope_key"] = selected_scope
    selected_effective_result = stage_result_contract.effective_stage_result(selected_payload)
    expected_scope_raw = str(scope_key or "").strip()
    qa_iteration_scope_required = stage == "qa" and expected_scope_raw.startswith("iteration_id_")
    if (
        expected_scope_raw
        and selected_scope
        and selected_scope != expected_scope_raw
        and (
            selected_effective_result == "blocked"
            or qa_iteration_scope_required
        )
    ):
        diagnostics_text = _stage_result_diagnostics(
            diagnostics,
            selected=selected_path,
        )
        marker = (
            f"scope_shape_invalid={selected_scope}"
            if qa_iteration_scope_required
            else f"scope_fallback_stale_ignored={selected_scope}"
        )
        diagnostics_text = f"{diagnostics_text}; {marker}" if diagnostics_text else marker
        return (
            None,
            preferred_path,
            "stage_result_missing_or_invalid",
            "",
            "",
            diagnostics_text,
        )
    mismatch_from = scope_key or ""
    mismatch_to = ""
    if scope_key and selected_scope and selected_scope != scope_key:
        mismatch_to = selected_scope
    return selected_payload, selected_path, "", mismatch_from, mismatch_to, _stage_result_diagnostics(
        diagnostics,
        selected=selected_path,
    )


def normalize_stage_result(result: str, reason_code: str) -> str:
    if reason_code in core.HARD_BLOCK_REASON_CODES:
        return "blocked"
    if result == "blocked" and reason_code in core.WARN_REASON_CODES:
        return "continue"
    return result


def review_pack_v2_required(root: Path) -> bool:
    config = runtime.load_gates_config(root)
    if not isinstance(config, dict):
        return False
    raw = config.get("review_pack_v2_required")
    if raw is None:
        return False
    if isinstance(raw, str):
        return raw.strip().lower() in {"1", "true", "yes", "block", "strict"}
    return bool(raw)


def parse_timestamp(value: str) -> dt.datetime | None:
    if not value:
        return None
    raw = value.strip()
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    try:
        return dt.datetime.fromisoformat(raw)
    except ValueError:
        return None


def resolve_review_report_path(root: Path, ticket: str, slug_hint: str, scope_key: str) -> Path:
    template = runtime.review_report_template(root)
    rel_text = (
        str(template)
        .replace("{ticket}", ticket)
        .replace("{slug}", slug_hint or ticket)
        .replace("{scope_key}", scope_key)
    )
    return runtime.resolve_path_for_target(Path(rel_text), root)


def _maybe_regen_review_pack(
    root: Path,
    *,
    ticket: str,
    slug_hint: str,
    scope_key: str,
) -> Tuple[bool, str]:
    report_path = resolve_review_report_path(root, ticket, slug_hint, scope_key)
    if not report_path.exists():
        return False, "review report missing"
    loop_pack_path = root / "reports" / "loops" / ticket / f"{scope_key}.loop.pack.md"
    if not loop_pack_path.exists():
        return False, "loop pack missing"
    try:
        from aidd_runtime import review_pack as review_pack_module

        args = ["--ticket", ticket]
        if slug_hint:
            args.extend(["--slug-hint", slug_hint])
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            review_pack_module.main(args)
    except Exception as exc:
        return False, f"review pack regen failed: {exc}"
    pack_path = root / "reports" / "loops" / ticket / scope_key / "review.latest.pack.md"
    if not pack_path.exists():
        return False, "review pack missing"
    return True, ""


def validate_review_pack(
    root: Path,
    *,
    ticket: str,
    slug_hint: str,
    scope_key: str,
) -> Tuple[bool, str, str]:
    pack_path = root / "reports" / "loops" / ticket / scope_key / "review.latest.pack.md"
    if not pack_path.exists():
        ok, regen_message = _maybe_regen_review_pack(
            root,
            ticket=ticket,
            slug_hint=slug_hint,
            scope_key=scope_key,
        )
        if ok:
            pack_path = root / "reports" / "loops" / ticket / scope_key / "review.latest.pack.md"
        else:
            reason = regen_message or "review pack missing"
            missing_reasons = {
                "review report missing",
                "loop pack missing",
                "review pack missing",
            }
            code = "review_pack_missing" if reason in missing_reasons else "review_pack_regen_failed"
            return False, reason, code
    lines = pack_path.read_text(encoding="utf-8").splitlines()
    front = parse_front_matter(lines)
    schema = str(front.get("schema") or "").strip()
    if schema not in {"aidd.review_pack.v1", "aidd.review_pack.v2"}:
        return False, "review pack schema invalid", "review_pack_invalid_schema"
    if schema == "aidd.review_pack.v1" and review_pack_v2_required(root):
        return False, "review pack v2 required", "review_pack_v2_required"
    if schema == "aidd.review_pack.v1":
        rel_path = runtime.rel_path(pack_path, root)
        print(f"[loop-step] WARN: review pack v1 in use ({rel_path})", file=sys.stderr)
    verdict = str(front.get("verdict") or "").strip().upper()
    if verdict == "REVISE":
        fix_plan_path = root / "reports" / "loops" / ticket / scope_key / "review.fix_plan.json"
        if not fix_plan_path.exists():
            return False, "review fix plan missing", "review_fix_plan_missing"
    report_path = resolve_review_report_path(root, ticket, slug_hint, scope_key)
    if report_path.exists():
        try:
            report = json.loads(report_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            report = {}
        pack_updated = parse_timestamp(str(front.get("updated_at") or ""))
        report_updated = parse_timestamp(str(report.get("updated_at") or report.get("generated_at") or ""))
        if pack_updated and report_updated and pack_updated < report_updated:
            ok, regen_message = _maybe_regen_review_pack(
                root,
                ticket=ticket,
                slug_hint=slug_hint,
                scope_key=scope_key,
            )
            if not ok:
                return False, regen_message or "review pack stale", "review_pack_stale"
            try:
                refreshed = pack_path.read_text(encoding="utf-8").splitlines()
                front = parse_front_matter(refreshed)
            except OSError:
                front = front
            pack_updated = parse_timestamp(str(front.get("updated_at") or ""))
            if pack_updated and report_updated and pack_updated < report_updated:
                return False, "review pack stale", "review_pack_stale"
    return True, "", ""
