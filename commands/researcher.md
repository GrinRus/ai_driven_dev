---
description: "Подготовка отчёта Researcher: сбор контекста и запуск агента"
argument-hint: "<TICKET> [note...] [--paths path1,path2] [--keywords kw1,kw2] [--note text]"
lang: ru
prompt_version: 1.2.3
source_version: 1.2.3
allowed-tools:
  - Read
  - Edit
  - Write
  - Glob
  - "Bash(rg:*)"
  - "Bash(sed:*)"
  - "Bash(${CLAUDE_PLUGIN_ROOT}/tools/set-active-feature.sh:*)"
  - "Bash(${CLAUDE_PLUGIN_ROOT}/tools/set-active-stage.sh:*)"
  - "Bash(${CLAUDE_PLUGIN_ROOT}/tools/research.sh:*)"
model: inherit
disable-model-invocation: false
---

## Контекст
Команда `/feature-dev-aidd:researcher` собирает кодовый контекст: читает `## AIDD:RESEARCH_HINTS` из PRD, запускает `${CLAUDE_PLUGIN_ROOT}/tools/research.sh`, затем запускает саб-агента `feature-dev-aidd:researcher`, который обновляет `aidd/docs/research/<ticket>.md`. Свободный ввод после тикета используй как заметку в отчёте. Call graph (если включён) сохраняется в sidecar и указывается в `call_graph_full_path`.
Следуй attention‑policy из `aidd/AGENTS.md` и начни с `aidd/docs/anchors/research.md`.

## Входные артефакты
- `aidd/docs/.active_ticket`, `aidd/docs/.active_feature`.
- `@aidd/docs/prd/<ticket>.prd.md` (раздел `## AIDD:RESEARCH_HINTS`).
- `@aidd/docs/research/template.md` — шаблон.
- `aidd/reports/research/<ticket>-context.json` — формируется CLI (содержит `call_graph_full_path`/`call_graph_full_columnar_path`).

## Когда запускать
- После `/feature-dev-aidd:idea-new`, до `/feature-dev-aidd:plan-new`.
- Повторно — при изменениях модулей/рисков.

## Автоматические хуки и переменные
- `${CLAUDE_PLUGIN_ROOT}/tools/set-active-stage.sh research` фиксирует стадию `research`.
- `${CLAUDE_PLUGIN_ROOT}/tools/research.sh --ticket <ticket> --auto [--graph-mode focus|full] [--graph-engine none] [--paths ... --keywords ... --note ...]` обновляет JSON контекст (auto: graph-scan для kt/kts/java, fast-scan для остальных).
- Команда должна запускать саб-агента `feature-dev-aidd:researcher` (Claude: Run agent → feature-dev-aidd:researcher).
- При необходимости добавь handoff через `${CLAUDE_PLUGIN_ROOT}/tools/tasks-derive.sh --source research --append --ticket <ticket>`.

## Что редактируется
- `aidd/docs/research/<ticket>.md`.
- PRD/tasklist — ссылки на отчёт.

## Пошаговый план
1. Убедись, что активный ticket задан; при необходимости вызови `${CLAUDE_PLUGIN_ROOT}/tools/set-active-feature.sh`.
2. Зафиксируй стадию `research`.
3. Извлеки `## AIDD:RESEARCH_HINTS` и запусти `${CLAUDE_PLUGIN_ROOT}/tools/research.sh ...` с `--paths/--keywords/--note`.
4. Запусти саб-агента `feature-dev-aidd:researcher` и обнови `aidd/docs/research/<ticket>.md`.
5. При необходимости добавь handoff-задачи в tasklist.

## Fail-fast и вопросы
- Нет активного тикета или PRD — остановись и попроси `/feature-dev-aidd:idea-new`.
- Если отчёт остаётся `pending`, верни вопросы/условия для `reviewed`.

## Ожидаемый вывод
- Обновлённый `aidd/docs/research/<ticket>.md` (status `pending|reviewed`).
- Актуальный `aidd/reports/research/<ticket>-context.json`.
- Ответ содержит `Checkbox updated`, `Status`, `Artifacts updated`, `Next actions`.

## Примеры CLI
- `/feature-dev-aidd:researcher ABC-123 --paths src/app:src/shared --keywords "payment,checkout" --graph-mode full`
