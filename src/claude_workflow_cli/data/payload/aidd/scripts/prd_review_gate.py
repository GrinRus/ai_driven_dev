#!/usr/bin/env python3
"""Shared PRD review gate logic for Claude workflow hooks.

The script checks that `docs/prd/<ticket>.prd.md` contains a `## PRD Review`
section with a READY status and no unresolved action items. Review runs after
plan review and blocks implementation until ready. Behaviour is
configured through `config/gates.json` (see the `prd_review` section).

Exit codes:
    0 — gate passed or skipped (disabled / branch excluded / direct PRD edit).
    1 — gate failed (message is printed to stdout).
"""

from __future__ import annotations

import argparse
import json
import os
from fnmatch import fnmatch
from pathlib import Path
from typing import Iterable, List, Set


DEFAULT_APPROVED = {"ready"}
DEFAULT_BLOCKING = {"blocked"}
DEFAULT_BLOCKING_SEVERITIES = {"critical"}
DEFAULT_CODE_PREFIXES = (
    "src/",
    "tests/",
    "test/",
    "app/",
    "services/",
    "backend/",
    "frontend/",
    "lib/",
    "core/",
    "packages/",
    "modules/",
    "cmd/",
)
REVIEW_HEADER = "## PRD Review"
DIALOG_HEADER = "## Диалог analyst"



def feature_label(ticket: str, slug_hint: str | None = None) -> str:
    ticket_value = ticket.strip()
    hint = (slug_hint or "").strip()
    if not ticket_value:
        return ""
    if hint and hint != ticket_value:
        return f"{ticket_value} (slug hint: {hint})"
    return ticket_value


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate PRD review readiness.")
    parser.add_argument(
        "--ticket",
        "--slug",
        dest="ticket",
        required=True,
        help="Active feature ticket (legacy alias: --slug).",
    )
    parser.add_argument(
        "--slug-hint",
        dest="slug_hint",
        default="",
        help="Optional slug hint used for messaging (defaults to docs/.active_feature).",
    )
    parser.add_argument(
        "--file-path",
        default="",
        help="Path being modified (used to skip checks for direct PRD edits).",
    )
    parser.add_argument(
        "--branch",
        default="",
        help="Current branch name for branch-based filters.",
    )
    parser.add_argument(
        "--config",
        default="config/gates.json",
        help="Path to gates configuration file (default: config/gates.json).",
    )
    parser.add_argument(
        "--skip-on-prd-edit",
        action="store_true",
        help="Return success when the PRD file itself is being edited.",
    )
    return parser.parse_args()


def load_gate_config(path: Path) -> dict:
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:  # pragma: no cover - malformed configs are rare
        return {}
    section = data.get("prd_review", {})
    if isinstance(section, bool):
        return {"enabled": section}
    return section if isinstance(section, dict) else {}


def matches(patterns: Iterable[str], value: str) -> bool:
    if not value:
        return False
    for pattern in patterns or ():
        if pattern and fnmatch(value, pattern):
            return True
    return False


def _normalize_file_path(raw: str) -> str:
    if not raw:
        return ""
    try:
        rel = Path(raw).resolve().relative_to(Path.cwd().resolve())
        return str(rel).replace("\\", "/")
    except Exception:
        normalized = raw.replace("\\", "/")
        if normalized.startswith("./"):
            normalized = normalized[2:]
        return normalized.lstrip("/")


def _normalize_items(values: Iterable[str] | None, *, suffix: str = "") -> List[str]:
    result: List[str] = []
    for item in values or ():
        text = str(item or "").strip()
        if not text:
            continue
        text = text.replace("\\", "/")
        while text.startswith("./"):
            text = text[2:]
        text = text.lstrip("/")
        if suffix and not text.endswith(suffix):
            text = f"{text}{suffix}"
        result.append(text)
    return result


def _is_code_path(path: str, prefixes: Iterable[str], globs: Iterable[str]) -> bool:
    normalized = path.replace("\\", "/")
    if not normalized:
        return False
    for prefix in prefixes:
        if normalized.startswith(prefix):
            return True
    for pattern in globs:
        if fnmatch(normalized, pattern):
            return True
    return False


