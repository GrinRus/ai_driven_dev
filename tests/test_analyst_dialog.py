import inspect
import sys
import tempfile
import unittest
from pathlib import Path

from tests.helpers import REPO_ROOT

SRC_ROOT = REPO_ROOT
if str(SRC_ROOT) not in sys.path:  # pragma: no cover - test environment setup
    sys.path.insert(0, str(SRC_ROOT))

try:
    import pytest
except ModuleNotFoundError:  # pragma: no cover - fallback for unittest environments
    class _RaisesContext:
        def __init__(self, expected_exception):
            self._expected = expected_exception
            self.value = None

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_value, traceback):
            if exc_type is None:
                message = f"Did not raise {self._expected!r}"
                raise AssertionError(message)
            if not issubclass(exc_type, self._expected):
                return False
            self.value = exc_value
            return True

    class _PytestStub:
        @staticmethod
        def raises(expected_exception):
            return _RaisesContext(expected_exception)

    pytest = _PytestStub()

from aidd_runtime.analyst_guard import (
    AnalystValidationError,
    load_settings,
    validate_prd,
)

from .helpers import ensure_gates_config, write_file


def _write_prd(root, slug, body):
    return write_file(root, f"docs/prd/{slug}.prd.md", body)


def _write_research(root, slug, status="reviewed"):
    payload = f"# Research\n\nStatus: {status}\n"
    return write_file(root, f"docs/research/{slug}.md", payload)


def test_validate_prd_passes_when_ready(tmp_path):
    project = tmp_path / "aidd"
    project.mkdir(parents=True, exist_ok=True)
    ensure_gates_config(project)
    slug = "demo"
    prd = """# PRD\n\n## Диалог analyst\nStatus: READY\nСсылка: docs/research/demo.md\n\nВопрос 1: Какие этапы checkout нужно покрыть?\n\n## AIDD:ANSWERS\nAIDD:ANSWERS Q1=C\n\n## AIDD:OPEN_QUESTIONS\n- none\n\n## 1. Обзор\n- **Название продукта/фичи**: Demo\n\n## 10. Открытые вопросы\n- [x] Все уточнения закрыты\n"""
    _write_prd(project, slug, prd)
    _write_research(project, slug)
    settings = load_settings(project)

    summary = validate_prd(project, slug, settings=settings)

    assert summary.status == "READY"
    assert summary.question_count == 1
    assert summary.answered_count == 1


def test_validate_prd_allows_missing_research_doc(tmp_path):
    project = tmp_path / "aidd"
    project.mkdir(parents=True, exist_ok=True)
    ensure_gates_config(project)
    slug = "demo"
    prd = """# PRD\n\n## Диалог analyst\nStatus: READY\nСсылка: docs/research/demo.md\n\nВопрос 1: Какие этапы checkout нужно покрыть?\n\n## AIDD:ANSWERS\nAIDD:ANSWERS Q1=C\n\n## AIDD:OPEN_QUESTIONS\n- none\n\n## 1. Обзор\n- **Название продукта/фичи**: Demo\n\n## 10. Открытые вопросы\n- [x] Все уточнения закрыты\n"""
    _write_prd(project, slug, prd)
    settings = load_settings(project)

    summary = validate_prd(project, slug, settings=settings)

    assert summary.status == "READY"
    assert summary.question_count == 1
    assert summary.answered_count == 1


def test_markdown_questions_allowed(tmp_path):
    project = tmp_path / "aidd"
    project.mkdir(parents=True, exist_ok=True)
    ensure_gates_config(project)
    slug = "demo"
    prd = """# PRD\n\n## Диалог analyst\nStatus: READY\nСсылка: docs/research/demo.md\n\n### **Вопрос 1 (Blocker):** Что уточнить?\n\n## AIDD:ANSWERS\nAIDD:ANSWERS Q1=B\n\n## AIDD:OPEN_QUESTIONS\n- none\n\n## 1. Обзор\n- **Название продукта/фичи**: Demo\n\n## 10. Открытые вопросы\n- [x] Все уточнения закрыты\n"""
    _write_prd(project, slug, prd)
    _write_research(project, slug)
    settings = load_settings(project)

    summary = validate_prd(project, slug, settings=settings)

    assert summary.status == "READY"
    assert summary.question_count == 1
    assert summary.answered_count == 1


