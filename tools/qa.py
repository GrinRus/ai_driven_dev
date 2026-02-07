from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import subprocess
import sys
from fnmatch import fnmatch
from pathlib import Path
from typing import Any, Dict, Optional

from tools import qa_agent as _qa_agent
from tools import runtime
from tools import tasklist_parser


def _default_qa_test_command() -> list[list[str]]:
    plugin_root = runtime.require_plugin_root()
    return [[sys.executable, str(plugin_root / "hooks" / "format-and-test.sh")]]


_TEST_COMMAND_PATTERNS = (
    r"\b\./gradlew\s+test\b",
    r"\bgradle\s+test\b",
    r"\bmvn\s+test\b",
    r"\bpython3?\s+-m\s+pytest\b",
    r"\bpytest\b",
    r"\bpython3?\s+-m\s+unittest\b",
    r"\bgo\s+test\b",
    r"\bnpm\s+test\b",
    r"\bpnpm\s+test\b",
    r"\byarn\s+test\b",
    r"\bmake\s+test\b",
    r"\bmake\s+check\b",
    r"\btox\b",
)

DEFAULT_DISCOVERY_MAX_FILES = 20
DEFAULT_DISCOVERY_MAX_BYTES = 200_000
DEFAULT_DISCOVERY_ALLOWLIST = (
    ".github/workflows/*.yml",
    ".github/workflows/*.yaml",
    ".gitlab-ci.yml",
    ".circleci/config.yml",
    "Jenkinsfile",
    "README*",
    "readme*",
)

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


def _read_text(path: Path, *, max_bytes: int = 1_000_000) -> str:
    try:
        if path.stat().st_size > max_bytes:
            return ""
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def _normalize_candidate_line(line: str) -> str:
    text = line.strip()
    if not text:
        return ""
    if text.startswith("run:"):
        text = text[4:].strip()
    if text.startswith("script:"):
        text = text[7:].strip()
    text = re.sub(r"^[-*]\s+", "", text)
    text = re.sub(r"^\d+\.\s+", "", text)
    if text.startswith("`") and text.endswith("`"):
        text = text[1:-1].strip()
    if " #" in text:
        text = text.split(" #", 1)[0].rstrip()
    return text


def _extract_test_commands(text: str) -> list[str]:
    commands: list[str] = []
    for line in text.splitlines():
        candidate = _normalize_candidate_line(line)
        if not candidate:
            continue
        for pattern in _TEST_COMMAND_PATTERNS:
            match = re.search(pattern, candidate, re.IGNORECASE)
            if not match:
                continue
            cmd = candidate[match.start():].strip().rstrip("`")
            if cmd:
                commands.append(cmd)
            break
    return commands


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
        task = _strip_placeholder(str(raw))
        if not task or task.lower() in {"none", "[]", "(none)", "n/a"}:
            continue
        try:
            parts = [token for token in shlex.split(task) if token]
        except ValueError:
            continue
        if parts:
            commands.append(parts)
    return commands


def _normalize_discovery_config(tests_cfg: dict) -> tuple[int, int, list[str]]:
    raw = tests_cfg.get("discover") if isinstance(tests_cfg, dict) else {}
    if not isinstance(raw, dict):
        raw = {}

    max_files = raw.get("max_files", DEFAULT_DISCOVERY_MAX_FILES)
    max_bytes = raw.get("max_bytes", DEFAULT_DISCOVERY_MAX_BYTES)
    try:
        max_files = max(int(max_files), 0)
    except (TypeError, ValueError):
        max_files = DEFAULT_DISCOVERY_MAX_FILES
    try:
        max_bytes = max(int(max_bytes), 0)
    except (TypeError, ValueError):
        max_bytes = DEFAULT_DISCOVERY_MAX_BYTES

    allow_paths = raw.get("allow_paths") or raw.get("allowlist")
    if isinstance(allow_paths, str):
        allow_paths = [allow_paths]
    allowlist = [str(item).strip() for item in allow_paths or [] if str(item).strip()]
    if not allowlist:
        allowlist = list(DEFAULT_DISCOVERY_ALLOWLIST)
    return max_files, max_bytes, allowlist


def _is_allowed_path(path: Path, base: Path, allowlist: list[str]) -> bool:
    if not allowlist:
        return True
    try:
        rel = path.relative_to(base)
        rel_str = rel.as_posix()
    except ValueError:
        rel_str = path.as_posix()
    rel_str = rel_str.lstrip("./")
    return any(fnmatch(rel_str, pattern) for pattern in allowlist)


