#!/usr/bin/env python3
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, List, Tuple


THIS_DIR = Path(__file__).resolve().parent
if str(THIS_DIR) not in sys.path:
    sys.path.insert(0, str(THIS_DIR))

import aidd_stream_paths


DEFAULT_MIN_FREE_BYTES = 1_073_741_824
STALL_SECONDS = 20 * 60
STATUS_ALIAS_ERROR_PATTERNS = (
    re.compile(r"unknown skill:\s*:status", re.IGNORECASE),
    re.compile(r"command not found:\s*:status", re.IGNORECASE),
)
SIBLING_TOOL_ERROR_RE = re.compile(r"sibling tool call errored", re.IGNORECASE)
CANONICAL_RUNTIME_CALL_RE = re.compile(
    r"skills/(?:implement/runtime/implement_run\.py|review/runtime/review_run\.py|qa/runtime/qa_run\.py|aidd-docio/runtime/actions_apply\.py|aidd-flow-state/runtime/stage_result\.py)\b",
    re.IGNORECASE,
)
MALFORMED_STAGE_ALIAS_RE = re.compile(
    r"(?:unknown skill|command not found):\s*:(?!status\b)([a-z0-9_-]+)",
    re.IGNORECASE,
)
STAGE_COMMAND_RE = re.compile(r"/feature-dev-aidd:([a-z0-9-]+)", re.IGNORECASE)


def build_paths(audit_dir: Path, step: str, run: int) -> Dict[str, Path]:
    prefix = f"{step}_run{run}"
    return {
        "log": audit_dir / f"{prefix}.log",
        "head": audit_dir / f"{prefix}.head.txt",
        "tail": audit_dir / f"{prefix}.tail.log",
        "heartbeat": audit_dir / f"{prefix}.heartbeat.log",
        "summary": audit_dir / f"{prefix}.summary.txt",
        "cmd": audit_dir / f"{prefix}.cmd.txt",
        "stream_paths": audit_dir / f"{step}_stream_paths_run{run}.txt",
        "stream_liveness": audit_dir / f"{step}_stream_liveness_check_run{run}.txt",
        "init_check": audit_dir / f"{prefix}.init_check.txt",
        "disk_preflight": audit_dir / f"{prefix}.disk_preflight.txt",
    }


def disk_preflight(project_dir: Path, out_path: Path, min_free_bytes: int) -> Tuple[int, int]:
    stat = os.statvfs(str(project_dir))
    free_bytes = int(stat.f_frsize * stat.f_bavail)
    lines = [
        f"project_dir={project_dir.resolve()}",
        f"free_bytes={free_bytes}",
        f"min_free_bytes={min_free_bytes}",
    ]
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return free_bytes, min_free_bytes


def build_command(stage_command: str, plugin_dir: Path, mode: str) -> List[str]:
    if mode == "stream-json":
        return [
            "claude",
            "-p",
            stage_command,
            "--dangerously-skip-permissions",
            "--verbose",
            "--output-format",
            "stream-json",
            "--include-partial-messages",
            "--plugin-dir",
            str(plugin_dir),
        ]
    return [
        "claude",
        "-p",
        stage_command,
        "--dangerously-skip-permissions",
        "--plugin-dir",
        str(plugin_dir),
    ]


def run_stage(
    *,
    cmd: List[str],
    cwd: Path,
    log_path: Path,
    heartbeat_path: Path,
    poll_seconds: int,
) -> int:
    with log_path.open("w", encoding="utf-8") as log_file, heartbeat_path.open("w", encoding="utf-8") as heartbeat_file:
        proc = subprocess.Popen(
            cmd,
            cwd=str(cwd),
            stdout=log_file,
            stderr=subprocess.STDOUT,
            text=True,
        )
        while True:
            rc = proc.poll()
            now = time.time()
            size = log_path.stat().st_size if log_path.exists() else 0
            tail = ""
            if log_path.exists() and size > 0:
                try:
                    tail = log_path.read_text(encoding="utf-8", errors="replace").splitlines()[-1][:220]
                except Exception:
                    tail = ""
            heartbeat_file.write(f"{int(now)} pid={proc.pid} size={size} tail={tail}\n")
            heartbeat_file.flush()
            if rc is not None:
                return int(rc)
            time.sleep(max(poll_seconds, 1))