def test_english_question_markers_are_accepted_on_read_path(tmp_path):
    project = tmp_path / "aidd"
    project.mkdir(parents=True, exist_ok=True)
    ensure_gates_config(project)
    slug = "demo"
    prd = """# PRD\n\n## Диалог analyst\nStatus: READY\nСсылка: docs/research/demo.md\n\nQuestion 1 (Blocker): What needs clarification?\nWhy: This changes the API boundary.\nOptions: A) Keep REST B) Switch to websocket\nDefault: A\n\n## AIDD:ANSWERS\nAIDD:ANSWERS Q1=A\n\n## AIDD:OPEN_QUESTIONS\n- none\n\n## 1. Обзор\n- **Название продукта/фичи**: Demo\n"""
    _write_prd(project, slug, prd)
    _write_research(project, slug)
    settings = load_settings(project)

    summary = validate_prd(project, slug, settings=settings)

    assert summary.status == "READY"
    assert summary.question_count == 1
    assert summary.answered_count == 1


def test_compact_answers_allow_quoted_short_text(tmp_path):
    project = tmp_path / "aidd"
    project.mkdir(parents=True, exist_ok=True)
    ensure_gates_config(project)
    slug = "demo"
    prd = """# PRD\n\n## Диалог analyst\nStatus: READY\nСсылка: docs/research/demo.md\n\nВопрос 1: Что уточнить?\n\n## AIDD:ANSWERS\nAIDD:ANSWERS Q1="нужен режим без кэша"\n\n## AIDD:OPEN_QUESTIONS\n- none\n"""
    _write_prd(project, slug, prd)
    _write_research(project, slug)
    settings = load_settings(project)

    summary = validate_prd(project, slug, settings=settings)

    assert summary.status == "READY"
    assert summary.question_count == 1
    assert summary.answered_count == 1


def test_compact_answers_allow_quoted_q2_text(tmp_path):
    project = tmp_path / "aidd"
    project.mkdir(parents=True, exist_ok=True)
    ensure_gates_config(project)
    slug = "demo"
    prd = """# PRD\n\n## Диалог analyst\nStatus: READY\nСсылка: docs/research/demo.md\n\nВопрос 1: Что уточнить?\nВопрос 2: Что нужно дополнительно?\n\n## AIDD:ANSWERS\nAIDD:ANSWERS Q1=A; Q2="нужен режим без кэша"\n\n## AIDD:OPEN_QUESTIONS\n- none\n"""
    _write_prd(project, slug, prd)
    _write_research(project, slug)
    settings = load_settings(project)

    summary = validate_prd(project, slug, settings=settings)

    assert summary.status == "READY"
    assert summary.question_count == 2
    assert summary.answered_count == 2


def test_missing_answer_blocks_validation(tmp_path):
    project = tmp_path / "aidd"
    project.mkdir(parents=True, exist_ok=True)
    ensure_gates_config(project)
    slug = "demo"
    prd = """# PRD\n\n## Диалог analyst\nStatus: BLOCKED\nСсылка: docs/research/demo.md\n\nВопрос 1: Что уточнить?\n\n## 1. Обзор\n- **Название продукта/фичи**: Demo\n\n## 10. Открытые вопросы\n- [ ] Уточнить детали\n"""
    _write_prd(project, slug, prd)
    _write_research(project, slug, status="pending")
    settings = load_settings(project)

    with pytest.raises(AnalystValidationError) as excinfo:
        validate_prd(project, slug, settings=settings)

    assert "отсутствуют ответы" in str(excinfo.value)


def test_aidd_answers_section_satisfies_missing_dialog_answer(tmp_path):
    project = tmp_path / "aidd"
    project.mkdir(parents=True, exist_ok=True)
    ensure_gates_config(project)
    slug = "demo"
    prd = """# PRD\n\n## Диалог analyst\nStatus: READY\nСсылка: docs/research/demo.md\n\nВопрос 1: Что уточнить?\n\n## AIDD:ANSWERS\nAIDD:ANSWERS Q1=A\n\n## AIDD:OPEN_QUESTIONS\n- none\n\n## 1. Обзор\n- **Название продукта/фичи**: Demo\n\n## 10. Открытые вопросы\n- [x] Все уточнения закрыты\n"""
    _write_prd(project, slug, prd)
    _write_research(project, slug)
    settings = load_settings(project)

    summary = validate_prd(project, slug, settings=settings)

    assert summary.status == "READY"
    assert summary.question_count == 1
    assert summary.answered_count == 1


