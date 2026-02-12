#!/usr/bin/env python3
"""Runner/wrapper execution helpers for loop-step."""

from __future__ import annotations

import datetime as dt
import os
import shlex
import shutil
import subprocess
import sys
import threading
from pathlib import Path
from typing import Dict, List, Optional, TextIO, Tuple

from aidd_runtime import claude_stream_render
from aidd_runtime import runtime

_APPROVAL_ALLOW_VALUES = {"1", "true", "yes", "on"}
_CLAUDE_COMMANDS = {"claude", "claude.exe"}


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


def _strip_flag_with_value(tokens: List[str], flag: str) -> Tuple[List[str], bool]:
    cleaned: List[str] = []
    stripped = False
    skip_next = False
    for token in tokens:
        if skip_next:
            skip_next = False
            stripped = True
            continue
        if token == flag:
            skip_next = True
            stripped = True
            continue
        if token.startswith(flag + "="):
            stripped = True
            continue
        cleaned.append(token)
    return cleaned, stripped


def inject_plugin_flags(tokens: List[str], plugin_root: Path) -> Tuple[List[str], List[str]]:
    notices: List[str] = []
    updated, stripped_plugin = _strip_flag_with_value(tokens, "--plugin-dir")
    updated, stripped_add = _strip_flag_with_value(updated, "--add-dir")
    if stripped_plugin or stripped_add:
        notices.append("runner plugin flags replaced with CLAUDE_PLUGIN_ROOT")
    updated.extend(["--plugin-dir", str(plugin_root), "--add-dir", str(plugin_root)])
    return updated, notices


def validate_command_available(plugin_root: Path, stage: str) -> Tuple[bool, str, str]:
    if not plugin_root.exists():
        return False, f"plugin root not found: {plugin_root}", "plugin_root_missing"
    skill_path = plugin_root / "skills" / stage / "SKILL.md"
    if skill_path.exists():
        return True, "", ""
    command_path = plugin_root / "commands" / f"{stage}.md"
    if command_path.exists():
        return True, "", ""
    return False, f"command not found: /feature-dev-aidd:{stage}", "command_unavailable"


def resolve_runner(args_runner: str | None, plugin_root: Path) -> Tuple[List[str], str, str]:
    raw = args_runner or os.environ.get("AIDD_LOOP_RUNNER") or "claude"
    tokens = shlex.split(raw) if raw.strip() else ["claude"]
    notices: List[str] = []
    if "-p" in tokens:
        tokens = [token for token in tokens if token != "-p"]
        notices.append("runner flag -p dropped; loop-step adds -p with slash command")
    if "--no-session-persistence" in tokens:
        if not runner_supports_flag(tokens[0], "--no-session-persistence"):
            tokens = [token for token in tokens if token != "--no-session-persistence"]
            notices.append("runner flag --no-session-persistence unsupported; dropped")
    approval_allowed = str(os.environ.get("AIDD_LOOP_ALLOW_APPROVAL") or "").strip().lower() in _APPROVAL_ALLOW_VALUES
    runner_name = Path(tokens[0]).name.lower() if tokens else ""
    if not approval_allowed and runner_name in _CLAUDE_COMMANDS:
        if "--dangerously-skip-permissions" not in tokens:
            if runner_supports_flag(tokens[0], "--dangerously-skip-permissions"):
                tokens.append("--dangerously-skip-permissions")
                notices.append("runner flag --dangerously-skip-permissions enforced for loop non-interactive mode")
            else:
                notices.append("runner missing --dangerously-skip-permissions support")
    tokens, flag_notices = inject_plugin_flags(tokens, plugin_root)
    notices.extend(flag_notices)
    return tokens, raw, "; ".join(notices)


def _parse_wrapper_output(stdout: str) -> Dict[str, str]:
    payload: Dict[str, str] = {}
    for raw in stdout.splitlines():
        line = raw.strip()
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not key or not value:
            continue
        payload[key] = value
    return payload


