#!/usr/bin/env python3
"""Execute a single loop step (implement/review)."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Tuple

from tools import runtime
from tools.io_utils import dump_yaml, parse_front_matter, utc_timestamp

DONE_CODE = 0
CONTINUE_CODE = 10
BLOCKED_CODE = 20
ERROR_CODE = 30
WARN_REASON_CODES = {"out_of_scope_warn", "no_boundaries_defined_warn"}


def read_active_stage(root: Path) -> str:
    stage_path = root / "docs" / ".active_stage"
    try:
        return stage_path.read_text(encoding="utf-8").strip().lower()
    except OSError:
        return ""


def write_active_mode(root: Path, mode: str = "loop") -> None:
    docs_dir = root / "docs"
    docs_dir.mkdir(parents=True, exist_ok=True)
    (docs_dir / ".active_mode").write_text(mode + "\n", encoding="utf-8")


def resolve_stage_scope(root: Path, ticket: str, stage: str) -> Tuple[str, str]:
    if stage in {"implement", "review"}:
        work_item_key = runtime.read_active_work_item(root)
        if not work_item_key:
            return "", ""
        return work_item_key, runtime.resolve_scope_key(work_item_key, ticket)
    return "", runtime.resolve_scope_key("", ticket)


def stage_result_path(root: Path, ticket: str, scope_key: str, stage: str) -> Path:
    return root / "reports" / "loops" / ticket / scope_key / f"stage.{stage}.result.json"


def load_stage_result(root: Path, ticket: str, scope_key: str, stage: str) -> Tuple[Dict[str, object] | None, Path, str]:
    path = stage_result_path(root, ticket, scope_key, stage)
    if not path.exists():
        return None, path, "stage_result_missing_or_invalid"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None, path, "stage_result_missing_or_invalid"
    if str(payload.get("schema") or "") != "aidd.stage_result.v1":
        return None, path, "stage_result_missing_or_invalid"
    if str(payload.get("stage") or "").strip().lower() != stage:
        return None, path, "stage_result_missing_or_invalid"
    result = str(payload.get("result") or "").strip().lower()
    if result not in {"blocked", "continue", "done"}:
        return None, path, "stage_result_missing_or_invalid"
    return payload, path, ""


def normalize_stage_result(result: str, reason_code: str) -> str:
    if result == "blocked" and reason_code in WARN_REASON_CODES:
        return "continue"
    return result


def runner_supports_flag(command: str, flag: str) -> bool:
    try:
        proc = subprocess.run(
            [command, "--help"],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
        )
    except OSError:
        return False
    if proc.returncode != 0:
        return False
    return flag in (proc.stdout or "")


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


def validate_review_pack(
    root: Path,
    *,
    ticket: str,
    slug_hint: str,
    scope_key: str,
) -> Tuple[bool, str, str]:
    pack_path = root / "reports" / "loops" / ticket / scope_key / "review.latest.pack.md"
    if not pack_path.exists():
        return False, "review pack missing", "review_pack_missing"
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
    report_path = resolve_review_report_path(root, ticket, slug_hint, scope_key)
    if report_path.exists():
        try:
            report = json.loads(report_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            report = {}
        pack_updated = parse_timestamp(str(front.get("updated_at") or ""))
        report_updated = parse_timestamp(str(report.get("updated_at") or report.get("generated_at") or ""))
        if pack_updated and report_updated and pack_updated < report_updated:
            return False, "review pack stale", "review_pack_stale"
    return True, "", ""


def resolve_runner(args_runner: str | None) -> Tuple[List[str], str, str]:
    raw = args_runner or os.environ.get("AIDD_LOOP_RUNNER") or "claude -p"
    tokens = shlex.split(raw)
    notice = ""
    if "--no-session-persistence" in tokens:
        if not runner_supports_flag(tokens[0], "--no-session-persistence"):
            tokens = [token for token in tokens if token != "--no-session-persistence"]
            notice = "runner flag --no-session-persistence unsupported; removed"
    return tokens, raw, notice


def build_command(stage: str, ticket: str) -> List[str]:
    command = f"/feature-dev-aidd:{stage}"
    return [command, ticket]


def run_command(command: List[str], cwd: Path, log_path: Path) -> int:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("w", encoding="utf-8") as handle:
        result = subprocess.run(
            command,
            cwd=cwd,
            text=True,
            stdout=handle,
            stderr=subprocess.STDOUT,
        )
    return result.returncode


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Execute a single loop step (implement/review).")
    parser.add_argument("--ticket", help="Ticket identifier (defaults to docs/.active_ticket).")
    parser.add_argument("--runner", help="Runner command override (default: claude -p).")
    parser.add_argument("--format", choices=("json", "yaml"), help="Emit structured output to stdout.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    workspace_root, target = runtime.require_workflow_root()
    context = runtime.resolve_feature_context(target, ticket=args.ticket, slug_hint=None)
    ticket = (context.resolved_ticket or "").strip()
    slug_hint = (context.slug_hint or ticket or "").strip()
    if not ticket:
        raise ValueError("feature ticket is required; pass --ticket or set docs/.active_ticket via /feature-dev-aidd:idea-new.")

    stage = read_active_stage(target)
    reason = ""
    reason_code = ""
    scope_key = ""
    stage_result_rel = ""

    if not stage:
        next_stage = "implement"
    else:
        work_item_key, scope_key = resolve_stage_scope(target, ticket, stage)
        if stage in {"implement", "review"} and not scope_key:
            reason = "active work item missing"
            reason_code = "stage_result_missing_or_invalid"
            return emit_result(args.format, ticket, stage, "blocked", BLOCKED_CODE, "", reason, reason_code)
        payload, result_path, error = load_stage_result(target, ticket, scope_key, stage)
        if error:
            reason = error
            reason_code = error
            return emit_result(
                args.format,
                ticket,
                stage,
                "blocked",
                BLOCKED_CODE,
                "",
                reason,
                reason_code,
                scope_key=scope_key,
            )
        result = str(payload.get("result") or "").strip().lower()
        reason = str(payload.get("reason") or "").strip()
        reason_code = str(payload.get("reason_code") or "").strip().lower()
        result = normalize_stage_result(result, reason_code)
        stage_result_rel = runtime.rel_path(result_path, target)
        if result == "blocked":
            return emit_result(
                args.format,
                ticket,
                stage,
                "blocked",
                BLOCKED_CODE,
                "",
                reason,
                reason_code,
                scope_key=scope_key,
                stage_result_path=stage_result_rel,
            )
        if stage == "review":
            if result == "done":
                ok, message, code = validate_review_pack(
                    target,
                    ticket=ticket,
                    slug_hint=slug_hint,
                    scope_key=scope_key,
                )
                if not ok:
                    return emit_result(
                        args.format,
                        ticket,
                        stage,
                        "blocked",
                        BLOCKED_CODE,
                        "",
                        message,
                        code,
                        scope_key=scope_key,
                        stage_result_path=stage_result_rel,
                    )
                return emit_result(
                    args.format,
                    ticket,
                    stage,
                    "done",
                    DONE_CODE,
                    "",
                    reason,
                    reason_code,
                    scope_key=scope_key,
                    stage_result_path=stage_result_rel,
                )
            if result == "continue":
                ok, message, code = validate_review_pack(
                    target,
                    ticket=ticket,
                    slug_hint=slug_hint,
                    scope_key=scope_key,
                )
                if not ok:
                    return emit_result(
                        args.format,
                        ticket,
                        stage,
                        "blocked",
                        BLOCKED_CODE,
                        "",
                        message,
                        code,
                        scope_key=scope_key,
                        stage_result_path=stage_result_rel,
                    )
                next_stage = "implement"
            else:
                reason = f"review result={result or 'unknown'}"
                reason_code = reason_code or "unsupported_stage_result"
                return emit_result(
                    args.format,
                    ticket,
                    stage,
                    "blocked",
                    BLOCKED_CODE,
                    "",
                    reason,
                    reason_code,
                    scope_key=scope_key,
                    stage_result_path=stage_result_rel,
                )
        elif stage == "implement":
            if result in {"continue", "done"}:
                next_stage = "review"
            else:
                reason = f"implement result={result or 'unknown'}"
                reason_code = reason_code or "unsupported_stage_result"
                return emit_result(
                    args.format,
                    ticket,
                    stage,
                    "blocked",
                    BLOCKED_CODE,
                    "",
                    reason,
                    reason_code,
                    scope_key=scope_key,
                    stage_result_path=stage_result_rel,
                )
        elif stage == "qa":
            if result == "done":
                return emit_result(
                    args.format,
                    ticket,
                    stage,
                    "done",
                    DONE_CODE,
                    "",
                    reason,
                    reason_code,
                    scope_key=scope_key,
                    stage_result_path=stage_result_rel,
                )
            if result == "blocked":
                return emit_result(
                    args.format,
                    ticket,
                    stage,
                    "blocked",
                    BLOCKED_CODE,
                    "",
                    reason,
                    reason_code,
                    scope_key=scope_key,
                    stage_result_path=stage_result_rel,
                )
            reason = f"qa result={result or 'unknown'}"
            reason_code = reason_code or "unsupported_stage_result"
            return emit_result(
                args.format,
                ticket,
                stage,
                "blocked",
                BLOCKED_CODE,
                "",
                reason,
                reason_code,
                scope_key=scope_key,
                stage_result_path=stage_result_rel,
            )
        else:
            reason = f"unsupported stage={stage}"
            reason_code = reason_code or "unsupported_stage"
            return emit_result(args.format, ticket, stage, "blocked", BLOCKED_CODE, "", reason, reason_code)

    write_active_mode(target, "loop")
    runner_tokens, runner_raw, runner_notice = resolve_runner(args.runner)
    command = runner_tokens + build_command(next_stage, ticket)
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%d-%H%M%S")
    log_path = target / "reports" / "loops" / ticket / f"cli.{next_stage}.{stamp}.log"

    returncode = run_command(command, workspace_root, log_path)
    if returncode != 0:
        status = "error"
        code = ERROR_CODE
        reason = f"runner exited with {returncode}"
        return emit_result(
            args.format,
            ticket,
            next_stage,
            status,
            code,
            log_path,
            reason,
            "",
            scope_key="",
            stage_result_path="",
            runner=runner_raw,
            runner_effective=" ".join(runner_tokens),
            runner_notice=runner_notice,
        )

    next_work_item_key, next_scope_key = resolve_stage_scope(target, ticket, next_stage)
    if next_stage in {"implement", "review"} and not next_scope_key:
        reason = "stage_result_missing_or_invalid"
        return emit_result(
            args.format,
            ticket,
            next_stage,
            "blocked",
            BLOCKED_CODE,
            log_path,
            reason,
            "stage_result_missing_or_invalid",
            runner=runner_raw,
            runner_effective=" ".join(runner_tokens),
            runner_notice=runner_notice,
        )
    payload, result_path, error = load_stage_result(target, ticket, next_scope_key, next_stage)
    if error:
        return emit_result(
            args.format,
            ticket,
            next_stage,
            "blocked",
            BLOCKED_CODE,
            log_path,
            error,
            error,
            scope_key=next_scope_key,
            stage_result_path=runtime.rel_path(result_path, target),
            runner=runner_raw,
            runner_effective=" ".join(runner_tokens),
            runner_notice=runner_notice,
        )
    result = str(payload.get("result") or "").strip().lower()
    reason = str(payload.get("reason") or "").strip()
    reason_code = str(payload.get("reason_code") or "").strip().lower()
    result = normalize_stage_result(result, reason_code)
    if next_stage == "review" and result in {"continue", "done"}:
        ok, message, code = validate_review_pack(
            target,
            ticket=ticket,
            slug_hint=slug_hint,
            scope_key=next_scope_key,
        )
        if not ok:
            return emit_result(
                args.format,
                ticket,
                next_stage,
                "blocked",
                BLOCKED_CODE,
                log_path,
                message,
                code,
                scope_key=next_scope_key,
                stage_result_path=runtime.rel_path(result_path, target),
                runner=runner_raw,
                runner_effective=" ".join(runner_tokens),
                runner_notice=runner_notice,
            )
    status = result if result in {"blocked", "continue", "done"} else "blocked"
    code = DONE_CODE if status == "done" else BLOCKED_CODE if status == "blocked" else CONTINUE_CODE
    return emit_result(
        args.format,
        ticket,
        next_stage,
        status,
        code,
        log_path,
        reason,
        reason_code,
        scope_key=next_scope_key,
        stage_result_path=runtime.rel_path(result_path, target),
        runner=runner_raw,
        runner_effective=" ".join(runner_tokens),
        runner_notice=runner_notice,
    )


def emit_result(
    fmt: str | None,
    ticket: str,
    stage: str,
    status: str,
    code: int,
    log_path: Path | str,
    reason: str,
    reason_code: str = "",
    *,
    scope_key: str = "",
    stage_result_path: str = "",
    runner: str = "",
    runner_effective: str = "",
    runner_notice: str = "",
) -> int:
    log_value = str(log_path) if log_path else ""
    payload = {
        "ticket": ticket,
        "stage": stage,
        "status": status,
        "exit_code": code,
        "scope_key": scope_key,
        "log_path": log_value,
        "stage_result_path": stage_result_path,
        "runner": runner,
        "runner_effective": runner_effective,
        "runner_notice": runner_notice,
        "updated_at": utc_timestamp(),
        "reason": reason,
        "reason_code": reason_code,
    }
    if fmt:
        output = json.dumps(payload, ensure_ascii=False, indent=2) if fmt == "json" else "\n".join(dump_yaml(payload))
        print(output)
        print(f"[loop-step] {status} stage={stage} log={log_value}", file=sys.stderr)
    else:
        summary = f"[loop-step] {status} stage={stage}"
        if log_value:
            summary += f" log={log_value}"
        if reason:
            summary += f" reason={reason}"
        print(summary)
    return code


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
