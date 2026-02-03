---
description: "Tasklist: scaffold + refiner (детализация по plan/PRD/spec)"
argument-hint: "$1 [note...]"
lang: ru
prompt_version: 1.1.18
source_version: 1.1.18
allowed-tools:
  - Read
  - Edit
  - Write
  - Glob
  - "Bash(rg:*)"
  - "Bash(sed:*)"
  - "Bash(cat:*)"
  - "Bash(${CLAUDE_PLUGIN_ROOT}/tools/set-active-stage.sh:*)"
  - "Bash(${CLAUDE_PLUGIN_ROOT}/tools/set-active-feature.sh:*)"
  - "Bash(${CLAUDE_PLUGIN_ROOT}/tools/prd-check.sh:*)"
  - "Bash(${CLAUDE_PLUGIN_ROOT}/tools/rlm-slice.sh:*)"
  - "Bash(${CLAUDE_PLUGIN_ROOT}/tools/tasklist-check.sh:*)"
model: inherit
disable-model-invocation: false
---

## Контекст
Команда `/feature-dev-aidd:tasks-new` работает inline: готовит `aidd/docs/tasklist/$1.md` (шаблон + anchors), собирает Context Pack и явно запускает саб‑агента **feature-dev-aidd:tasklist-refiner** для детальной разбивки задач по plan/PRD/spec.
Интервью проводится командой `/feature-dev-aidd:spec-interview` (опционально), которая пишет `aidd/docs/spec/$1.spec.yaml`. Tasklist обновляется только через `/feature-dev-aidd:tasks-new`.
Следуй attention‑policy из `aidd/AGENTS.md`, канону `aidd/docs/prompting/conventions.md` и начни с `aidd/docs/anchors/tasklist.md`.

## Входные артефакты
- `aidd/docs/plan/$1.md` — итерации и DoD.
- `aidd/docs/prd/$1.prd.md` + `## PRD Review`.
- `aidd/docs/research/$1.md` — reuse и риски.
- `aidd/docs/spec/$1.spec.yaml` — итоговая спецификация (если есть).
- Шаблон `aidd/docs/tasklist/template.md` (если файл создаётся с нуля).

## Evidence Read Policy (RLM-first)
- Primary evidence: `aidd/reports/research/<ticket>-rlm.pack.json` (pack-first summary).
- Slice on demand: `${CLAUDE_PLUGIN_ROOT}/tools/rlm-slice.sh --ticket <ticket> --query "<token>"`.
- Use raw `rg` only for spot-checks.
- Legacy `ast_grep` evidence is fallback-only.

## Когда запускать
- После `/feature-dev-aidd:review-spec`, перед `/feature-dev-aidd:implement`.
- При наличии spec‑интервью — для синхронизации tasklist.
- Повторно — если поменялась спецификация.

## Автоматические хуки и переменные
- `${CLAUDE_PLUGIN_ROOT}/tools/set-active-stage.sh tasklist` фиксирует стадию `tasklist`.
- `${CLAUDE_PLUGIN_ROOT}/tools/set-active-feature.sh $1` фиксирует активную фичу.
- `${CLAUDE_PLUGIN_ROOT}/tools/prd-check.sh --ticket $1` подтверждает PRD `Status: READY`.
- `gate-workflow` проверяет наличие tasklist и новых `- [x]`.

## Что редактируется
- `aidd/docs/tasklist/$1.md` — фронт-маттер + секции `AIDD:SPEC_PACK`, `AIDD:TEST_STRATEGY`, `AIDD:TEST_EXECUTION`, `AIDD:ITERATIONS_FULL`, `AIDD:NEXT_3`, `AIDD:HANDOFF_INBOX`.

## Context Pack (шаблон)
- Шаблон: `aidd/reports/context/template.context-pack.md`.
- Целевой файл: `aidd/reports/context/$1.tasklist.pack.md` (stage/agent/paths/what-to-do заполняются под tasklist).
- Paths: plan, tasklist, prd, arch_profile, spec/research/test_policy (if exists).
- What to do now: refine AIDD:SPEC_PACK/TEST_* and produce executable NEXT_3.
- User note: $ARGUMENTS.

## Пошаговый план
1. Команда (до subagent): зафиксируй стадию `tasklist` через `${CLAUDE_PLUGIN_ROOT}/tools/set-active-stage.sh tasklist` и активную фичу через `${CLAUDE_PLUGIN_ROOT}/tools/set-active-feature.sh "$1"`.
2. Команда (до subagent): проверь PRD через `${CLAUDE_PLUGIN_ROOT}/tools/prd-check.sh --ticket $1` (при ошибке → `BLOCKED`).
3. Команда (до subagent): создай/открой tasklist; при отсутствии скопируй `aidd/docs/tasklist/template.md`.
4. Команда (до subagent): если секций `AIDD:SPEC_PACK`/`AIDD:TEST_STRATEGY`/`AIDD:TEST_EXECUTION`/`AIDD:ITERATIONS_FULL` нет — добавь их из шаблона.
5. Команда (до subagent): собери Context Pack `aidd/reports/context/$1.tasklist.pack.md` по шаблону `aidd/reports/context/template.context-pack.md`.
6. Команда → subagent: **Use the feature-dev-aidd:tasklist-refiner subagent. First action: Read `aidd/reports/context/$1.tasklist.pack.md`.**
7. Subagent: обновляет `AIDD:SPEC_PACK`, `AIDD:TEST_STRATEGY`, `AIDD:TEST_EXECUTION`, `AIDD:ITERATIONS_FULL` (чекбоксы + iteration_id/parent_iteration_id + optional deps/locks/Priority/Blocking) и `AIDD:NEXT_3` (pointer list с `ref: iteration_id|id`, deps удовлетворены).
8. Команда (после subagent): запусти `${CLAUDE_PLUGIN_ROOT}/tools/tasklist-check.sh --ticket $1`. При ошибках (включая spec‑required) верни `Status: BLOCKED` и запроси `/feature-dev-aidd:spec-interview`, затем `/feature-dev-aidd:tasks-new`.

## Fail-fast и вопросы
- Нет plan/Plan Review/PRD Review READY — остановись и попроси завершить `/feature-dev-aidd:review-spec`.
- Если есть UI/UX или front-end изменения (а также API/DATA/E2E) и spec отсутствует — `Status: BLOCKED` и запросить `/feature-dev-aidd:spec-interview`.
- Если непонятны владельцы/сроки — запроси уточнения.

## Ожидаемый вывод
- Актуальный `aidd/docs/tasklist/$1.md` с `AIDD:SPEC_PACK`, `AIDD:TEST_STRATEGY`, `AIDD:TEST_EXECUTION`, `AIDD:ITERATIONS_FULL`, `AIDD:NEXT_3` и `AIDD:HANDOFF_INBOX`.
- Если данных недостаточно — `Status: BLOCKED` и рекомендация повторить `/feature-dev-aidd:spec-interview`, затем `/feature-dev-aidd:tasks-new`.
- Ответ содержит `Checkbox updated`, `Status`, `Artifacts updated`, `Next actions`.

## Примеры CLI
- `/feature-dev-aidd:tasks-new ABC-123`
