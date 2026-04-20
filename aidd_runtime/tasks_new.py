from __future__ import annotations

import argparse
import json
import os
import shlex
import sys
from datetime import date
from pathlib import Path

try:
    from aidd_runtime._bootstrap import ensure_repo_root
except ImportError:  # pragma: no cover - direct script execution
    from _bootstrap import ensure_repo_root

ensure_repo_root(__file__)

from aidd_runtime import runtime  # noqa: E402
from aidd_runtime import tasklist_check  # noqa: E402
from aidd_runtime import gates  # noqa: E402


def _is_cwd_wrong_runtime_error(exc: Exception) -> bool:
    return "refusing to use plugin repository as workspace root" in str(exc).lower()


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Ensure tasklist artifact exists for the active ticket and run tasklist validation.",
    )
    parser.add_argument(
        "--ticket",
        dest="ticket",
        help="Ticket identifier (defaults to docs/.active.json).",
    )
    parser.add_argument(
        "--slug-hint",
        dest="slug_hint",
        help="Optional slug hint override (defaults to docs/.active.json).",
    )
    parser.add_argument(
        "--tasklist",
        dest="tasklist_path",
        help="Optional tasklist path override (defaults to docs/tasklist/<ticket>.md).",
    )
    parser.add_argument(
        "--force-template",
        action="store_true",
        help="Rewrite tasklist from template even when the file already exists.",
    )
    parser.add_argument(
        "--strict",
        dest="strict",
        action="store_true",
        default=True,
        help="Return non-zero when tasklist-check returns an error (default).",
    )
    parser.add_argument(
        "--no-strict",
        dest="strict",
        action="store_false",
        help="Allow continuation on tasklist-check:error only with AIDD_ALLOW_TASKLIST_ERROR_SUCCESS=1.",
    )
    parser.add_argument(
        "--docs-only",
        action="store_true",
        help="Enable docs-only rewrite mode for this invocation.",
    )
    return parser.parse_args(argv)


def _replace_placeholders(text: str, ticket: str, slug: str, today: str, scope_key: str) -> str:
    return (
        text.replace("<ABC-123>", ticket)
        .replace("<short-slug>", slug)
        .replace("<YYYY-MM-DD>", today)
        .replace("<scope_key>", scope_key)
        .replace(
            "Stage: <idea|research|plan|review-spec|review-plan|review-prd|tasklist|implement|review|qa|status>",
            "Stage: tasklist",
        )
    )


def _resolve_tasklist_path(target: Path, override: str | None, ticket: str) -> Path:
    if not override:
        return target / "docs" / "tasklist" / f"{ticket}.md"
    candidate = Path(override)
    if candidate.is_absolute():
        return candidate
    return runtime.resolve_path_for_target(candidate, target)


def _validate_tasklist_postcondition(tasklist_path: Path) -> tuple[bool, str]:
    if not tasklist_path.exists():
        return False, "tasklist_missing"
    try:
        text = tasklist_path.read_text(encoding="utf-8")
    except OSError:
        return False, "tasklist_unreadable"
    if not text.strip():
        return False, "tasklist_empty"
    return True, ""


def _replace_section(text: str, title: str, body_lines: list[str]) -> str:
    lines = text.splitlines()
    start = None
    end = None
    for idx, line in enumerate(lines):
        if line.strip() == f"## {title}":
            start = idx
            break
    if start is None:
        return text
    end = len(lines)
    for idx in range(start + 1, len(lines)):
        if lines[idx].startswith("## "):
            end = idx
            break
    replacement = [lines[start], *body_lines, ""]
    updated = [*lines[:start], *replacement, *lines[end:]]
    return "\n".join(updated).rstrip("\n") + "\n"


def _migrate_legacy_expected_reports(text: str) -> str:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return text
    for idx in range(1, len(lines)):
        stripped = lines[idx].strip()
        if stripped == "---":
            break
        if stripped == "Reports:":
            indent = lines[idx][: len(lines[idx]) - len(lines[idx].lstrip())]
            lines[idx] = f"{indent}ExpectedReports:"
            return "\n".join(lines).rstrip("\n") + "\n"
    return text


def _issue_categories(
    result: tasklist_check.TasklistCheckResult,
    *,
    severity: str | None = None,
) -> set[str]:
    categories: set[str] = set()
    for issue in result.issues or []:
        issue_severity = str(getattr(issue, "severity", "") or "").strip().lower()
        if severity and issue_severity != severity:
            continue
        category = str(getattr(issue, "category", "") or "").strip()
        if category:
            categories.add(category)
    return categories