def _runtime_env(plugin_root: Path) -> Dict[str, str]:
    env = os.environ.copy()
    env["CLAUDE_PLUGIN_ROOT"] = str(plugin_root)
    current = env.get("PYTHONPATH", "")
    if current:
        parts = current.split(os.pathsep)
        if str(plugin_root) not in parts:
            env["PYTHONPATH"] = f"{plugin_root}{os.pathsep}{current}"
    else:
        env["PYTHONPATH"] = str(plugin_root)
    return env


def _validate_preflight_contract_inputs(
    *,
    stage: str,
    ticket: str,
    scope_key: str,
    work_item_key: str,
    paths: Dict[str, Path],
    target: Path,
) -> Tuple[bool, str]:
    missing: List[str] = []
    if not str(ticket or "").strip():
        missing.append("ticket")
    if not str(scope_key or "").strip():
        missing.append("scope_key")
    if stage not in {"implement", "review", "qa"}:
        missing.append("stage")
    if not str(work_item_key or "").strip():
        missing.append("work_item_key")
    elif not runtime.is_valid_work_item_key(work_item_key):
        return False, f"invalid work_item_key format: {work_item_key}"

    required_paths = (
        ("actions_template", paths.get("actions_template")),
        ("readmap_json", paths.get("readmap_json")),
        ("readmap_md", paths.get("readmap_md")),
        ("writemap_json", paths.get("writemap_json")),
        ("writemap_md", paths.get("writemap_md")),
        ("preflight_result", paths.get("preflight_result")),
    )
    for label, value in required_paths:
        if value is None:
            missing.append(label)
            continue
        rel = runtime.rel_path(value, target)
        if not rel or rel.strip() == ".":
            missing.append(label)

    if missing:
        joined = ",".join(sorted(set(missing)))
        return False, f"missing required preflight inputs: {joined}"
    return True, ""


def _stage_wrapper_log_path(target: Path, stage: str, ticket: str, scope_key: str, kind: str) -> Path:
    ts = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    log_dir = target / "reports" / "logs" / stage / ticket / scope_key
    log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir / f"wrapper.{kind}.{ts}.log"


def _append_stage_wrapper_log(log_path: Path, command: List[str], stdout: str, stderr: str) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write("$ " + " ".join(shlex.quote(token) for token in command) + "\n")
        handle.write("[stdout]\n")
        handle.write(stdout)
        if not stdout.endswith("\n"):
            handle.write("\n")
        handle.write("[stderr]\n")
        handle.write(stderr)
        if not stderr.endswith("\n"):
            handle.write("\n")


def _run_runtime_command(
    *,
    command: List[str],
    cwd: Path,
    env: Dict[str, str],
    log_path: Path,
) -> Tuple[int, str, str]:
    proc = subprocess.run(
        command,
        cwd=cwd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        env=env,
    )
    stdout = proc.stdout or ""
    stderr = proc.stderr or ""
    _append_stage_wrapper_log(log_path, command, stdout, stderr)
    return proc.returncode, stdout, stderr


def _resolve_stage_paths(target: Path, ticket: str, scope_key: str, stage: str) -> Dict[str, Path]:
    actions_dir = target / "reports" / "actions" / ticket / scope_key
    context_dir = target / "reports" / "context" / ticket
    loops_dir = target / "reports" / "loops" / ticket / scope_key
    return {
        "actions_template": actions_dir / f"{stage}.actions.template.json",
        "actions_path": actions_dir / f"{stage}.actions.json",
        "apply_log": actions_dir / f"{stage}.apply.jsonl",
        "readmap_json": context_dir / f"{scope_key}.readmap.json",
        "readmap_md": context_dir / f"{scope_key}.readmap.md",
        "writemap_json": context_dir / f"{scope_key}.writemap.json",
        "writemap_md": context_dir / f"{scope_key}.writemap.md",
        "preflight_result": loops_dir / "stage.preflight.result.json",
        "readmap_json_fallback": actions_dir / "readmap.json",
        "readmap_md_fallback": actions_dir / "readmap.md",
        "writemap_json_fallback": actions_dir / "writemap.json",
        "writemap_md_fallback": actions_dir / "writemap.md",
        "preflight_result_fallback": actions_dir / "stage.preflight.result.json",
    }


