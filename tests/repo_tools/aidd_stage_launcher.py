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
from typing import Any, Dict, List, Mapping, Tuple


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
TOP_LEVEL_STATUS_TOKENS = ("blocked", "done", "ship", "success", "error", "continue", "pending")
STATUS_TEXT_PATTERNS = (
    re.compile(r'"status"\s*:\s*"(blocked|done|ship|success|error|continue|pending)"', re.IGNORECASE),
    re.compile(r"\bstatus=(blocked|done|ship|success|error|continue|pending)\b", re.IGNORECASE),
    re.compile(r"\bresult=(blocked|done|ship|success|error|continue|pending)\b", re.IGNORECASE),
    re.compile(r"\*\*\s*статус\s*:\s*(blocked|done|ship|success|error|continue|pending)\s*\*\*", re.IGNORECASE),
    re.compile(r"\bстатус\s*:\s*(blocked|done|ship|success|error|continue|pending)\b", re.IGNORECASE),
    re.compile(r"^\s*\*\*(blocked|done|ship|success|error|continue|pending)\*\*", re.IGNORECASE | re.MULTILINE),
    re.compile(r"^\s*(blocked|done|ship|success|error|continue|pending)\b", re.IGNORECASE | re.MULTILINE),
)
QUESTION_HEADING_RE = re.compile(
    r"^\s*(?:#+\s*)?(?:\*\*)?(?:Вопрос|Question)\s+(\d+)(?:\s*\(([^)]+)\))?(?::\s*(.*))?\s*(?:\*\*)?\s*$",
    re.IGNORECASE,
)
QUESTION_NUMBER_RE = re.compile(r"\b(?:Q|Вопрос|Question)\s*([0-9]+)\b", re.IGNORECASE)
WHY_LINE_RE = re.compile(r"^\s*(?:\*\*)?(?:Зачем|Why)(?:\*\*)?:\s*(.+?)\s*$", re.IGNORECASE)
OPTIONS_HEADER_RE = re.compile(r"^\s*(?:\*\*)?(?:Варианты|Options|Choices)(?:\*\*)?:?\s*$", re.IGNORECASE)
DEFAULT_LINE_RE = re.compile(r"^\s*(?:\*\*)?Default(?:\*\*)?:\s*([A-Z])\b", re.IGNORECASE)
OPTION_LINE_RE = re.compile(r"^\s*[-*]?\s*(?:\*\*)?([A-Z])\)(?:\*\*)?\s*(.+?)\s*$")
QUESTION_STAGE_HINT_RE = re.compile(r"(idea[-_ ]new|plan[-_ ]new|05_idea_new|05_plan_new)", re.IGNORECASE)
AIDD_OPEN_QUESTIONS_HEADING_RE = re.compile(r"^\s*##\s+AIDD:OPEN_QUESTIONS\s*$", re.IGNORECASE | re.MULTILINE)
SECTION_HEADING_RE = re.compile(r"^\s*##\s+.+$", re.MULTILINE)


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
        "questions_raw": audit_dir / f"{step}_questions_raw.txt",
        "questions_normalized": audit_dir / f"{step}_questions_normalized.txt",
        "questions_json": audit_dir / f"{step}_questions.json",
        "retry_payload": audit_dir / f"{step}_retry_payload_run{run}.txt",
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
    if re.search(r"\bstatus=(blocked|done|ship|success|error|continue|pending)\b", log_text, re.IGNORECASE):
        return 1
    return 0


def _iter_json_events(log_text: str) -> List[Dict[str, Any]]:
    events: List[Dict[str, Any]] = []
    for raw in str(log_text or "").splitlines():
        line = raw.strip()
        if not line.startswith("{"):
            continue
        try:
            payload = json.loads(line)
        except Exception:
            continue
        if isinstance(payload, dict):
            events.append(payload)
    return events


def _last_result_event(log_text: str) -> Dict[str, Any] | None:
    for event in reversed(_iter_json_events(log_text)):
        if str(event.get("type") or "").strip().lower() == "result":
            return event
    return None


