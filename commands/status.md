---
description: "Навигация по тикету: индекс, артефакты и последние события"
argument-hint: "[<TICKET>]"
lang: ru
prompt_version: 1.0.0
source_version: 1.0.0
allowed-tools:
  - Read
  - "Bash(rg:*)"
  - "Bash(PYTHONPATH=${CLAUDE_PLUGIN_ROOT:-.} python3 -m aidd_runtime.cli status:*)"
model: inherit
disable-model-invocation: false
---

## Контекст
`/status` показывает краткий статус тикета: stage, summary, артефакты, отчёты, последние события и тест‑логи (JSONL). CLI автоматически обновляет индекс при отсутствии или по `--refresh`, а также после ключевых команд (research/prd-review/qa/progress/reviewer-tests/tasks-derive/set-active-*).
Следуй attention‑policy из `aidd/AGENTS.md` и начни с `aidd/docs/anchors/<stage>.md`.

## Входные артефакты
- `@aidd/docs/index/<ticket>.yaml` — derived‑index (обновляется автоматически при `/status` и после ключевых команд).
- `@aidd/reports/events/<ticket>.jsonl` — последние события (если есть).
- `@aidd/reports/tests/<ticket>.jsonl` — тест‑логи (если есть).
- `@aidd/docs/.active_ticket`, `@aidd/docs/.active_feature`, `@aidd/docs/.active_stage` — маркеры активного тикета.

## Когда запускать
- Перед началом работы, чтобы быстро понять контекст.
- Перед handoff, чтобы сверить артефакты и события.

## Автоматические хуки и переменные
- Команда `PYTHONPATH=${CLAUDE_PLUGIN_ROOT:-.} python3 -m aidd_runtime.cli status --ticket <ticket> [--refresh]` выводит статус в CLI.
- `AIDD_INDEX_AUTO=0` отключает авто‑обновление индекса; тогда используйте `--refresh` или запустите `PYTHONPATH=${CLAUDE_PLUGIN_ROOT:-.} python3 -m aidd_runtime.cli index-sync`.

## Что редактируется
- Ничего (read-only).

## Пошаговый план
1. Определи ticket: аргумент команды или `aidd/docs/.active_ticket`.
2. Запусти `PYTHONPATH=${CLAUDE_PLUGIN_ROOT:-.} python3 -m aidd_runtime.cli status --ticket <ticket> [--refresh]` — индекс обновится автоматически.
3. Покажи stage, summary, список артефактов/отчётов и последние события.

## Fail-fast и вопросы
- Нет активного тикета и аргумент не задан — попроси пользователя указать ticket.

## Ожидаемый вывод
- Краткая сводка тикета, список артефактов и последних событий.

## Примеры CLI
- `/status ABC-123`
- `PYTHONPATH=${CLAUDE_PLUGIN_ROOT:-.} python3 -m aidd_runtime.cli status --ticket ABC-123 --refresh`
