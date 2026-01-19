---
description: "Код-ревью и возврат замечаний в задачи"
argument-hint: "<TICKET> [note...]"
lang: ru
prompt_version: 1.0.8
source_version: 1.0.8
allowed-tools:
  - Read
  - Edit
  - Write
  - Glob
  - "Bash(rg:*)"
  - "Bash(sed:*)"
  - "Bash(${CLAUDE_PLUGIN_ROOT}/tools/set-active-stage.sh:*)"
  - "Bash(${CLAUDE_PLUGIN_ROOT}/tools/review-report.sh:*)"
  - "Bash(${CLAUDE_PLUGIN_ROOT}/tools/reviewer-tests.sh:*)"
  - "Bash(${CLAUDE_PLUGIN_ROOT}/tools/tasks-derive.sh:*)"
  - "Bash(${CLAUDE_PLUGIN_ROOT}/tools/progress.sh:*)"
  - "Bash(${CLAUDE_PLUGIN_ROOT}/tools/set-active-feature.sh:*)"
model: inherit
disable-model-invocation: false
---

## Контекст
Команда `/feature-dev-aidd:review` запускает саб-агента **@agent-feature-dev-aidd:reviewer** для проверки изменений перед QA и фиксирует замечания в tasklist. После ревью создаётся отчёт и формируются handoff‑задачи в `AIDD:HANDOFF_INBOX`. Свободный ввод после тикета используй как контекст ревью.
Следуй attention‑policy из `aidd/AGENTS.md` и начни с `aidd/docs/anchors/review.md`.

## Входные артефакты
- Diff/PR.
- `@aidd/docs/prd/<ticket>.prd.md`, `@aidd/docs/plan/<ticket>.md`, `@aidd/docs/tasklist/<ticket>.md`.
- `@aidd/docs/spec/<ticket>.spec.yaml` (если есть).
- Логи тестов/гейтов (если есть), `aidd/reports/reviewer/<ticket>.json`.

## Когда запускать
- После `/feature-dev-aidd:implement`, до `/feature-dev-aidd:qa`.
- Повторять до снятия блокеров.

## Автоматические хуки и переменные
- `${CLAUDE_PLUGIN_ROOT}/tools/set-active-stage.sh review` фиксирует стадию `review`.
- Команда должна запускать саб-агента **@agent-feature-dev-aidd:reviewer** (Claude: Run agent → @agent-feature-dev-aidd:reviewer).
- `${CLAUDE_PLUGIN_ROOT}/tools/review-report.sh --ticket <ticket>` сохраняет отчёт ревью в `aidd/reports/reviewer/<ticket>.json`.
- `${CLAUDE_PLUGIN_ROOT}/tools/reviewer-tests.sh --status required|optional|clear` управляет обязательностью тестов.
- `${CLAUDE_PLUGIN_ROOT}/tools/tasks-derive.sh --source review --append --ticket <ticket>` добавляет handoff‑задачи в `AIDD:HANDOFF_INBOX`.
- `${CLAUDE_PLUGIN_ROOT}/tools/progress.sh --source review --ticket <ticket>` фиксирует новые `[x]`.

## Что редактируется
- `aidd/docs/tasklist/<ticket>.md` (замечания, прогресс).
- `aidd/reports/reviewer/<ticket>.json`.

## Пошаговый план
1. Зафиксируй стадию `review`.
2. Запусти саб-агента **@agent-feature-dev-aidd:reviewer** и обнови tasklist.
3. Сохрани отчёт ревью через `${CLAUDE_PLUGIN_ROOT}/tools/review-report.sh`.
4. При необходимости запроси автотесты через `reviewer-tests`.
5. Запусти `${CLAUDE_PLUGIN_ROOT}/tools/tasks-derive.sh --source review --append` — повторный запуск не должен дублировать задачи.
6. Подтверди прогресс через `${CLAUDE_PLUGIN_ROOT}/tools/progress.sh`.

## Fail-fast и вопросы
- Нет актуального tasklist/плана — остановись и попроси обновить артефакты.
- Если diff не соответствует тикету — остановись и согласуй объём.

## Ожидаемый вывод
- Обновлённый `aidd/docs/tasklist/<ticket>.md`.
- Ответ содержит `Checkbox updated`, `Status`, `Artifacts updated`, `Next actions`.

## Примеры CLI
- `/feature-dev-aidd:review ABC-123`
