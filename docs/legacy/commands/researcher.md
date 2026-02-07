---
description: "Подготовка отчёта Researcher: сбор контекста и запуск агента"
argument-hint: "$1 [note...] [--paths path1,path2] [--keywords kw1,kw2] [--note text]"
lang: ru
prompt_version: 1.2.30
source_version: 1.2.30
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
  - "Bash(${CLAUDE_PLUGIN_ROOT}/tools/rlm-slice.sh:*)"
  - "Bash(${CLAUDE_PLUGIN_ROOT}/tools/rlm-nodes-build.sh:*)"
  - "Bash(${CLAUDE_PLUGIN_ROOT}/tools/rlm-verify.sh:*)"
  - "Bash(${CLAUDE_PLUGIN_ROOT}/tools/rlm-links-build.sh:*)"
  - "Bash(${CLAUDE_PLUGIN_ROOT}/tools/rlm-jsonl-compact.sh:*)"
  - "Bash(${CLAUDE_PLUGIN_ROOT}/tools/rlm-finalize.sh:*)"
  - "Bash(${CLAUDE_PLUGIN_ROOT}/tools/reports-pack.sh:*)"
model: inherit
disable-model-invocation: false
---

## Контекст
Команда `/feature-dev-aidd:researcher` работает inline: читает `## AIDD:RESEARCH_HINTS` из PRD, запускает `${CLAUDE_PLUGIN_ROOT}/tools/research.sh`, пишет Context Pack и явно запускает саб‑агента `feature-dev-aidd:researcher`, который обновляет `aidd/docs/research/$1.md`. Свободный ввод после тикета используй как заметку в отчёте. RLM evidence сохраняется как pack + worklist.
Следуй `aidd/AGENTS.md` и канону `aidd/docs/prompting/conventions.md` (pack‑first/read‑budget).

## Входные артефакты
- `aidd/docs/.active.json`.
- `aidd/docs/prd/$1.prd.md` (раздел `## AIDD:RESEARCH_HINTS`).
- `aidd/docs/research/template.md` — шаблон.
- `aidd/reports/research/$1-context.pack.json` (pack-first).
- `aidd/reports/research/$1-rlm.pack.json` (pack-first), `rlm-slice` pack (по запросу).
- `aidd/reports/research/$1-rlm-targets.json`, `-rlm-manifest.json`, `-rlm.worklist.pack.json` (если `rlm_status=pending`).

## Evidence Read Policy (RLM-first)
- Primary evidence: `aidd/reports/research/<ticket>-rlm.pack.json` (pack-first summary).
- Slice on demand: `${CLAUDE_PLUGIN_ROOT}/tools/rlm-slice.sh --ticket <ticket> --query "<token>"`.
- Use raw `rg` only for spot-checks.

## Когда запускать
- После `/feature-dev-aidd:idea-new`, до `/feature-dev-aidd:plan-new`.
- Повторно — при изменениях модулей/рисков.

## Автоматические хуки и переменные
- `${CLAUDE_PLUGIN_ROOT}/tools/set-active-stage.sh research` фиксирует стадию `research`.
- `${CLAUDE_PLUGIN_ROOT}/tools/research.sh --ticket $1 --auto [--paths ... --keywords ... --note ...]` обновляет JSON контекст и RLM targets/manifest/worklist.
- Если `entries_total` в worklist слишком большой или trimmed — перегенерируй worklist с `${CLAUDE_PLUGIN_ROOT}/tools/rlm-nodes-build.sh --worklist-paths/--worklist-keywords` (или настрой `rlm.worklist_paths/rlm.worklist_keywords`).
- Для жёсткого контроля scope включай `rlm.targets_mode=explicit` (или передай `--targets-mode explicit` в `research.sh`) и настраивай `rlm.exclude_path_prefixes`.
- Для узкого RLM‑scope используй `--rlm-paths <paths>` (comma/colon‑list) при запуске `research.sh`.
- Если `--rlm-paths` задан и `--paths` не указан — research scope синхронизируется с RLM paths (без лишних tags/keywords).
- Команда должна запускать саб-агента `feature-dev-aidd:researcher`.
- Handoff‑задачи (если нужны) добавляет команда через `${CLAUDE_PLUGIN_ROOT}/tools/tasks-derive.sh --source research --append --ticket $1`.
- Если nodes отсутствуют/пустые — сначала создай baseline через `${CLAUDE_PLUGIN_ROOT}/tools/rlm-nodes-build.sh --bootstrap --ticket $1`, затем запускай `rlm-finalize.sh`.
- Когда nodes/links готовы, команда должна запустить `rlm-finalize.sh --ticket $1` (verify → links → compact → refresh worklist → reports-pack --update-context) для `rlm_status=ready`; если после этого `rlm_status` остаётся `pending` или pack отсутствует — вернуть `Status: BLOCKED`.