def _copy_optional_preflight_fallback(paths: Dict[str, Path]) -> None:
    if os.environ.get("AIDD_WRITE_FALLBACK_PREFLIGHT", "").strip() != "1":
        return
    mappings = (
        ("readmap_json", "readmap_json_fallback"),
        ("readmap_md", "readmap_md_fallback"),
        ("writemap_json", "writemap_json_fallback"),
        ("writemap_md", "writemap_md_fallback"),
        ("preflight_result", "preflight_result_fallback"),
    )
    for source_key, target_key in mappings:
        source = paths[source_key]
        target = paths[target_key]
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
    print(
        "[loop-step] WARN: fallback preflight artifacts emitted (AIDD_WRITE_FALLBACK_PREFLIGHT=1)",
        file=sys.stderr,
    )


def run_stage_wrapper(
    *,
    plugin_root: Path,
    workspace_root: Path,
    stage: str,
    kind: str,
    ticket: str,
    scope_key: str,
    work_item_key: str,
    actions_path: str = "",
    result: str = "",
    verdict: str = "",
) -> Tuple[bool, Dict[str, str], str]:
    _, target = runtime.require_workflow_root(workspace_root)
    env = _runtime_env(plugin_root)
    parsed: Dict[str, str] = {}
    paths = _resolve_stage_paths(target, ticket, scope_key, stage)
    wrapper_log_path = _stage_wrapper_log_path(target, stage, ticket, scope_key, kind)

    actions_provided = bool(actions_path)
    resolved_actions_path = (
        runtime.resolve_path_for_target(Path(actions_path), target)
        if actions_path
        else paths["actions_path"]
    )

    if kind == "preflight":
        ok_contract, contract_message = _validate_preflight_contract_inputs(
            stage=stage,
            ticket=ticket,
            scope_key=scope_key,
            work_item_key=work_item_key,
            paths=paths,
            target=target,
        )
        if not ok_contract:
            return (
                False,
                parsed,
                f"{kind} wrapper failed: reason_code=preflight_contract_mismatch {contract_message}",
            )
        commands: List[List[str]] = [
            [
                sys.executable,
                str(plugin_root / "skills" / "aidd-flow-state" / "runtime" / "set_active_feature.py"),
                ticket,
            ],
            [
                sys.executable,
                str(plugin_root / "skills" / "aidd-flow-state" / "runtime" / "set_active_stage.py"),
                stage,
            ],
        ]
        if stage == "implement":
            commands.append(
                [
                    sys.executable,
                    str(plugin_root / "skills" / "aidd-flow-state" / "runtime" / "prd_check.py"),
                    "--ticket",
                    ticket,
                ]
            )
        commands.extend(
            [
                [
                    sys.executable,
                    str(plugin_root / "skills" / "aidd-loop" / "runtime" / "preflight_prepare.py"),
                    "--ticket",
                    ticket,
                    "--scope-key",
                    scope_key,
                    "--work-item-key",
                    work_item_key,
                    "--stage",
                    stage,
                    "--actions-template",
                    runtime.rel_path(paths["actions_template"], target),
                    "--readmap-json",
                    runtime.rel_path(paths["readmap_json"], target),
                    "--readmap-md",
                    runtime.rel_path(paths["readmap_md"], target),
                    "--writemap-json",
                    runtime.rel_path(paths["writemap_json"], target),
                    "--writemap-md",
                    runtime.rel_path(paths["writemap_md"], target),
                    "--result",
                    runtime.rel_path(paths["preflight_result"], target),
                ],
                [
                    sys.executable,
                    str(plugin_root / "skills" / "aidd-docio" / "runtime" / "context_map_validate.py"),
                    "--map",
                    runtime.rel_path(paths["readmap_json"], target),
                ],
                [
                    sys.executable,
                    str(plugin_root / "skills" / "aidd-docio" / "runtime" / "context_map_validate.py"),
                    "--map",
                    runtime.rel_path(paths["writemap_json"], target),
                ],
                [
                    sys.executable,
                    str(plugin_root / "skills" / "aidd-docio" / "runtime" / "actions_validate.py"),
                    "--actions",
                    runtime.rel_path(paths["actions_template"], target),
                ],
                [
                    sys.executable,
                    str(plugin_root / "skills" / "aidd-loop" / "runtime" / "preflight_result_validate.py"),
                    "--result",
                    runtime.rel_path(paths["preflight_result"], target),
                ],
            ]
        )
        for command in commands:
            rc, stdout, stderr = _run_runtime_command(
                command=command,
                cwd=workspace_root,
                env=env,
                log_path=wrapper_log_path,
            )
            parsed.update(_parse_wrapper_output(stdout))
            if rc != 0:
                details = (stderr or stdout).strip() or f"exit={rc}"
                return False, parsed, f"{kind} wrapper failed: {details}"
        _copy_optional_preflight_fallback(paths)
        parsed.setdefault("log_path", runtime.rel_path(wrapper_log_path, target))
        parsed.setdefault("template_path", runtime.rel_path(paths["actions_template"], target))
        parsed.setdefault("readmap_path", runtime.rel_path(paths["readmap_json"], target))
        parsed.setdefault("writemap_path", runtime.rel_path(paths["writemap_json"], target))
        parsed.setdefault("preflight_result", runtime.rel_path(paths["preflight_result"], target))
        if not actions_provided:
            parsed.setdefault("actions_path", runtime.rel_path(resolved_actions_path, target))
        return True, parsed, ""

    if kind == "run":
        stage_runtime = {
            "implement": plugin_root / "skills" / "implement" / "runtime" / "implement_run.py",
            "review": plugin_root / "skills" / "review" / "runtime" / "review_run.py",
            "qa": plugin_root / "skills" / "qa" / "runtime" / "qa_run.py",
        }.get(stage)
        if not stage_runtime or not stage_runtime.exists():
            return False, parsed, f"run wrapper failed: stage runtime missing for {stage}"
        command = [
            sys.executable,
            str(stage_runtime),
            "--ticket",
            ticket,
            "--scope-key",
            scope_key,
            "--work-item-key",
            work_item_key,
            "--stage",
            stage,
        ]
        if actions_path:
            command.extend(["--actions", actions_path])
        rc, stdout, stderr = _run_runtime_command(
            command=command,
            cwd=workspace_root,
            env=env,
            log_path=wrapper_log_path,
        )
        parsed.update(_parse_wrapper_output(stdout))
        if rc != 0:
            details = (stderr or stdout).strip() or f"exit={rc}"
            return False, parsed, f"{kind} wrapper failed: {details}"
        parsed.setdefault("log_path", runtime.rel_path(wrapper_log_path, target))
        if not actions_provided:
            parsed.setdefault("actions_path", runtime.rel_path(resolved_actions_path, target))
        return True, parsed, ""

    if kind == "postflight":
        if not resolved_actions_path.exists():
            rel = runtime.rel_path(resolved_actions_path, target)
            return False, parsed, f"{kind} wrapper failed: actions file missing: {rel}"
        commands = [
            [
                sys.executable,
                str(plugin_root / "skills" / "aidd-docio" / "runtime" / "actions_apply.py"),
                "--actions",
                runtime.rel_path(resolved_actions_path, target),
                "--apply-log",
                runtime.rel_path(paths["apply_log"], target),
            ],
        ]
        if stage in {"implement", "review"}:
            commands.append(
                [
                    sys.executable,
                    str(plugin_root / "skills" / "aidd-core" / "runtime" / "diff_boundary_check.py"),
                    "--ticket",
                    ticket,
                ]
            )
        commands.append(
            [
                sys.executable,
                str(plugin_root / "skills" / "aidd-flow-state" / "runtime" / "progress_cli.py"),
                "--ticket",
                ticket,
                "--source",
                stage,
            ]
        )
        stage_result_cmd = [
            sys.executable,
            str(plugin_root / "skills" / "aidd-flow-state" / "runtime" / "stage_result.py"),
            "--ticket",
            ticket,
            "--stage",
            stage,
            "--result",
            result or "continue",
            "--scope-key",
            scope_key,
        ]
        if work_item_key:
            stage_result_cmd.extend(["--work-item-key", work_item_key])
        if verdict:
            stage_result_cmd.extend(["--verdict", verdict])
        commands.append(stage_result_cmd)
        commands.append(
            [
                sys.executable,
                str(plugin_root / "skills" / "aidd-flow-state" / "runtime" / "status_summary.py"),
                "--ticket",
                ticket,
                "--stage",
                stage,
                "--scope-key",
                scope_key,
            ]
        )
        for command in commands:
            rc, stdout, stderr = _run_runtime_command(
                command=command,
                cwd=workspace_root,
                env=env,
                log_path=wrapper_log_path,
            )
            parsed.update(_parse_wrapper_output(stdout))
            if rc != 0:
                details = (stderr or stdout).strip() or f"exit={rc}"
                return False, parsed, f"{kind} wrapper failed: {details}"
        parsed.setdefault("log_path", runtime.rel_path(wrapper_log_path, target))
        parsed.setdefault("apply_log", runtime.rel_path(paths["apply_log"], target))
        if not actions_provided:
            parsed.setdefault("actions_path", runtime.rel_path(resolved_actions_path, target))
        return True, parsed, ""

    return False, parsed, f"wrapper kind unsupported: {kind}"