def _detect_result_count(log_text: str) -> str:
    result_count = ""
    for match in re.finditer(r"result_count[=:]([0-9]+)", log_text):
        result_count = str(match.group(1))
    return result_count


def _detect_top_level_result(log_text: str) -> int:
    if re.search(r'"type"\s*:\s*"result"', log_text):
        return 1
    if re.search(r"\bstatus=(blocked|done|ship|success|error|continue)\b", log_text, re.IGNORECASE):
        return 1
    return 0


def _extract_prompt_exec_telemetry(log_text: str) -> Dict[str, int]:
    status_alias_error_count = sum(len(pattern.findall(log_text)) for pattern in STATUS_ALIAS_ERROR_PATTERNS)
    sibling_tool_error_count = len(SIBLING_TOOL_ERROR_RE.findall(log_text))
    canonical_runtime_call_count = len(CANONICAL_RUNTIME_CALL_RE.findall(log_text))
    malformed_stage_alias_count = len(MALFORMED_STAGE_ALIAS_RE.findall(log_text))
    return {
        "status_alias_error_count": int(status_alias_error_count),
        "sibling_tool_error_count": int(sibling_tool_error_count),
        "canonical_runtime_call_count": int(canonical_runtime_call_count),
        "malformed_stage_alias_count": int(malformed_stage_alias_count),
    }


def _detect_seed_stage_non_converging_command(
    *,
    result_count: str,
    top_level_result: int,
    telemetry: Dict[str, int],
) -> int:
    if int(top_level_result or 0) != 0:
        return 0
    if str(result_count).strip() not in {"", "0"}:
        return 0
    if int(telemetry.get("status_alias_error_count") or 0) <= 0:
        return 0
    if int(telemetry.get("sibling_tool_error_count") or 0) <= 0:
        return 0
    if int(telemetry.get("canonical_runtime_call_count") or 0) > 0:
        return 0
    return 1


def _is_seed_stage_step(step: str) -> bool:
    normalized = str(step or "").strip().lower()
    if not normalized:
        return False
    stage = re.sub(r"^[0-9]+_", "", normalized)
    if "seed" in stage:
        return True
    return stage.startswith("implement")


def _infer_stage_name(*, stage_command: str, step_hint: str) -> str:
    match = STAGE_COMMAND_RE.search(str(stage_command or ""))
    if match:
        return str(match.group(1) or "").strip().lower()
    stage = re.sub(r"^[0-9]+_", "", str(step_hint or "").strip().lower())
    return stage.replace("_", "-") if stage else "unknown"


def _synthetic_reason_code(*, exit_code: int, log_text: str) -> str:
    if MALFORMED_STAGE_ALIAS_RE.search(log_text):
        return "launcher_prompt_contract_mismatch"
    if int(exit_code) == 143:
        return "parent_terminated_or_external_terminate"
    if int(exit_code) == 127:
        return "launcher_tokenization_or_command_not_found"
    return "stage_command_exit_nonzero"


def _synthetic_classification(reason_code: str) -> str:
    if reason_code == "parent_terminated_or_external_terminate":
        return "ENV_MISCONFIG(parent_terminated_or_external_terminate)"
    if reason_code == "launcher_tokenization_or_command_not_found":
        return "PROMPT_EXEC_ISSUE(launcher_tokenization_or_command_not_found)"
    if reason_code == "launcher_prompt_contract_mismatch":
        return "PROMPT_EXEC_ISSUE(launcher_prompt_contract_mismatch)"
    return "PROMPT_EXEC_ISSUE(stage_command_exit_nonzero)"


