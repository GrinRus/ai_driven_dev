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
from tools import review_pack as review_pack_tools

DONE_CODE = 0
CONTINUE_CODE = 10
BLOCKED_CODE = 20
ERROR_CODE = 30


def _utc_stamp() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


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


def parse_front_matter(text: str) -> Dict[str, str]:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}
    data: Dict[str, str] = {}
    for line in lines[1:]:
        if line.strip() == "---":
            break
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        data[key.strip()] = value.strip()
    return data


def read_review_pack(root: Path, ticket: str) -> Tuple[str, str, str]:
    pack_path = root / "reports" / "loops" / ticket / "review.latest.pack.md"
    if not pack_path.exists():
        return "", "", ""
    front = parse_front_matter(pack_path.read_text(encoding="utf-8"))
    return front.get("schema", ""), front.get("verdict", ""), front.get("updated_at", "")


def read_review_report(root: Path, ticket: str) -> Dict[str, object]:
    report_path = root / "reports" / "reviewer" / f"{ticket}.json"
    if not report_path.exists():
        return {}
    try:
        return json.loads(report_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def parse_timestamp(value: str) -> dt.datetime | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    try:
        return dt.datetime.fromisoformat(raw)
    except ValueError:
        return None


def check_review_pack_freshness(pack_updated_at: str, report_payload: Dict[str, object], verdict: str) -> str:
    if not report_payload:
        return ""
    report_updated_at = str(report_payload.get("updated_at") or report_payload.get("generated_at") or "").strip()
    report_stamp = parse_timestamp(report_updated_at) if report_updated_at else None
    pack_stamp = parse_timestamp(pack_updated_at) if pack_updated_at else None
    if report_stamp and not pack_stamp:
        return "review pack updated_at missing"
    if report_stamp and pack_stamp and report_stamp > pack_stamp:
        return "review pack stale (report newer than pack)"
    findings = review_pack_tools.extract_findings(report_payload)
    expected_verdict = review_pack_tools.verdict_from_status(str(report_payload.get("status") or ""), findings)
    verdict = verdict.strip().upper()
    if expected_verdict and verdict and expected_verdict != verdict:
        return f"review pack verdict mismatch (pack={verdict}, report={expected_verdict})"
    return ""


def resolve_runner(args_runner: str | None) -> List[str]:
    raw = args_runner or os.environ.get("AIDD_LOOP_RUNNER") or "claude -p --no-session-persistence"
    return shlex.split(raw)


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


def dump_yaml(data: object, indent: int = 0) -> List[str]:
    lines: List[str] = []
    prefix = " " * indent
    if isinstance(data, dict):
        for key, value in data.items():
            if isinstance(value, (dict, list)):
                lines.append(f"{prefix}{key}:")
                lines.extend(dump_yaml(value, indent + 2))
            else:
                lines.append(f"{prefix}{key}: {json.dumps(value)}")
    elif isinstance(data, list):
        for item in data:
            if isinstance(item, (dict, list)):
                lines.append(f"{prefix}-")
                lines.extend(dump_yaml(item, indent + 2))
            else:
                lines.append(f"{prefix}- {json.dumps(item)}")
    else:
        lines.append(f"{prefix}{json.dumps(data)}")
    return lines


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Execute a single loop step (implement/review).")
    parser.add_argument("--ticket", help="Ticket identifier (defaults to docs/.active_ticket).")
    parser.add_argument("--runner", help="Runner command override (default: claude -p --no-session-persistence).")
    parser.add_argument("--format", choices=("json", "yaml"), help="Emit structured output to stdout.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    workspace_root, target = runtime.require_workflow_root()
    context = runtime.resolve_feature_context(target, ticket=args.ticket, slug_hint=None)
    ticket = (context.resolved_ticket or "").strip()
    if not ticket:
        raise ValueError("feature ticket is required; pass --ticket or set docs/.active_ticket via /feature-dev-aidd:idea-new.")

    stage = read_active_stage(target)
    verdict = ""
    reason = ""

    if not stage:
        next_stage = "implement"
    elif stage == "implement":
        next_stage = "review"
    elif stage == "review":
        schema, verdict, pack_updated_at = read_review_pack(target, ticket)
        if not schema:
            reason = "review pack missing"
            status = "blocked"
            code = BLOCKED_CODE
            return emit_result(args.format, ticket, stage, status, code, verdict, "", reason)
        if schema != "aidd.review_pack.v1":
            reason = f"review pack schema invalid ({schema})"
            status = "blocked"
            code = BLOCKED_CODE
            return emit_result(args.format, ticket, stage, status, code, verdict, "", reason)
        freshness_reason = check_review_pack_freshness(
            pack_updated_at,
            read_review_report(target, ticket),
            verdict,
        )
        if freshness_reason:
            status = "blocked"
            code = BLOCKED_CODE
            return emit_result(args.format, ticket, stage, status, code, verdict, "", freshness_reason)
        verdict = verdict.strip().upper()
        if verdict == "SHIP":
            status = "done"
            code = DONE_CODE
            return emit_result(args.format, ticket, stage, status, code, verdict, "", "")
        if verdict == "REVISE":
            next_stage = "implement"
        else:
            reason = f"review verdict={verdict or 'unknown'}"
            status = "blocked"
            code = BLOCKED_CODE
            return emit_result(args.format, ticket, stage, status, code, verdict, "", reason)
    else:
        reason = f"unsupported stage={stage}"
        status = "blocked"
        code = BLOCKED_CODE
        return emit_result(args.format, ticket, stage, status, code, verdict, "", reason)

    write_active_mode(target, "loop")
    runner = resolve_runner(args.runner)
    command = runner + build_command(next_stage, ticket)
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%d-%H%M%S")
    log_path = target / "reports" / "loops" / ticket / f"cli.{next_stage}.{stamp}.log"

    returncode = run_command(command, workspace_root, log_path)
    if returncode != 0:
        status = "error"
        code = ERROR_CODE
        reason = f"runner exited with {returncode}"
        return emit_result(args.format, ticket, next_stage, status, code, verdict, log_path, reason)

    status = "continue"
    code = CONTINUE_CODE
    return emit_result(args.format, ticket, next_stage, status, code, verdict, log_path, "")


def emit_result(
    fmt: str | None,
    ticket: str,
    stage: str,
    status: str,
    code: int,
    verdict: str,
    log_path: Path | str,
    reason: str,
) -> int:
    log_value = str(log_path) if log_path else ""
    payload = {
        "ticket": ticket,
        "stage": stage,
        "status": status,
        "exit_code": code,
        "verdict": verdict,
        "log_path": log_value,
        "updated_at": _utc_stamp(),
        "reason": reason,
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