def _last_top_level_assistant_text(log_text: str) -> str:
    for event in reversed(_iter_json_events(log_text)):
        if str(event.get("type") or "").strip().lower() != "assistant":
            continue
        if event.get("parent_tool_use_id") is not None:
            continue
        message = event.get("message")
        if not isinstance(message, dict):
            continue
        if str(message.get("role") or "").strip().lower() != "assistant":
            continue
        parts = message.get("content") or []
        texts: List[str] = []
        for part in parts:
            if not isinstance(part, dict):
                continue
            if str(part.get("type") or "").strip().lower() != "text":
                continue
            text = str(part.get("text") or "").strip()
            if text:
                texts.append(text)
        if texts:
            return "\n\n".join(texts)
    return ""


def _clean_text(value: str) -> str:
    text = str(value or "").strip()
    while True:
        updated = text.strip()
        if updated.startswith("**") and updated.endswith("**") and len(updated) >= 4:
            text = updated[2:-2].strip()
            continue
        if updated.startswith("`") and updated.endswith("`") and len(updated) >= 2:
            text = updated[1:-1].strip()
            continue
        return updated


def _plain_text_markers(value: str) -> str:
    return str(value or "").replace("**", "").replace("`", "").strip()


def _detect_top_level_status(log_text: str) -> str:
    result_event = _last_result_event(log_text)
    candidate_texts: List[str] = []
    if result_event:
        candidate_texts.append(str(result_event.get("result") or ""))
        candidate_texts.append(json.dumps(result_event, ensure_ascii=False))
    assistant_text = _last_top_level_assistant_text(log_text)
    if assistant_text:
        candidate_texts.append(assistant_text)
    candidate_texts.append(str(log_text or ""))
    for text in candidate_texts:
        for pattern in STATUS_TEXT_PATTERNS:
            match = pattern.search(text)
            if match:
                return str(match.group(1) or "").strip().lower()
    return ""


def _normalize_question_number(raw_number: object) -> int:
    try:
        value = int(str(raw_number).strip())
    except Exception:
        return 0
    return value if value > 0 else 0


def _parse_command_answers(stage_command: str) -> Dict[str, str]:
    text = str(stage_command or "")
    if "AIDD:ANSWERS" not in text:
        return {}
    _, tail = text.split("AIDD:ANSWERS", 1)
    matches = re.finditer(r"\bQ([0-9]+)=((?:\"[^\"]*\")|(?:'[^']*')|[^;\s]+)", tail)
    payload: Dict[str, str] = {}
    for match in matches:
        number = _normalize_question_number(match.group(1))
        if not number:
            continue
        value = str(match.group(2) or "").strip()
        payload[f"Q{number}"] = value
    return payload


def _normalize_choice(value: str) -> str:
    token = str(value or "").strip().upper()
    if re.fullmatch(r"[A-Z]", token):
        return token
    return ""


def _extract_number_from_header_or_text(header: str, text: str) -> int:
    for source in (text, header):
        match = QUESTION_NUMBER_RE.search(str(source or ""))
        if match:
            return _normalize_question_number(match.group(1))
    return 0


def _extract_default_from_options(options: List[Dict[str, str]]) -> str:
    for option in options:
        label = str(option.get("label") or "")
        description = str(option.get("description") or "")
        if "recommended" in label.lower() or "recommended" in description.lower():
            choice = _normalize_choice(option.get("choice") or "")
            if choice:
                return choice
    return ""


def _normalize_option_entry(raw_label: str, raw_description: str) -> Dict[str, str]:
    label = _clean_text(raw_label)
    description = _clean_text(raw_description)
    choice = ""
    match = re.match(r"^\s*([A-Z])\)", label)
    if match:
        choice = _normalize_choice(match.group(1))
        label = label[match.end() :].strip()
    if not choice:
        match = re.match(r"^\s*([A-Z])\)", description)
        if match:
            choice = _normalize_choice(match.group(1))
            description = description[match.end() :].strip()
    return {
        "choice": choice,
        "label": label,
        "description": description,
    }


