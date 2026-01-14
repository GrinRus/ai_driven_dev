---
description: "Финальная QA-проверка фичи"
argument-hint: "<TICKET> [note...]"
lang: ru
prompt_version: 1.0.9
source_version: 1.0.9
allowed-tools:
  - Read
  - Edit
  - Write
  - Glob
  - "Bash(rg:*)"
  - "Bash(claude-workflow set-active-stage:*)"
  - "Bash(claude-workflow qa:*)"
  - "Bash(claude-workflow tasks-derive:*)"
  - "Bash(claude-workflow progress:*)"
  - "Bash(claude-workflow set-active-feature:*)"
model: inherit
disable-model-invocation: false
---

## Контекст
Команда `/qa` запускает финальную проверку: запускает саб-агента **qa** через `claude-workflow qa --gate`, обновляет QA секцию tasklist и фиксирует прогресс. После отчёта автоматически формируются handoff‑задачи в `AIDD:HANDOFF_INBOX`. Выполняется после `/review`.
Следуй attention‑policy из `aidd/AGENTS.md` и начни с `aidd/docs/anchors/qa.md`.

## Входные артефакты
- `@aidd/docs/prd/<ticket>.prd.md` (AIDD:ACCEPTANCE).
- `@aidd/docs/plan/<ticket>.md`.
- `@aidd/docs/tasklist/<ticket>.md`.
- Логи тестов/гейтов (если есть).

## Когда запускать
- После `/review`, перед релизом.
- Повторять при новых изменениях.

## Автоматические хуки и переменные
- `claude-workflow set-active-stage qa` фиксирует стадию `qa`.
- Команда должна запускать саб-агента **qa** (Claude: Run agent → qa) через `claude-workflow qa --gate`.
- `claude-workflow qa --ticket <ticket> --report "aidd/reports/qa/<ticket>.json" --gate` формирует отчёт.
- `claude-workflow tasks-derive --source qa --append --ticket <ticket>` добавляет handoff‑задачи в `AIDD:HANDOFF_INBOX`.
- `claude-workflow progress --source qa --ticket <ticket>` фиксирует новые `[x]`.

## Что редактируется
- `aidd/docs/tasklist/<ticket>.md`.
- `aidd/reports/qa/<ticket>.json`.

## Пошаговый план
1. Зафиксируй стадию `qa`.
2. Запусти саб-агента **qa** через `claude-workflow qa --gate` и получи отчёт.
3. Обнови QA секцию tasklist, добавь traceability к AIDD:ACCEPTANCE.
4. Запусти `claude-workflow tasks-derive --source qa --append` — повторный запуск не должен дублировать задачи.
5. Подтверди прогресс через `claude-workflow progress`.

## Fail-fast и вопросы
- Нет tasklist/PRD — остановись и попроси обновить артефакты.
- Отчёт не записался — перезапусти CLI команду и приложи stderr.

## Ожидаемый вывод
- Обновлённый tasklist и отчёт QA.
- Ответ содержит `Checkbox updated`, `Status`, `Artifacts updated`, `Next actions`.

## Примеры CLI
- `/qa ABC-123`
