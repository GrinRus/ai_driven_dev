---
description: "Ревью плана реализации перед PRD review"
argument-hint: "<TICKET> [note...]"
lang: ru
prompt_version: 1.0.1
source_version: 1.0.1
allowed-tools:
  - Read
  - Edit
  - Write
  - Glob
  - "Bash(rg:*)"
  - "Bash(${CLAUDE_PLUGIN_ROOT:-./aidd}/tools/set_active_stage.py:*)"
model: inherit
disable-model-invocation: false
---

## Контекст
Команда `/review-plan` проводит ревью плана после `/plan-new` и до `/review-prd`. Она фиксирует стадию `review-plan`, вызывает `plan-reviewer` и обновляет раздел `## Plan Review` в `aidd/docs/plan/<ticket>.md`. Свободный ввод после тикета используй как дополнительный контекст ревью.

## Входные артефакты
- `@aidd/docs/plan/<ticket>.md` — план реализации.
- `@aidd/docs/prd/<ticket>.prd.md` — цели и acceptance criteria.
- `@aidd/docs/research/<ticket>.md` — точки интеграции/reuse.
- ADR (если есть).

## Когда запускать
- После `/plan-new`, до `/review-prd` и `/tasks-new`.
- Повторный запуск — после существенных правок плана.

## Автоматические хуки и переменные
- `${CLAUDE_PLUGIN_ROOT:-./aidd}/tools/set_active_stage.py review-plan` фиксирует стадию `review-plan`.
- `gate-workflow` блокирует переход к `review-prd`/`tasks-new`, если `Status: READY` в `## Plan Review` не выставлен.

## Что редактируется
- `aidd/docs/plan/<ticket>.md` — раздел `## Plan Review`.

## Пошаговый план
1. Зафиксируй стадию `review-plan`: `${CLAUDE_PLUGIN_ROOT:-./aidd}/tools/set_active_stage.py review-plan`.
2. Убедись, что план существует и имеет актуальный статус (READY/PENDING/BLOCKED).
3. Вызови саб-агента **plan-reviewer** и передай ему контекст (PRD, research, ADR).
4. Обнови `## Plan Review` и верни статус.

## Fail-fast и вопросы
- Нет плана или PRD/research → остановись и попроси завершить `/plan-new` или `/researcher`.
- При блокерах верни статус `BLOCKED` и вопросы в формате `Вопрос N (Blocker|Clarification)` с `Зачем/Варианты/Default`.

## Ожидаемый вывод
- `aidd/docs/plan/<ticket>.md` содержит обновлённый `## Plan Review` со статусом.
- Команда возвращает `Checkbox updated`, `Status`, `Artifacts updated`, `Next actions`.

## Примеры CLI
- `/review-plan ABC-123`
