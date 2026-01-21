---
description: "Навигация по тикету: индекс, артефакты и последние события"
argument-hint: "[$1]"
lang: ru
prompt_version: 1.0.2
source_version: 1.0.2
allowed-tools:
  - Read
  - "Bash(rg:*)"
  - "Bash(${CLAUDE_PLUGIN_ROOT}/tools/status.sh:*)"
  - "Bash(${CLAUDE_PLUGIN_ROOT}/tools/index-sync.sh:*)"
model: inherit
disable-model-invocation: false
---

## Контекст
`/feature-dev-aidd:status` показывает краткий статус тикета: stage, summary, артефакты, отчёты, последние события и тест‑логи (JSONL). CLI автоматически обновляет индекс при отсутствии или по `--refresh`, а также после ключевых команд (research/prd-review/qa/progress/reviewer-tests/tasks-derive/set-active-*).
Следуй attention‑policy из `aidd/AGENTS.md` и начни с `aidd/docs/anchors/<stage>.md`.

## Входные артефакты
- `aidd/docs/index/$1.yaml` — derived‑index (обновляется автоматически при `/feature-dev-aidd:status` и после ключевых команд).
- `aidd/reports/events/$1.jsonl` — последние события (если есть).
- `aidd/reports/tests/$1.jsonl` — тест‑логи (если есть).
- `aidd/docs/.active_ticket`, `aidd/docs/.active_feature`, `aidd/docs/.active_stage` — маркеры активного тикета.

## Когда запускать
- Перед началом работы, чтобы быстро понять контекст.
- Перед handoff, чтобы сверить артефакты и события.

## Автоматические хуки и переменные
- Команда `${CLAUDE_PLUGIN_ROOT}/tools/status.sh --ticket $1 [--refresh]` выводит статус в CLI.
- `AIDD_INDEX_AUTO=0` отключает авто‑обновление индекса; тогда используйте `--refresh` или запустите `${CLAUDE_PLUGIN_ROOT}/tools/index-sync.sh`.

## Что редактируется
- Ничего (read-only).

## Пошаговый план
1. Определи ticket: аргумент команды или `aidd/docs/.active_ticket`.
2. Запусти `${CLAUDE_PLUGIN_ROOT}/tools/status.sh --ticket $1 [--refresh]` — индекс обновится автоматически.
3. Покажи stage, summary, список артефактов/отчётов и последние события.

## Fail-fast и вопросы
- Нет активного тикета и аргумент не задан — попроси пользователя указать ticket.

## Ожидаемый вывод
- Краткая сводка тикета, список артефактов и последних событий.

## Примеры CLI
- `/feature-dev-aidd:status ABC-123`
- `${CLAUDE_PLUGIN_ROOT}/tools/status.sh --ticket ABC-123 --refresh`
