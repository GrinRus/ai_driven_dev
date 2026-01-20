---
description: "Подготовка отчёта Researcher: сбор контекста и запуск агента"
argument-hint: "$1 [note...] [--paths path1,path2] [--keywords kw1,kw2] [--note text]"
lang: ru
prompt_version: 1.2.8
source_version: 1.2.8
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
  - "Bash(${CLAUDE_PLUGIN_ROOT}/tools/tasks-derive.sh:*)"
model: inherit
disable-model-invocation: false
---

## Контекст
Команда `/feature-dev-aidd:researcher` работает inline: читает `## AIDD:RESEARCH_HINTS` из PRD, запускает `${CLAUDE_PLUGIN_ROOT}/tools/research.sh`, пишет Context Pack и явно запускает саб‑агента `agent-feature-dev-aidd:researcher`, который обновляет `aidd/docs/research/$1.md`. Свободный ввод после тикета используй как заметку в отчёте. Call graph (если включён) сохраняется в sidecar и указывается в `call_graph_full_path`.
Следуй attention‑policy из `aidd/AGENTS.md` и начни с `aidd/docs/anchors/research.md`.

## Входные артефакты
- `aidd/docs/.active_ticket`, `aidd/docs/.active_feature`.
- `aidd/docs/prd/$1.prd.md` (раздел `## AIDD:RESEARCH_HINTS`).
- `aidd/docs/research/template.md` — шаблон.
- `aidd/reports/research/$1-context.json` — формируется CLI (содержит `call_graph_full_path`/`call_graph_full_columnar_path`).

## Когда запускать
- После `/feature-dev-aidd:idea-new`, до `/feature-dev-aidd:plan-new`.
- Повторно — при изменениях модулей/рисков.

## Автоматические хуки и переменные
- `${CLAUDE_PLUGIN_ROOT}/tools/set-active-stage.sh research` фиксирует стадию `research`.
- `${CLAUDE_PLUGIN_ROOT}/tools/research.sh --ticket $1 --auto [--graph-mode focus|full] [--graph-engine none] [--paths ... --keywords ... --note ...]` обновляет JSON контекст (auto: graph-scan для kt/kts/java, fast-scan для остальных).
- Команда должна запускать саб-агента `agent-feature-dev-aidd:researcher`.
- Handoff‑задачи (если нужны) добавляет команда через `${CLAUDE_PLUGIN_ROOT}/tools/tasks-derive.sh --source research --append --ticket $1`.

## Что редактируется
- `aidd/docs/research/$1.md`.
- PRD/tasklist — ссылки на отчёт.

## Context Pack (шаблон)
Файл: `aidd/reports/context/$1.research.pack.md`.

```md
# AIDD Context Pack — research
ticket: $1
stage: research
agent: agent-feature-dev-aidd:researcher
generated_at: <UTC ISO-8601>

## Paths
- prd: aidd/docs/prd/$1.prd.md
- research: aidd/docs/research/$1.md
- plan: aidd/docs/plan/$1.md (if exists)
- tasklist: aidd/docs/tasklist/$1.md (if exists)
- spec: aidd/docs/spec/$1.spec.yaml (if exists)
- test_policy: aidd/.cache/test-policy.env (if exists)
- research_context: aidd/reports/research/$1-context.json
- research_targets: aidd/reports/research/$1-targets.json (if exists)

## What to do now
- Summarize integration points/reuse/risks, validate call_graph/import_graph.

## User note
- $ARGUMENTS

## Git snapshot (optional)
- branch: <git rev-parse --abbrev-ref HEAD>
- diffstat: <git diff --stat>
```

## Пошаговый план
1. Команда (до subagent): зафиксируй активную фичу `${CLAUDE_PLUGIN_ROOT}/tools/set-active-feature.sh "$1"` при необходимости и выставь стадию `research` через `${CLAUDE_PLUGIN_ROOT}/tools/set-active-stage.sh research`.
2. Команда (до subagent): извлеки `## AIDD:RESEARCH_HINTS` и запусти `${CLAUDE_PLUGIN_ROOT}/tools/research.sh ...` с `--paths/--keywords/--note`.
3. Команда (до subagent): собери Context Pack `aidd/reports/context/$1.research.pack.md` по шаблону W79-10.
4. Команда → subagent: **Use the agent-feature-dev-aidd:researcher subagent. First action: Read `aidd/reports/context/$1.research.pack.md`.**
5. Subagent: обновляет `aidd/docs/research/$1.md` и фиксирует findings.
6. Команда (после subagent): при необходимости добавь handoff‑задачи через `${CLAUDE_PLUGIN_ROOT}/tools/tasks-derive.sh --source research --append --ticket $1`.

## Fail-fast и вопросы
- Нет активного тикета или PRD — остановись и попроси `/feature-dev-aidd:idea-new`.
- Если отчёт остаётся `pending`, верни вопросы/условия для `reviewed`.

## Ожидаемый вывод
- Обновлённый `aidd/docs/research/$1.md` (status `pending|reviewed`).
- Актуальный `aidd/reports/research/$1-context.json`.
- Ответ содержит `Checkbox updated`, `Status`, `Artifacts updated`, `Next actions`.

## Примеры CLI
- `/feature-dev-aidd:researcher ABC-123 --paths src/app:src/shared --keywords "payment,checkout" --graph-mode full`
