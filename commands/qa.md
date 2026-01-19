---
description: "Финальная QA-проверка фичи"
argument-hint: "<TICKET> [note...]"
lang: ru
prompt_version: 1.0.10
source_version: 1.0.10
allowed-tools:
  - Read
  - Edit
  - Write
  - Glob
  - "Bash(rg:*)"
  - "Bash(${CLAUDE_PLUGIN_ROOT}/tools/set-active-stage.sh:*)"
  - "Bash(${CLAUDE_PLUGIN_ROOT}/tools/qa.sh:*)"
  - "Bash(${CLAUDE_PLUGIN_ROOT}/tools/tasks-derive.sh:*)"
  - "Bash(${CLAUDE_PLUGIN_ROOT}/tools/progress.sh:*)"
  - "Bash(${CLAUDE_PLUGIN_ROOT}/tools/set-active-feature.sh:*)"
model: inherit
disable-model-invocation: false
---

## Контекст
Команда `/feature-dev-aidd:qa` запускает финальную проверку: запускает саб-агента **@agent-feature-dev-aidd:qa** через `${CLAUDE_PLUGIN_ROOT}/tools/qa.sh --gate`, обновляет QA секцию tasklist и фиксирует прогресс. После отчёта автоматически формируются handoff‑задачи в `AIDD:HANDOFF_INBOX`. Выполняется после `/feature-dev-aidd:review`.
Следуй attention‑policy из `aidd/AGENTS.md` и начни с `aidd/docs/anchors/qa.md`.

## Входные артефакты
- `@aidd/docs/prd/<ticket>.prd.md` (AIDD:ACCEPTANCE).
- `@aidd/docs/plan/<ticket>.md`.
- `@aidd/docs/tasklist/<ticket>.md`.
- `@aidd/docs/spec/<ticket>.spec.yaml` (если есть).
- Логи тестов/гейтов (если есть).

## Когда запускать
- После `/feature-dev-aidd:review`, перед релизом.
- Повторять при новых изменениях.

## Автоматические хуки и переменные
- `${CLAUDE_PLUGIN_ROOT}/tools/set-active-stage.sh qa` фиксирует стадию `qa`.
- Команда должна запускать саб-агента **@agent-feature-dev-aidd:qa** (Claude: Run agent → @agent-feature-dev-aidd:qa) через `${CLAUDE_PLUGIN_ROOT}/tools/qa.sh --gate`.
- `${CLAUDE_PLUGIN_ROOT}/tools/qa.sh --ticket <ticket> --report "aidd/reports/qa/<ticket>.json" --gate` формирует отчёт.
- `${CLAUDE_PLUGIN_ROOT}/tools/tasks-derive.sh --source qa --append --ticket <ticket>` добавляет handoff‑задачи в `AIDD:HANDOFF_INBOX`.
- `${CLAUDE_PLUGIN_ROOT}/tools/progress.sh --source qa --ticket <ticket>` фиксирует новые `[x]`.

## Что редактируется
- `aidd/docs/tasklist/<ticket>.md`.
- `aidd/reports/qa/<ticket>.json`.

## Пошаговый план
1. Зафиксируй стадию `qa`.
2. Запусти саб-агента **@agent-feature-dev-aidd:qa** через `${CLAUDE_PLUGIN_ROOT}/tools/qa.sh --gate` и получи отчёт.
3. Обнови QA секцию tasklist, добавь traceability к AIDD:ACCEPTANCE (AIDD:QA_TRACEABILITY).
4. Запусти `${CLAUDE_PLUGIN_ROOT}/tools/tasks-derive.sh --source qa --append` — повторный запуск не должен дублировать задачи.
5. Подтверди прогресс через `${CLAUDE_PLUGIN_ROOT}/tools/progress.sh`.

## Fail-fast и вопросы
- Нет tasklist/PRD — остановись и попроси обновить артефакты.
- Отчёт не записался — перезапусти CLI команду и приложи stderr.

## Ожидаемый вывод
- Обновлённый tasklist и отчёт QA.
- Ответ содержит `Checkbox updated`, `Status`, `Artifacts updated`, `Next actions`.

## Примеры CLI
- `/feature-dev-aidd:qa ABC-123`