def validate_stage_wrapper_contract(
    *,
    target: Path,
    ticket: str,
    scope_key: str,
    stage: str,
    actions_log_rel: str,
    wrapper_logs: List[str] | None = None,
    stage_result_path: str = "",
) -> Tuple[bool, str, str]:
    if stage not in {"implement", "review", "qa"}:
        return True, "", ""
    actions_dir = target / "reports" / "actions" / ticket / scope_key
    context_dir = target / "reports" / "context" / ticket
    loops_dir = target / "reports" / "loops" / ticket / scope_key
    logs_dir = target / "reports" / "logs" / stage / ticket / scope_key

    required_paths = {
        "actions_template": actions_dir / f"{stage}.actions.template.json",
        "actions_payload": actions_dir / f"{stage}.actions.json",
        "readmap_json": context_dir / f"{scope_key}.readmap.json",
        "readmap_md": context_dir / f"{scope_key}.readmap.md",
        "writemap_json": context_dir / f"{scope_key}.writemap.json",
        "writemap_md": context_dir / f"{scope_key}.writemap.md",
        "preflight_result": loops_dir / "stage.preflight.result.json",
    }
    stage_result_candidates: List[Path] = []
    if stage in {"implement", "review"}:
        stage_result_candidates.append(loops_dir / f"stage.{stage}.result.json")
        stage_result_value = (stage_result_path or "").strip()
        if stage_result_value:
            stage_result_resolved = runtime.resolve_path_for_target(Path(stage_result_value), target)
            if stage_result_resolved not in stage_result_candidates:
                stage_result_candidates.append(stage_result_resolved)
    missing: List[str] = []
    for path in required_paths.values():
        if not path.exists():
            missing.append(runtime.rel_path(path, target))

    if stage_result_candidates and not any(path.exists() for path in stage_result_candidates):
        expected = " | ".join(runtime.rel_path(path, target) for path in stage_result_candidates)
        missing.append(f"stage_result={expected}")

    required_wrapper_kinds = ("preflight", "run", "postflight")
    if wrapper_logs:
        kind_to_paths: Dict[str, List[Path]] = {kind: [] for kind in required_wrapper_kinds}
        for value in wrapper_logs:
            rel = str(value or "").strip()
            if not rel:
                continue
            path = runtime.resolve_path_for_target(Path(rel), target)
            name = path.name
            for kind in required_wrapper_kinds:
                if f"wrapper.{kind}." in name:
                    kind_to_paths[kind].append(path)
                    break
        for kind in required_wrapper_kinds:
            paths = kind_to_paths.get(kind) or []
            if not paths:
                missing.append(runtime.rel_path(logs_dir / f"wrapper.{kind}.*.log", target))
                continue
            if not any(path.exists() for path in paths):
                missing.append(" | ".join(runtime.rel_path(path, target) for path in paths))
    else:
        required_wrapper_logs = ("wrapper.preflight.*.log", "wrapper.run.*.log", "wrapper.postflight.*.log")
        for pattern in required_wrapper_logs:
            matches = sorted(logs_dir.glob(pattern)) if logs_dir.exists() else []
            if not matches:
                missing.append(runtime.rel_path(logs_dir / pattern, target))

    actions_log_value = (actions_log_rel or "").strip()
    if not actions_log_value:
        missing.append("AIDD:ACTIONS_LOG")
    else:
        actions_log_path = runtime.resolve_path_for_target(Path(actions_log_value), target)
        if not actions_log_path.exists():
            missing.append(runtime.rel_path(actions_log_path, target))

    if not missing:
        return True, "", ""
    lowered = [item.lower() for item in missing]
    if any("stage_result=" in item or f"stage.{stage}.result.json" in item for item in lowered):
        reason_code = "stage_result_missing"
    elif any("wrapper.preflight" in item or "wrapper.run" in item or "wrapper.postflight" in item for item in lowered):
        reason_code = "wrapper_chain_missing"
    elif any("actions" in item for item in lowered):
        reason_code = "actions_missing"
    else:
        reason_code = "preflight_missing"
    message = "missing stage wrapper artifacts: " + ", ".join(missing)
    return False, message, reason_code