def test_aidd_answers_missing_blocks_validation(tmp_path):
    project = tmp_path / "aidd"
    project.mkdir(parents=True, exist_ok=True)
    ensure_gates_config(project)
    slug = "demo"
    prd = """# PRD\n\n## Диалог analyst\nStatus: BLOCKED\nСсылка: docs/research/demo.md\n\nВопрос 1: Что уточнить?\n\n## AIDD:ANSWERS\nAIDD:ANSWERS Q2=B\n\n## 1. Обзор\n- **Название продукта/фичи**: Demo\n"""
    _write_prd(project, slug, prd)
    _write_research(project, slug, status="pending")
    settings = load_settings(project)

    with pytest.raises(AnalystValidationError) as excinfo:
        validate_prd(project, slug, settings=settings)

    assert "отсутствуют ответы" in str(excinfo.value)


def test_ready_status_ignores_narrative_open_questions_section(tmp_path):
    project = tmp_path / "aidd"
    project.mkdir(parents=True, exist_ok=True)
    ensure_gates_config(project)
    slug = "demo"
    prd = """# PRD\n\n## Диалог analyst\nStatus: READY\nСсылка: docs/research/demo.md\n\nВопрос 1: Что уточнить?\n\n## AIDD:ANSWERS\nAIDD:ANSWERS Q1=A\n\n## AIDD:OPEN_QUESTIONS\n- none\n\n## 1. Обзор\n- **Название продукта/фичи**: Demo\n\n## 10. Открытые вопросы\n- [ ] Остаётся блокер\n"""
    _write_prd(project, slug, prd)
    _write_research(project, slug)
    settings = load_settings(project)

    summary = validate_prd(project, slug, settings=settings)
    assert summary.status == "READY"


def test_ready_status_with_aidd_open_questions_fails(tmp_path):
    project = tmp_path / "aidd"
    project.mkdir(parents=True, exist_ok=True)
    ensure_gates_config(project)
    slug = "demo"
    prd = """# PRD\n\n## Диалог analyst\nStatus: READY\nСсылка: docs/research/demo.md\n\nВопрос 1: Что уточнить?\n\n## AIDD:ANSWERS\nAIDD:ANSWERS Q1=B\n\n## AIDD:OPEN_QUESTIONS\n- Q1: Остаётся блокер → Analyst → 2026-01-01\n\n## 1. Обзор\n- **Название продукта/фичи**: Demo\n"""
    _write_prd(project, slug, prd)
    _write_research(project, slug)
    settings = load_settings(project)

    with pytest.raises(AnalystValidationError) as excinfo:
        validate_prd(project, slug, settings=settings)

    assert "AIDD:OPEN_QUESTIONS" in str(excinfo.value)


def test_ready_allows_aidd_open_questions_none(tmp_path):
    project = tmp_path / "aidd"
    project.mkdir(parents=True, exist_ok=True)
    ensure_gates_config(project)
    slug = "demo"
    prd = """# PRD\n\n## Диалог analyst\nStatus: READY\nСсылка: docs/research/demo.md\n\nВопрос 1: Что уточнить?\n\n## AIDD:ANSWERS\nAIDD:ANSWERS Q1=C\n\n## AIDD:OPEN_QUESTIONS\n- `none`\n\n## 1. Обзор\n- **Название продукта/фичи**: Demo\n"""
    _write_prd(project, slug, prd)
    _write_research(project, slug)
    settings = load_settings(project)

    summary = validate_prd(project, slug, settings=settings)

    assert summary.status == "READY"


def test_open_questions_q_requires_matching_question(tmp_path):
    project = tmp_path / "aidd"
    project.mkdir(parents=True, exist_ok=True)
    ensure_gates_config(project)
    slug = "demo"
    prd = """# PRD\n\n## Диалог analyst\nStatus: READY\nСсылка: docs/research/demo.md\n\nВопрос 1: Что уточнить?\n\n## AIDD:OPEN_QUESTIONS\n- Q2: Другой вопрос → Analyst → 2026-01-01\n\n## AIDD:ANSWERS\nAIDD:ANSWERS Q1=A; Q2=B\n\n## 1. Обзор\n- **Название продукта/фичи**: Demo\n"""
    _write_prd(project, slug, prd)
    _write_research(project, slug)
    settings = load_settings(project)

    with pytest.raises(AnalystValidationError) as excinfo:
        validate_prd(project, slug, settings=settings)

    assert "Q2" in str(excinfo.value)


