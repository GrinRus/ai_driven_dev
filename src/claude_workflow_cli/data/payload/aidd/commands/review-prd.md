---
description: "Ревью PRD и фиксация статуса готовности"
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
  - "Bash(claude-workflow progress:*)"
  - "Bash(python3 ${CLAUDE_PLUGIN_ROOT:-./aidd}/scripts/prd-review-agent.py:*)"
  - "Bash(${CLAUDE_PLUGIN_ROOT:-./aidd}/tools/set_active_stage.py:*)"
model: inherit
disable-model-invocation: false
---

## Контекст
Команда `/review-prd` проводит структурное ревью PRD после `/review-plan` и до `/tasks-new`. Она фиксирует стадию `review-prd`, вызывает `prd-reviewer`, обновляет раздел `## PRD Review` и сохраняет отчёт (`${CLAUDE_PLUGIN_ROOT:-./aidd}/reports/prd/<ticket>.json`). Свободный ввод после тикета используйте как дополнительный контекст ревью.

## Входные артефакты
- `@aidd/docs/prd/<ticket>.prd.md` — основной документ.
- `@aidd/docs/plan/<ticket>.md` — план и раздел `## Plan Review` со статусом READY.
- `@aidd/docs/research/<ticket>.md` — контекст интеграций.
- ADR (если есть).

## Когда запускать
- После `/review-plan`, перед `/tasks-new`.
- Повторять при существенных изменениях PRD.

## Автоматические хуки и переменные
- `${CLAUDE_PLUGIN_ROOT:-./aidd}/tools/set_active_stage.py review-prd` фиксирует стадию `review-prd`.
- `gate-workflow` требует `## PRD Review` со статусом `READY` перед изменениями кода.
- Скрипт `python3 "${CLAUDE_PLUGIN_ROOT:-./aidd}/scripts/prd-review-agent.py" --ticket <ticket> --report "${CLAUDE_PLUGIN_ROOT:-./aidd}/reports/prd/<ticket>.json" --emit-text` сохраняет отчёт.

## Что редактируется
- `aidd/docs/prd/<ticket>.prd.md` — раздел `## PRD Review`.
- `aidd/docs/tasklist/<ticket>.md` — перенос блокирующих action items.
- `${CLAUDE_PLUGIN_ROOT:-./aidd}/reports/prd/<ticket>.json` — структурированный отчёт.

## Пошаговый план
1. Зафиксируй стадию `review-prd`: `${CLAUDE_PLUGIN_ROOT:-./aidd}/tools/set_active_stage.py review-prd`.
2. Убедись, что `## Plan Review` в плане имеет `Status: READY`.
3. Вызови `prd-reviewer` и обнови `## PRD Review`.
4. Перенеси блокирующие action items в tasklist.
5. Сохрани отчёт через `prd-review-agent.py`.

## Fail-fast и вопросы
- Если PRD не заполнен (`Status: draft`) или план/plan-review отсутствуют — остановись и попроси завершить предыдущие шаги.
- При блокерах верни `BLOCKED` и вопросы в формате `Вопрос N (Blocker|Clarification)` с `Зачем/Варианты/Default`.

## Ожидаемый вывод
- Раздел `## PRD Review` обновлён, статус выставлен, findings/action items перечислены.
- `${CLAUDE_PLUGIN_ROOT:-./aidd}/reports/prd/<ticket>.json` содержит тот же вывод.
- Блокирующие action items перенесены в tasklist.

## Примеры CLI
- `/review-prd ABC-123`
- `!bash -lc 'python3 "${CLAUDE_PLUGIN_ROOT:-./aidd}/scripts/prd-review-agent.py" --ticket "ABC-123" --report "${CLAUDE_PLUGIN_ROOT:-./aidd}/reports/prd/ABC-123.json" --emit-text'`