def _build_question_entry(
    *,
    number: int,
    source: str,
    kind: str = "",
    header: str = "",
    question: str = "",
    why: str = "",
    options: List[Dict[str, str]] | None = None,
    default: str = "",
) -> Dict[str, Any]:
    return {
        "id": f"Q{number}",
        "number": number,
        "source": source,
        "kind": _clean_text(kind),
        "header": _clean_text(header),
        "question": _clean_text(question),
        "why": _clean_text(why),
        "options": list(options or []),
        "default": _normalize_choice(default),
    }


def _extract_questions_from_permission_denials(result_event: Mapping[str, Any]) -> List[Dict[str, Any]]:
    questions: List[Dict[str, Any]] = []
    permission_denials = result_event.get("permission_denials") or []
    for denial in permission_denials:
        if not isinstance(denial, dict):
            continue
        if str(denial.get("tool_name") or "").strip() != "AskUserQuestion":
            continue
        tool_input = denial.get("tool_input")
        if not isinstance(tool_input, dict):
            continue
        for raw_item in tool_input.get("questions") or []:
            if not isinstance(raw_item, dict):
                continue
            prompt_text = str(raw_item.get("question") or "").strip()
            header = str(raw_item.get("header") or "").strip()
            heading_match = QUESTION_HEADING_RE.match(prompt_text)
            number = _extract_number_from_header_or_text(header, prompt_text)
            if not number:
                continue
            kind = heading_match.group(2) if heading_match else ""
            question = heading_match.group(3) if heading_match and heading_match.group(3) else prompt_text
            options: List[Dict[str, str]] = []
            for raw_option in raw_item.get("options") or []:
                if not isinstance(raw_option, dict):
                    continue
                options.append(
                    _normalize_option_entry(
                        str(raw_option.get("label") or ""),
                        str(raw_option.get("description") or ""),
                    )
                )
            questions.append(
                _build_question_entry(
                    number=number,
                    source="result_permission_denials",
                    kind=kind,
                    header=header,
                    question=question,
                    options=options,
                    default=_extract_default_from_options(options),
                )
            )
    return _dedupe_questions(questions)


def _extract_questions_from_text(text: str, *, source: str) -> List[Dict[str, Any]]:
    lines = str(text or "").splitlines()
    headings: List[Tuple[int, re.Match[str]]] = []
    for idx, raw in enumerate(lines):
        match = QUESTION_HEADING_RE.match(raw)
        if match:
            headings.append((idx, match))
    if not headings:
        return []

    questions: List[Dict[str, Any]] = []
    for pos, (line_idx, match) in enumerate(headings):
        number = _normalize_question_number(match.group(1))
        if not number:
            continue
        kind = match.group(2) or ""
        inline_question = _clean_text(match.group(3) or "")
        next_idx = headings[pos + 1][0] if pos + 1 < len(headings) else len(lines)
        body = lines[line_idx + 1 : next_idx]

        question_text = inline_question
        why = ""
        options: List[Dict[str, str]] = []
        default = ""
        in_options = False

        for raw in body:
            line = raw.strip()
            if not line:
                continue
            plain_line = _plain_text_markers(line)
            why_match = WHY_LINE_RE.match(plain_line)
            if why_match and not why:
                why = why_match.group(1).strip()
                in_options = False
                continue
            default_match = DEFAULT_LINE_RE.match(plain_line)
            if default_match and not default:
                default = default_match.group(1).strip().upper()
                in_options = False
                continue
            if OPTIONS_HEADER_RE.match(plain_line):
                in_options = True
                continue
            option_match = OPTION_LINE_RE.match(line)
            if option_match:
                in_options = True
                options.append(
                    {
                        "choice": _normalize_choice(option_match.group(1)),
                        "label": "",
                        "description": _clean_text(option_match.group(2)),
                    }
                )
                continue
            if in_options:
                choice_matches = re.findall(r"([A-Z])\)\s*([^A-Z]+?)(?=(?:\s+[A-Z]\))|$)", line)
                if choice_matches:
                    for choice, description in choice_matches:
                        options.append(
                            {
                                "choice": _normalize_choice(choice),
                                "label": "",
                                "description": _clean_text(description),
                            }
                        )
                    continue
            if not question_text:
                question_text = _clean_text(line)
        questions.append(
            _build_question_entry(
                number=number,
                source=source,
                kind=kind,
                question=question_text,
                why=why,
                options=options,
                default=default,
            )
        )
    return _dedupe_questions(questions)