def test_open_questions_q_blocks_when_blocked(tmp_path):
    project = tmp_path / "aidd"
    project.mkdir(parents=True, exist_ok=True)
    ensure_gates_config(project)
    slug = "demo"
    prd = """# PRD\n\n## Диалог analyst\nStatus: BLOCKED\nСсылка: docs/research/demo.md\n\nВопрос 1: Что уточнить?\n\n## AIDD:OPEN_QUESTIONS\n- Q2: Другой вопрос → Analyst → 2026-01-01\n\n## AIDD:ANSWERS\nAIDD:ANSWERS Q1=A\n\n## 1. Обзор\n- **Название продукта/фичи**: Demo\n"""
    _write_prd(project, slug, prd)
    _write_research(project, slug)
    settings = load_settings(project)

    with pytest.raises(AnalystValidationError) as excinfo:
        validate_prd(project, slug, settings=settings)

    assert "Q2" in str(excinfo.value)


def test_open_questions_q_requires_matching_answer(tmp_path):
    project = tmp_path / "aidd"
    project.mkdir(parents=True, exist_ok=True)
    ensure_gates_config(project)
    slug = "demo"
    prd = """# PRD\n\n## Диалог analyst\nStatus: READY\nСсылка: docs/research/demo.md\n\nВопрос 1: Что уточнить?\nВопрос 2: Другой вопрос?\n\n## AIDD:OPEN_QUESTIONS\n- Q2: Другой вопрос → Analyst → 2026-01-01\n\n## AIDD:ANSWERS\nAIDD:ANSWERS Q1=A\n\n## 1. Обзор\n- **Название продукта/фичи**: Demo\n"""
    _write_prd(project, slug, prd)
    _write_research(project, slug)
    settings = load_settings(project)

    with pytest.raises(AnalystValidationError) as excinfo:
        validate_prd(project, slug, settings=settings)

    assert "Q2" in str(excinfo.value)


def test_draft_status_rejected(tmp_path):
    project = tmp_path / "aidd"
    project.mkdir(parents=True, exist_ok=True)
    ensure_gates_config(project)
    slug = "demo"
    prd = """# PRD\n\n## Диалог analyst\nStatus: draft\nСсылка: docs/research/demo.md\n\nВопрос 1: Что уточнить?\n\n## AIDD:ANSWERS\nAIDD:ANSWERS Q1=A\n"""
    _write_prd(project, slug, prd)
    _write_research(project, slug, status="pending")
    settings = load_settings(project)

    with pytest.raises(AnalystValidationError) as excinfo:
        validate_prd(project, slug, settings=settings)

    assert "draft" in str(excinfo.value).lower()


def test_non_compact_answers_payload_is_rejected(tmp_path):
    project = tmp_path / "aidd"
    project.mkdir(parents=True, exist_ok=True)
    ensure_gates_config(project)
    slug = "demo"
    prd = """# PRD\n\n## Диалог analyst\nStatus: READY\nСсылка: docs/research/demo.md\n\nВопрос 1: Что уточнить?\n\n## AIDD:ANSWERS\n- свободный ответ вне compact формата\n"""
    _write_prd(project, slug, prd)
    _write_research(project, slug)
    settings = load_settings(project)

    with pytest.raises(AnalystValidationError) as excinfo:
        validate_prd(project, slug, settings=settings)

    assert "должен быть в compact формате" in str(excinfo.value)


def test_placeholder_comment_is_rejected_before_answers_format_check(tmp_path):
    project = tmp_path / "aidd"
    project.mkdir(parents=True, exist_ok=True)
    ensure_gates_config(project)
    slug = "demo"
    prd = """# PRD\n\nStatus: BLOCKED\n\n## Диалог analyst\nСсылка: docs/research/demo.md\n\n<!-- Analyst will populate questions here after reviewing context -->\n\n## AIDD:ANSWERS\n> Единый формат ответов из чата.\n> Используй только compact формат.\n"""
    _write_prd(project, slug, prd)
    _write_research(project, slug)
    settings = load_settings(project)

    with pytest.raises(AnalystValidationError) as excinfo:
        validate_prd(project, slug, settings=settings)

    assert "нет ни одного валидного вопроса" in str(excinfo.value)
    assert "compact формате" not in str(excinfo.value)


