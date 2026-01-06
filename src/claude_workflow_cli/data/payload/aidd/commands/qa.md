---
description: "Финальная QA-проверка фичи"
argument-hint: "<TICKET> [note...]"
lang: ru
prompt_version: 1.0.7
source_version: 1.0.7
allowed-tools:
  - Read
  - Edit
  - Write
  - Glob
  - "Bash(rg:*)"
  - "Bash(${CLAUDE_PLUGIN_ROOT:-./aidd}/tools/set_active_stage.py:*)"
  - "Bash(claude-workflow qa:*)"
  - "Bash(claude-workflow progress:*)"
  - "Bash(${CLAUDE_PLUGIN_ROOT:-./aidd}/tools/set_active_feature.py:*)"
model: inherit
disable-model-invocation: false
---

## Контекст
Команда `/qa` запускает финальную проверку: запускает саб-агента **qa** через `claude-workflow qa --gate`, обновляет QA секцию tasklist и фиксирует прогресс. Выполняется после `/review`.

## Входные артефакты
- `@aidd/docs/prd/<ticket>.prd.md` (acceptance criteria).
- `@aidd/docs/plan/<ticket>.md`.
- `@aidd/docs/tasklist/<ticket>.md`.
- Логи тестов/гейтов (если есть).

## Когда запускать
- После `/review`, перед релизом.
- Повторять при новых изменениях.

## Автоматические хуки и переменные
- `${CLAUDE_PLUGIN_ROOT:-./aidd}/tools/set_active_stage.py qa` фиксирует стадию `qa`.
- Команда должна запускать саб-агента **qa** (Claude: Run agent → qa) через `claude-workflow qa --gate`.
- `claude-workflow qa --ticket <ticket> --report "${CLAUDE_PLUGIN_ROOT:-./aidd}/reports/qa/<ticket>.json" --gate` формирует отчёт.
- `claude-workflow progress --source qa --ticket <ticket>` фиксирует новые `[x]`.

## Что редактируется
- `aidd/docs/tasklist/<ticket>.md`.
- `${CLAUDE_PLUGIN_ROOT:-./aidd}/reports/qa/<ticket>.json`.

## Пошаговый план
1. Зафиксируй стадию `qa`.
2. Запусти саб-агента **qa** через `claude-workflow qa --gate` и получи отчёт.
3. Обнови QA секцию tasklist, добавь traceability к acceptance criteria.
4. Подтверди прогресс через `claude-workflow progress`.

## Fail-fast и вопросы
- Нет tasklist/PRD — остановись и попроси обновить артефакты.
- Отчёт не записался — перезапусти CLI команду и приложи stderr.

## Ожидаемый вывод
- Обновлённый tasklist и отчёт QA.
- Ответ содержит `Checkbox updated`, `Status`, `Artifacts updated`, `Next actions`.

## Примеры CLI
- `/qa ABC-123`
