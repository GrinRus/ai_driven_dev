---
description: "Код-ревью и возврат замечаний в задачи"
argument-hint: "<TICKET> [note...]"
lang: ru
prompt_version: 1.0.5
source_version: 1.0.5
allowed-tools:
  - Read
  - Edit
  - Write
  - Glob
  - "Bash(rg:*)"
  - "Bash(sed:*)"
  - "Bash(claude-workflow set-active-stage:*)"
  - "Bash(claude-workflow reviewer-tests:*)"
  - "Bash(claude-workflow progress:*)"
  - "Bash(claude-workflow set-active-feature:*)"
model: inherit
disable-model-invocation: false
---

## Контекст
Команда `/review` запускает саб-агента **reviewer** для проверки изменений перед QA и фиксирует замечания в tasklist. Свободный ввод после тикета используй как контекст ревью.
Следуй attention‑policy из `aidd/AGENTS.md` и начни с `aidd/docs/anchors/review.md`.

## Входные артефакты
- Diff/PR.
- `@aidd/docs/prd/<ticket>.prd.md`, `@aidd/docs/plan/<ticket>.md`, `@aidd/docs/tasklist/<ticket>.md`.
- Логи тестов/гейтов (если есть), `aidd/reports/reviewer/<ticket>.json`.

## Когда запускать
- После `/implement`, до `/qa`.
- Повторять до снятия блокеров.

## Автоматические хуки и переменные
- `claude-workflow set-active-stage review` фиксирует стадию `review`.
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
