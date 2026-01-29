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


def _default_qa_test_command() -> list[list[str]]:
    plugin_root = runtime.require_plugin_root()
    return [[sys.executable, str(plugin_root / "hooks" / "format-and-test.sh")]]


_TEST_COMMAND_PATTERNS = (
    r"\b\./gradlew\s+test\b",
    r"\bgradle\s+test\b",
    r"\bmvn\s+test\b",
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

    qa_cfg = data.get("qa")
    if isinstance(qa_cfg, bool):
        qa_cfg = {"enabled": qa_cfg}
    if not isinstance(qa_cfg, dict):
        qa_cfg = {}
    tests_cfg = qa_cfg.get("tests")
    if not isinstance(tests_cfg, dict):
        tests_cfg = {}
    allow_skip = bool(tests_cfg.get("allow_skip", True))
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
) -> tuple[list[dict], str]:
    commands, allow_skip_cfg = _load_qa_tests_config(target)
    allow_skip = allow_missing or allow_skip_cfg

    tests_executed: list[dict] = []
    if not commands:
        summary = "skipped"
        return tests_executed, summary

    logs_dir = report_path.parent
    base_name = report_path.stem
    summary = "not-run"

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
        help="Ticket identifier to use (defaults to docs/.active_ticket).",
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

    context = runtime.resolve_feature_context(
        target,
        ticket=getattr(args, "ticket", None),
        slug_hint=getattr(args, "slug_hint", None),
    )
    ticket = (context.resolved_ticket or "").strip()
    slug_hint = (context.slug_hint or ticket or "").strip()
    if not ticket:
        raise ValueError("feature ticket is required; pass --ticket or set docs/.active_ticket via /feature-dev-aidd:idea-new.")

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
    skip_tests = bool(getattr(args, "skip_tests", False) or os.getenv("CLAUDE_QA_SKIP_TESTS", "").strip() == "1")

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

    _, allow_skip_cfg = _load_qa_tests_config(target)
    allow_no_tests_env = allow_no_tests or allow_skip_cfg

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
    return exit_code


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