def _emit_tasklist_issues(result: tasklist_check.TasklistCheckResult) -> None:
    if result.issues:
        for issue in result.issues:
            print(
                "[tasks-new] issue "
                f"severity={issue.severity} category={issue.category} code={issue.code}: {issue.message}",
                file=sys.stderr,
            )
        return
    for detail in result.details or []:
        print(f"[tasks-new] {detail}", file=sys.stderr)


def _materialize_contract_command(entry: dict) -> str:
    tokens = [str(item).strip() for item in (entry.get("command") or []) if str(item).strip()]
    if not tokens:
        return ""
    cwd = str(entry.get("cwd") or ".").strip() or "."
    if cwd not in {".", "./"}:
        head = tokens[0]
        tail = tokens[1:]
        if head.startswith("./"):
            head = f"./{cwd.strip('./')}/{head[2:]}"
            tokens = [head, *tail]
        elif head == "npm":
            tokens = ["npm", "--prefix", cwd, *tail]
        elif head == "pnpm":
            tokens = ["pnpm", "--dir", cwd, *tail]
        elif head == "yarn":
            tokens = ["yarn", "--cwd", cwd, *tail]
        elif head == "mvn" and "-f" not in tail:
            tokens = ["mvn", "-f", f"./{cwd.strip('./')}/pom.xml", *tail]
        elif head == "cargo" and "--manifest-path" not in tail:
            tokens = ["cargo", *tail, "--manifest-path", f"./{cwd.strip('./')}/Cargo.toml"]
        elif head in {"python", "python3", "pytest"}:
            tokens = [head, *tail, f"./{cwd.strip('./')}"]
        elif head == "go":
            transformed: list[str] = []
            replaced = False
            for item in tail:
                if item == "./..." and not replaced:
                    transformed.append(f"./{cwd.strip('./')}/...")
                    replaced = True
                else:
                    transformed.append(item)
            if not transformed:
                transformed = [f"./{cwd.strip('./')}/..."]
            tokens = [head, *transformed]
    return " ".join(shlex.quote(token) for token in tokens if token)


