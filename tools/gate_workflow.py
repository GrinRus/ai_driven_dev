#!/usr/bin/env python3
from __future__ import annotations

import io
import json
import os
import re
import sys
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from typing import Optional


HOOK_PREFIX = "[gate-workflow]"


def _bootstrap() -> None:
    raw = os.environ.get("CLAUDE_PLUGIN_ROOT")
    if not raw:
        print(f"{HOOK_PREFIX} CLAUDE_PLUGIN_ROOT is required to run hooks.", file=sys.stderr)
        raise SystemExit(2)
    plugin_root = Path(raw).expanduser().resolve()
    if str(plugin_root) not in sys.path:
        sys.path.insert(0, str(plugin_root))
    vendor_dir = plugin_root / "hooks" / "_vendor"
    if vendor_dir.exists():
        sys.path.insert(0, str(vendor_dir))


def _log_stdout(message: str) -> None:
    from hooks import hooklib

    if message:
        print(hooklib.prefix_lines(HOOK_PREFIX, message))


def _log_stderr(message: str) -> None:
    from hooks import hooklib

    if message:
        print(hooklib.prefix_lines(HOOK_PREFIX, message), file=sys.stderr)


def _select_file_path(paths: list[str]) -> str:
    for candidate in paths:
        if re.search(r"(^|/)src/", candidate):
            return candidate
    return paths[0] if paths else ""


def _next3_has_real_items(tasklist_path: Path) -> bool:
    if not tasklist_path.exists():
        return False
    lines = tasklist_path.read_text(encoding="utf-8").splitlines()
    start = None
    end = len(lines)
    for idx, line in enumerate(lines):
        if line.strip().lower().startswith("## aidd:next_3"):
            start = idx + 1
            break
    if start is None:
        return False
    for idx in range(start, len(lines)):
        if lines[idx].strip().startswith("##"):
            end = idx
            break
    section = lines[start:end]

    def is_placeholder(text: str) -> bool:
        lower = text.lower()
        placeholders = ("<1.", "<2.", "<3.", "<ticket>", "<slug>", "<abc-123>")
        return any(token in lower for token in placeholders)

    for raw in section:
        line = raw.strip()
        if line.lower().startswith("- (none)") or "no pending tasks" in line.lower():
            return True
        if not line.startswith("- ["):
            continue
        if not (line.startswith("- [ ]") or line.startswith("- [x]") or line.startswith("- [X]")):
            continue
        if is_placeholder(line):
            continue
        return True
    return False


def _run_plan_review_gate(root: Path, ticket: str, file_path: str, branch: str) -> tuple[int, str]:
    from tools import plan_review_gate

    args = ["--ticket", ticket, "--file-path", file_path, "--skip-on-plan-edit"]
    if branch:
        args.extend(["--branch", branch])
    parsed = plan_review_gate.parse_args(args)
    buf = io.StringIO()
    with redirect_stdout(buf):
        status = plan_review_gate.run_gate(parsed)
    return status, buf.getvalue().strip()


def _run_prd_review_gate(root: Path, ticket: str, slug_hint: str, file_path: str, branch: str) -> tuple[int, str]:
    from tools import prd_review_gate

    args = ["--ticket", ticket, "--file-path", file_path, "--skip-on-prd-edit"]
    if slug_hint:
        args.extend(["--slug-hint", slug_hint])
    if branch:
        args.extend(["--branch", branch])
    parsed = prd_review_gate.parse_args(args)
    buf = io.StringIO()
    with redirect_stdout(buf):
        status = prd_review_gate.run_gate(parsed)
    return status, buf.getvalue().strip()


def _run_tasklist_check(root: Path, ticket: str, slug_hint: str, branch: str) -> tuple[int, str]:
    from tools import tasklist_check

    args = ["--ticket", ticket, "--quiet-ok"]
    if slug_hint:
        args.extend(["--slug-hint", slug_hint])
    if branch:
        args.extend(["--branch", branch])
    parsed = tasklist_check.parse_args(args)
    buf = io.StringIO()
    with redirect_stderr(buf):
        status = tasklist_check.run_check(parsed)
    return status, buf.getvalue().strip()


