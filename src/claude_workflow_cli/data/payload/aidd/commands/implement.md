---
description: "Реализация фичи по плану + выборочные тесты"
argument-hint: "<TICKET> [note...]"
lang: ru
prompt_version: 1.1.11
source_version: 1.1.11
allowed-tools:
  - Read
  - Edit
  - Write
  - Glob
  - "Bash(rg:*)"
  - "Bash(sed:*)"
  - "Bash(cat:*)"
  - "Bash(xargs:*)"
  - "Bash(./gradlew:*)"
  - "Bash(claude-workflow set-active-stage:*)"
  - "Bash(${CLAUDE_PLUGIN_ROOT:-./aidd}/hooks/format-and-test.sh:*)"
  - "Bash(claude-workflow progress:*)"
  - "Bash(git:*)"
  - "Bash(claude-workflow set-active-feature:*)"
model: inherit
disable-model-invocation: false
---

## Контекст
Команда `/implement` запускает саб-агента **implementer** для выполнения следующей итерации по плану и tasklist. Свободный ввод после тикета используйте как контекст для текущей итерации.

## Входные артефакты
- `@aidd/docs/plan/<ticket>.md`.
- `@aidd/docs/tasklist/<ticket>.md`.
- `@aidd/docs/prd/<ticket>.prd.md`, `@aidd/docs/research/<ticket>.md` — при необходимости.

## Когда запускать
- После `/tasks-new`, когда план и оба ревью готовы (Plan Review + PRD Review через `/review-spec`).
- Повторять на каждой итерации разработки.

## Автоматические хуки и переменные
- `claude-workflow set-active-stage implement` фиксирует стадию `implement`.
- Команда должна запускать саб-агента **implementer** (Claude: Run agent → implementer).
- `${CLAUDE_PLUGIN_ROOT:-./aidd}/hooks/format-and-test.sh` запускается на Stop/SubagentStop (управляется `SKIP_AUTO_TESTS`, `FORMAT_ONLY`, `TEST_SCOPE`, `STRICT_TESTS`).
- `claude-workflow progress --source implement --ticket <ticket>` проверяет наличие новых `- [x]`.

## Что редактируется
- Код/конфиги и `aidd/docs/tasklist/<ticket>.md` (прогресс и чекбоксы).

## Пошаговый план
1. Зафиксируй стадию `implement`.
2. Запусти саб-агента **implementer** и передай контекст итерации.
3. Убедись, что tasklist обновлён и прогресс подтверждён через `claude-workflow progress`.

## Fail-fast и вопросы
- Нет plan/tasklist или ревью не готовы — остановись и попроси завершить предыдущие шаги.
- Падающие тесты или блокеры — остановись до исправления/согласования.

## Ожидаемый вывод
- Обновлённый код и `aidd/docs/tasklist/<ticket>.md`.
- Ответ содержит `Checkbox updated`, `Status`, `Artifacts updated`, `Next actions`.

## Примеры CLI
- `/implement ABC-123`
