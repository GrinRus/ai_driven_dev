from __future__ import annotations

import argparse
import json
import os
from contextlib import suppress
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Optional

_PLUGIN_ROOT = Path(__file__).resolve().parents[3]
os.environ.setdefault("CLAUDE_PLUGIN_ROOT", str(_PLUGIN_ROOT))
if str(_PLUGIN_ROOT) not in sys.path:
    sys.path.insert(0, str(_PLUGIN_ROOT))

from aidd_runtime import qa_agent as _qa_agent
from aidd_runtime import gates
from aidd_runtime import runtime
from aidd_runtime import tasklist_parser
from aidd_runtime.feature_ids import write_active_state

def _resolve_qa_scope_context(target: Path, ticket: str) -> tuple[str, str]:
    active_work_item = str(runtime.read_active_work_item(target) or "").strip()
    if runtime.is_iteration_work_item_key(active_work_item):
        return active_work_item, runtime.resolve_scope_key(active_work_item, ticket)
    return "", runtime.resolve_scope_key("", ticket)


def _sync_active_stage_to_qa(target: Path, ticket: str) -> tuple[bool, str]:
    active_before = str(runtime.read_active_stage(target) or "").strip().lower()
    if active_before == "qa":
        return False, active_before
    write_active_state(target, ticket=ticket, stage="qa")
    return True, active_before


def _qa_stage_chain_context_available(target: Path, ticket: str) -> tuple[bool, str]:
    active_work_item, primary_scope = _resolve_qa_scope_context(target, ticket)
    scopes = [primary_scope]
    # QA stage-chain may be emitted in ticket scope even when active work-item is iteration scoped.
    if runtime.is_iteration_work_item_key(active_work_item):
        ticket_scope = runtime.resolve_scope_key("", ticket)
        if ticket_scope and ticket_scope not in scopes:
            scopes.append(ticket_scope)
    for scope_key in scopes:
        logs_dir = target / "reports" / "logs" / "qa" / ticket / scope_key
        if logs_dir.exists() and any(logs_dir.glob("stage.*.log")):
            return True, scope_key
    return False, primary_scope


def _active_mode(target: Path) -> str:
    path = target / "docs" / ".active_mode"
    try:
        return path.read_text(encoding="utf-8").strip().lower()
    except OSError:
        return ""


SKIP_MARKERS = (
    "форматирование/тесты пропущены",
    "стадия тестов пропущена",
    "тесты пропущены",
    "tests skipped",
    "skipping tests",
    "no tests to run",
    "no tests ran",
    "no tests collected",
    "no test files",
    "nothing to test",
)

def _strip_placeholder(value: str) -> str:
    text = value.strip()
    if not text:
        return ""
    if text.startswith("<") and text.endswith(">"):
        return ""
    return text


def _load_tasklist_test_execution(root: Path, ticket: str) -> dict:
    path = root / "docs" / "tasklist" / f"{ticket}.md"
    if not path.exists():
        return {}
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return {}
    section = tasklist_parser.extract_section(lines, "AIDD:TEST_EXECUTION")
    if not section:
        return {}
    return tasklist_parser.parse_test_execution(section)


def _has_tasklist_execution(data: dict) -> bool:
    if not data:
        return False
    return any(
        bool(str(data.get(key) or "").strip())
        for key in ("profile", "when", "reason")
    ) or bool(data.get("tasks")) or bool(data.get("filters"))


def _commands_from_tasks(tasks: list[str]) -> list[list[str]]:
    commands: list[list[str]] = []
    for raw in tasks:
        normalized = tasklist_parser.normalize_test_execution_task(str(raw))
        task = _strip_placeholder(normalized)
        if not task or task.lower() in {"none", "[]", "(none)", "n/a"}:
            continue
        try:
            parts = [token for token in shlex.split(task) if token]
        except ValueError:
            continue
        if parts:
            commands.append(parts)
    return commands


def _materialize_contract_command_tokens(entry: dict) -> list[str]:
    tokens = [str(item).strip() for item in (entry.get("command") or []) if str(item).strip()]
    if not tokens:
        return []
    return tokens