def _reviewer_notice(root: Path, ticket: str, slug_hint: str) -> str:
    config_path = root / "config" / "gates.json"
    try:
        config = json.loads(config_path.read_text(encoding="utf-8"))
    except Exception:
        return ""

    reviewer_cfg = config.get("reviewer") or {}
    if not reviewer_cfg or not reviewer_cfg.get("enabled", True):
        return ""

    template = str(
        reviewer_cfg.get("tests_marker")
        or reviewer_cfg.get("marker")
        or "aidd/reports/reviewer/{ticket}/{scope_key}.json"
    )
    field = str(reviewer_cfg.get("tests_field") or reviewer_cfg.get("field") or "tests")
    required_values_source = reviewer_cfg.get("requiredValues", reviewer_cfg.get("required_values", ["required"]))
    if isinstance(required_values_source, list):
        required_values = [str(value).strip().lower() for value in required_values_source]
    else:
        required_values = ["required"]
    optional_values = reviewer_cfg.get("optionalValues", reviewer_cfg.get("optional_values", []))
    if isinstance(optional_values, list):
        optional_values = [str(value).strip().lower() for value in optional_values]
    else:
        optional_values = []
    allowed_values = set(required_values + optional_values)

    slug_value = slug_hint.strip() or ticket
    try:
        from tools import runtime as _runtime

        work_item_key = _runtime.read_active_work_item(root)
        scope_key = _runtime.resolve_scope_key(work_item_key, ticket)
        marker_path = _runtime.reviewer_marker_path(
            root,
            template,
            ticket,
            slug_hint or None,
            scope_key=scope_key,
        )
    except Exception:
        raw_scope = ""
        try:
            raw_scope = (root / "docs" / ".active_work_item").read_text(encoding="utf-8").strip()
        except OSError:
            raw_scope = ""
        raw_scope = raw_scope or ticket or ""
        cleaned_scope = "".join(ch if ch.isalnum() or ch in "._-" else "_" for ch in raw_scope).strip("._-") or "ticket"
        raw_path = (
            template.replace("{ticket}", ticket)
            .replace("{slug}", slug_value)
            .replace("{scope_key}", cleaned_scope)
        )
        marker_path = Path(raw_path)
        if not marker_path.is_absolute() and marker_path.parts and marker_path.parts[0] == "aidd" and root.name == "aidd":
            marker_path = root / Path(*marker_path.parts[1:])
        elif not marker_path.is_absolute():
            marker_path = root / marker_path

    if not marker_path.exists():
        if reviewer_cfg.get("warn_on_missing", True):
            return (
                "WARN: reviewer маркер не найден ({}). Используйте "
                "`${{CLAUDE_PLUGIN_ROOT}}/tools/reviewer-tests.sh --status required` при необходимости.".format(
                    marker_path
                )
            )
        return ""

    try:
        data = json.loads(marker_path.read_text(encoding="utf-8"))
    except Exception:
        return (
            "WARN: повреждён маркер reviewer ({}). Пересоздайте его командой "
            "`${{CLAUDE_PLUGIN_ROOT}}/tools/reviewer-tests.sh --status required`.".format(marker_path)
        )

    value = str(data.get(field, "")).strip().lower()
    if allowed_values and value not in allowed_values:
        label = value or "empty"
        return f"WARN: некорректный статус reviewer marker ({label}). Используйте required|optional|skipped."
    if value in required_values:
        return f"WARN: reviewer запросил тесты ({marker_path}). Запустите format-and-test или обновите маркер после прогонов."
    return ""


