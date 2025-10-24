from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from fnmatch import fnmatch
from pathlib import Path
from typing import Iterable, Optional


QUESTION_RE = re.compile(r"^\s*Вопрос\s+(\d+)\s*:", re.MULTILINE)
ANSWER_RE = re.compile(r"^\s*Ответ\s+(\d+)\s*:", re.MULTILINE)
STATUS_RE = re.compile(r"^\s*Status:\s*([A-Za-z]+)", re.MULTILINE)
DIALOG_HEADING = "## Диалог analyst"
OPEN_QUESTIONS_HEADING = "## 10. Открытые вопросы"
ALLOWED_STATUSES = {"READY", "BLOCKED", "PENDING"}


class AnalystValidationError(RuntimeError):
    """Raised when analyst dialog validation fails."""


@dataclass
class AnalystSettings:
    enabled: bool = True
    min_questions: int = 1
    require_ready: bool = True
    allow_blocked: bool = False
    check_open_questions: bool = True
    require_dialog_section: bool = True
    branches: Optional[list[str]] = None
    skip_branches: Optional[list[str]] = None


@dataclass
class AnalystCheckSummary:
    status: Optional[str]
    question_count: int
    answered_count: int


def _load_gates_config(root: Path) -> dict:
    config_path = root / "config" / "gates.json"
    if not config_path.exists():
        return {}
    try:
        return json.loads(config_path.read_text(encoding="utf-8"))
    except Exception as exc:  # pragma: no cover - defensive
        raise AnalystValidationError(f"не удалось прочитать {config_path}: {exc}")


def _normalize_patterns(raw: Iterable[str] | None) -> list[str] | None:
    if not raw:
        return None
    patterns: list[str] = []
    for item in raw:
        if isinstance(item, str) and item.strip():
            patterns.append(item.strip())
    return patterns or None


def load_settings(root: Path) -> AnalystSettings:
    config = _load_gates_config(root)
    raw = config.get("analyst") or {}
    settings = AnalystSettings()

    if isinstance(raw, dict):
        if "enabled" in raw:
            settings.enabled = bool(raw["enabled"])
        if "min_questions" in raw:
            try:
                settings.min_questions = max(int(raw["min_questions"]), 0)
            except (ValueError, TypeError):
                raise AnalystValidationError("config/gates.json: поле analyst.min_questions должно быть числом")
        if "require_ready" in raw:
            settings.require_ready = bool(raw["require_ready"])
        if "allow_blocked" in raw:
            settings.allow_blocked = bool(raw["allow_blocked"])
        if "check_open_questions" in raw:
            settings.check_open_questions = bool(raw["check_open_questions"])
        if "require_dialog_section" in raw:
            settings.require_dialog_section = bool(raw["require_dialog_section"])
        settings.branches = _normalize_patterns(raw.get("branches"))
        settings.skip_branches = _normalize_patterns(raw.get("skip_branches"))

    return settings


def _branch_enabled(branch: Optional[str], settings: AnalystSettings) -> bool:
    if not branch:
        return True
    if settings.skip_branches and any(fnmatch(branch, pattern) for pattern in settings.skip_branches):
        return False
    if settings.branches and not any(fnmatch(branch, pattern) for pattern in settings.branches):
        return False
    return True


def _extract_section(text: str, heading_prefix: str) -> str | None:
    lines = text.splitlines()
    start_idx: Optional[int] = None
    heading_lower = heading_prefix.strip().lower()
    for idx, raw in enumerate(lines):
        if raw.strip().lower().startswith(heading_lower):
            start_idx = idx + 1
            break
    if start_idx is None:
        return None
    end_idx = len(lines)
    for idx in range(start_idx, len(lines)):
        if lines[idx].startswith("## ") and idx != start_idx:
            end_idx = idx
            break
    return "\n".join(lines[start_idx:end_idx]).strip()


def _collect_numbers(pattern: re.Pattern[str], text: str) -> list[int]:
    numbers: list[int] = []
    seen = set()
    for match in pattern.finditer(text):
        try:
            num = int(match.group(1))
        except ValueError:
            continue
        numbers.append(num)
        seen.add(num)
    return numbers