def parse_review_section(content: str) -> tuple[bool, str, List[str]]:
    inside = False
    found = False
    status = ""
    action_items: List[str] = []
    for raw in content.splitlines():
        stripped = raw.strip()
        if stripped.startswith("## "):
            inside = stripped == REVIEW_HEADER
            if inside:
                found = True
            continue
        if not inside:
            continue
        lower = stripped.lower()
        if lower.startswith("status:"):
            status = stripped.split(":", 1)[1].strip().lower()
        elif stripped.startswith("- ["):
            action_items.append(stripped)
    return found, status, action_items


def format_message(kind: str, ticket: str, slug_hint: str | None = None, status: str | None = None) -> str:
    label = feature_label(ticket, slug_hint)
    human_status = (status or "PENDING").upper()
    if kind == "missing_section":
        return (
            f"BLOCK: нет раздела '## PRD Review' в aidd/docs/prd/{ticket}.prd.md → выполните /review-prd {label} (после /review-plan)"
        )
    if kind == "missing_prd":
        return (
            f"BLOCK: PRD не найден или не заполнен → откройте docs/prd/{ticket}.prd.md, допишите диалог и завершите /review-prd {label or ticket}."
        )
    if kind == "blocking_status":
        return (
            f"BLOCK: PRD Review помечен как '{human_status}' → устраните блокеры и обновите статус через /review-prd {label or ticket}"
        )
    if kind == "not_approved":
        return f"BLOCK: PRD Review не READY (Status: {human_status}) → выполните /review-prd {label or ticket}"
    if kind == "open_actions":
        return (
            f"BLOCK: В PRD Review остались незакрытые action items → перенесите их в docs/tasklist/{ticket}.md и отметьте выполнение."
        )
    if kind == "missing_report":
        return f"BLOCK: нет отчёта PRD Review (reports/prd/{ticket}.json) → перезапустите /review-prd {label or ticket}"
    if kind == "report_corrupted":
        return f"BLOCK: отчёт PRD Review повреждён → пересоздайте через /review-prd {label or ticket}"
    if kind == "blocking_finding":
        return (
            f"BLOCK: отчёт PRD Review содержит критичные findings → устраните замечания и обновите отчёт для {label or ticket}."
        )
    if kind == "draft_dialog":
        return (
            f"BLOCK: PRD в статусе draft → заполните раздел '## Диалог analyst', обновите Status: READY и только затем запускайте /review-prd {label or ticket}."
        )
    return f"BLOCK: PRD Review не готов → выполните /review-prd {label or ticket}"


def detect_project_root() -> Path:
    """Prefer the plugin root (aidd) even if workspace-level docs/ exist."""
    cwd = Path.cwd().resolve()
    env_root = os.getenv("CLAUDE_PLUGIN_ROOT")
    project_root = os.getenv("CLAUDE_PROJECT_DIR")
    candidates = []
    if env_root:
        candidates.append(Path(env_root).expanduser().resolve())
    if cwd.name == "aidd":
        candidates.append(cwd)
    candidates.append(cwd / "aidd")
    candidates.append(cwd)
    if project_root:
        candidates.append(Path(project_root).expanduser().resolve())
    for candidate in candidates:
        docs_dir = candidate / "docs"
        if docs_dir.is_dir():
            return candidate
    return cwd


def extract_dialog_status(content: str) -> str | None:
    inside = False
    for raw in content.splitlines():
        stripped = raw.strip()
        lower = stripped.lower()
        if lower.startswith(DIALOG_HEADER.lower()):
            inside = True
            continue
        if inside and stripped.startswith("## "):
            break
        if inside and lower.startswith("status:"):
            return stripped.split(":", 1)[1].strip().lower()
    return None