def _render_test_execution_from_contract(target: Path) -> tuple[list[str], str]:
    contract, errors = gates.load_qa_tests_contract_for_target(target)
    profile = str(contract.get("profile_default") or "none").strip().lower()
    if errors and (profile != "none" or "project_contract_missing" in errors):
        return [], "project_contract_missing"

    when_value = str(contract.get("when_default") or "manual").strip() or "manual"
    reason_value = str(contract.get("reason_default") or "project-owned test contract").strip()
    filters = [str(item).strip() for item in (contract.get("filters_default") or []) if str(item).strip()]
    if profile == "none":
        return [
            f"- profile: {profile}",
            "- tasks: []",
            f"- filters: {json.dumps(filters, ensure_ascii=False)}",
            f"- when: {when_value}",
            f"- reason: {reason_value}",
        ], ""

    selected = gates.select_commands_for_profile(contract, profile) or list(contract.get("commands") or [])
    tasks: list[str] = []
    for entry in selected:
        if not isinstance(entry, dict):
            continue
        materialized = _materialize_contract_command(entry)
        if materialized:
            tasks.append(materialized)
    if not tasks:
        return [], "project_contract_missing"

    lines = [f"- profile: {profile}", "- tasks:"]
    lines.extend([f"  - {task}" for task in tasks])
    if filters:
        lines.append("- filters:")
        lines.extend([f"  - {item}" for item in filters])
    else:
        lines.append("- filters: []")
    lines.extend(
        [
            f"- when: {when_value}",
            f"- reason: {reason_value}",
        ]
    )
    return lines, ""


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        _, target = runtime.require_workflow_root()
    except RuntimeError as exc:
        if _is_cwd_wrong_runtime_error(exc):
            print(
                "[tasks-new] BLOCK: refusing to use plugin repository as workspace root "
                "(reason_code=cwd_wrong, classification=ENV_MISCONFIG(cwd_wrong)). "
                "Retry from PROJECT_DIR once after fixing cwd/plugin topology.",
                file=sys.stderr,
            )
            return 2
        raise
    ticket, context = runtime.require_ticket(
        target,
        ticket=getattr(args, "ticket", None),
        slug_hint=getattr(args, "slug_hint", None),
    )
    docs_only_mode = runtime.docs_only_mode_requested(explicit=getattr(args, "docs_only", False))
    slug = (context.slug_hint or ticket).strip() or ticket
    today = date.today().isoformat()
    scope_key = runtime.resolve_scope_key(work_item_key=None, ticket=ticket)

    plugin_root = runtime.require_plugin_root()
    template_path = plugin_root / "skills" / "tasks-new" / "templates" / "tasklist.template.md"
    if not template_path.exists():
        raise FileNotFoundError(f"tasklist template not found: {template_path}")
    template_text = template_path.read_text(encoding="utf-8")

    tasklist_path = _resolve_tasklist_path(target, getattr(args, "tasklist_path", None), ticket)
    tasklist_path.parent.mkdir(parents=True, exist_ok=True)

    created = not tasklist_path.exists()
    if created or args.force_template:
        rendered = _replace_placeholders(template_text, ticket, slug, today, scope_key)
        tasklist_path.write_text(rendered, encoding="utf-8")
    else:
        current = tasklist_path.read_text(encoding="utf-8")
        updated = _replace_placeholders(current, ticket, slug, today, scope_key)
        if updated != current:
            tasklist_path.write_text(updated, encoding="utf-8")

    contract_lines, contract_error = _render_test_execution_from_contract(target)
    if contract_error:
        if docs_only_mode:
            print(
                "[tasks-new] WARN: docs-only rewrite mode bypasses project test execution contract blocker "
                "(reason_code=project_contract_missing, docs_only_mode=1).",
                file=sys.stderr,
            )
            contract_lines = [
                "- profile: none",
                "- tasks: []",
                "- filters: []",
                "- when: manual",
                "- reason: docs-only rewrite mode",
            ]
        else:
            print(
                "[tasks-new] BLOCK: project test execution contract missing/invalid "
                "(reason_code=project_contract_missing). "
                "Update aidd/config/gates.json -> qa.tests.",
                file=sys.stderr,
            )
            return 2
    if contract_lines:
        tasklist_text = tasklist_path.read_text(encoding="utf-8")
        tasklist_text = _replace_section(tasklist_text, "AIDD:TEST_EXECUTION", contract_lines)
        tasklist_text = _migrate_legacy_expected_reports(tasklist_text)
        tasklist_path.write_text(tasklist_text, encoding="utf-8")
    else:
        tasklist_text = tasklist_path.read_text(encoding="utf-8")
        migrated = _migrate_legacy_expected_reports(tasklist_text)
        if migrated != tasklist_text:
            tasklist_path.write_text(migrated, encoding="utf-8")

    result = tasklist_check.check_tasklist(target, ticket)
    rel_path = runtime.rel_path(tasklist_path, target)
    print(f"[tasks-new] tasklist: {rel_path}")
    if result.status == "ok":
        print("[tasks-new] tasklist-check: ok")
    elif result.status == "warn":
        print("[tasks-new] tasklist-check: warn", file=sys.stderr)
        _emit_tasklist_issues(result)
    elif result.status == "error":
        print("[tasks-new] tasklist-check: error", file=sys.stderr)
        print(f"[tasks-new] {result.message}", file=sys.stderr)
        _emit_tasklist_issues(result)
        categories = _issue_categories(result, severity="error")
        if "upstream_blocker" in categories:
            remediation = (
                f"fix upstream PRD/plan/readiness blockers first, then rerun /feature-dev-aidd:review-spec {ticket} "
                f"and /feature-dev-aidd:tasks-new {ticket}"
            )
        elif categories == {"repairable_structure"}:
            remediation = (
                f"fix tasklist structural issues and rerun /feature-dev-aidd:tasks-new {ticket}; "
                "bounded retry applies only once for repairable_structure"
            )
        else:
            remediation = (
                f"fix tasklist contract issues and rerun /feature-dev-aidd:tasks-new {ticket}; "
                "do not create upstream artifacts manually in this stage"
            )
        print(f"[tasks-new] remediation: {remediation}", file=sys.stderr)
        if docs_only_mode:
            print(
                "[tasks-new] WARN: docs-only rewrite mode continues despite tasklist-check:error "
                "(invocation-local override).",
                file=sys.stderr,
            )
        else:
            allow_error_success = os.getenv("AIDD_ALLOW_TASKLIST_ERROR_SUCCESS", "").strip() == "1"
            if args.strict or not allow_error_success:
                return result.exit_code()
            print(
                "[tasks-new] WARN: non-strict success override enabled "
                "(AIDD_ALLOW_TASKLIST_ERROR_SUCCESS=1).",
                file=sys.stderr,
            )
    else:
        print(f"[tasks-new] tasklist-check: {result.status}")

    ok_postcondition, postcondition_code = _validate_tasklist_postcondition(tasklist_path)
    if not ok_postcondition:
        print(
            "[tasks-new] ERROR: mandatory tasklist artifact postcondition failed "
            f"(reason_code={postcondition_code}): {runtime.rel_path(tasklist_path, target)}",
            file=sys.stderr,
        )
        return 2

    runtime.maybe_sync_index(target, ticket, slug, reason="tasks-new")
    if docs_only_mode:
        print("[tasks-new] docs_only_mode=1 reinvoke_allowed=1 retry_scope=invocation", file=sys.stderr)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
