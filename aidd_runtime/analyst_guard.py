from __future__ import annotations

import argparse
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional



try:
    from aidd_runtime._bootstrap import ensure_repo_root
except ImportError:  # pragma: no cover - direct script execution
    from _bootstrap import ensure_repo_root

ensure_repo_root(__file__)

from aidd_runtime import gates
from aidd_runtime.feature_ids import resolve_aidd_root

# Allow Markdown prefixes (headings/bullets/bold) so analyst output doesn't trip the gate.
QUESTION_RE = re.compile(
    r"^\s*(?:[#>*-]+\s*)?(?:\*\*)?(?:Вопрос|Question)\s+(\d+)\b[^:\n]*:(?:\*\*)?",
    re.MULTILINE | re.IGNORECASE,
)
COMPACT_ANSWER_RE = re.compile(r'\bQ(\d+)\s*=\s*(?:"([^"\n]+)"|([^\s;,#`]+))')
STATUS_RE = re.compile(r"^\s*Status:\s*([A-Za-z]+)", re.MULTILINE)
DIALOG_HEADING = "## Диалог analyst"
ANSWERS_HEADING = "## AIDD:ANSWERS"
AIDD_OPEN_QUESTIONS_HEADING = "## AIDD:OPEN_QUESTIONS"
Q_RE = re.compile(r"\bQ(\d+)\b")
NONE_VALUES = {"none", "нет", "n/a", "na"}
INVALID_ANSWER_VALUES = {"tbd", "todo", "none", "нет", "n/a", "na", "empty", "unknown", "-", "?"}
OPEN_ITEM_PREFIX_RE = re.compile(r"^(?:[-*+]\s+|\d+\.\s+)")
CHECKBOX_PREFIX_RE = re.compile(r"^\[[ xX]\]\s*")
ALLOWED_STATUSES = {"READY", "BLOCKED", "PENDING"}
RESEARCH_REF_TEMPLATE = "aidd/docs/research/{ticket}.md"
LEGACY_RESEARCH_REF_TEMPLATE = "docs/research/{ticket}.md"
MARKDOWN_HEADING_RE = re.compile(r"^\s{0,3}#{1,6}\s+\S")
HTML_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)
DIALOG_METADATA_PREFIXES = (
    "status:",
    "ссылка:",
    "ссылка на исследование:",
    "researcher:",
)


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


def load_settings(root: Path) -> AnalystSettings:
    try:
        config = gates.load_gates_config(root)
    except ValueError as exc:  # pragma: no cover - defensive
        raise AnalystValidationError(str(exc))
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
        settings.branches = gates.normalize_patterns(raw.get("branches"))
        settings.skip_branches = gates.normalize_patterns(raw.get("skip_branches"))

    return settings


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
        if idx != start_idx and MARKDOWN_HEADING_RE.match(lines[idx]) and not QUESTION_RE.match(lines[idx]):
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


def _collect_compact_answers(section: str) -> dict[int, str]:
    answers: dict[int, str] = {}
    for match in COMPACT_ANSWER_RE.finditer(section or ""):
        try:
            number = int(match.group(1))
        except ValueError:
            continue
        if number <= 0:
            continue
        value = str((match.group(2) if match.group(2) is not None else match.group(3)) or "").strip()
        if not value:
            continue
        answers[number] = value
    return answers


def _invalid_compact_answers(answers: dict[int, str]) -> list[int]:
    invalid: list[int] = []
    for number, value in answers.items():
        normalized = str(value).strip().lower()
        stripped = str(value).strip()
        if normalized in INVALID_ANSWER_VALUES:
            invalid.append(number)
            continue
        if stripped.startswith("<") and stripped.endswith(">"):
            invalid.append(number)
            continue
        if "<" in stripped or ">" in stripped:
            invalid.append(number)
    return sorted(set(invalid))


