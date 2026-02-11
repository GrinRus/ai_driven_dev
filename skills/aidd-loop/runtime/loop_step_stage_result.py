#!/usr/bin/env python3
"""Stage-result and review-pack handlers for loop-step."""

from __future__ import annotations

import datetime as dt
import io
import json
import sys
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from typing import Dict, List, Tuple

from aidd_runtime import runtime
from aidd_runtime.io_utils import parse_front_matter
from aidd_runtime import loop_step as core


def stage_result_path(root: Path, ticket: str, scope_key: str, stage: str) -> Path:
    return root / "reports" / "loops" / ticket / scope_key / f"stage.{stage}.result.json"


def _parse_stage_result(path: Path, stage: str) -> Tuple[Dict[str, object] | None, str]:
    if not path.exists():
        return None, "missing"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None, "invalid-json"
    if str(payload.get("schema") or "") != "aidd.stage_result.v1":
        return None, "invalid-schema"
    if str(payload.get("stage") or "").strip().lower() != stage:
        return None, "wrong-stage"
    result = str(payload.get("result") or "").strip().lower()
    if result not in {"blocked", "continue", "done"}:
        return None, "invalid-result"
    work_item_key = str(payload.get("work_item_key") or "").strip()
    if work_item_key and not runtime.is_valid_work_item_key(work_item_key):
        return None, "invalid-work-item"
    return payload, ""


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


def _stage_result_diagnostics(candidates: List[Tuple[Path, str]]) -> str:
    if not candidates:
        return "candidates=none"
    parts: List[str] = []
    for path, status in candidates[:5]:
        timestamp = "n/a"
        if path.exists():
            timestamp = dt.datetime.fromtimestamp(path.stat().st_mtime, tz=dt.timezone.utc).isoformat()
        parts.append(f"{path.as_posix()}:{status}@{timestamp}")
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

    validated: List[Tuple[Path, Dict[str, object]]] = []
    diagnostics: List[Tuple[Path, str]] = [(preferred_path, preferred_error)]
    for candidate in _collect_stage_result_candidates(root, ticket, stage):
        if candidate == preferred_path:
            continue
        payload, status = _parse_stage_result(candidate, stage)
        diagnostics.append((candidate, status))
        if payload is None:
            continue
        validated.append((candidate, payload))

    fresh = [
        (path, payload)
        for path, payload in validated
        if _in_window(path, started_at=started_at, finished_at=finished_at)
    ]
    selected_pool = fresh or validated
    if not selected_pool:
        return (
            None,
            preferred_path,
            "stage_result_missing_or_invalid",
            "",
            "",
            _stage_result_diagnostics(diagnostics),
        )

    selected_path, selected_payload = selected_pool[0]
    selected_scope = str(selected_payload.get("scope_key") or "").strip() or selected_path.parent.name
    mismatch_from = scope_key or ""
    mismatch_to = ""
    if scope_key and selected_scope and selected_scope != scope_key:
        mismatch_to = selected_scope
    return selected_payload, selected_path, "", mismatch_from, mismatch_to, _stage_result_diagnostics(diagnostics)


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