def _extract_questions_from_persisted_doc(project_dir: Path, ticket: str) -> List[Dict[str, Any]]:
    if not ticket:
        return []
    aidd_root = project_dir / "aidd"
    if not aidd_root.exists():
        aidd_root = project_dir
    candidates = [
        aidd_root / "docs" / "prd" / f"{ticket}.prd.md",
        aidd_root / "docs" / "plan" / f"{ticket}.md",
    ]
    for candidate in candidates:
        if not candidate.exists():
            continue
        text = candidate.read_text(encoding="utf-8", errors="replace")
        open_ids = _extract_open_question_ids_from_persisted_doc(text)
        questions = _extract_questions_from_text(text, source=f"persisted_doc:{candidate.name}")
        if open_ids:
            filtered = [item for item in questions if int(item.get("number") or 0) in open_ids]
            if filtered:
                return filtered
        if questions:
            return questions
    return []


def _extract_open_question_ids_from_persisted_doc(text: str) -> set[int]:
    match = AIDD_OPEN_QUESTIONS_HEADING_RE.search(text)
    if not match:
        return set()
    start = match.end()
    next_heading = SECTION_HEADING_RE.search(text, start)
    end = next_heading.start() if next_heading else len(text)
    section = text[start:end]
    if re.search(r"^\s*-\s*`?none`?\s*$", section, re.IGNORECASE | re.MULTILINE):
        return set()
    ids = {
        _normalize_question_number(found.group(1))
        for found in re.finditer(r"\bQ([0-9]+)\b", section)
    }
    return {number for number in ids if number > 0}