def _maybe_append_synthetic_terminal_result(
    *,
    log_path: Path,
    exit_code: int,
    ticket: str,
    stage: str,
) -> Dict[str, object]:
    if int(exit_code) == 0:
        return {}
    current = log_path.read_text(encoding="utf-8", errors="replace") if log_path.exists() else ""
    if _detect_top_level_result(current):
        return {}
    reason_code = _synthetic_reason_code(exit_code=exit_code, log_text=current)
    classification = _synthetic_classification(reason_code)
    signal = "SIGTERM" if int(exit_code) == 143 else ""
    updated_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    normalized_ticket = str(ticket or "").strip()
    normalized_stage = str(stage or "").strip().lower() or "unknown"
    event = {
        "type": "result",
        "schema": "aidd.stage_result.v1",
        "schema_version": "aidd.stage_result.v1",
        "ticket": normalized_ticket,
        "stage": normalized_stage,
        "result": "blocked",
        "updated_at": updated_at,
        "status": "blocked",
        "terminal_marker": 1,
        "synthetic": True,
        "exit_code": int(exit_code),
        "reason_code": reason_code,
        "classification": classification,
        "termination_attribution": {
            "exit_code": int(exit_code),
            "signal": signal,
            "killed_flag": 0,
            "watchdog_marker": 0,
            "classification": classification,
        },
    }
    append = json.dumps(event, ensure_ascii=False)
    with log_path.open("a", encoding="utf-8") as handle:
        if current and not current.endswith("\n"):
            handle.write("\n")
        handle.write(append + "\n")
    return event


def parse_init(log_text: str) -> Dict[str, int]:
    plugins_ok = 0
    slash_ok = 0
    skills_ok = 0
    for raw in log_text.splitlines():
        line = raw.strip()
        if not line.startswith("{"):
            continue
        try:
            event = json.loads(line)
        except Exception:
            continue
        if event.get("type") != "system" or event.get("subtype") != "init":
            continue

        plugins = event.get("plugins") or []
        plugin_names = set()
        for item in plugins:
            if isinstance(item, dict):
                plugin_names.add(str(item.get("name") or ""))
            elif isinstance(item, str):
                plugin_names.add(item)
        plugins_ok = int("feature-dev-aidd" in plugin_names)

        slash_commands = event.get("slash_commands") or []
        slash_names = set()
        for item in slash_commands:
            if isinstance(item, dict):
                slash_names.add(str(item.get("name") or ""))
            elif isinstance(item, str):
                slash_names.add(item)
        slash_ok = int(any(name.startswith("feature-dev-aidd:") for name in slash_names))

        skills = event.get("skills") or []
        skill_names = set()
        for item in skills:
            if isinstance(item, dict):
                skill_names.add(str(item.get("name") or ""))
            elif isinstance(item, str):
                skill_names.add(item)
        skills_ok = int(any(name.startswith("feature-dev-aidd:") for name in skill_names))
        break
    return {"plugins_ok": plugins_ok, "slash_ok": slash_ok, "skills_ok": skills_ok}


def _safe_stat(path: Path) -> Tuple[int, int]:
    if not path.exists():
        return 0, 0
    st = path.stat()
    return int(st.st_size), int(st.st_mtime)


