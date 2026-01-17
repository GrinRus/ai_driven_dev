#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import shlex
import subprocess
import sys
import time
from fnmatch import fnmatch
from pathlib import Path
from typing import Iterable


HOOK_PREFIX = "[gate-qa]"


def _bootstrap() -> Path:
    raw = os.environ.get("CLAUDE_PLUGIN_ROOT")
    if not raw:
        print(f"{HOOK_PREFIX} CLAUDE_PLUGIN_ROOT is required to run hooks.", file=sys.stderr)
        raise SystemExit(2)
    plugin_root = Path(raw).expanduser().resolve()
    if str(plugin_root) not in sys.path:
        sys.path.insert(0, str(plugin_root))
    vendor_dir = Path(__file__).resolve().parent / "_vendor"
    if vendor_dir.exists():
        sys.path.insert(0, str(vendor_dir))
    return plugin_root


def _log_stdout(message: str) -> None:
    from hooks import hooklib

    if message:
        print(hooklib.prefix_lines(HOOK_PREFIX, message))


def _log_stderr(message: str) -> None:
    from hooks import hooklib

    if message:
        print(hooklib.prefix_lines(HOOK_PREFIX, message), file=sys.stderr)


def _parse_args(argv: Iterable[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--only", default="")
    parser.add_argument("--payload", default="")
    parser.add_argument("--help", "-h", action="store_true")
    return parser.parse_args(list(argv))


def _should_run(filters: list[str]) -> bool:
    if not filters:
        return True
    for raw in filters:
        if not raw:
            continue
        for token in raw.replace(",", " ").split():
            if token.strip().lower() == "qa":
                return True
    return False


def _load_qa_config(config_path: Path) -> dict:
    try:
        data = json.loads(config_path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise ValueError(f"failed to parse config/gates.json: {exc}") from exc
    qa = data.get("qa", {})
    if isinstance(qa, bool):
        qa = {"enabled": qa}
    elif qa is None:
        qa = {}
    elif not isinstance(qa, dict):
        qa = {}
    return qa


def _norm_list(value: object) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, (list, tuple)):
        return [str(item) for item in value if str(item)]
    return []


def _replace_placeholders(raw: str, plugin_root: Path, ticket: str, slug_hint: str, branch: str) -> str:
    value = raw
    value = value.replace("{ticket}", ticket or "unknown")
    value = value.replace("{slug}", slug_hint or ticket or "unknown")
    value = value.replace("{branch}", branch or "detached")
    value = value.replace("${CLAUDE_PLUGIN_ROOT}", str(plugin_root))
    value = value.replace("$CLAUDE_PLUGIN_ROOT", str(plugin_root))
    return value


def _matches_any(branch: str, patterns: list[str]) -> bool:
    if not branch:
        return False
    for pattern in patterns:
        if pattern and fnmatch(branch, pattern):
            return True
    return False


def _handoff_check(root: Path, tasklist_path: Path, ticket: str, mode: str) -> str:
    if not tasklist_path.exists():
        return f"{mode.upper()}: tasklist не найден ({tasklist_path})."
    try:
        lines = tasklist_path.read_text(encoding="utf-8").splitlines()
    except Exception:
        return f"{mode.upper()}: не удалось прочитать {tasklist_path}."

    start = None
    end = len(lines)
    for idx, line in enumerate(lines):
        if line.strip().lower().startswith("## aidd:handoff_inbox"):
            start = idx
            break
    if start is not None:
        for idx in range(start + 1, len(lines)):
            if lines[idx].strip().startswith("##"):
                end = idx
                break
        scan_text = "\n".join(lines[start:end]).lower()
    else:
        scan_text = "\n".join(lines).lower()

    prefix = "aidd/" if root.name == "aidd" else ""
    markers = [
        f"{prefix}reports/qa/{ticket}".lower(),
        f"reports/qa/{ticket}".lower(),
    ]
    if not any(marker in scan_text for marker in markers):
        hint = f"${{CLAUDE_PLUGIN_ROOT}}/tools/tasks-derive.sh --source qa --append --ticket {ticket}"
        return f"{mode.upper()}: handoff-задачи QA не найдены в tasklist. Запустите `{hint}`."
    return ""


def main(argv: Iterable[str] | None = None) -> int:
    plugin_root = _bootstrap()
    from hooks import hooklib

    args = _parse_args(argv or [])
    if args.help:
        _log_stdout("Usage: gate-qa.sh [--dry-run] [--only qa] [--payload <json>]")
        return 0

    if os.environ.get("CLAUDE_SKIP_QA") == "1":
        return 0

    filters: list[str] = []
    if os.environ.get("CLAUDE_GATES_ONLY"):
        filters.append(os.environ.get("CLAUDE_GATES_ONLY", ""))
    if args.only:
        filters.append(args.only)
    if not _should_run(filters):
        return 0

    dry_run = args.dry_run or os.environ.get("CLAUDE_QA_DRY_RUN") == "1"

    ctx = hooklib.read_hook_context()
    payload: dict = {}
    if args.payload:
        try:
            payload = json.loads(args.payload)
        except json.JSONDecodeError:
            payload = {}
    elif isinstance(ctx.raw, dict):
        payload = ctx.raw

    root, used_workspace = hooklib.resolve_project_root(
        ctx,
        cwd=payload.get("cwd") if isinstance(payload, dict) else None,
    )
    if used_workspace:
        _log_stdout(f"WARN: detected workspace root; using {root} as project root")

    if not (root / "docs").is_dir():
        _log_stderr(
            "BLOCK: aidd/docs not found at {}. Run '/feature-dev-aidd:aidd-init' or "
            "'${CLAUDE_PLUGIN_ROOT}/tools/init.sh' from the workspace root to bootstrap ./aidd.".format(
                root / "docs"
            )
        )
        return 2

    if os.environ.get("CLAUDE_SKIP_STAGE_CHECKS") != "1":
        active_stage = hooklib.resolve_stage(root / "docs" / ".active_stage")
        if active_stage != "qa":
            return 0

    config_path = root / "config" / "gates.json"
    if not config_path.exists():
        _log_stdout(f"WARN: не найден {config_path} — QA-гейт пропущен.")
        return 0

    try:
        qa_cfg = _load_qa_config(config_path)
    except ValueError as exc:
        _log_stdout(f"WARN: {exc}")
        return 0

    enabled = bool(qa_cfg.get("enabled", True))
    if not enabled:
        return 0

    branch = hooklib.git_current_branch(root) or "detached"
    qa_branches = _norm_list(qa_cfg.get("branches", []))
    qa_skip = _norm_list(qa_cfg.get("skip_branches", []))
    if qa_branches and not _matches_any(branch, qa_branches):
        return 0
    if qa_skip and _matches_any(branch, qa_skip):
        return 0

    file_path = hooklib.payload_file_path(payload) or ""
    if file_path:
        if file_path.startswith(("docs/qa/", "reports/qa/", "aidd/docs/qa/", "aidd/reports/qa/")):
            pass
        elif file_path.startswith(("src/", "tests/", "docs/", "config/", "dev/repo_tools/")):
            pass
        else:
            return 0

    ticket_source = hooklib.config_get_str(config_path, "feature_ticket_source", "docs/.active_ticket")
    slug_hint_source = hooklib.config_get_str(config_path, "feature_slug_hint_source", "docs/.active_feature")

    def _resolve_rel(path_str: str | None) -> Path | None:
        if not path_str:
            return None
        raw = Path(path_str)
        return raw if raw.is_absolute() else root / raw

    ticket_path = _resolve_rel(ticket_source)
    slug_path = _resolve_rel(slug_hint_source)
    if ticket_path and ticket_source and ticket_source.startswith("aidd/") and not ticket_path.exists():
        alt = _resolve_rel(ticket_source[5:])
        if alt and alt.exists():
            ticket_path = alt
    if slug_path and slug_hint_source and slug_hint_source.startswith("aidd/") and not slug_path.exists():
        alt = _resolve_rel(slug_hint_source[5:])
        if alt and alt.exists():
            slug_path = alt

    ticket = hooklib.read_ticket(ticket_path, slug_path) if (ticket_path or slug_path) else None
    slug_hint = hooklib.read_slug(slug_path) if slug_path else ""

    qa_requires = _norm_list(qa_cfg.get("requires", []))
    if qa_requires:
        tests_mode = hooklib.config_get_str(config_path, "tests_required", "disabled")
        for req in qa_requires:
            req_norm = req.strip().lower()
            if req_norm == "gate-tests" and tests_mode.lower() == "disabled":
                _log_stdout("WARN: qa.requires содержит gate-tests, но tests_required=disabled.")
            if req_norm == "gate-api-contract" and not hooklib.config_get_bool(config_path, "api_contract", False):
                _log_stdout("WARN: qa.requires содержит gate-api-contract, но гейт отключён.")

    qa_command = _norm_list(qa_cfg.get("command", []))
    if not qa_command:
        qa_command = [str(plugin_root / "tools" / "qa.sh")]
    override = os.environ.get("CLAUDE_QA_COMMAND")
    if override:
        qa_command = shlex.split(override)

    cmd = [
        _replace_placeholders(part, plugin_root, ticket or "unknown", slug_hint or "", branch)
        for part in qa_command
        if part
    ]

    qa_block = [item.lower() for item in _norm_list(qa_cfg.get("block_on", ("blocker", "critical")))]
    qa_warn = [item.lower() for item in _norm_list(qa_cfg.get("warn_on", ("major", "minor")))]
    if not qa_block:
        qa_block = ["blocker", "critical"]
    if not qa_warn:
        qa_warn = ["major", "minor"]

    runner = list(cmd)
    if "--gate" not in runner:
        runner.append("--gate")
    runner.extend(["--block-on", ",".join(qa_block), "--warn-on", ",".join(qa_warn)])
    if ticket:
        runner.extend(["--ticket", ticket])
        if slug_hint and slug_hint != ticket:
            runner.extend(["--slug-hint", slug_hint])
    if branch:
        runner.extend(["--branch", branch])

    report_path = str(qa_cfg.get("report", "aidd/reports/qa/latest.json") or "")
    if report_path:
        report_path = _replace_placeholders(report_path, plugin_root, ticket or "unknown", slug_hint or "", branch)
        report_path = report_path.lstrip("./")
        if report_path.startswith("aidd/") and root.name == "aidd":
            report_path = report_path[5:]
        runner.extend(["--report", report_path])

    debounce_minutes = 0
    stamp_path = ""
    if os.environ.get("CLAUDE_SKIP_QA_DEBOUNCE") != "1":
        raw_debounce = os.environ.get("CLAUDE_QA_DEBOUNCE_MINUTES")
        if raw_debounce is not None:
            try:
                debounce_minutes = int(raw_debounce)
            except ValueError:
                debounce_minutes = 0
        else:
            try:
                debounce_minutes = int(qa_cfg.get("debounce_minutes", 0) or 0)
            except (ValueError, TypeError):
                debounce_minutes = 0

        if debounce_minutes > 0:
            now_ts = int(time.time())
            stamp_dir = "aidd/reports/qa"
            if report_path:
                stamp_dir = str(Path(report_path).parent)
            if stamp_dir.startswith("aidd/") and root.name == "aidd":
                stamp_dir = stamp_dir[5:]
            stamp_path = str(Path(stamp_dir) / f".gate-qa.{ticket or 'unknown'}.stamp")
            stamp_full = root / stamp_path
            if stamp_full.exists():
                try:
                    last_ts = int(stamp_full.read_text(encoding="utf-8").strip())
                except Exception:
                    last_ts = 0
                delta = now_ts - last_ts
                if last_ts and delta < debounce_minutes * 60:
                    _log_stdout(f"debounce: QA пропущен ({delta}s < {debounce_minutes}m).")
                    return 0

    if dry_run:
        runner.append("--dry-run")

    timeout_seconds = int(qa_cfg.get("timeout", 600) or 0)
    status = 0
    if ticket:
        label = f"ticket: {ticket}" + (f", slug hint: {slug_hint}" if slug_hint and slug_hint != ticket else "")
        _log_stdout(f"Запуск QA-агента (ветка: {branch}, {label})")
    else:
        _log_stdout(f"Запуск QA-агента (ветка: {branch}, ticket: n/a)")
    if dry_run:
        _log_stdout("dry-run режим: блокеры не провалят команду.")

    event_status = "fail"
    event_report = ""
    event_should_log = True
    try:
        try:
            completed = subprocess.run(runner, cwd=str(root), timeout=timeout_seconds if timeout_seconds > 0 else None)
            status = completed.returncode
        except subprocess.TimeoutExpired:
            _log_stderr(f"ERROR: QA command timed out after {timeout_seconds}s.")
            status = 124
        except FileNotFoundError:
            _log_stderr(f"ERROR: не удалось выполнить команду QA ({runner[0]}).")
            status = 127

        report_candidate = report_path
        if report_candidate and not (root / report_candidate).is_file():
            if report_candidate.endswith(".json"):
                for suffix in (".pack.yaml", ".pack.toon"):
                    alt = report_candidate[: -len(".json")] + suffix
                    if (root / alt).is_file():
                        report_candidate = alt
                        break
        if report_candidate and not (root / report_candidate).is_file():
            if not bool(qa_cfg.get("allow_missing_report", False)):
                _log_stderr(f"ERROR: отчёт QA не создан: {report_candidate}")
                if status == 0:
                    status = 1
        report_path = report_candidate

        if status == 0 and not dry_run and stamp_path and os.environ.get("CLAUDE_SKIP_QA_DEBOUNCE") != "1":
            stamp_full = root / stamp_path
            stamp_full.parent.mkdir(parents=True, exist_ok=True)
            stamp_full.write_text(str(int(time.time())), encoding="utf-8")

        if status == 0 and qa_cfg.get("handoff", False) and os.environ.get("CLAUDE_SKIP_QA_HANDOFF") != "1":
            if ticket:
                _log_stdout("handoff: формируем задачи из отчёта QA")
                handoff_cmd = [
                    str(plugin_root / "tools" / "tasks-derive.sh"),
                    "--source",
                    "qa",
                    "--append",
                    "--ticket",
                    ticket,
                ]
                if slug_hint and slug_hint != ticket:
                    handoff_cmd.extend(["--slug-hint", slug_hint])
                if report_path:
                    handoff_cmd.extend(["--report", report_path])
                result = subprocess.run(handoff_cmd, cwd=str(root))
                if result.returncode != 0:
                    _log_stdout(f"WARN: tasks-derive завершился с кодом {result.returncode} (handoff пропущен).")
            else:
                _log_stdout("WARN: ticket не определён — handoff пропущен.")

        handoff_mode = str(qa_cfg.get("handoff_mode", qa_cfg.get("handoffMode", "warn")) or "warn").lower()
        override_mode = os.environ.get("CLAUDE_QA_HANDOFF_MODE")
        if override_mode:
            handoff_mode = override_mode.strip().lower()
        if handoff_mode in {"1", "true", "yes", "on", "block"}:
            handoff_mode = "block"
        elif handoff_mode in {"0", "false", "no", "off", "skip", "disabled"}:
            handoff_mode = "off"
        elif handoff_mode in {"warn", "warning"}:
            handoff_mode = "warn"

        if (
            status == 0
            and qa_cfg.get("handoff", False)
            and os.environ.get("CLAUDE_SKIP_QA_HANDOFF") != "1"
            and handoff_mode != "off"
            and ticket
        ):
            msg = _handoff_check(root, root / "docs" / "tasklist" / f"{ticket}.md", ticket, handoff_mode)
            if msg:
                if handoff_mode == "block" and not dry_run:
                    _log_stderr(msg.replace("BLOCK:", "BLOCK:"))
                    status = 2
                else:
                    _log_stdout(msg.replace("BLOCK:", "WARN:"))

        if dry_run:
            event_status = "skipped"
        elif status == 0:
            event_status = "pass"
        else:
            event_status = "fail"
        event_report = report_path
        return status
    finally:
        if event_should_log:
            hooklib.append_event(root, "gate-qa", event_status, report=event_report, source="hook gate-qa")


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main(sys.argv[1:]))