def _dedupe_questions(questions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    deduped: Dict[int, Dict[str, Any]] = {}
    for question in questions:
        number = _normalize_question_number(question.get("number"))
        if not number:
            continue
        current = deduped.get(number)
        if current is None:
            deduped[number] = dict(question)
            continue
        current_score = sum(
            1
            for key in ("question", "why", "default", "header", "kind")
            if str(current.get(key) or "").strip()
        ) + len(current.get("options") or [])
        new_score = sum(
            1
            for key in ("question", "why", "default", "header", "kind")
            if str(question.get(key) or "").strip()
        ) + len(question.get("options") or [])
        if new_score > current_score:
            deduped[number] = dict(question)
    return [deduped[number] for number in sorted(deduped)]


def extract_question_cycle(
    *,
    log_text: str,
    project_dir: Path,
    ticket: str,
) -> Dict[str, Any]:
    result_event = _last_result_event(log_text)
    top_level_status = _detect_top_level_status(log_text)
    sources: List[Tuple[str, List[Dict[str, Any]]]] = []
    if result_event:
        sources.append(
            (
                "result_permission_denials",
                _extract_questions_from_permission_denials(result_event),
            )
        )
        sources.append(
            (
                "result_text",
                _extract_questions_from_text(str(result_event.get("result") or ""), source="result_text"),
            )
        )
    assistant_text = _last_top_level_assistant_text(log_text)
    if assistant_text:
        sources.append(("assistant_text", _extract_questions_from_text(assistant_text, source="assistant_text")))
    persisted_questions = _extract_questions_from_persisted_doc(project_dir=project_dir, ticket=ticket)
    if persisted_questions:
        sources.append(("persisted_doc", persisted_questions))

    selected_source = "none"
    selected_questions: List[Dict[str, Any]] = []
    for source, questions in sources:
        if questions:
            selected_source = source
            selected_questions = questions
            break

    pending_ids = [str(item.get("id") or f"Q{item.get('number')}") for item in selected_questions]
    question_cycle_required = int(bool(selected_questions))
    return {
        "source": selected_source,
        "top_level_status": top_level_status,
        "question_cycle_required": question_cycle_required,
        "pending_question_count": len(selected_questions),
        "pending_question_ids": pending_ids,
        "questions": selected_questions,
    }


def _format_questions_raw(question_cycle: Mapping[str, Any]) -> str:
    lines = [
        f"source={str(question_cycle.get('source') or 'none')}",
        f"top_level_status={str(question_cycle.get('top_level_status') or '')}",
        f"question_cycle_required={int(bool(question_cycle.get('question_cycle_required')))}",
        f"pending_question_count={int(question_cycle.get('pending_question_count') or 0)}",
        "pending_question_ids=" + ",".join(str(item) for item in question_cycle.get("pending_question_ids") or []),
    ]
    for question in question_cycle.get("questions") or []:
        if not isinstance(question, dict):
            continue
        lines.extend(
            [
                "",
                f"## {question.get('id')}",
                f"kind={question.get('kind') or ''}",
                f"header={question.get('header') or ''}",
                f"question={question.get('question') or ''}",
                f"why={question.get('why') or ''}",
                f"default={question.get('default') or ''}",
            ]
        )
        options = question.get("options") or []
        if isinstance(options, list):
            for option in options:
                if not isinstance(option, dict):
                    continue
                lines.append(
                    "option="
                    + f"{option.get('choice') or ''}|{option.get('label') or ''}|{option.get('description') or ''}"
                )
    return "\n".join(lines).strip() + "\n"


def _format_questions_normalized(question_cycle: Mapping[str, Any]) -> str:
    lines = [
        f"source={str(question_cycle.get('source') or 'none')}",
        f"top_level_status={str(question_cycle.get('top_level_status') or '')}",
        f"question_cycle_required={int(bool(question_cycle.get('question_cycle_required')))}",
    ]
    for question in question_cycle.get("questions") or []:
        if not isinstance(question, dict):
            continue
        options = question.get("options") or []
        choices = ",".join(
            str(option.get("choice") or "").strip()
            for option in options
            if isinstance(option, dict) and str(option.get("choice") or "").strip()
        )
        lines.append(
            "|".join(
                [
                    str(question.get("id") or ""),
                    f"kind={question.get('kind') or ''}",
                    f"default={question.get('default') or ''}",
                    f"choices={choices}",
                    f"header={question.get('header') or ''}",
                    "question=" + str(question.get("question") or "").replace("\n", " ").strip(),
                ]
            )
        )
    return "\n".join(lines).strip() + "\n"


def write_question_sidecars(question_cycle: Mapping[str, Any], *, raw_path: Path, normalized_path: Path, json_path: Path) -> None:
    raw_path.write_text(_format_questions_raw(question_cycle), encoding="utf-8")
    normalized_path.write_text(_format_questions_normalized(question_cycle), encoding="utf-8")
    json_path.write_text(json.dumps(question_cycle, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _load_question_cycle_from_normalized_file(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {"questions": []}
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    questions: List[Dict[str, Any]] = []
    for raw in lines:
        line = raw.strip()
        if not line or "|" not in line or not line.startswith("Q"):
            continue
        parts = line.split("|")
        question_id = parts[0].strip()
        match = re.fullmatch(r"Q([0-9]+)", question_id)
        if not match:
            continue
        number = _normalize_question_number(match.group(1))
        if not number:
            continue
        questions.append({"id": f"Q{number}", "number": number})
    return {"questions": questions}


def materialize_retry_payload(
    question_cycle: Mapping[str, Any],
    answers_map: Mapping[str, object],
) -> Dict[str, Any]:
    normalized_answers: Dict[int, str] = {}
    for raw_key, raw_value in dict(answers_map).items():
        value = str(raw_value or "").strip()
        if not value:
            continue
        key_text = str(raw_key or "").strip()
        match = QUESTION_NUMBER_RE.search(key_text)
        number = _normalize_question_number(match.group(1)) if match else _normalize_question_number(key_text)
        if not number:
            continue
        if re.fullmatch(r"[A-Za-z]", value):
            value = value.upper()
        elif " " in value and not (value.startswith('"') and value.endswith('"')):
            value = json.dumps(value, ensure_ascii=False)
        normalized_answers[number] = value

    pending_numbers = [
        _normalize_question_number(question.get("number"))
        for question in question_cycle.get("questions") or []
        if isinstance(question, dict)
    ]
    pending_numbers = [number for number in pending_numbers if number > 0]
    unanswered_ids = [f"Q{number}" for number in pending_numbers if number not in normalized_answers]
    answered_ids = [f"Q{number}" for number in pending_numbers if number in normalized_answers]
    if unanswered_ids:
        return {
            "retry_attempted": int(bool(normalized_answers)),
            "complete": False,
            "payload": "",
            "answered_question_ids": answered_ids,
            "unanswered_question_ids": unanswered_ids,
        }
    if not pending_numbers:
        return {
            "retry_attempted": int(bool(normalized_answers)),
            "complete": False,
            "payload": "",
            "answered_question_ids": [],
            "unanswered_question_ids": [],
        }
    parts = [f"Q{number}={normalized_answers[number]}" for number in pending_numbers]
    return {
        "retry_attempted": int(bool(normalized_answers)),
        "complete": True,
        "payload": "AIDD:ANSWERS " + "; ".join(parts),
        "answered_question_ids": answered_ids,
        "unanswered_question_ids": [],
    }


def materialize_retry_payload_from_normalized_file(normalized_path: Path, stage_command: str) -> Dict[str, Any]:
    question_cycle = _load_question_cycle_from_normalized_file(normalized_path)
    answers_map = _parse_command_answers(stage_command)
    payload = materialize_retry_payload(question_cycle, answers_map)
    payload["source"] = "normalized_questions+stage_command"
    payload["command_answer_ids"] = sorted(answers_map)
    return payload


def write_retry_payload_sidecar(payload: Mapping[str, Any], out_path: Path) -> None:
    lines = [
        f"source={str(payload.get('source') or '')}",
        f"retry_attempted={int(payload.get('retry_attempted') or 0)}",
        f"complete={int(bool(payload.get('complete')))}",
        "answered_question_ids=" + ",".join(str(item) for item in payload.get("answered_question_ids") or []),
        "unanswered_question_ids=" + ",".join(str(item) for item in payload.get("unanswered_question_ids") or []),
        "command_answer_ids=" + ",".join(str(item) for item in payload.get("command_answer_ids") or []),
        f"payload={str(payload.get('payload') or '')}",
    ]
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


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

    question_cycle = extract_question_cycle(
        log_text=log_text,
        project_dir=project_dir,
        ticket=str(args.ticket or ""),
    )
    write_question_sidecars(
        question_cycle,
        raw_path=paths["questions_raw"],
        normalized_path=paths["questions_normalized"],
        json_path=paths["questions_json"],
    )
    retry_payload = materialize_retry_payload_from_normalized_file(
        paths["questions_normalized"],
        args.stage_command,
    )
    write_retry_payload_sidecar(retry_payload, paths["retry_payload"])
    retry_attempted = int(retry_payload.get("retry_attempted") or 0)
    question_retry_incomplete = int(
        retry_attempted
        and not bool(retry_payload.get("complete"))
        and bool(retry_payload.get("unanswered_question_ids") or [])
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
        f"top_level_status={str(question_cycle.get('top_level_status') or '')}",
        f"question_cycle_required={int(bool(question_cycle.get('question_cycle_required')))}",
        f"pending_question_count={int(question_cycle.get('pending_question_count') or 0)}",
        "pending_question_ids=" + ",".join(str(item) for item in question_cycle.get("pending_question_ids") or []),
        f"retry_attempted={retry_attempted}",
        "answered_question_ids=" + ",".join(str(item) for item in retry_payload.get("answered_question_ids") or []),
        "unanswered_question_ids=" + ",".join(str(item) for item in retry_payload.get("unanswered_question_ids") or []),
        f"question_retry_incomplete={question_retry_incomplete}",
        f"question_source={str(question_cycle.get('source') or 'none')}",
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
