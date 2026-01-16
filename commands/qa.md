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
  - "Bash(PYTHONPATH=${CLAUDE_PLUGIN_ROOT:-.} python3 -m aidd_runtime.cli set-active-stage:*)"
  - "Bash(PYTHONPATH=${CLAUDE_PLUGIN_ROOT:-.} python3 -m aidd_runtime.cli qa:*)"
  - "Bash(PYTHONPATH=${CLAUDE_PLUGIN_ROOT:-.} python3 -m aidd_runtime.cli tasks-derive:*)"
  - "Bash(PYTHONPATH=${CLAUDE_PLUGIN_ROOT:-.} python3 -m aidd_runtime.cli progress:*)"
  - "Bash(PYTHONPATH=${CLAUDE_PLUGIN_ROOT:-.} python3 -m aidd_runtime.cli set-active-feature:*)"
model: inherit
disable-model-invocation: false
---

## Контекст
Команда `/qa` запускает финальную проверку: запускает саб-агента **qa** через `PYTHONPATH=${CLAUDE_PLUGIN_ROOT:-.} python3 -m aidd_runtime.cli qa --gate`, обновляет QA секцию tasklist и фиксирует прогресс. После отчёта автоматически формируются handoff‑задачи в `AIDD:HANDOFF_INBOX`. Выполняется после `/review`.
Следуй attention‑policy из `aidd/AGENTS.md` и начни с `aidd/docs/anchors/qa.md`.

## Входные артефакты
- `@aidd/docs/prd/<ticket>.prd.md` (AIDD:ACCEPTANCE).
- `@aidd/docs/plan/<ticket>.md`.
- `@aidd/docs/tasklist/<ticket>.md`.
- `@aidd/docs/spec/<ticket>.spec.yaml` (если есть).
- Логи тестов/гейтов (если есть).

## Когда запускать
- После `/review`, перед релизом.
- Повторять при новых изменениях.

## Автоматические хуки и переменные
- `PYTHONPATH=${CLAUDE_PLUGIN_ROOT:-.} python3 -m aidd_runtime.cli set-active-stage qa` фиксирует стадию `qa`.
- Команда должна запускать саб-агента **qa** (Claude: Run agent → qa) через `PYTHONPATH=${CLAUDE_PLUGIN_ROOT:-.} python3 -m aidd_runtime.cli qa --gate`.
- `PYTHONPATH=${CLAUDE_PLUGIN_ROOT:-.} python3 -m aidd_runtime.cli qa --ticket <ticket> --report "aidd/reports/qa/<ticket>.json" --gate` формирует отчёт.
- `PYTHONPATH=${CLAUDE_PLUGIN_ROOT:-.} python3 -m aidd_runtime.cli tasks-derive --source qa --append --ticket <ticket>` добавляет handoff‑задачи в `AIDD:HANDOFF_INBOX`.
- `PYTHONPATH=${CLAUDE_PLUGIN_ROOT:-.} python3 -m aidd_runtime.cli progress --source qa --ticket <ticket>` фиксирует новые `[x]`.

## Что редактируется
- `aidd/docs/tasklist/<ticket>.md`.
- `aidd/reports/qa/<ticket>.json`.

## Пошаговый план
1. Зафиксируй стадию `qa`.
2. Запусти саб-агента **qa** через `PYTHONPATH=${CLAUDE_PLUGIN_ROOT:-.} python3 -m aidd_runtime.cli qa --gate` и получи отчёт.
3. Обнови QA секцию tasklist, добавь traceability к AIDD:ACCEPTANCE (AIDD:QA_TRACEABILITY).
4. Запусти `PYTHONPATH=${CLAUDE_PLUGIN_ROOT:-.} python3 -m aidd_runtime.cli tasks-derive --source qa --append` — повторный запуск не должен дублировать задачи.
5. Подтверди прогресс через `PYTHONPATH=${CLAUDE_PLUGIN_ROOT:-.} python3 -m aidd_runtime.cli progress`.

## Fail-fast и вопросы
- Нет tasklist/PRD — остановись и попроси обновить артефакты.
- Отчёт не записался — перезапусти CLI команду и приложи stderr.

## Ожидаемый вывод
- Обновлённый tasklist и отчёт QA.
- Ответ содержит `Checkbox updated`, `Status`, `Artifacts updated`, `Next actions`.

## Примеры CLI
- `/qa ABC-123`