def test_placeholder_comment_with_dialog_metadata_uses_placeholder_failure(tmp_path):
    project = tmp_path / "aidd"
    project.mkdir(parents=True, exist_ok=True)
    ensure_gates_config(project)
    slug = "demo"
    prd = """# PRD\n\n## Диалог analyst\nStatus: BLOCKED\nСсылка на исследование: `aidd/docs/research/demo.md`\n\n> Этот раздел создаётся автоматически после idea-new.\n\n<!-- Analyst will populate questions here after reviewing context -->\n\n## AIDD:ANSWERS\n> Единый формат ответов из чата.\n"""
    _write_prd(project, slug, prd)
    _write_research(project, slug)
    settings = load_settings(project)

    with pytest.raises(AnalystValidationError) as excinfo:
        validate_prd(project, slug, settings=settings)

    assert "Placeholder-комментарии не считаются вопросом" in str(excinfo.value)
    assert "compact формате" not in str(excinfo.value)


def test_compact_answers_with_tbd_are_rejected(tmp_path):
    project = tmp_path / "aidd"
    project.mkdir(parents=True, exist_ok=True)
    ensure_gates_config(project)
    slug = "demo"
    prd = """# PRD\n\n## Диалог analyst\nStatus: READY\nСсылка: docs/research/demo.md\n\nВопрос 1: Что уточнить?\n\n## AIDD:ANSWERS\nAIDD:ANSWERS Q1=TBD\n"""
    _write_prd(project, slug, prd)
    _write_research(project, slug)
    settings = load_settings(project)

    with pytest.raises(AnalystValidationError) as excinfo:
        validate_prd(project, slug, settings=settings)

    assert "недопустимое значение" in str(excinfo.value)


def test_compact_answers_with_placeholder_are_rejected(tmp_path):
    project = tmp_path / "aidd"
    project.mkdir(parents=True, exist_ok=True)
    ensure_gates_config(project)
    slug = "demo"
    prd = """# PRD\n\n## Диалог analyst\nStatus: READY\nСсылка: docs/research/demo.md\n\nВопрос 1: Что уточнить?\n\n## AIDD:ANSWERS\nAIDD:ANSWERS Q1=<указать позже>\n"""
    _write_prd(project, slug, prd)
    _write_research(project, slug)
    settings = load_settings(project)

    with pytest.raises(AnalystValidationError) as excinfo:
        validate_prd(project, slug, settings=settings)

    assert "недопустимое значение" in str(excinfo.value)


def test_validation_skipped_when_disabled(tmp_path):
    project = tmp_path / "aidd"
    project.mkdir(parents=True, exist_ok=True)
    ensure_gates_config(project, {"analyst": {"enabled": False}})
    slug = "demo"
    prd = """# PRD\n\n## Диалог analyst\nStatus: BLOCKED\nСсылка: docs/research/demo.md\n\nВопрос 1: Что уточнить?\n\n## 1. Обзор\n- **Название продукта/фичи**: Demo\n"""
    _write_prd(project, slug, prd)
    _write_research(project, slug, status="pending")
    settings = load_settings(project)

    summary = validate_prd(project, slug, settings=settings)

    assert summary.status is None
    assert summary.question_count == 0


def _wrap_tmp_path(func):
    def _wrapped():
        with tempfile.TemporaryDirectory() as tmp_dir:
            return func(Path(tmp_dir))

    return _wrapped


def load_tests(loader, tests, pattern):  # pragma: no cover - unittest discovery hook
    suite = unittest.TestSuite()
    for name, func in sorted(globals().items()):
        if not name.startswith("test_") or not callable(func):
            continue
        params = len(inspect.signature(func).parameters)
        if params == 1:
            suite.addTest(unittest.FunctionTestCase(_wrap_tmp_path(func)))
        else:
            suite.addTest(unittest.FunctionTestCase(func))
    return suite