def _handoff_block(root: Path, ticket: str, slug_hint: str, branch: str, tasklist_path: Path) -> str:
    config_path = root / "config" / "gates.json"
    try:
        config = json.loads(config_path.read_text(encoding="utf-8"))
    except Exception:
        config = {}

    def marker_for(path: Path) -> str:
        if path.is_absolute():
            try:
                rel = path.relative_to(root)
                rel_str = rel.as_posix()
            except ValueError:
                rel_str = path.as_posix()
        else:
            rel_str = path.as_posix()
        if root.name == "aidd" and not rel_str.startswith("aidd/"):
            return f"aidd/{rel_str}"
        return rel_str

    def resolve_report(path: Path) -> Optional[Path]:
        if path.exists():
            return path
        if path.suffix == ".json":
            candidate = path.with_suffix(".pack.json")
            if candidate.exists():
                return candidate
        return None

    def research_requires_handoff(report_path: Path) -> bool:
        try:
            from tools import tasks_derive
        except Exception:
            return True

        try:
            payload = json.loads(report_path.read_text(encoding="utf-8"))
        except Exception:
            return True

        label = marker_for(report_path)
        blocks = tasks_derive._derive_tasks_from_research_context(payload, label)
        ast_path = root / "reports" / "research" / f"{ticket}-ast-grep.pack.json"
        if ast_path.exists():
            try:
                ast_payload = json.loads(ast_path.read_text(encoding="utf-8"))
            except Exception:
                ast_payload = {}
            blocks.extend(tasks_derive._derive_tasks_from_ast_grep_pack(ast_payload, marker_for(ast_path)))
        blocks = tasks_derive._dedupe_task_blocks(blocks)
        blocks = tasks_derive._filter_research_handoff_blocks(blocks)
        return bool(blocks)

    reports: list[tuple[str, Path, str]] = []
    qa_template = None
    qa_cfg = config.get("qa") or {}
    if isinstance(qa_cfg, dict):
        qa_template = qa_cfg.get("report")
    if not qa_template:
        qa_template = "aidd/reports/qa/{ticket}.json"
    slug_value = slug_hint.strip() or ticket
    branch_value = branch.strip() or "detached"
    raw_qa_path = (
        str(qa_template)
        .replace("{ticket}", ticket)
        .replace("{slug}", slug_value)
        .replace("{branch}", branch_value)
    )
    qa_path = Path(raw_qa_path)
    if not qa_path.is_absolute() and qa_path.parts and qa_path.parts[0] == "aidd" and root.name == "aidd":
        qa_path = root / Path(*qa_path.parts[1:])
    elif not qa_path.is_absolute():
        qa_path = root / qa_path
    qa_path = resolve_report(qa_path)
    if qa_path:
        reports.append(("qa", qa_path, marker_for(qa_path)))

    research_path = resolve_report(root / "reports" / "research" / f"{ticket}-context.json")
    if research_path and research_requires_handoff(research_path):
        reports.append(("research", research_path, marker_for(research_path)))

    reviewer_cfg = config.get("reviewer") or {}
    review_template = (
        reviewer_cfg.get("marker")
        or reviewer_cfg.get("tests_marker")
        or "aidd/reports/reviewer/{ticket}/{scope_key}.json"
    )
    try:
        from tools import runtime as _runtime

        work_item_key = _runtime.read_active_work_item(root)
        scope_key = _runtime.resolve_scope_key(work_item_key, ticket)
        review_path = _runtime.reviewer_marker_path(
            root,
            str(review_template),
            ticket,
            slug_hint or None,
            scope_key=scope_key,
        )
    except Exception:
        raw_scope = ""
        try:
            raw_scope = (root / "docs" / ".active_work_item").read_text(encoding="utf-8").strip()
        except OSError:
            raw_scope = ""
        raw_scope = raw_scope or ticket or ""
        cleaned_scope = "".join(ch if ch.isalnum() or ch in "._-" else "_" for ch in raw_scope).strip("._-") or "ticket"
        raw_path = (
            str(review_template)
            .replace("{ticket}", ticket)
            .replace("{slug}", slug_value)
            .replace("{scope_key}", cleaned_scope)
        )
        review_path = Path(raw_path)
        if not review_path.is_absolute() and review_path.parts and review_path.parts[0] == "aidd" and root.name == "aidd":
            review_path = root / Path(*review_path.parts[1:])
        elif not review_path.is_absolute():
            review_path = root / review_path
    if review_path.exists():
        has_review_report = False
        try:
            review_payload = json.loads(review_path.read_text(encoding="utf-8"))
        except Exception:
            review_payload = {}
            has_review_report = True
        if isinstance(review_payload, dict):
            kind = str(review_payload.get("kind") or "").strip().lower()
            stage = str(review_payload.get("stage") or "").strip().lower()
            if kind == "review" or stage == "review":
                has_review_report = True
            elif "findings" in review_payload:
                has_review_report = True
        else:
            has_review_report = True
        if has_review_report:
            reports.append(("review", review_path, marker_for(review_path)))

    try:
        lines = tasklist_path.read_text(encoding="utf-8").splitlines()
    except Exception:
        return ""

    def read_tasklist_section(lines: list[str]) -> str:
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
            return "\n".join(lines[start:end]).lower()
        return "\n".join(lines).lower()

    text = read_tasklist_section(lines)
    missing: list[tuple[str, str]] = []
    for name, report_path, marker in reports:
        marker_lower = marker.lower()
        alt_marker = marker_lower.replace("aidd/", "")
        if marker_lower not in text and alt_marker not in text:
            missing.append((name, marker))
    if missing:
        items = ", ".join(f"{name}: {marker}" for name, marker in missing)
        return (
            f"BLOCK: handoff-задачи не добавлены в tasklist ({items}). "
            f"Запустите `${{CLAUDE_PLUGIN_ROOT}}/tools/tasks-derive.sh --source <qa|research|review> --append --ticket {ticket}`."
        )
    return ""