def _malformed_task_entries(tasklist_execution: dict) -> list[dict]:
    raw = tasklist_execution.get("malformed_tasks") if isinstance(tasklist_execution, dict) else []
    if not isinstance(raw, list):
        return []
    malformed: list[dict] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        task = str(item.get("task") or "").strip()
        token = str(item.get("token") or "").strip()
        reason_code = str(item.get("reason_code") or "tasklist_shell_chain_single_entry").strip()
        if not task:
            continue
        malformed.append(
            {
                "task": task,
                "token": token,
                "reason_code": reason_code,
            }
        )
    return malformed


def _is_relative_to(path: Path, base: Path) -> bool:
    try:
        path.relative_to(base)
        return True
    except ValueError:
        return False


def _is_explicit_path_command(head: str) -> bool:
    normalized = head.replace("\\", "/")
    return normalized.startswith(("./", "../", "/")) or "/" in normalized


def _command_head_exists(head: str, cwd: Path) -> bool:
    cmd_path = Path(head)
    if cmd_path.is_absolute():
        return cmd_path.exists()
    return (cwd / cmd_path).exists()


def _resolve_explicit_command_path(head: str, *, target_root: Path, workspace_root: Path) -> Path | None:
    path = Path(head)
    if path.is_absolute():
        return path if path.exists() else None
    for base in (target_root, workspace_root):
        candidate = base / path
        if candidate.exists():
            return candidate
        resolved = candidate.resolve()
        if resolved.exists():
            return resolved
    return None


def _command_execution_plans(
    command: list[str],
    *,
    target_root: Path,
    workspace_root: Path,
) -> list[tuple[list[str], Path, str]]:
    if not command:
        return []
    head = command[0]
    command_tail = command[1:]
    if not _is_explicit_path_command(head):
        return [(command, target_root, " ".join(command).strip())]

    resolved = _resolve_explicit_command_path(head, target_root=target_root, workspace_root=workspace_root)
    if resolved is None:
        return [(command, target_root, " ".join(command).strip())]

    if _is_relative_to(resolved, workspace_root):
        rel_to_workspace = resolved.relative_to(workspace_root).as_posix()
        plan_cmd = [f"./{resolved.name}", *command_tail]
        display_cmd = f"{rel_to_workspace} {' '.join(command_tail)}".strip()
    else:
        plan_cmd = [resolved.as_posix(), *command_tail]
        display_cmd = f"{resolved.as_posix()} {' '.join(command_tail)}".strip()
    return [(plan_cmd, resolved.parent, display_cmd)]


