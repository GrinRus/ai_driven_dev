#!/usr/bin/env python3
"""Heuristic QA agent used by gate-qa.sh and CI workflows.

The agent analyses the current workspace (or diff against a base commit),
collects lightweight QA findings and produces a structured report with
severity levels. In gate mode it prints a short summary and returns a non-zero
exit code when blocking issues are detected.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Set, Tuple

REPO_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_SRC = Path.cwd() / "src"
for candidate in (REPO_ROOT / "src", WORKSPACE_SRC):
    if candidate.is_dir():
        candidate_str = str(candidate)
        if candidate_str not in sys.path:
            sys.path.insert(0, candidate_str)

ROOT_DIR = Path.cwd()

from claude_workflow_cli.feature_ids import resolve_identifiers  # type: ignore

DEFAULT_BLOCKERS = ("blocker", "critical")
DEFAULT_WARNINGS = ("major", "minor")
SEVERITY_ORDER = ["blocker", "critical", "major", "minor", "info"]


def feature_label(ticket: Optional[str], slug_hint: Optional[str]) -> str:
    ticket_value = (ticket or "").strip()
    hint_value = (slug_hint or "").strip()
    if not ticket_value:
        return ""
    if hint_value and hint_value != ticket_value:
        return f"{ticket_value} (slug hint: {hint_value})"
    return ticket_value


@dataclass
class Finding:
    severity: str
    scope: str
    title: str
    details: str
    recommendation: str

    def to_dict(self) -> dict:
        return {
            "severity": self.severity,
            "scope": self.scope,
            "title": self.title,
            "details": self.details,
            "recommendation": self.recommendation,
        }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run heuristic QA checks for the current Claude workflow project."
    )
    parser.add_argument("--ticket", "--slug", dest="ticket", help="Active feature ticket (legacy alias: --slug).")
    parser.add_argument("--slug-hint", dest="slug_hint", help="Optional slug hint used for messaging.")
    parser.add_argument("--branch", help="Current branch name. Autodetected when omitted.")
    parser.add_argument(
        "--format",
        choices=("json", "text"),
        default="json",
        help="Output format for the generated report (default: json).",
    )
    parser.add_argument(
        "--report",
        type=Path,
        help="Optional path to write JSON report. Directories are created automatically.",
    )
    parser.add_argument(
        "--gate",
        action="store_true",
        help="Enable gate mode: print human-readable summary and exit with non-zero code on blockers.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Do not fail the process even if blockers are detected (gate mode only).",
    )
    parser.add_argument(
        "--block-on",
        default=",".join(DEFAULT_BLOCKERS),
        help="Comma separated list of severities treated as blockers.",
    )
    parser.add_argument(
        "--warn-on",
        default=",".join(DEFAULT_WARNINGS),
        help="Comma separated list of severities treated as warnings (non-blocking).",
    )
    parser.add_argument(
        "--emit-json",
        action="store_true",
        help="Emit JSON to stdout even in gate mode (useful for tooling).",
    )
    parser.add_argument(
        "--scope",
        action="append",
        help="Optional scope filters (reserved for future heuristics).",
    )
    return parser.parse_args()


def detect_feature(ticket_arg: Optional[str], slug_hint_arg: Optional[str]) -> tuple[Optional[str], Optional[str]]:
    identifiers = resolve_identifiers(ROOT_DIR, ticket=ticket_arg, slug_hint=slug_hint_arg)
    return identifiers.resolved_ticket, identifiers.slug_hint


def run_git(args: Sequence[str]) -> List[str]:
    cmd = ["git", *args]
    try:
        proc = subprocess.run(
            cmd,
            cwd=ROOT_DIR,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            check=False,
        )
    except (FileNotFoundError, OSError):
        return []
    if proc.returncode != 0:
        return []
    return [line.strip() for line in proc.stdout.splitlines() if line.strip()]


def detect_branch(explicit: Optional[str]) -> Optional[str]:
    if explicit:
        return explicit
    branch = run_git(["rev-parse", "--abbrev-ref", "HEAD"])
    return branch[0] if branch else None


def collect_changed_files() -> List[str]:
    files: Set[str] = set()
    diff_base = os.environ.get("QA_AGENT_DIFF_BASE", "").strip()
    if diff_base:
        files.update(run_git(["diff", "--name-only", f"{diff_base}...HEAD"]))
    files.update(run_git(["diff", "--name-only", "HEAD"]))
    files.update(run_git(["diff", "--name-only", "--cached"]))
    files.update(run_git(["ls-files", "--others", "--exclude-standard"]))
    return sorted(files)


def _find_token_lines(content: str, token: str) -> Iterable[Tuple[int, str]]:
    for idx, line in enumerate(content.splitlines(), start=1):
        if token in line:
            yield idx, line.strip()


def analyse_code_tokens(files: Iterable[str]) -> List[Finding]:
    findings: List[Finding] = []
    token_rules = {
        "FIXME": (
            "blocker",
            "Обнаружен FIXME в коде",
            "Удалите/устраните FIXME перед мерджем (QA блокер).",
        ),
        "TODO": (
            "major",
            "Не закрыт TODO",
            "Уберите TODO или перенесите в задачу с ссылкой перед релизом.",
        ),
    }
    for relative in files:
        path = ROOT_DIR / relative
        if not path.is_file():
            continue
        # Ограничимся только исходниками и тестами
        if not any(part in relative for part in ("src/", "tests/", ".kt", ".java", ".py", ".js", ".ts", ".tsx", ".json", ".yaml")):
            continue
        try:
            content = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        for token, (severity, title, recommendation) in token_rules.items():
            matches = list(_find_token_lines(content, token))
            if not matches:
                continue
            line_no, snippet = matches[0]
            findings.append(
                Finding(
                    severity=severity,
                    scope=relative,
                    title=title,
                    details=f"{relative}:{line_no} → {snippet}",
                    recommendation=recommendation,
                )
            )
    return findings


def analyse_tasklist(ticket: Optional[str], slug_hint: Optional[str]) -> List[Finding]:
    tasklist_dir = ROOT_DIR / "docs" / "tasklist"
    candidates: List[Path] = []
    if ticket:
        candidate = tasklist_dir / f"{ticket}.md"
        if candidate.exists():
            candidates.append(candidate)
    else:
        candidates.extend(sorted(tasklist_dir.glob("*.md")))
    findings: List[Finding] = []
    for tasklist_path in candidates:
        try:
            lines = tasklist_path.read_text(encoding="utf-8").splitlines()
        except OSError:
            continue
        in_front_matter = False
        for idx, raw in enumerate(lines, start=1):
            stripped = raw.strip()
            if stripped == "---":
                in_front_matter = not in_front_matter
                continue
            if in_front_matter:
                continue
            if not stripped.startswith("- ["):
                continue
            if re.match(r"- \[[xX]\]", stripped):
                continue
            if "qa" not in stripped.lower():
                continue
            label = feature_label(ticket, slug_hint)
            findings.append(
                Finding(
                    severity="blocker",
                    scope="checklist",
                    title=f"Незакрыт QA пункт в {tasklist_path.relative_to(ROOT_DIR)}",
                    details=f"{tasklist_path.relative_to(ROOT_DIR)}:{idx} → {stripped}",
                    recommendation="Закройте QA задачи в чеклисте или перенесите их в backlog с обоснованием.",
                )
            )
    return findings


def analyse_tests_coverage(files: Sequence[str]) -> List[Finding]:
    main_changes = [f for f in files if f.startswith("src/main/")]
    test_changes = [f for f in files if f.startswith("src/test/") or f.startswith("tests/")]
    if not main_changes or test_changes:
        return []
    changed_preview = ", ".join(main_changes[:3])
    if len(main_changes) > 3:
        changed_preview += "…"
    return [
        Finding(
            severity="major",
            scope="tests",
            title="Нет обновлений тестов для изменённого кода",
            details=f"Изменены {len(main_changes)} файла(ов): {changed_preview}",
            recommendation="Добавьте или обновите тесты, либо зафиксируйте причину отсутствия покрывающих сценариев.",
        )
    ]


def load_tests_metadata() -> tuple[str, List[Dict], bool]:
    summary = (os.environ.get("QA_TESTS_SUMMARY") or "").strip().lower() or "not-run"
    allow_no_tests = (os.environ.get("QA_ALLOW_NO_TESTS") or "").strip() == "1"
    executed_raw = os.environ.get("QA_TESTS_EXECUTED") or ""
    executed: List[Dict] = []
    if executed_raw:
        try:
            parsed = json.loads(executed_raw)
            if isinstance(parsed, list):
                executed = parsed
        except json.JSONDecodeError:
            executed = []
    return summary, executed, allow_no_tests


def analyse_tests_run(summary: str, executed: List[Dict], allow_missing: bool) -> List[Finding]:
    findings: List[Finding] = []
    summary = summary.strip().lower() if summary else "not-run"
    if summary == "fail":
        log_hint = ""
        for entry in executed:
            if str(entry.get("status")).lower() == "fail":
                log_hint = entry.get("log") or entry.get("log_path") or ""
                break
        details = f"Лог: {log_hint}" if log_hint else ""
        findings.append(
            Finding(
                severity="blocker",
                scope="tests",
                title="Автотесты завершились с ошибкой",
                details=details,
                recommendation="Исправьте упавшие тесты и повторите запуск.",
            )
        )
    elif summary in {"not-run", "skipped"}:
        severity = "major" if allow_missing else "blocker"
        findings.append(
            Finding(
                severity=severity,
                scope="tests",
                title="Тесты не запускались",
                details="Автотесты не были выполнены на стадии QA.",
                recommendation="Запустите автотесты или укажите причину пропуска.",
            )
        )
    return findings


def aggregate_findings(
    files: Sequence[str],
    ticket: Optional[str],
    slug_hint: Optional[str],
    *,
    tests_summary: str,
    tests_executed: List[Dict],
    allow_missing_tests: bool,
) -> List[Finding]:
    findings: List[Finding] = []
    findings.extend(analyse_code_tokens(files))
    findings.extend(analyse_tasklist(ticket, slug_hint))
    findings.extend(analyse_tests_coverage(files))
    findings.extend(analyse_tests_run(tests_summary, tests_executed, allow_missing_tests))
    return findings


def summarise(findings: Sequence[Finding]) -> Tuple[str, dict, int, int]:
    counts = {severity: 0 for severity in SEVERITY_ORDER}
    for finding in findings:
        severity = finding.severity.lower()
        counts[severity] = counts.get(severity, 0) + 1

    blockers = counts.get("blocker", 0) + counts.get("critical", 0)
    warnings = counts.get("major", 0) + counts.get("minor", 0)

    parts: List[str] = []
    if blockers:
        parts.append(f"блокеров {blockers}")
    if warnings:
        parts.append(f"предупреждений {warnings}")
    if not parts:
        summary = "замечаний не найдено"
    else:
        summary = ", ".join(parts)
    summary = f"Итог: {summary}."

    status = "pass"
    if blockers:
        status = "fail"
    elif warnings:
        status = "warn"

    return summary, counts, blockers, warnings


def write_report(report_path: Path, payload: dict) -> None:
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> int:
    args = parse_args()
    ticket, slug_hint = detect_feature(args.ticket, args.slug_hint)
    branch = detect_branch(args.branch)
    files = collect_changed_files()
    tests_summary, tests_executed, allow_missing_tests = load_tests_metadata()
    findings = aggregate_findings(
        files,
        ticket,
        slug_hint,
        tests_summary=tests_summary,
        tests_executed=tests_executed,
        allow_missing_tests=allow_missing_tests,
    )

    summary, counts, blockers, warnings = summarise(findings)
    label = feature_label(ticket, slug_hint)
    generated_at = (
        dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    )

    payload = {
        "generated_at": generated_at,
        "status": "fail" if blockers else ("warn" if warnings else "pass"),
        "summary": summary,
        "ticket": ticket,
        "slug_hint": slug_hint,
        "branch": branch,
        "counts": counts,
        "files_considered": files,
        "findings": [finding.to_dict() for finding in findings],
        "tests_summary": tests_summary,
        "tests_executed": tests_executed,
        "inputs": {
            "diff_base": os.environ.get("QA_AGENT_DIFF_BASE") or None,
        },
    }

    if args.report:
        write_report(args.report, payload)

    if not args.gate or args.emit_json:
        if args.format == "json":
            print(json.dumps(payload, ensure_ascii=False, indent=2))
        else:
            print(summary)

    if args.gate:
        log_prefix = "[qa-agent]"
        context = f"{label}" if label else ""
        if context:
            print(f"{log_prefix} {summary} (feature: {context})", file=sys.stderr)
        else:
            print(f"{log_prefix} {summary}", file=sys.stderr)
        for finding in findings:
            severity = finding.severity.upper()
            scope = finding.scope or "-"
            print(f"{log_prefix} {severity} [{scope}] {finding.title}", file=sys.stderr)
            if finding.details:
                print(f"{log_prefix}   {finding.details}", file=sys.stderr)
            if finding.recommendation:
                print(f"{log_prefix}   → {finding.recommendation}", file=sys.stderr)

        blockers_set = {sev.strip().lower() for sev in args.block_on.split(",") if sev.strip()}
        warnings_set = {sev.strip().lower() for sev in args.warn_on.split(",") if sev.strip()}

        has_blockers = any(f.severity.lower() in blockers_set for f in findings)
        if has_blockers and not args.dry_run:
            return 1
        return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())