def build_liveness_payload(
    *,
    main_log: Path,
    valid_stream_paths: List[str],
    run_start_epoch: int,
) -> Dict[str, object]:
    now_epoch = int(time.time())
    main_bytes, main_mtime = _safe_stat(main_log)
    main_age = now_epoch - main_mtime if main_mtime else now_epoch - int(run_start_epoch)
    stream_entries: List[Dict[str, object]] = []
    for item in valid_stream_paths:
        path = Path(item)
        size, mtime = _safe_stat(path)
        age = now_epoch - mtime if mtime else now_epoch - int(run_start_epoch)
        stream_entries.append({"path": str(path), "bytes": size, "mtime": mtime, "age": age})

    if not stream_entries:
        classification = "no_stream_emitted"
        active_source = "main" if main_mtime and main_age <= STALL_SECONDS else "none"
        stagnation_seconds = max(main_age, 0)
    else:
        stream_age_min = min(entry["age"] for entry in stream_entries)
        main_active = bool(main_mtime) and main_age <= STALL_SECONDS
        stream_active = stream_age_min <= STALL_SECONDS
        if main_active:
            classification = "active_stream"
            active_source = "main"
            stagnation_seconds = main_age
        elif stream_active:
            classification = "active_stream"
            active_source = "stream"
            stagnation_seconds = stream_age_min
        else:
            classification = "silent_stall"
            active_source = "none"
            stagnation_seconds = min(main_age, stream_age_min)

    return {
        "run_start_epoch": int(run_start_epoch),
        "main_log_bytes": main_bytes,
        "main_log_mtime": main_mtime,
        "valid_stream_count": len(stream_entries),
        "stream_entries": stream_entries,
        "active_source": active_source,
        "stagnation_seconds": int(max(stagnation_seconds, 0)),
        "classification": classification,
    }


