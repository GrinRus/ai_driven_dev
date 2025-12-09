# Prompt Versioning & Localization

Этот документ описывает правила двуязычных промптов, хранение версий и инструменты синхронизации.

## 1. Цели
- RU — исходная локаль (рабочий язык команды), EN — синхронизированный перевод.
- Любое изменение промпта сопровождается повышением `prompt_version` (semver) и обновлением обеих локалей.
- Гейты/линтеры блокируют ситуации, когда изменена только одна локаль.

## 2. Структура директорий
- RU-файлы используются рантаймом Claude: `.claude/agents/*.md`, `.claude/commands/*.md`.
- EN-файлы живут в `prompts/en/agents/*.md` и `prompts/en/commands/*.md`.
- Оба варианта используют одинаковую структуру (см. `aidd/docs/prompt-playbook.md`), но заголовки переведены (`Контекст` → `Context` и т.д.).

## 3. Поля версий
- `prompt_version`: semver (`MAJOR.MINOR.PATCH`).
  - `major` — изменена структура секций или поведение агента.
  - `minor` — новые инструкции/блоки без изменения контракта.
  - `patch` — формулировки, правки текста, уточнения примеров.
- `source_version`:
  - Для RU всегда равен `prompt_version` (исходный текст).
  - Для EN указывает, на основе какой RU-версии сделан перевод; линтер требует `source_version == RU prompt_version`.
- `Lang-Parity: skip` — допускается только для редких временных файлов (например, одноязычные драфты). Добавляйте поле в обе локали и удаляйте после синхронизации.

## 4. Рабочий процесс
1. Изменили RU-промпт → запустите `scripts/prompt-version bump --prompts <name> --kind agent|command --lang ru,en --part <major|minor|patch>` (или обновите вручную, если обе локали меняются одновременно).
2. Обновите EN-файл (перевод, ссылки, примеры).
3. Сравните отличия через `tools/prompt_diff.py --kind agent --name <name>`.
4. Запустите `python3 scripts/lint-prompts.py` — убедитесь, что секции, версии и пары совпадают.
5. При необходимости упомяните изменения в release notes/CHANGELOG.

## 5. Инструменты
- `scripts/lint-prompts.py` — валидирует фронт-маттер, обязательные секции, пары агент↔команда и RU↔EN.
- `tools/prompt_diff.py --kind command --name plan-new` — быстрый diff между локалями.
- `scripts/prompt-version bump --prompts analyst --kind agent --lang ru,en --part minor` — повышает версии и обновляет `source_version`. Используйте `--dry-run` для проверки.
- `scripts/prompt-version` интегрирован в `scripts/ci-lint.sh` (dry-run) и `gate-workflow` вызывает `lint-prompts`, поэтому несогласованные локали блокируют commit.

## 6. Release checklist
- Перед релизом убедитесь, что все правки промптов имеют согласованные версии:
  - `python3 scripts/prompt-version bump --lang ru,en --prompts <список> --part patch --dry-run`
  - `python3 scripts/lint-prompts.py`
  - `python3 tools/prompt_diff.py --kind agent --name <name>` (по необходимости)
- Зафиксируйте изменения в `aidd/docs/release-notes.md` и `CHANGELOG.md`.

Соблюдайте эти правила, чтобы RU и EN инструкции оставались синхронными и понятными как русскоязычной, так и англоязычной команде.

## 7. Автоматизация (prompt-release)
- Используйте `scripts/prompt-release.sh`, чтобы единой командой выполнить:
  1. `scripts/prompt-version bump --prompts all --kind both --lang ru,en --part <…>` (с `--dry-run`, если нужно только проверить).
  2. `scripts/lint-prompts.py`.
  3. Pytest-сьюты `tests/test_prompt_lint.py`, `tests/test_prompt_diff.py`, `tests/test_prompt_versioning.py`.
  4. `tools/check_payload_sync.py` (включая директорию `prompts/en/**`).
  5. `tests/test_gate_workflow.py` — убеждаемся, что gate ловит несинхрон.
- Пример запуска: `./scripts/prompt-release.sh --part minor` или `./scripts/prompt-release.sh --dry-run`.
- Этот скрипт включён в release checklist `aidd/docs/release-notes.md` и позволяет быстро убедиться, что payload готов к публикации.