def build_command(stage: str, ticket: str) -> List[str]:
    command = f"/feature-dev-aidd:{stage} {ticket}"
    return ["-p", command]


class MultiWriter:
    def __init__(self, *streams: Optional[TextIO]) -> None:
        self._streams: List[TextIO] = [stream for stream in streams if stream is not None]

    def write(self, data: str) -> None:
        for stream in self._streams:
            stream.write(data)

    def flush(self) -> None:
        for stream in self._streams:
            stream.flush()


def _drain_stream(pipe: Optional[TextIO], writer: MultiWriter, raw_log: TextIO) -> None:
    if pipe is None:
        return
    for line in pipe:
        raw_log.write(line)
        writer.write(line)
        raw_log.flush()
        writer.flush()


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


def run_stream_command(
    *,
    command: List[str],
    cwd: Path,
    log_path: Path,
    stream_mode: str,
    stream_jsonl_path: Path,
    stream_log_path: Path,
    output_stream: TextIO,
    header_lines: Optional[List[str]] = None,
) -> int:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    stream_jsonl_path.parent.mkdir(parents=True, exist_ok=True)
    stream_log_path.parent.mkdir(parents=True, exist_ok=True)

    with (
        log_path.open("w", encoding="utf-8") as raw_log,
        stream_jsonl_path.open("w", encoding="utf-8") as stream_jsonl,
        stream_log_path.open("w", encoding="utf-8") as stream_log,
    ):
        writer = MultiWriter(stream_log, output_stream)
        if header_lines:
            for line in header_lines:
                writer.write(line + "\n")
            writer.flush()
        if stream_mode == "raw":
            writer.write("[stream] WARN: raw mode enabled; JSON events will be printed.\n")
            writer.flush()
        proc = subprocess.Popen(
            command,
            cwd=cwd,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            bufsize=1,
        )
        drain_thread = threading.Thread(
            target=_drain_stream,
            args=(proc.stderr, writer, raw_log),
            daemon=True,
        )
        drain_thread.start()
        for line in proc.stdout or []:
            raw_log.write(line)
            stream_jsonl.write(line)
            raw_log.flush()
            stream_jsonl.flush()
            if stream_mode == "raw":
                writer.write(line)
                writer.flush()
                continue
            claude_stream_render.render_line(
                line,
                writer=writer,
                mode="text+tools" if stream_mode == "tools" else "text-only",
                strict=False,
                warn_stream=writer,
            )
        if proc.stdout:
            proc.stdout.close()
        returncode = proc.wait()
        drain_thread.join(timeout=1)
        return returncode