def write_liveness_report(payload: Dict[str, object], out_path: Path) -> None:
    lines: List[str] = [
        f"run_start_epoch={payload['run_start_epoch']}",
        f"main_log_bytes={payload['main_log_bytes']}",
        f"main_log_mtime={payload['main_log_mtime']}",
        f"valid_stream_count={payload['valid_stream_count']}",
    ]
    stream_entries = payload.get("stream_entries") or []
    for idx, entry in enumerate(stream_entries):
        lines.append(f"stream_{idx}_path={entry['path']}")
        lines.append(f"stream_{idx}_bytes={entry['bytes']}")
        lines.append(f"stream_{idx}_mtime={entry['mtime']}")
    lines.append(f"active_source={payload['active_source']}")
    lines.append(f"stagnation_seconds={payload['stagnation_seconds']}")
    lines.append(f"classification={payload['classification']}")
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Canonical stage launcher for AIDD audit runs.")
    parser.add_argument("--project-dir", required=True)
    parser.add_argument("--plugin-dir", required=True)
    parser.add_argument("--audit-dir", required=True)
    parser.add_argument("--step", required=True)
    parser.add_argument("--run", type=int, required=True)
    parser.add_argument("--ticket", default="")
    parser.add_argument("--stage-command", required=True)
    parser.add_argument("--mode", choices=("stream-json", "text"), default="stream-json")
    parser.add_argument("--poll-seconds", type=int, default=15)
    parser.add_argument("--min-free-bytes", type=int, default=DEFAULT_MIN_FREE_BYTES)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    project_dir = Path(args.project_dir).resolve()
    plugin_dir = Path(args.plugin_dir).resolve()
    audit_dir = Path(args.audit_dir).resolve()
    audit_dir.mkdir(parents=True, exist_ok=True)
    paths = build_paths(audit_dir=audit_dir, step=args.step, run=args.run)

    free_bytes, min_free = disk_preflight(project_dir=project_dir, out_path=paths["disk_preflight"], min_free_bytes=args.min_free_bytes)
    if free_bytes < min_free:
        no_space = [
            "classification=ENV_MISCONFIG(no_space_left_on_device)",
            f"free_bytes={free_bytes}",
            f"min_free_bytes={min_free}",
        ]
        (audit_dir / f"{args.step}_run{args.run}.env_misconfig.txt").write_text("\n".join(no_space) + "\n", encoding="utf-8")
        return 12

    cmd = build_command(stage_command=args.stage_command, plugin_dir=plugin_dir, mode=args.mode)
    paths["cmd"].write_text(
        "\n".join(
            [
                f"cwd={project_dir}",
                f"mode={args.mode}",
                "command=" + " ".join(cmd),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    run_start_epoch = int(time.time())
    exit_code = run_stage(
        cmd=cmd,
        cwd=project_dir,
        log_path=paths["log"],
        heartbeat_path=paths["heartbeat"],
        poll_seconds=args.poll_seconds,
    )
    synthetic_event = _maybe_append_synthetic_terminal_result(
        log_path=paths["log"],
        exit_code=exit_code,
        ticket=args.ticket,
        stage=_infer_stage_name(stage_command=args.stage_command, step_hint=args.step),
    )

    log_text = paths["log"].read_text(encoding="utf-8", errors="replace") if paths["log"].exists() else ""
    paths["head"].write_text("\n".join(log_text.splitlines()[:200]) + ("\n" if log_text else ""), encoding="utf-8")
    tail_lines = log_text.splitlines()[-200:] if log_text else []
    paths["tail"].write_text("\n".join(tail_lines) + ("\n" if tail_lines else ""), encoding="utf-8")

    init = parse_init(log_text)
    paths["init_check"].write_text(
        "\n".join(
            [
                f"plugins_ok={init['plugins_ok']}",
                f"slash_ok={init['slash_ok']}",
                f"skills_ok={init['skills_ok']}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    stream_result = aidd_stream_paths.resolve_stream_paths(
        log_path=paths["log"],
        out_path=paths["stream_paths"],
        project_dir=project_dir,
        ticket=args.ticket,
        run_start_epoch=run_start_epoch,
        step=args.step,
    )

    liveness = build_liveness_payload(
        main_log=paths["log"],
        valid_stream_paths=list(stream_result.get("valid_paths") or []),
        run_start_epoch=run_start_epoch,
    )
    write_liveness_report(liveness, paths["stream_liveness"])

    result_count = _detect_result_count(log_text)
    top_level_result = _detect_top_level_result(log_text)
    prompt_exec_telemetry = _extract_prompt_exec_telemetry(log_text)
    seed_stage_non_converging_command = 0
    if _is_seed_stage_step(args.step):
        seed_stage_non_converging_command = _detect_seed_stage_non_converging_command(
            result_count=result_count,
            top_level_result=top_level_result,
            telemetry=prompt_exec_telemetry,
        )

    summary_lines = [
        f"exit_code={exit_code}",
        f"result_count={result_count}",
        f"top_level_result={top_level_result}",
        f"status_alias_error_count={prompt_exec_telemetry['status_alias_error_count']}",
        f"sibling_tool_error_count={prompt_exec_telemetry['sibling_tool_error_count']}",
        f"canonical_runtime_call_count={prompt_exec_telemetry['canonical_runtime_call_count']}",
        f"malformed_stage_alias_count={prompt_exec_telemetry['malformed_stage_alias_count']}",
        f"seed_stage_non_converging_command={seed_stage_non_converging_command}",
        f"primary_stream_count={stream_result['primary_candidates']}",
        f"valid_stream_count={stream_result['valid_count']}",
        f"invalid_stream_count={stream_result['invalid_count']}",
        f"missing_stream_count={stream_result['missing_count']}",
        f"fallback_used={stream_result['used_fallback']}",
        f"stream_path_not_emitted_by_cli={stream_result['cli_not_emitted']}",
        f"synthetic_terminal_result={1 if synthetic_event else 0}",
    ]
    if synthetic_event:
        reason_code = str(synthetic_event.get("reason_code") or "")
        term = synthetic_event.get("termination_attribution") or {}
        summary_lines.extend(
            [
                "terminal_marker=1",
                "status=blocked",
                f"reason_code={reason_code}",
                f"termination_exit_code={term.get('exit_code', '')}",
                f"termination_signal={term.get('signal', '')}",
                f"killed_flag={term.get('killed_flag', 0)}",
                f"watchdog_marker={term.get('watchdog_marker', 0)}",
                f"termination_classification={term.get('classification', reason_code)}",
            ]
        )
    if _is_seed_stage_step(args.step) and seed_stage_non_converging_command:
        summary_lines.extend(
            [
                "terminal_marker=1",
                "status=blocked",
                "reason_code=seed_stage_non_converging_command",
            ]
        )
    paths["summary"].write_text("\n".join(summary_lines) + "\n", encoding="utf-8")
    return int(exit_code)


if __name__ == "__main__":
    raise SystemExit(main())
