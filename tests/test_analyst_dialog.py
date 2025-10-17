import sys
from pathlib import Path

SRC_ROOT = Path(__file__).resolve().parents[1] / "src"
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

from claude_workflow_cli.tools.analyst_guard import (
    AnalystValidationError,
    load_settings,
    validate_prd,
)

from .helpers import ensure_gates_config, write_file


def _write_prd(root, slug, body):
    return write_file(root, f"docs/prd/{slug}.prd.md", body)


def test_validate_prd_passes_when_ready(tmp_path):
    ensure_gates_config(tmp_path)
    slug = "demo"
    prd = """# PRD\n\n## Диалог analyst\nStatus: READY\n\nВопрос 1: Какие этапы checkout нужно покрыть?\nОтвет 1: Используем happy-path и неуспешную оплату.\n\n## 1. Обзор\n- **Название продукта/фичи**: Demo\n\n## 10. Открытые вопросы\n- [x] Все уточнения закрыты\n"""
    _write_prd(tmp_path, slug, prd)
    settings = load_settings(tmp_path)

    summary = validate_prd(tmp_path, slug, settings=settings)

    assert summary.status == "READY"
    assert summary.question_count == 1
    assert summary.answered_count == 1


def test_missing_answer_blocks_validation(tmp_path):
    ensure_gates_config(tmp_path)
    slug = "demo"
    prd = """# PRD\n\n## Диалог analyst\nStatus: BLOCKED\n\nВопрос 1: Что уточнить?\n\n## 1. Обзор\n- **Название продукта/фичи**: Demo\n\n## 10. Открытые вопросы\n- [ ] Уточнить детали\n"""
    _write_prd(tmp_path, slug, prd)
    settings = load_settings(tmp_path)

    with pytest.raises(AnalystValidationError) as excinfo:
        validate_prd(tmp_path, slug, settings=settings)

    assert "отсутствуют ответы" in str(excinfo.value)


def test_ready_status_with_open_questions_fails(tmp_path):
    ensure_gates_config(tmp_path)
    slug = "demo"
    prd = """# PRD\n\n## Диалог analyst\nStatus: READY\n\nВопрос 1: Что уточнить?\nОтвет 1: Ответ получен.\n\n## 1. Обзор\n- **Название продукта/фичи**: Demo\n\n## 10. Открытые вопросы\n- [ ] Остаётся блокер\n"""
    _write_prd(tmp_path, slug, prd)
    settings = load_settings(tmp_path)

    with pytest.raises(AnalystValidationError) as excinfo:
        validate_prd(tmp_path, slug, settings=settings)

    assert "Открытые вопросы" in str(excinfo.value)


def test_validation_skipped_when_disabled(tmp_path):
    ensure_gates_config(tmp_path, {"analyst": {"enabled": False}})
    slug = "demo"
    prd = """# PRD\n\n## Диалог analyst\nStatus: BLOCKED\n\nВопрос 1: Что уточнить?\n\n## 1. Обзор\n- **Название продукта/фичи**: Demo\n"""
    _write_prd(tmp_path, slug, prd)
    settings = load_settings(tmp_path)

    summary = validate_prd(tmp_path, slug, settings=settings)

    assert summary.status is None
    assert summary.question_count == 0