def main() -> int:
    _bootstrap()
    from hooks import hooklib
    from tools.analyst_guard import AnalystValidationError, load_settings as load_analyst_settings, validate_prd
    from tools.progress import ProgressConfig, check_progress
    from tools.research_guard import ResearchValidationError, load_settings as load_research_settings, validate_research

    ctx = hooklib.read_hook_context()
    root, used_workspace = hooklib.resolve_project_root(ctx)
    if used_workspace:
        _log_stdout(f"WARN: detected workspace root; using {root} as project root")

    if not (root / "docs").is_dir():
        _log_stderr(
            "BLOCK: aidd/docs not found at {}. Run '/feature-dev-aidd:aidd-init' or "
            "'${{CLAUDE_PLUGIN_ROOT}}/tools/init.sh' from the workspace root to bootstrap ./aidd.".format(
                root / "docs"
            )
        )
        return 2

    os.chdir(root)

    payload = ctx.raw
    file_path = hooklib.payload_file_path(payload) or ""

    current_branch = hooklib.git_current_branch(root)
    changed_files = hooklib.collect_changed_files(root)
    if file_path:
        changed_files.insert(0, file_path)
    changed_files = list(dict.fromkeys(changed_files))

    if not file_path and changed_files:
        file_path = _select_file_path(changed_files)

    has_src_changes = any(re.search(r"(^|/)src/", candidate) for candidate in changed_files)

    ticket_path = root / "docs" / ".active_ticket"
    slug_path = root / "docs" / ".active_feature"
    if not ticket_path.exists() and not slug_path.exists():
        return 0

    ticket = hooklib.read_ticket(ticket_path, slug_path)
    slug_hint = hooklib.read_slug(slug_path) if slug_path.exists() else ""
    if not ticket:
        _log_stdout("WARN: active ticket not set; skipping tasklist checks.")
        return 0

    active_stage = hooklib.resolve_stage(root / "docs" / ".active_stage") or ""
    if os.environ.get("CLAUDE_SKIP_STAGE_CHECKS") != "1":
        if active_stage and active_stage not in {"implement", "review", "qa"}:
            if has_src_changes:
                _log_stderr(
                    f"BLOCK: активная стадия '{active_stage}' не разрешает правки кода. "
                    "Переключитесь на /feature-dev-aidd:implement (или установите стадию вручную)."
                )
                return 2
            return 0

    tasklist_path = root / "docs" / "tasklist" / f"{ticket}.md"
    if not tasklist_path.exists():
        _log_stdout(f"WARN: tasklist missing ({tasklist_path}).")
        if not has_src_changes:
            return 0
    else:
        status, output = _run_tasklist_check(root, ticket, slug_hint, current_branch)
        if status != 0:
            if active_stage in {"review", "qa"}:
                if output:
                    _log_stderr(output)
                else:
                    _log_stderr(f"BLOCK: tasklist check failed for {ticket}")
                return 2
            if output:
                _log_stdout(output)
            else:
                _log_stdout(f"WARN: tasklist check failed for {ticket}")

    if not has_src_changes:
        return 0

    event_status = "fail"
    event_should_log = True
    try:
        hooklib.ensure_template(root, "docs/research/template.md", root / "docs" / "research" / f"{ticket}.md")
        hooklib.ensure_template(root, "docs/prd/template.md", root / "docs" / "prd" / f"{ticket}.prd.md")

        plan_path = root / "docs" / "plan" / f"{ticket}.md"
        if not plan_path.exists():
            hooklib.ensure_template(root, "docs/plan/template.md", plan_path)
            _log_stderr(f"BLOCK: нет плана → запустите /feature-dev-aidd:plan-new {ticket}")
            return 2

        if not tasklist_path.exists():
            hooklib.ensure_template(root, "docs/tasklist/template.md", tasklist_path)
            _log_stderr(f"BLOCK: нет задач → запустите /feature-dev-aidd:tasks-new {ticket} (docs/tasklist/{ticket}.md)")
            return 2

        if not (root / "docs" / "prd" / f"{ticket}.prd.md").exists():
            _log_stderr(f"BLOCK: нет PRD → запустите /feature-dev-aidd:idea-new {ticket}")
            return 2

        analyst_settings = load_analyst_settings(root)
        try:
            validate_prd(root, ticket, settings=analyst_settings, branch=current_branch or None)
        except AnalystValidationError as exc:
            _log_stderr(str(exc))
            return 2

        status, output = _run_plan_review_gate(root, ticket, file_path, current_branch)
        if status != 0:
            if output:
                _log_stderr(output)
            else:
                _log_stderr(f"BLOCK: Plan Review не готов → выполните /feature-dev-aidd:review-spec {ticket}")
            return 2

        status, output = _run_prd_review_gate(root, ticket, slug_hint, file_path, current_branch)
        if status != 0:
            if output:
                _log_stderr(output)
            else:
                _log_stderr(f"BLOCK: PRD Review не готов → выполните /feature-dev-aidd:review-spec {ticket}")
            return 2

        research_settings = load_research_settings(root)
        try:
            research_summary = validate_research(root, ticket, settings=research_settings, branch=current_branch or None)
        except ResearchValidationError as exc:
            _log_stderr(str(exc))
            return 2

        if research_summary.skipped_reason == "pending-baseline":
            event_status = "pass"
            return 0

        if not _next3_has_real_items(tasklist_path):
            _log_stderr(f"BLOCK: нет задач → запустите /feature-dev-aidd:tasks-new {ticket} (docs/tasklist/{ticket}.md)")
            return 2

        reviewer_notice = _reviewer_notice(root, ticket, slug_hint)
        if reviewer_notice:
            _log_stdout(reviewer_notice)

        handoff_msg = _handoff_block(root, ticket, slug_hint, current_branch, tasklist_path)
        if handoff_msg:
            _log_stderr(handoff_msg)
            return 2

        progress_config = ProgressConfig.load(root)
        progress_result = check_progress(
            root=root,
            ticket=ticket,
            slug_hint=slug_hint or None,
            source="gate",
            branch=current_branch or None,
            config=progress_config,
        )
        if progress_result.exit_code() != 0:
            if progress_result.message:
                _log_stderr(progress_result.message)
            else:
                _log_stderr("BLOCK: tasklist не обновлён — отметьте завершённые чекбоксы перед продолжением.")
            return 2
        if progress_result.message:
            _log_stdout(progress_result.message)

        event_status = "pass"
        return 0
    finally:
        if event_should_log:
            hooklib.append_event(root, "gate-workflow", event_status, source="hook gate-workflow")


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