def _load_qa_tests_config(root: Path) -> tuple[list[list[str]], str]:
    config_path = root / "config" / "gates.json"
    commands: list[list[str]] = []
    try:
        data = json.loads(config_path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return commands, "project_contract_missing"

    contract, contract_errors = gates.load_qa_tests_contract(data)
    profile_default = str(contract.get("profile_default") or "none").strip().lower()
    if contract_errors and (profile_default != "none" or "project_contract_missing" in contract_errors):
        return [], "project_contract_missing"

    selected_entries = gates.select_commands_for_profile(contract, profile_default) or list(contract.get("commands") or [])
    for entry in selected_entries:
        if not isinstance(entry, dict):
            continue
        cmd = _materialize_contract_command_tokens(entry)
        if cmd:
            commands.append(cmd)

    if profile_default == "none":
        return [], ""

    if not commands:
        return [], "project_contract_missing"
    return commands, ""


def _run_qa_tests(
    target: Path,
    workspace_root: Path,
    *,
    ticket: str,
    slug_hint: str | None,
    branch: str | None,
    report_path: Path,
    allow_missing: bool,
    commands_override: list[list[str]] | None = None,
) -> tuple[list[dict], str, str]:
    run_reason_code = ""
    if commands_override is not None:
        commands = commands_override
    else:
        commands, contract_reason_code = _load_qa_tests_config(target)
        if contract_reason_code:
            tests_executed = [
                {
                    "command": "",
                    "status": "fail",
                    "cwd": ".",
                    "log": "",
                    "exit_code": None,
                    "reason_code": contract_reason_code,
                    "details": "project QA test contract missing or invalid (aidd/config/gates.json -> qa.tests)",
                }
            ]
            return tests_executed, "fail", contract_reason_code
    allow_skip = allow_missing

    tests_executed: list[dict] = []
    if not commands:
        summary = "skipped"
        return tests_executed, summary, run_reason_code

    logs_dir = report_path.parent
    base_name = report_path.stem
    summary = "not-run"

    def _output_indicates_skip(text: str) -> bool:
        lowered = text.lower()
        return any(marker in lowered for marker in SKIP_MARKERS)

    for index, cmd in enumerate(commands, start=1):
        execution_plans = _command_execution_plans(
            cmd,
            target_root=target,
            workspace_root=workspace_root,
        )
        for plan_index, (plan_cmd, plan_cwd, display_cmd) in enumerate(execution_plans, start=1):
            suffix = ""
            if len(commands) > 1:
                suffix = f"-{index}"
            if len(execution_plans) > 1:
                suffix += f"-m{plan_index}"
            log_path = logs_dir / f"{base_name}-tests{suffix}.log"
            log_path.parent.mkdir(parents=True, exist_ok=True)
            status = "fail"
            exit_code: Optional[int] = None
            output = ""
            if plan_cmd and _is_explicit_path_command(plan_cmd[0]) and not _command_head_exists(plan_cmd[0], plan_cwd):
                status = "fail"
                run_reason_code = run_reason_code or "tests_cwd_mismatch"
                output = (
                    f"command path not found in selected cwd: {plan_cmd[0]} "
                    f"(cwd={plan_cwd.as_posix()}; "
                    "use an existing executable path or adjust tasklist command cwd)"
                )
            else:
                try:
                    proc = subprocess.run(
                        plan_cmd,
                        cwd=plan_cwd,
                        text=True,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT,
                        check=False,
                    )
                    output = proc.stdout or ""
                    exit_code = proc.returncode
                    status = "pass" if proc.returncode == 0 else "fail"
                except FileNotFoundError as exc:
                    status = "fail"
                    run_reason_code = run_reason_code or "tests_cwd_mismatch"
                    output = f"command not found: {plan_cmd[0]} ({exc})"
            log_path.write_text(output, encoding="utf-8")
            if status == "pass" and _output_indicates_skip(output):
                status = "skipped"

            try:
                cwd_rel = plan_cwd.relative_to(workspace_root).as_posix()
            except ValueError:
                cwd_rel = plan_cwd.as_posix()
            tests_executed.append(
                {
                    "command": display_cmd or " ".join(plan_cmd),
                    "status": status,
                    "cwd": cwd_rel or ".",
                    "log": runtime.rel_path(log_path, target),
                    "exit_code": exit_code,
                    "reason_code": run_reason_code if status == "fail" and run_reason_code else "",
                }
            )

    if any(entry.get("status") == "fail" for entry in tests_executed):
        summary = "fail"
    elif any(entry.get("status") == "skipped" for entry in tests_executed):
        summary = "skipped"
    else:
        summary = "pass" if tests_executed else "not-run"

    if summary in {"not-run", "skipped"} and allow_skip:
        summary = "skipped"

    return tests_executed, summary, run_reason_code


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run QA agent and generate aidd/reports/qa/<ticket>.json.",
    )
    parser.add_argument(
        "--ticket",
        dest="ticket",
        help="Ticket identifier to use (defaults to docs/.active.json).",
    )
    parser.add_argument(
        "--slug-hint",
        dest="slug_hint",
        help="Optional slug hint override used for messaging.",
    )
    parser.add_argument(
        "--branch",
        help="Git branch name for logging (autodetected by default).",
    )
    parser.add_argument(
        "--report",
        help="Path to JSON report (default: aidd/reports/qa/<ticket>.json).",
    )
    parser.add_argument(
        "--block-on",
        help="Comma-separated severities treated as blockers (pass-through to qa-agent).",
    )
    parser.add_argument(
        "--warn-on",
        help="Comma-separated severities treated as warnings (pass-through to qa-agent).",
    )
    parser.add_argument(
        "--scope",
        action="append",
        help="Optional scope filters (pass-through to qa-agent).",
    )
    parser.add_argument(
        "--scope-key",
        dest="scope",
        action="append",
        help="Alias for --scope (wrapper compatibility).",
    )
    parser.add_argument(
        "--format",
        choices=("json", "text"),
        default="json",
        help="qa-agent output format (default: json).",
    )
    parser.add_argument(
        "--emit-json",
        action="store_true",
        help="Emit JSON to stdout even in gate mode.",
    )
    parser.add_argument(
        "--emit-patch",
        action="store_true",
        help="Emit RFC6902 patch file when a previous report exists.",
    )
    parser.add_argument(
        "--pack-only",
        action="store_true",
        help="Remove JSON report after writing pack sidecar.",
    )
    parser.add_argument(
        "--skip-tests",
        action="store_true",
        help="Skip QA test run (not recommended; override is respected in gate mode).",
    )
    parser.add_argument(
        "--allow-no-tests",
        action="store_true",
        help="Allow QA to proceed without tests (or with skipped test commands).",
    )
    parser.add_argument(
        "--gate",
        action="store_true",
        help="Gate mode: non-zero exit code on blocker severities.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Gate mode without failing on blockers.",
    )
    parser.add_argument(
        "--docs-only",
        action="store_true",
        help="Enable docs-only rewrite mode for this invocation.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    workspace_root, target = runtime.require_workflow_root()

    gates_config = runtime.load_gates_config(target)
    tests_required_mode = str(gates_config.get("tests_required", "disabled")).strip().lower()

    context = runtime.resolve_feature_context(
        target,
        ticket=getattr(args, "ticket", None),
        slug_hint=getattr(args, "slug_hint", None),
    )
    ticket = (context.resolved_ticket or "").strip()
    slug_hint = (context.slug_hint or ticket or "").strip()
    if not ticket:
        raise ValueError("feature ticket is required; pass --ticket or set docs/.active.json via /feature-dev-aidd:idea-new.")
    docs_only_mode = runtime.docs_only_mode_requested(explicit=getattr(args, "docs_only", False))

    try:
        stage_sync_applied, active_stage_before = _sync_active_stage_to_qa(target, ticket)
    except Exception as exc:
        message = str(exc).strip() or exc.__class__.__name__
        print(
            "[aidd] BLOCK: QA active stage sync failed "
            f"(reason_code=active_stage_sync_failed): {message}",
            file=sys.stderr,
        )
        return 2
    if stage_sync_applied:
        print(
            f"[aidd] QA stage sync: {active_stage_before or 'none'} -> qa.",
            file=sys.stderr,
        )

    loop_mode = _active_mode(target) == "loop"
    if loop_mode:
        stage_chain_context_ok, stage_chain_scope = _qa_stage_chain_context_available(target, ticket)
        if not stage_chain_context_ok:
            if docs_only_mode:
                print(
                    "[aidd] WARN: docs-only rewrite mode bypasses QA preflight blocker "
                    f"(reason_code=preflight_missing scope_key={stage_chain_scope or 'n/a'}, docs_only_mode=1).",
                    file=sys.stderr,
                )
            else:
                print(
                    "[aidd] BLOCK: QA stage-chain context missing "
                    f"(reason_code=preflight_missing scope_key={stage_chain_scope or 'n/a'}). "
                    f"Next action: `/feature-dev-aidd:implement {ticket}`.",
                    file=sys.stderr,
                )
                return 2

    branch = args.branch or runtime.detect_branch(target)

    def _fmt(text: str) -> str:
        return (
            text.replace("{ticket}", ticket)
            .replace("{slug}", slug_hint or ticket)
            .replace("{branch}", branch or "")
        )

    report_template = args.report or "aidd/reports/qa/{ticket}.json"
    report_text = _fmt(report_template)
    report_path = runtime.resolve_path_for_target(Path(report_text), target)

    allow_no_tests = bool(
        getattr(args, "allow_no_tests", False)
        or os.getenv("CLAUDE_QA_ALLOW_NO_TESTS", "").strip() == "1"
    )
    if tests_required_mode == "hard":
        allow_no_tests = False
    elif tests_required_mode == "soft":
        allow_no_tests = True
    skip_tests = bool(getattr(args, "skip_tests", False) or os.getenv("CLAUDE_QA_SKIP_TESTS", "").strip() == "1")
    if docs_only_mode:
        allow_no_tests = True
        skip_tests = True
        print(
            "[aidd] QA docs-only rewrite mode active: skipping QA tests for this invocation.",
            file=sys.stderr,
        )

    tasklist_exec = _load_tasklist_test_execution(target, ticket)
    tasklist_exec_present = _has_tasklist_execution(tasklist_exec)
    tasklist_profile = str(tasklist_exec.get("profile") or "").strip().lower() if tasklist_exec_present else ""
    tasklist_tasks = tasklist_exec.get("tasks") or []
    tasklist_filters = tasklist_exec.get("filters") or []
    tasklist_malformed = _malformed_task_entries(tasklist_exec)
    tasklist_commands: list[list[str]] = []
    if tasklist_exec_present and tasklist_profile != "none":
        tasklist_commands = _commands_from_tasks(list(tasklist_tasks))
    commands_override = None
    if tasklist_exec_present:
        commands_override = [] if tasklist_profile == "none" else tasklist_commands

    tests_executed: list[dict] = []
    tests_summary = "skipped" if skip_tests else "not-run"
    malformed_tests_blocked = False
    malformed_reason_codes: set[str] = set()
    run_reason_code = ""

    if not skip_tests and tasklist_malformed:
        malformed_tests_blocked = True
        tests_summary = "fail"
        for item in tasklist_malformed:
            reason_code = str(item.get("reason_code") or "tasklist_malformed_entry").strip()
            malformed_reason_codes.add(reason_code)
            if reason_code == "tasklist_shell_chain_single_entry":
                diagnostics = (
                    "AIDD:TEST_EXECUTION contains single-entry shell command chain "
                    "(token: &&/||/;) and must be split into separate task entries."
                )
            else:
                diagnostics = (
                    "AIDD:TEST_EXECUTION entry is not an executable command. "
                    "Use concrete command lines in task entries."
                )
            tests_executed.append(
                {
                    "command": item.get("task"),
                    "status": "fail",
                    "cwd": ".",
                    "log": "",
                    "exit_code": None,
                    "reason_code": reason_code,
                    "details": diagnostics,
                    "token": item.get("token") or None,
                }
            )
        if malformed_reason_codes == {"tasklist_shell_chain_single_entry"}:
            print(
                "[aidd] BLOCK: malformed AIDD:TEST_EXECUTION task contains shell-chain token; split into separate commands.",
                file=sys.stderr,
            )
        elif malformed_reason_codes == {"tasklist_non_command_entry"}:
            print(
                "[aidd] BLOCK: malformed AIDD:TEST_EXECUTION task is not an executable command entry.",
                file=sys.stderr,
            )
        else:
            print(
                "[aidd] BLOCK: malformed AIDD:TEST_EXECUTION tasks detected; fix invalid entries.",
                file=sys.stderr,
            )
    elif not skip_tests:
        tests_executed, tests_summary, run_reason_code = _run_qa_tests(
            target,
            workspace_root,
            ticket=ticket,
            slug_hint=slug_hint or None,
            branch=branch,
            report_path=report_path,
            allow_missing=allow_no_tests,
            commands_override=commands_override,
        )
        if tests_summary == "fail":
            if run_reason_code == "project_contract_missing":
                print(
                    "[aidd] BLOCK: project test execution contract missing/invalid "
                    "(reason_code=project_contract_missing).",
                    file=sys.stderr,
                )
            elif run_reason_code == "tests_cwd_mismatch":
                print(
                    "[aidd] BLOCK: configured test command is not executable from selected cwd "
                    "(reason_code=tests_cwd_mismatch).",
                    file=sys.stderr,
                )
            else:
                print("[aidd] QA tests failed; see aidd/reports/qa/*-tests.log.", file=sys.stderr)
        elif tests_summary == "skipped":
            print(
                "[aidd] QA tests skipped (allow_no_tests enabled or no commands configured).",
                file=sys.stderr,
            )
        else:
            print("[aidd] QA tests completed.", file=sys.stderr)
    else:
        run_reason_code = ""

    with suppress(Exception):
        from aidd_runtime.reports import tests_log as _tests_log

        qa_work_item_key, scope_key = _resolve_qa_scope_context(target, ticket)
        if tasklist_exec_present:
            commands = [str(item) for item in (tasklist_tasks or []) if str(item).strip()]
        else:
            commands = [entry.get("command") for entry in tests_executed if entry.get("command")]
        log_path = ""
        for entry in reversed(tests_executed):
            if entry.get("log"):
                log_path = str(entry.get("log"))
                break
        exit_code = None
        if tests_summary == "pass":
            exit_code = 0
        elif tests_summary == "fail":
            exit_code = 1
        reason_code = ""
        reason = ""
        if tests_summary == "fail" and malformed_tests_blocked:
            if len(malformed_reason_codes) == 1:
                reason_code = next(iter(malformed_reason_codes))
            else:
                reason_code = "tasklist_malformed_entry"
            if reason_code == "tasklist_shell_chain_single_entry":
                reason = (
                    "AIDD:TEST_EXECUTION contains single-entry shell chain; "
                    "split commands into separate task entries"
                )
            elif reason_code == "tasklist_non_command_entry":
                reason = (
                    "AIDD:TEST_EXECUTION contains non-command task entry; "
                    "replace prose/labels with executable command"
                )
            else:
                reason = "AIDD:TEST_EXECUTION contains malformed task entries"
        elif tests_summary == "fail" and run_reason_code:
            reason_code = run_reason_code
            if reason_code == "project_contract_missing":
                reason = "project test execution contract missing or invalid"
            elif reason_code == "tests_cwd_mismatch":
                reason = "configured test command is not executable from selected cwd"
            else:
                reason = "qa tests failed"
        elif tests_summary in {"skipped", "not-run"}:
            if skip_tests:
                reason_code = "manual_skip"
                reason = "qa skip-tests flag"
            elif tasklist_exec_present and tasklist_profile == "none":
                reason_code = "profile_none"
                reason = "tasklist test profile none"
            elif tasklist_exec_present and tasklist_profile != "none" and not tasklist_commands:
                reason_code = "tasklist_no_commands"
                reason = "tasklist test commands missing"
            elif allow_no_tests:
                reason_code = "allow_no_tests"
                reason = "qa allow_no_tests enabled"
            else:
                reason_code = "tests_skipped"
                reason = "qa tests skipped"
        if tests_summary in {"skipped", "not-run"}:
            if tasklist_exec_present and tasklist_profile:
                profile = tasklist_profile
            else:
                profile = "none"
        else:
            if tasklist_exec_present and tasklist_profile:
                profile = tasklist_profile
            else:
                profile = "full" if commands else "none"
        _tests_log.append_log(
            target,
            ticket=ticket,
            slug_hint=slug_hint or ticket,
            stage="qa",
            scope_key=scope_key,
            work_item_key=qa_work_item_key or None,
            profile=profile,
            tasks=commands or None,
            filters=tasklist_filters or None,
            exit_code=exit_code,
            log_path=log_path or None,
            status=tests_summary,
            reason_code=reason_code or None,
            reason=reason or None,
            details={
                "qa_tests": True,
                "source": "tasklist" if tasklist_exec_present else "config",
            },
            source="qa",
            cwd=str(target),
        )

    qa_args: list[str] = []
    if args.gate:
        qa_args.append("--gate")
    if args.dry_run:
        qa_args.append("--dry-run")
    if args.emit_json:
        qa_args.append("--emit-json")
    if args.format:
        qa_args.extend(["--format", args.format])
    if args.block_on:
        qa_args.extend(["--block-on", args.block_on])
    if args.warn_on:
        qa_args.extend(["--warn-on", args.warn_on])
    if args.scope:
        for scope in args.scope:
            qa_args.extend(["--scope", scope])
    if args.emit_patch:
        qa_args.append("--emit-patch")
    if args.pack_only:
        qa_args.append("--pack-only")

    qa_args.extend(["--ticket", ticket])
    if slug_hint and slug_hint != ticket:
        qa_args.extend(["--slug-hint", slug_hint])
    if branch:
        qa_args.extend(["--branch", branch])
    if report_path:
        qa_args.extend(["--report", str(report_path)])

    allow_no_tests_env = allow_no_tests
    if docs_only_mode:
        allow_no_tests_env = True
    elif tests_required_mode == "hard":
        allow_no_tests_env = False
    elif tests_required_mode == "soft":
        allow_no_tests_env = True

    old_env = {
        "QA_TESTS_SUMMARY": os.environ.get("QA_TESTS_SUMMARY"),
        "QA_TESTS_EXECUTED": os.environ.get("QA_TESTS_EXECUTED"),
        "QA_ALLOW_NO_TESTS": os.environ.get("QA_ALLOW_NO_TESTS"),
    }
    os.environ["QA_TESTS_SUMMARY"] = tests_summary
    os.environ["QA_TESTS_EXECUTED"] = json.dumps(tests_executed, ensure_ascii=False)
    os.environ["QA_ALLOW_NO_TESTS"] = "1" if allow_no_tests_env else "0"
    try:
        exit_code = _qa_agent.main(qa_args)
    finally:
        for key, value in old_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    if tests_summary == "fail":
        exit_code = max(exit_code, 1)
    elif tests_summary in {"not-run", "skipped"} and not allow_no_tests_env:
        exit_code = max(exit_code, 1)

    report_status = ""
    if report_path.exists():
        try:
            report_payload = json.loads(report_path.read_text(encoding="utf-8"))
        except Exception:
            report_payload = {}
        report_status = str(report_payload.get("status") or "").strip().upper()
    if report_status == "BLOCKED":
        if docs_only_mode:
            print(
                "[aidd] WARN: docs-only rewrite mode ignores QA report BLOCKED status for this invocation.",
                file=sys.stderr,
            )
        else:
            exit_code = 2
            print("[aidd] BLOCK: QA report status is BLOCKED.", file=sys.stderr)

    stage_result_emit_error = ""
    try:
        qa_work_item_key, qa_scope_key = _resolve_qa_scope_context(target, ticket)
        stage_result_args = [
            "--ticket",
            ticket,
            "--stage",
            "qa",
            "--result",
            "blocked" if report_status == "BLOCKED" and not docs_only_mode else "done",
            "--scope-key",
            qa_scope_key,
        ]
        if docs_only_mode:
            stage_result_args.append("--docs-only")
        if qa_work_item_key:
            stage_result_args.extend(["--work-item-key", qa_work_item_key])
        if report_path.exists():
            stage_result_args.extend(
                ["--evidence-link", f"qa_report={runtime.rel_path(report_path, target)}"]
            )
            pack_path = report_path.with_suffix(".pack.json")
            if pack_path.exists():
                stage_result_args.extend(
                    ["--evidence-link", f"qa_pack={runtime.rel_path(pack_path, target)}"]
                )
        if tests_executed:
            log_paths = [entry.get("log") for entry in tests_executed if entry.get("log")]
            if log_paths:
                stage_result_args.extend(
                    ["--evidence-link", f"qa_tests_log={log_paths[-1]}"]
                )
        from aidd_runtime import stage_result as _stage_result
        import io
        from contextlib import redirect_stderr, redirect_stdout

        stage_result_args.extend(["--format", "json"])
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            stage_result_rc = _stage_result.main(stage_result_args)
        if stage_result_rc != 0:
            stage_result_emit_error = f"stage_result.main exited with code {stage_result_rc}"
    except Exception as exc:
        stage_result_emit_error = str(exc).strip() or exc.__class__.__name__

    if stage_result_emit_error:
        exit_code = max(exit_code, 2)
        print(
            "[aidd] BLOCK: QA stage-result emission failed "
            f"(reason_code=qa_stage_result_emit_failed): {stage_result_emit_error}",
            file=sys.stderr,
        )

    with suppress(Exception):
        from aidd_runtime.reports import events as _events
        payload = None
        report_for_event: Path | None = None
        if report_path.exists():
            payload = json.loads(report_path.read_text(encoding="utf-8"))
            report_for_event = report_path
        else:
            from aidd_runtime.reports.loader import load_report_for_path

            payload, source, report_paths = load_report_for_path(report_path, prefer_pack=True)
            report_for_event = report_paths.pack_path if source == "pack" else report_paths.json_path

        if payload and report_for_event:
            _events.append_event(
                target,
                ticket=ticket,
                slug_hint=slug_hint or None,
                event_type="qa",
                status=str(payload.get("status") or ""),
                details={"summary": payload.get("summary")},
                report_path=Path(runtime.rel_path(report_for_event, target)),
                source="aidd qa",
            )

    if not args.dry_run:
        runtime.maybe_sync_index(target, ticket, slug_hint or None, reason="qa")
    report_rel = runtime.rel_path(report_path, target)
    pack_path = report_path.with_suffix(".pack.json")
    if report_path.exists():
        print(f"[aidd] QA report saved to {report_rel}.", file=sys.stderr)
    if pack_path.exists():
        print(f"[aidd] QA pack saved to {runtime.rel_path(pack_path, target)}.", file=sys.stderr)
    return exit_code


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