def main() -> None:
    args = parse_args()
    root = detect_project_root()
    config_path = Path(args.config)
    if not config_path.is_absolute():
        config_path = root / config_path
    gate = load_gate_config(config_path)

    ticket = args.ticket.strip()
    slug_hint = args.slug_hint.strip() or None

    enabled = bool(gate.get("enabled", True))
    if not enabled:
        raise SystemExit(0)

    if matches(gate.get("skip_branches", []), args.branch):
        raise SystemExit(0)
    branches = gate.get("branches")
    if branches and not matches(branches, args.branch):
        raise SystemExit(0)

    code_prefixes = tuple(_normalize_items(gate.get("code_prefixes"), suffix="/") or DEFAULT_CODE_PREFIXES)
    code_globs = tuple(_normalize_items(gate.get("code_globs")))
    normalized = _normalize_file_path(args.file_path)
    target_suffix = f"docs/prd/{ticket}.prd.md"
    if args.skip_on_prd_edit and normalized.endswith(target_suffix):
        raise SystemExit(0)
    if normalized and not _is_code_path(normalized, code_prefixes, code_globs):
        raise SystemExit(0)

    prd_path = root / "docs" / "prd" / f"{ticket}.prd.md"
    if not prd_path.is_file():
        expected = prd_path.as_posix()
        print(f"BLOCK: нет PRD (ожидается {expected}) → откройте aidd/docs/prd/{ticket}.prd.md, допишите диалог и завершите /review-prd {feature_label(ticket, slug_hint) or ticket}.")
        raise SystemExit(1)

    allow_missing = bool(gate.get("allow_missing_section", False))
    require_closed = bool(gate.get("require_action_items_closed", True))
    approved: Set[str] = {str(item).lower() for item in gate.get("approved_statuses", DEFAULT_APPROVED)}
    blocking: Set[str] = {str(item).lower() for item in gate.get("blocking_statuses", DEFAULT_BLOCKING)}

    content = prd_path.read_text(encoding="utf-8")
    dialog_status = extract_dialog_status(content)
    if dialog_status == "draft":
        print(format_message("draft_dialog", ticket, slug_hint))
        raise SystemExit(1)
    found, status, action_items = parse_review_section(content)

    if not found:
        if allow_missing:
            raise SystemExit(0)
        print(format_message("missing_section", ticket, slug_hint))
        raise SystemExit(1)

    if status in blocking:
        print(format_message("blocking_status", ticket, slug_hint, status))
        raise SystemExit(1)

    if approved and status not in approved:
        print(format_message("not_approved", ticket, slug_hint, status))
        raise SystemExit(1)

    if require_closed:
        for item in action_items:
            if item.startswith("- [ ]"):
                print(format_message("open_actions", ticket, slug_hint, status))
                raise SystemExit(1)

    allow_missing_report = bool(gate.get("allow_missing_report", False))
    report_template = gate.get("report_path") or "reports/prd/{ticket}.json"
    resolved_report = report_template.replace("{ticket}", ticket).replace("{slug}", slug_hint or ticket)
    report_path = Path(resolved_report)
    if not report_path.is_absolute():
        report_path = root / report_path

    if report_path.exists():
        try:
            report_data = json.loads(report_path.read_text(encoding="utf-8"))
        except Exception:
            print(format_message("report_corrupted", ticket, slug_hint))
            raise SystemExit(1)

        findings = report_data.get("findings") or []
        blocking_severities: Set[str] = {
            str(item).lower() for item in gate.get("blocking_severities", DEFAULT_BLOCKING_SEVERITIES)
        }
        if blocking_severities:
            for finding in findings:
                severity = ""
                if isinstance(finding, dict):
                    severity = str(finding.get("severity") or "").lower()
                if severity and severity in blocking_severities:
                    label = feature_label(ticket, slug_hint)
                    print(
                        f"BLOCK: PRD Review содержит findings уровня '{severity}' → обновите PRD и повторно вызовите /review-prd {label or ticket}."
                    )
                    raise SystemExit(1)
    else:
        if not allow_missing_report:
            if "{ticket}" in report_template or "{slug}" in report_template:
                message = format_message("missing_report", ticket, slug_hint)
            else:
                label = feature_label(ticket, slug_hint)
                message = f"BLOCK: нет отчёта PRD Review ({report_path}) → перезапустите /review-prd {label or ticket}"
            print(message)
            raise SystemExit(1)

    raise SystemExit(0)


if __name__ == "__main__":
    main()