def _has_open_items(section: str) -> bool:
    for line in section.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith(">"):
            continue
        normalized = OPEN_ITEM_PREFIX_RE.sub("", stripped)
        normalized = CHECKBOX_PREFIX_RE.sub("", normalized).strip()
        if normalized.startswith("`") and normalized.endswith("`") and len(normalized) > 1:
            normalized = normalized[1:-1].strip()
        if normalized.startswith("**") and normalized.endswith("**") and len(normalized) > 3:
            normalized = normalized[2:-2].strip()
        if normalized.startswith("__") and normalized.endswith("__") and len(normalized) > 3:
            normalized = normalized[2:-2].strip()
        if normalized.lower() in NONE_VALUES:
            continue
        return True
    return False


def _collect_q_numbers(section: str) -> set[int]:
    numbers: set[int] = set()
    for line in section.splitlines():
        for match in Q_RE.finditer(line):
            try:
                numbers.add(int(match.group(1)))
            except ValueError:
                continue
    return numbers


def _strip_html_comments(text: str) -> str:
    return HTML_COMMENT_RE.sub("", text or "")


def _dialog_substantive_body(text: str) -> str:
    lines: list[str] = []
    for raw in _strip_html_comments(text).splitlines():
        stripped = raw.strip()
        if not stripped or stripped.startswith(">"):
            continue
        lowered = stripped.lower()
        if any(lowered.startswith(prefix) for prefix in DIALOG_METADATA_PREFIXES):
            continue
        lines.append(stripped)
    return "\n".join(lines).strip()


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
    if not settings.enabled or not gates.branch_enabled(branch, allow=settings.branches, skip=settings.skip_branches):
        return AnalystCheckSummary(status=None, question_count=0, answered_count=0)

    prd_path = root / "docs" / "prd" / f"{ticket}.prd.md"
    if not prd_path.exists():
        raise AnalystValidationError(f"BLOCK: нет PRD → запустите /feature-dev-aidd:idea-new {ticket}")

    text = prd_path.read_text(encoding="utf-8")
    dialog_section = _extract_section(text, DIALOG_HEADING)
    if settings.require_dialog_section and dialog_section is None:
        raise AnalystValidationError("BLOCK: PRD не содержит раздела `## Диалог analyst` → повторите /feature-dev-aidd:idea-new с уточнениями.")

    min_questions = settings.min_questions
    if min_questions_override is not None:
        min_questions = max(min_questions_override, 0)

    questions_source = dialog_section or text
    questions = _collect_numbers(QUESTION_RE, questions_source)
    if dialog_section is not None and not questions:
        dialog_body = _dialog_substantive_body(dialog_section)
        if not dialog_body:
            raise AnalystValidationError(
                f"BLOCK: в `## Диалог analyst` нет ни одного валидного вопроса (`Вопрос N` или transitional `Question N`). "
                f"Placeholder-комментарии не считаются вопросом. Повторите /feature-dev-aidd:idea-new {ticket} без ручного редактирования PRD."
            )
        raise AnalystValidationError(
            f"BLOCK: в `## Диалог analyst` нет ни одного валидного вопроса (`Вопрос N` или transitional `Question N`). "
            f"Используйте канонический persisted формат `Вопрос / Зачем / Варианты / Default` и повторите /feature-dev-aidd:idea-new {ticket}."
        )

    if min_questions and len(set(questions)) < min_questions:
        raise AnalystValidationError(
            f"BLOCK: analyst должен задать минимум {min_questions} вопрос(ов) в формате «Вопрос N: …» "
            f"(transitional read-path also accepts `Question N: ...`)."
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

    answers_section = _extract_section(text, ANSWERS_HEADING)
    answers_source = answers_section or ""
    answers_map = _collect_compact_answers(answers_source)
    if answers_source.strip() and not answers_map:
        raise AnalystValidationError(
            "BLOCK: AIDD:ANSWERS должен быть в compact формате `Q<N>=<value>`."
        )
    invalid_compact = _invalid_compact_answers(answers_map)
    if invalid_compact:
        sample = ", ".join(f"Q{num}" for num in invalid_compact[:3])
        if len(invalid_compact) > 3:
            sample = f"{sample}, …"
        raise AnalystValidationError(
            f"BLOCK: ответы {sample} содержат недопустимое значение (TBD/TODO/empty). "
            "Используйте `Q<N>=...` или `Q<N>=\"короткий текст\"`."
        )

    status_match = STATUS_RE.search(text)
    status = status_match.group(1).upper() if status_match else None
    aidd_open_section = _extract_section(text, AIDD_OPEN_QUESTIONS_HEADING)
    if settings.check_open_questions and aidd_open_section:
        q_numbers = _collect_q_numbers(aidd_open_section)
        if q_numbers:
            question_numbers = set(questions)
            answer_numbers = set(answers_map)
            missing_q = sorted(q_numbers - question_numbers)
            if missing_q:
                sample = ", ".join(f"Q{num}" for num in missing_q[:3])
                if len(missing_q) > 3:
                    sample = f"{sample}..."
                raise AnalystValidationError(
                    f"BLOCK: AIDD:OPEN_QUESTIONS содержит {sample}, но нет соответствующих `Вопрос N`/`Question N`."
                )
            missing_answer = sorted(q_numbers - answer_numbers)
            if missing_answer:
                sample = ", ".join(f"Q{num}" for num in missing_answer[:3])
                if len(missing_answer) > 3:
                    sample = f"{sample}..."
                raise AnalystValidationError(
                    f"BLOCK: AIDD:OPEN_QUESTIONS содержит {sample}, но нет соответствующих ответов в `AIDD:ANSWERS QN=<value>`."
                )

    if settings.check_open_questions and status == "READY":
        if aidd_open_section and _has_open_items(aidd_open_section):
            raise AnalystValidationError(
                "BLOCK: статус READY, но AIDD:OPEN_QUESTIONS содержит незакрытые пункты."
            )

    missing_answers = sorted(set(questions) - set(answers_map))
    if missing_answers:
        sample = ", ".join(str(num) for num in missing_answers[:3])
        if len(missing_answers) > 3:
            sample += ", …"
        raise AnalystValidationError(
            f"BLOCK: отсутствуют ответы для вопросов {sample}. "
            f"Заполните `AIDD:ANSWERS` в compact формате `Q<N>=<value>` и повторите /feature-dev-aidd:idea-new {ticket}."
        )

    extra_answers = sorted(set(answers_map) - set(questions))
    if extra_answers:
        sample = ", ".join(str(num) for num in extra_answers[:3])
        if len(extra_answers) > 3:
            sample += ", …"
        raise AnalystValidationError(
            f"BLOCK: найдены ответы без соответствующих вопросов ({sample}). "
            "Согласуйте пары `Вопрос N`/`Question N` и `AIDD:ANSWERS QN=<value>`."
        )

    if status is None:
        raise AnalystValidationError("BLOCK: в PRD отсутствует строка `Status:` → обновите раздел `## Диалог analyst`.")
    if status == "DRAFT":
        raise AnalystValidationError(
            "BLOCK: PRD в статусе draft. Заполните диалог analyst и обновите Status: READY перед запуском analyst-check."
        )
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

    research_ref = RESEARCH_REF_TEMPLATE.format(ticket=ticket)
    legacy_ref = LEGACY_RESEARCH_REF_TEMPLATE.format(ticket=ticket)
    if research_ref not in text and legacy_ref not in text:
        raise AnalystValidationError(
            f"BLOCK: PRD должен ссылаться на `{research_ref}` в разделе `## Диалог analyst` → добавьте ссылку на отчёт Researcher."
        )

    return AnalystCheckSummary(status=status, question_count=len(set(questions)), answered_count=len(set(answers_map)))


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Validate analyst dialog state for the active feature PRD.",
    )
    parser.add_argument("--ticket", "--slug", dest="ticket", required=True, help="Feature ticket to validate (alias: --slug).")
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
    root = resolve_aidd_root(Path.cwd())
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