## Что редактируется
- `aidd/docs/research/$1.md`.
- PRD/tasklist — ссылки на отчёт.

## Context Pack (шаблон)
- Шаблон: `aidd/reports/context/template.context-pack.md`.
- Целевой файл: `aidd/reports/context/$1.pack.md` (rolling pack).
- Заполни поля stage/agent/read_next/artefact_links под research.
- What to do now: summarize integration points/reuse/risks, validate RLM pack/slice.
- User note: $ARGUMENTS.

## Пошаговый план
1. Команда (до subagent): зафиксируй активную фичу `${CLAUDE_PLUGIN_ROOT}/tools/set-active-feature.sh "$1"` при необходимости и выставь стадию `research` через `${CLAUDE_PLUGIN_ROOT}/tools/set-active-stage.sh research`.
2. Команда (до subagent): извлеки `## AIDD:RESEARCH_HINTS` и запусти `${CLAUDE_PLUGIN_ROOT}/tools/research.sh ...` с `--paths/--keywords/--note`.
3. Команда (до subagent): собери Context Pack `aidd/reports/context/$1.pack.md` по шаблону `aidd/reports/context/template.context-pack.md`.
4. Команда → subagent: **Use the feature-dev-aidd:researcher subagent. First action: Read `aidd/reports/context/$1.pack.md`.**
5. Subagent: обновляет `aidd/docs/research/$1.md` и фиксирует findings; секция `AIDD:PRD_OVERRIDES` должна совпадать с PRD (`USER OVERRIDE`) и не содержать неактуальных решений.
6. Команда (после subagent): если `rlm_status=pending` или отсутствует `*-rlm.pack.json` — убедись, что `*-rlm.nodes.jsonl` существует; при отсутствии создай baseline `${CLAUDE_PLUGIN_ROOT}/tools/rlm-nodes-build.sh --bootstrap --ticket $1`.
7. Команда (после subagent): запусти `rlm-finalize.sh --ticket $1` (verify → links → compact → refresh worklist → reports-pack --update-context).
8. Команда (после subagent): если после `rlm-finalize` остаётся `rlm_status=pending` или pack/nodes/links отсутствуют — верни `Status: BLOCKED` и требуй завершить agent‑flow.
9. Команда (после subagent): при необходимости добавь handoff‑задачи через `${CLAUDE_PLUGIN_ROOT}/tools/tasks-derive.sh --source research --append --ticket $1`.

## Fail-fast и вопросы
- Нет активного тикета или PRD — остановись и попроси `/feature-dev-aidd:idea-new`.
- Если отсутствует `*-rlm.pack.json` или `rlm_status` остаётся `pending` после `rlm-finalize` — верни BLOCKED и попроси завершить agent‑flow по worklist.
- Если отчёт остаётся `pending`, верни вопросы/условия для `reviewed`.

## Ожидаемый вывод
- Обновлённый `aidd/docs/research/$1.md` (status `pending|reviewed`, reviewed только при готовом RLM pack).
- Актуальный `aidd/reports/research/$1-context.json` (не читать целиком — только pack/фрагменты).
- Ответ содержит `Checkbox updated`, `Status`, `Artifacts updated`, `Next actions`.

## Примеры CLI
- `/feature-dev-aidd:researcher ABC-123 --paths src/app:src/shared --keywords "payment,checkout"`