def validate_prd(
    root: Path,
    ticket: str,
    *,
    settings: AnalystSettings,
    branch: Optional[str] = None,
    require_ready_override: Optional[bool] = None,
    allow_blocked_override: Optional[bool] = None,
    min_questions_override: Optional[int] = None,
) -> AnalystCheckSummary:
    if not settings.enabled or not _branch_enabled(branch, settings):
        return AnalystCheckSummary(status=None, question_count=0, answered_count=0)

    prd_path = root / "docs" / "prd" / f"{ticket}.prd.md"
    if not prd_path.exists():
        raise AnalystValidationError(f"BLOCK: нет PRD → запустите /idea-new {ticket}")

    text = prd_path.read_text(encoding="utf-8")
    dialog_section = _extract_section(text, DIALOG_HEADING)
    questions = _collect_numbers(QUESTION_RE, text)
    answers = _collect_numbers(ANSWER_RE, text)

    min_questions = settings.min_questions
    if min_questions_override is not None:
        min_questions = max(min_questions_override, 0)

    if settings.require_dialog_section and dialog_section is None:
        raise AnalystValidationError("BLOCK: PRD не содержит раздела `## Диалог analyst` → повторите /idea-new с уточнениями.")

    if min_questions and len(set(questions)) < min_questions:
        raise AnalystValidationError(
            f"BLOCK: analyst должен задать минимум {min_questions} вопрос(ов) в формате «Вопрос N: …»."
        )

    if questions:
        sorted_unique = sorted(set(questions))
        expected = list(range(1, sorted_unique[-1] + 1))
        if sorted_unique != expected:
            missing = [str(num) for num in expected if num not in sorted_unique]
            missing_repr = ", ".join(missing[:3])
            if len(missing) > 3:
                missing_repr += ", …"
            raise AnalystValidationError(
                f"BLOCK: нарушена последовательность нумерации вопросов (пропущены {missing_repr}). Перенумеруйте вопросы и ответы."
            )

    extra_answers = sorted(set(answers) - set(questions))
    if extra_answers:
        sample = ", ".join(str(num) for num in extra_answers[:3])
        if len(extra_answers) > 3:
            sample += ", …"
        raise AnalystValidationError(
            f"BLOCK: найдены ответы без соответствующих вопросов ({sample}). Согласуйте пары «Вопрос N»/«Ответ N»."
        )

    missing_answers = sorted(set(questions) - set(answers))
    if missing_answers:
        sample = ", ".join(str(num) for num in missing_answers[:3])
        if len(missing_answers) > 3:
            sample += ", …"
        raise AnalystValidationError(
            f"BLOCK: отсутствуют ответы для вопросов {sample}. Ответьте в формате «Ответ N: …» и повторите /idea-new {ticket}."
        )

    status_match = STATUS_RE.search(text)
    status = status_match.group(1).upper() if status_match else None
    if status is None:
        raise AnalystValidationError("BLOCK: в PRD отсутствует строка `Status:` → обновите раздел `## Диалог analyst`.")
    if status not in ALLOWED_STATUSES:
        raise AnalystValidationError(
            f"BLOCK: некорректное значение статуса (`{status}`), допустимо READY|BLOCKED|PENDING."
        )

    require_ready = settings.require_ready
    if require_ready_override is not None:
        require_ready = require_ready_override

    allow_blocked = settings.allow_blocked
    if allow_blocked_override is not None:
        allow_blocked = allow_blocked_override

    if require_ready and status != "READY":
        if status == "BLOCKED" and not allow_blocked:
            raise AnalystValidationError(
                f"BLOCK: PRD помечен Status: {status}. Ответьте на вопросы и доведите аналитический цикл до READY."
            )
        if status == "PENDING":
            raise AnalystValidationError("BLOCK: статус PENDING. Закройте вопросы и установите Status: READY.")

    if settings.check_open_questions and status == "READY":
        open_section = _extract_section(text, OPEN_QUESTIONS_HEADING)
        if open_section:
            for line in open_section.splitlines():
                stripped = line.strip()
                if not stripped:
                    continue
                if stripped.startswith("- [ ]"):
                    raise AnalystValidationError(
                        "BLOCK: статус READY, но раздел «Открытые вопросы» содержит незакрытые пункты."
                    )

    return AnalystCheckSummary(status=status, question_count=len(set(questions)), answered_count=len(set(answers)))


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Validate analyst dialog state for the active feature PRD.",
    )
    parser.add_argument("--ticket", "--slug", dest="ticket", required=True, help="Feature ticket to validate (legacy alias: --slug).")
    parser.add_argument(
        "--target",
        default=".",
        help="Project root (defaults to current working directory).",
    )
    parser.add_argument(
        "--branch",
        help="Current Git branch (used to evaluate branch/skip rules in config/gates.json).",
    )
    parser.add_argument(
        "--allow-blocked",
        action="store_true",
        help="Allow Status: BLOCKED without failing validation.",
    )
    parser.add_argument(
        "--no-ready-required",
        action="store_true",
        help="Do not enforce Status: READY; useful for diagnostics mid-dialog.",
    )
    parser.add_argument(
        "--min-questions",
        type=int,
        help="Override minimum number of questions expected from analyst.",
    )
    return parser


def main(argv: Optional[list[str]] = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    root = Path(args.target).resolve()
    settings = load_settings(root)
    try:
        summary = validate_prd(
            root,
            args.ticket,
            settings=settings,
            branch=args.branch,
            require_ready_override=False if args.no_ready_required else None,
            allow_blocked_override=True if args.allow_blocked else None,
            min_questions_override=args.min_questions,
        )
    except AnalystValidationError as exc:
        parser.exit(1, f"{exc}\n")
    if summary.status is None:
        print("analyst gate disabled — ничего проверять.")
    else:
        print(
            f"analyst dialog OK (status: {summary.status}, questions: {summary.question_count})"
        )
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