def _is_relative_to(path: Path, base: Path) -> bool:
    try:
        path.relative_to(base)
        return True
    except ValueError:
        return False


def _discover_test_commands(
    root: Path,
    *,
    max_files: int,
    max_bytes: int,
    allow_paths: list[str],
) -> list[list[str]]:
    commands: list[str] = []
    seen: set[str] = set()
    seen_files: set[Path] = set()
    files_seen = 0

    if max_files == 0:
        return []

    search_roots = [root]
    if root.name == "aidd" and root.parent != root:
        search_roots.append(root.parent)

    ci_paths: list[Path] = []
    for base in search_roots:
        workflows = base / ".github" / "workflows"
        if workflows.exists():
            ci_paths.extend(sorted(workflows.glob("*.yml")))
            ci_paths.extend(sorted(workflows.glob("*.yaml")))
        ci_paths.append(base / ".gitlab-ci.yml")
        ci_paths.append(base / ".circleci" / "config.yml")
        ci_paths.append(base / "Jenkinsfile")

    def _add_commands_from(paths: list[Path], *, base: Path) -> None:
        nonlocal files_seen
        for path in paths:
            if max_files and files_seen >= max_files:
                return
            if not path.exists() or not path.is_file():
                continue
            if not _is_allowed_path(path, base, allow_paths):
                continue
            resolved = path.resolve()
            if resolved in seen_files:
                continue
            seen_files.add(resolved)
            files_seen += 1
            for cmd in _extract_test_commands(_read_text(path, max_bytes=max_bytes)):
                if cmd in seen:
                    continue
                seen.add(cmd)
                commands.append(cmd)

    for base in search_roots:
        base_ci = [path for path in ci_paths if _is_relative_to(path, base)]
        _add_commands_from(base_ci, base=base)
    if commands:
        return [shlex.split(cmd) for cmd in commands if cmd.strip()]

    readmes: list[Path] = []
    for base in search_roots:
        readmes.extend([path for path in sorted(base.glob("README*")) if path.is_file()])
        readmes.extend([path for path in sorted(base.glob("readme*")) if path.is_file()])
    for base in search_roots:
        base_readmes = [path for path in readmes if _is_relative_to(path, base)]
        _add_commands_from(base_readmes, base=base)

    return [shlex.split(cmd) for cmd in commands if cmd.strip()]


