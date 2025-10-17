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
from typing import Iterable, List, Optional, Sequence, Set, Tuple

ROOT_DIR = Path.cwd()
DEFAULT_BLOCKERS = ("blocker", "critical")
DEFAULT_WARNINGS = ("major", "minor")
SEVERITY_ORDER = ["blocker", "critical", "major", "minor", "info"]


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
    parser.add_argument("--slug", help="Active feature slug. Autodetected from docs/.active_feature when omitted.")
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


def detect_slug(explicit: Optional[str]) -> Optional[str]:
    if explicit:
        return explicit.strip() or None
    slug_path = ROOT_DIR / "docs" / ".active_feature"
    if not slug_path.exists():
        return None
    try:
        value = slug_path.read_text(encoding="utf-8").strip()
    except OSError:
        return None
    return value or None


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


def analyse_tasklist(slug: Optional[str]) -> List[Finding]:
    tasklist_dir = ROOT_DIR / "docs" / "tasklist"
    candidates: List[Path] = []
    if slug:
        candidate = tasklist_dir / f"{slug}.md"
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


def aggregate_findings(files: Sequence[str], slug: Optional[str]) -> List[Finding]:
    findings: List[Finding] = []
    findings.extend(analyse_code_tokens(files))
    findings.extend(analyse_tasklist(slug))
    findings.extend(analyse_tests_coverage(files))
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
    slug = detect_slug(args.slug)
    branch = detect_branch(args.branch)
    files = collect_changed_files()
    findings = aggregate_findings(files, slug)

    summary, counts, blockers, warnings = summarise(findings)

    payload = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "status": "fail" if blockers else ("warn" if warnings else "pass"),
        "summary": summary,
        "slug": slug,
        "branch": branch,
        "counts": counts,
        "files_considered": files,
        "findings": [finding.to_dict() for finding in findings],
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
