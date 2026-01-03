---
description: "Код-ревью и возврат замечаний в задачи"
argument-hint: "<TICKET> [note...]"
lang: ru
prompt_version: 1.0.4
source_version: 1.0.4
allowed-tools:
  - Read
  - Edit
  - Write
  - Glob
  - "Bash(rg:*)"
  - "Bash(${CLAUDE_PLUGIN_ROOT:-./aidd}/tools/set_active_stage.py:*)"
  - "Bash(claude-workflow reviewer-tests:*)"
  - "Bash(claude-workflow progress:*)"
model: inherit
disable-model-invocation: false
---

## Контекст
Команда `/review` запускает саб-агента **reviewer** для проверки изменений перед QA и фиксирует замечания в tasklist. Свободный ввод после тикета используй как контекст ревью.

## Входные артефакты
- Diff/PR.
- `@aidd/docs/prd/<ticket>.prd.md`, `@aidd/docs/plan/<ticket>.md`, `@aidd/docs/tasklist/<ticket>.md`.
- Логи тестов/гейтов (если есть), `reports/reviewer/<ticket>.json`.

## Когда запускать
- После `/implement`, до `/qa`.
- Повторять до снятия блокеров.

## Автоматические хуки и переменные
- `${CLAUDE_PLUGIN_ROOT:-./aidd}/tools/set_active_stage.py review` фиксирует стадию `review`.
- Команда должна запускать саб-агента **reviewer** (Claude: Run agent → reviewer).
- `claude-workflow reviewer-tests --status required|optional|clear` управляет обязательностью тестов.
- `claude-workflow progress --source review --ticket <ticket>` фиксирует новые `[x]`.

## Что редактируется
- `aidd/docs/tasklist/<ticket>.md` (замечания, прогресс).

## Пошаговый план
1. Зафиксируй стадию `review`.
2. Запусти саб-агента **reviewer** и обнови tasklist.
3. При необходимости запроси автотесты через `reviewer-tests`.
4. Подтверди прогресс через `claude-workflow progress`.

## Fail-fast и вопросы
- Нет актуального tasklist/плана — остановись и попроси обновить артефакты.
- Если diff не соответствует тикету — остановись и согласуй объём.

## Ожидаемый вывод
- Обновлённый `aidd/docs/tasklist/<ticket>.md`.
- Ответ содержит `Checkbox updated`, `Status`, `Artifacts updated`, `Next actions`.

## Примеры CLI
- `/review ABC-123`