def _load_qa_tests_config(root: Path) -> tuple[list[list[str]], bool]:
    config_path = root / "config" / "gates.json"
    commands: list[list[str]] = []
    allow_skip = True
    try:
        data = json.loads(config_path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return _default_qa_test_command(), allow_skip

    tests_required_mode = str(data.get("tests_required", "disabled")).strip().lower()

    qa_cfg = data.get("qa")
    if isinstance(qa_cfg, bool):
        qa_cfg = {"enabled": qa_cfg}
    if not isinstance(qa_cfg, dict):
        qa_cfg = {}
    tests_cfg = qa_cfg.get("tests")
    if not isinstance(tests_cfg, dict):
        tests_cfg = {}
    allow_skip = bool(tests_cfg.get("allow_skip", True))
    if tests_required_mode == "hard":
        allow_skip = False
    source = str(tests_cfg.get("source") or tests_cfg.get("mode") or "").strip().lower()
    max_files, max_bytes, allow_paths = _normalize_discovery_config(tests_cfg)
    raw_commands = tests_cfg.get("commands")
    if isinstance(raw_commands, str):
        raw_commands = [raw_commands]
    if isinstance(raw_commands, list):
        for entry in raw_commands:
            parts: list[str] = []
            if isinstance(entry, list):
                parts = [str(item) for item in entry if str(item)]
            elif isinstance(entry, str):
                try:
                    parts = [token for token in shlex.split(entry) if token]
                except ValueError:
                    continue
            if parts:
                commands.append(parts)

    if not commands and source in {"readme-ci", "readme", "ci"}:
        commands = _discover_test_commands(root, max_files=max_files, max_bytes=max_bytes, allow_paths=allow_paths)
        return commands, allow_skip

    if not commands:
        commands = _default_qa_test_command()
    return commands, allow_skip


def _run_qa_tests(
    target: Path,
    *,
    ticket: str,
    slug_hint: str | None,
    branch: str | None,
    report_path: Path,
    allow_missing: bool,
    commands_override: list[list[str]] | None = None,
    allow_skip_override: bool | None = None,
) -> tuple[list[dict], str]:
    if commands_override is not None:
        commands = commands_override
        allow_skip_cfg = True if allow_skip_override is None else allow_skip_override
    else:
        commands, allow_skip_cfg = _load_qa_tests_config(target)
    allow_skip = allow_missing or allow_skip_cfg

    tests_executed: list[dict] = []
    if not commands:
        summary = "skipped"
        return tests_executed, summary

    logs_dir = report_path.parent
    base_name = report_path.stem
    summary = "not-run"

    def _output_indicates_skip(text: str) -> bool:
        lowered = text.lower()
        return any(marker in lowered for marker in SKIP_MARKERS)

    for index, cmd in enumerate(commands, start=1):
        log_path = logs_dir / f"{base_name}-tests{'' if len(commands) == 1 else f'-{index}'}.log"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        status = "fail"
        exit_code: Optional[int] = None
        output = ""
        try:
            proc = subprocess.run(
                cmd,
                cwd=target,
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
            output = f"command not found: {cmd[0]} ({exc})"
        log_path.write_text(output, encoding="utf-8")
        if status == "pass" and _output_indicates_skip(output):
            status = "skipped"

        tests_executed.append(
            {
                "command": " ".join(cmd),
                "status": status,
                "log": runtime.rel_path(log_path, target),
                "exit_code": exit_code,
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

    return tests_executed, summary


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
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    _, target = runtime.require_workflow_root()

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

    tasklist_exec = _load_tasklist_test_execution(target, ticket)
    tasklist_exec_present = _has_tasklist_execution(tasklist_exec)
    tasklist_profile = str(tasklist_exec.get("profile") or "").strip().lower() if tasklist_exec_present else ""
    tasklist_tasks = tasklist_exec.get("tasks") or []
    tasklist_filters = tasklist_exec.get("filters") or []
    tasklist_commands: list[list[str]] = []
    if tasklist_exec_present and tasklist_profile != "none":
        tasklist_commands = _commands_from_tasks(list(tasklist_tasks))
    commands_override = None
    allow_skip_override = None
    if tasklist_exec_present:
        commands_override = [] if tasklist_profile == "none" else tasklist_commands
        allow_skip_override = tests_required_mode != "hard"

    tests_executed: list[dict] = []
    tests_summary = "skipped" if skip_tests else "not-run"

    if not skip_tests:
        tests_executed, tests_summary = _run_qa_tests(
            target,
            ticket=ticket,
            slug_hint=slug_hint or None,
            branch=branch,
            report_path=report_path,
            allow_missing=allow_no_tests,
            commands_override=commands_override,
            allow_skip_override=allow_skip_override,
        )
        if tests_summary == "fail":
            print("[aidd] QA tests failed; see aidd/reports/qa/*-tests.log.", file=sys.stderr)
        elif tests_summary == "skipped":
            print(
                "[aidd] QA tests skipped (allow_no_tests enabled or no commands configured).",
                file=sys.stderr,
            )
        else:
            print("[aidd] QA tests completed.", file=sys.stderr)

    try:
        from tools.reports import tests_log as _tests_log

        scope_key = runtime.resolve_scope_key("", ticket)
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
        if tests_summary in {"skipped", "not-run"}:
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
            work_item_key=None,
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
    except Exception:
        pass

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

    if tasklist_exec_present:
        allow_skip_cfg = True if allow_skip_override is None else allow_skip_override
    else:
        _, allow_skip_cfg = _load_qa_tests_config(target)
    allow_no_tests_env = allow_no_tests or allow_skip_cfg
    if tests_required_mode == "hard":
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

    try:
        report_status = ""
        if report_path.exists():
            report_payload = json.loads(report_path.read_text(encoding="utf-8"))
            report_status = str(report_payload.get("status") or "").strip().upper()
        stage_result_args = [
            "--ticket",
            ticket,
            "--stage",
            "qa",
            "--result",
            "blocked" if report_status == "BLOCKED" else "done",
        ]
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
        from tools import stage_result as _stage_result
        import io
        from contextlib import redirect_stderr, redirect_stdout

        stage_result_args.extend(["--format", "json"])
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            _stage_result.main(stage_result_args)
    except Exception:
        pass

    try:
        from tools.reports import events as _events
        payload = None
        report_for_event: Path | None = None
        if report_path.exists():
            payload = json.loads(report_path.read_text(encoding="utf-8"))
            report_for_event = report_path
        else:
            from tools.reports.loader import load_report_for_path

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
    except Exception:
        pass

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
