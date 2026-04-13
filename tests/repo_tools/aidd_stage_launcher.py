#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import signal
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
CWD_BLOCKER_EXIT_CODE = 14
WATCHDOG_GRACE_SECONDS = 10
TESTS_ENV_DEP_MISSING_REASON_CODE = "tests_env_dependency_missing"
_PLAYWRIGHT_DEPENDENCY_PATTERNS = (
    re.compile(r"browsertype\.launch:\s*executable doesn't exist", re.IGNORECASE),
    re.compile(r"looks like playwright test or playwright was just installed or updated", re.IGNORECASE),
    re.compile(r"\bnpx playwright install\b", re.IGNORECASE),
)


def build_paths(audit_dir: Path, step: str, run: int) -> Dict[str, Path]:
    prefix = f"{step}_run{run}"
    return {
        "log": audit_dir / f"{prefix}.log",
        "head": audit_dir / f"{prefix}.head.txt",
        "tail": audit_dir / f"{prefix}.tail.log",
        "heartbeat": audit_dir / f"{prefix}.heartbeat.log",
        "summary": audit_dir / f"{prefix}.summary.txt",
        "cmd": audit_dir / f"{prefix}.cmd.txt",
        "termination": audit_dir / f"{step}_termination_attribution.txt",
        "stream_paths": audit_dir / f"{step}_stream_paths_run{run}.txt",
        "stream_liveness": audit_dir / f"{step}_stream_liveness_check_run{run}.txt",
        "init_check": audit_dir / f"{prefix}.init_check.txt",
        "disk_preflight": audit_dir / f"{prefix}.disk_preflight.txt",
        "env_misconfig": audit_dir / f"{prefix}.env_misconfig.txt",
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


def _looks_like_plugin_root(path: Path) -> bool:
    return (path / ".claude-plugin").exists() and (path / "skills").exists()


def write_cwd_blocker_artifacts(
    *,
    paths: Dict[str, Path],
    step: str,
    run: int,
    project_dir: Path,
    plugin_dir: Path,
    reason_detail: str,
    stage_command: str,
    mode: str,
    exit_code: int = CWD_BLOCKER_EXIT_CODE,
) -> None:
    message = (
        "[aidd] ERROR: refusing to use plugin repository as workspace root for runtime artifacts; "
        "run commands from the project workspace root."
    )
    paths["log"].write_text(message + "\n", encoding="utf-8")
    paths["head"].write_text(message + "\n", encoding="utf-8")
    paths["tail"].write_text(message + "\n", encoding="utf-8")
    paths["heartbeat"].write_text(
        "\n".join(
            [
                f"pid=0 size={len(message)} tail={message[:220]}",
                "classification=ENV_MISCONFIG(cwd_wrong)",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    paths["init_check"].write_text(
        "\n".join(
            [
                "plugins_ok=0",
                "slash_ok=0",
                "skills_ok=0",
                "classification=ENV_MISCONFIG(cwd_wrong)",
                "reason_code=cwd_wrong",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    paths["stream_paths"].write_text("fallback_scan=1\nstream_path_not_emitted_by_cli=1\n", encoding="utf-8")
    write_liveness_report(
        {
            "run_start_epoch": int(time.time()),
            "main_log_bytes": len(message),
            "main_log_mtime": int(time.time()),
            "valid_stream_count": 0,
            "stream_entries": [],
            "active_source": "none",
            "stagnation_seconds": 0,
            "classification": "no_stream_emitted",
        },
        paths["stream_liveness"],
    )
    paths["cmd"].write_text(
        "\n".join(
            [
                f"cwd={project_dir}",
                f"mode={mode}",
                f"stage_command={stage_command}",
                "command=NOT_EXECUTED(cwd_wrong_preflight)",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    paths["summary"].write_text(
        "\n".join(
            [
                f"step={step}",
                f"run={run}",
                f"mode={mode}",
                f"stage_command={stage_command}",
                f"exit_code={exit_code}",
                "result_count=1",
                "top_level_result=1",
                "top_level_status=blocked",
                "reason_code=cwd_wrong",
                "classification=ENV_MISCONFIG(cwd_wrong)",
                f"project_dir={project_dir}",
                f"plugin_dir={plugin_dir}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    paths["env_misconfig"].write_text(
        "\n".join(
            [
                "classification=ENV_MISCONFIG(cwd_wrong)",
                "reason_code=cwd_wrong",
                f"reason_detail={reason_detail}",
                f"project_dir={project_dir}",
                f"plugin_dir={plugin_dir}",
                f"evidence_log={paths['log']}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def _normalize_exit_code(raw_exit_code: int) -> int:
    if raw_exit_code < 0:
        return 128 + abs(raw_exit_code)
    return int(raw_exit_code)


def _signal_name_from_number(sig_num: int) -> str:
    try:
        return str(signal.Signals(sig_num).name)
    except Exception:
        return f"SIG{sig_num}"


def _read_log_tail(log_path: Path, *, max_bytes: int = 131072) -> str:
    if not log_path.exists():
        return ""
    try:
        with log_path.open("rb") as handle:
            handle.seek(0, os.SEEK_END)
            size = handle.tell()
            handle.seek(max(size - max_bytes, 0))
            raw = handle.read()
    except OSError:
        return ""
    return raw.decode("utf-8", errors="replace")


def _detect_tests_env_dependency_issue(log_path: Path) -> tuple[bool, str]:
    text = _read_log_tail(log_path).lower()
    if not text:
        return False, ""
    if all(pattern.search(text) for pattern in _PLAYWRIGHT_DEPENDENCY_PATTERNS[:2]) or (
        _PLAYWRIGHT_DEPENDENCY_PATTERNS[0].search(text) and _PLAYWRIGHT_DEPENDENCY_PATTERNS[2].search(text)
    ):
        return True, "playwright_executable_missing"
    if _PLAYWRIGHT_DEPENDENCY_PATTERNS[1].search(text) and _PLAYWRIGHT_DEPENDENCY_PATTERNS[2].search(text):
        return True, "playwright_install_loop_hint"
    return False, ""


def run_stage(
    *,
    cmd: List[str],
    cwd: Path,
    log_path: Path,
    heartbeat_path: Path,
    poll_seconds: int,
    budget_seconds: int,
    env: Dict[str, str] | None = None,
    enable_tests_env_failfast: bool = False,
) -> Dict[str, object]:
    raw_exit_code = 0
    killed_flag = 0
    watchdog_marker = 0
    signal_name = ""
    reason_code = ""
    reason = ""
    start_monotonic = time.monotonic()
    with log_path.open("w", encoding="utf-8") as log_file, heartbeat_path.open("w", encoding="utf-8") as heartbeat_file:
        proc = subprocess.Popen(
            cmd,
            cwd=str(cwd),
            env=env,
            stdout=log_file,
            stderr=subprocess.STDOUT,
            text=True,
        )
        while True:
            rc = proc.poll()
            now = time.time()
            elapsed = max(time.monotonic() - start_monotonic, 0.0)
            size = log_path.stat().st_size if log_path.exists() else 0
            tail = ""
            if log_path.exists() and size > 0:
                try:
                    tail = log_path.read_text(encoding="utf-8", errors="replace").splitlines()[-1][:220]
                except Exception:
                    tail = ""
            heartbeat_file.write(f"{int(now)} pid={proc.pid} size={size} elapsed={int(elapsed)} tail={tail}\n")
            heartbeat_file.flush()
            if rc is not None:
                raw_exit_code = int(rc)
                break
            if enable_tests_env_failfast:
                dep_hit, dep_reason = _detect_tests_env_dependency_issue(log_path)
                if dep_hit:
                    killed_flag = 1
                    signal_name = "SIGTERM"
                    reason_code = TESTS_ENV_DEP_MISSING_REASON_CODE
                    reason = dep_reason
                    proc.terminate()
                    terminate_deadline = time.monotonic() + WATCHDOG_GRACE_SECONDS
                    while proc.poll() is None and time.monotonic() < terminate_deadline:
                        time.sleep(0.2)
                    if proc.poll() is None:
                        signal_name = "SIGKILL"
                        proc.kill()
                    while proc.poll() is None:
                        time.sleep(0.1)
                    raw_exit_code = int(proc.poll() or 0)
                    break
            if budget_seconds > 0 and elapsed >= float(budget_seconds) and watchdog_marker == 0:
                watchdog_marker = 1
                killed_flag = 1
                signal_name = "SIGTERM"
                proc.terminate()
                terminate_deadline = time.monotonic() + WATCHDOG_GRACE_SECONDS
                while proc.poll() is None and time.monotonic() < terminate_deadline:
                    time.sleep(0.2)
                if proc.poll() is None:
                    signal_name = "SIGKILL"
                    proc.kill()
                while proc.poll() is None:
                    time.sleep(0.1)
                raw_exit_code = int(proc.poll() or 0)
                break
            sleep_seconds = max(poll_seconds, 1)
            if budget_seconds > 0:
                sleep_seconds = min(sleep_seconds, 1)
            time.sleep(sleep_seconds)
    normalized_exit_code = _normalize_exit_code(raw_exit_code)
    if not signal_name and raw_exit_code < 0:
        signal_name = _signal_name_from_number(abs(raw_exit_code))
    return {
        "exit_code": normalized_exit_code,
        "raw_exit_code": raw_exit_code,
        "signal": signal_name,
        "killed_flag": int(killed_flag),
        "watchdog_marker": int(watchdog_marker),
        "reason_code": reason_code,
        "reason": reason,
        "stage_elapsed_seconds": int(max(time.monotonic() - start_monotonic, 0.0)),
    }


def _termination_classification(
    exit_code: int,
    *,
    killed_flag: int,
    watchdog_marker: int,
    reason_code: str = "",
) -> str:
    normalized_reason = str(reason_code or "").strip().lower()
    if normalized_reason == TESTS_ENV_DEP_MISSING_REASON_CODE:
        return f"NOT VERIFIED ({TESTS_ENV_DEP_MISSING_REASON_CODE}) + prompt-exec issue ({TESTS_ENV_DEP_MISSING_REASON_CODE})"
    if killed_flag and watchdog_marker:
        return "NOT VERIFIED (killed) + prompt-exec issue (watchdog_terminated)"
    if int(exit_code) == 143:
        return "ENV_MISCONFIG(parent_terminated_or_external_terminate)"
    return "completed"


def write_termination_attribution(
    *,
    out_path: Path,
    step: str,
    run: int,
    exit_code: int,
    signal_name: str,
    killed_flag: int,
    watchdog_marker: int,
    reason_code: str,
    reason: str,
    stage_elapsed_seconds: int,
    evidence_paths: List[Path],
) -> None:
    classification = _termination_classification(
        int(exit_code),
        killed_flag=int(killed_flag),
        watchdog_marker=int(watchdog_marker),
        reason_code=reason_code,
    )
    evidence = ",".join(str(path.name) for path in evidence_paths if path is not None)
    lines = [
        f"step={step}",
        f"run={run}",
        f"exit_code={int(exit_code)}",
        f"signal={signal_name}",
        f"killed_flag={int(killed_flag)}",
        f"watchdog_marker={int(watchdog_marker)}",
        f"reason_code={reason_code}",
        f"reason={reason}",
        f"stage_elapsed_seconds={int(stage_elapsed_seconds)}",
        f"parent_pid={os.getpid()}",
        f"classification={classification}",
        f"evidence_paths={evidence}",
    ]
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


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
    parser.add_argument("--budget-seconds", type=int, default=0)
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
        paths["env_misconfig"].write_text("\n".join(no_space) + "\n", encoding="utf-8")
        return 12

    cwd_reason = ""
    if project_dir == plugin_dir:
        cwd_reason = "project_dir_equals_plugin_dir"
    elif _looks_like_plugin_root(project_dir):
        cwd_reason = "project_dir_looks_like_plugin_root"
    if cwd_reason:
        write_cwd_blocker_artifacts(
            paths=paths,
            step=args.step,
            run=args.run,
            project_dir=project_dir,
            plugin_dir=plugin_dir,
            reason_detail=cwd_reason,
            stage_command=args.stage_command,
            mode=args.mode,
        )
        return CWD_BLOCKER_EXIT_CODE

    cmd = build_command(stage_command=args.stage_command, plugin_dir=plugin_dir, mode=args.mode)
    lock_ticket = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(args.ticket or "no-ticket")).strip("._-") or "no-ticket"
    stage_run_lock_id = f"{args.step}-run{args.run}-{lock_ticket}"
    launch_env = os.environ.copy()
    launch_env["AIDD_STAGE_RUN_LOCK_ID"] = stage_run_lock_id
    paths["cmd"].write_text(
        "\n".join(
            [
                f"cwd={project_dir}",
                f"mode={args.mode}",
                f"stage_run_lock_id={stage_run_lock_id}",
                "command=" + " ".join(cmd),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    run_start_epoch = int(time.time())
    stage_run = run_stage(
        cmd=cmd,
        cwd=project_dir,
        log_path=paths["log"],
        heartbeat_path=paths["heartbeat"],
        poll_seconds=args.poll_seconds,
        budget_seconds=max(int(args.budget_seconds or 0), 0),
        env=launch_env,
        enable_tests_env_failfast=args.step.startswith("06_implement")
        or "/feature-dev-aidd:implement" in args.stage_command,
    )
    exit_code = int(stage_run.get("exit_code") or 0)
    write_termination_attribution(
        out_path=paths["termination"],
        step=args.step,
        run=args.run,
        exit_code=exit_code,
        signal_name=str(stage_run.get("signal") or ""),
        killed_flag=int(stage_run.get("killed_flag") or 0),
        watchdog_marker=int(stage_run.get("watchdog_marker") or 0),
        reason_code=str(stage_run.get("reason_code") or ""),
        reason=str(stage_run.get("reason") or ""),
        stage_elapsed_seconds=int(stage_run.get("stage_elapsed_seconds") or 0),
        evidence_paths=[paths["log"], paths["heartbeat"], paths["summary"]],
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
    )

    liveness = build_liveness_payload(
        main_log=paths["log"],
        valid_stream_paths=list(stream_result.get("valid_paths") or []),
        run_start_epoch=run_start_epoch,
    )
    write_liveness_report(liveness, paths["stream_liveness"])

    summary_lines = [
        f"exit_code={exit_code}",
        f"effective_exit_code={exit_code}",
        f"killed_flag={int(stage_run.get('killed_flag') or 0)}",
        f"watchdog_marker={int(stage_run.get('watchdog_marker') or 0)}",
        f"signal={str(stage_run.get('signal') or '')}",
        f"reason_code={str(stage_run.get('reason_code') or '')}",
        f"reason={str(stage_run.get('reason') or '')}",
        f"stage_elapsed_seconds={int(stage_run.get('stage_elapsed_seconds') or 0)}",
        f"result_count={_detect_result_count(log_text)}",
        f"top_level_result={_detect_top_level_result(log_text)}",
        f"primary_stream_count={stream_result['primary_candidates']}",
        f"valid_stream_count={stream_result['valid_count']}",
        f"invalid_stream_count={stream_result['invalid_count']}",
        f"missing_stream_count={stream_result['missing_count']}",
        f"fallback_used={stream_result['used_fallback']}",
        f"stream_path_not_emitted_by_cli={stream_result['cli_not_emitted']}",
    ]
    paths["summary"].write_text("\n".join(summary_lines) + "\n", encoding="utf-8")
    return int(exit_code)


if __name__ == "__main__":
    raise SystemExit(main())
