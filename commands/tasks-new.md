---
description: "Tasklist: scaffold + refiner (детализация по plan/PRD/spec)"
argument-hint: "$1 [note...]"
lang: ru
prompt_version: 1.1.13
source_version: 1.1.13
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
  - "Bash(${CLAUDE_PLUGIN_ROOT}/tools/rlm-slice.sh:*)"
model: inherit
disable-model-invocation: false
---

## Контекст
Команда `/feature-dev-aidd:tasks-new` работает inline: готовит `aidd/docs/tasklist/$1.md` (шаблон + anchors), собирает Context Pack и явно запускает саб‑агента **feature-dev-aidd:tasklist-refiner** для детальной разбивки задач по plan/PRD/spec.
Интервью проводится командой `/feature-dev-aidd:spec-interview` (опционально), которая пишет `aidd/docs/spec/$1.spec.yaml`. Tasklist обновляется только через `/feature-dev-aidd:tasks-new`.
Следуй attention‑policy из `aidd/AGENTS.md` и начни с `aidd/docs/anchors/tasklist.md`.

## Входные артефакты
- `aidd/docs/plan/$1.md` — итерации и DoD.
- `aidd/docs/prd/$1.prd.md` + `## PRD Review`.
- `aidd/docs/research/$1.md` — reuse и риски.
- `aidd/docs/spec/$1.spec.yaml` — итоговая спецификация (если есть).
- Шаблон `aidd/docs/tasklist/template.md` (если файл создаётся с нуля).

## Evidence Read Policy (RLM-first)
- Primary evidence: `aidd/reports/research/<ticket>-rlm.pack.*` (pack-first summary).
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
- `gate-workflow` проверяет наличие tasklist и новых `- [x]`.

## Что редактируется
- `aidd/docs/tasklist/$1.md` — фронт-маттер + секции `AIDD:SPEC_PACK`, `AIDD:TEST_STRATEGY`, `AIDD:TEST_EXECUTION`, `AIDD:ITERATIONS_FULL`, `AIDD:NEXT_3`, `AIDD:HANDOFF_INBOX`.

## Context Pack (шаблон)
Файл: `aidd/reports/context/$1.tasklist.pack.md`.

```md
# AIDD Context Pack — tasklist
ticket: $1
stage: tasklist
agent: feature-dev-aidd:tasklist-refiner
generated_at: <UTC ISO-8601>

## Paths
- plan: aidd/docs/plan/$1.md
- tasklist: aidd/docs/tasklist/$1.md
- prd: aidd/docs/prd/$1.prd.md
- arch_profile: aidd/docs/architecture/profile.md
- spec: aidd/docs/spec/$1.spec.yaml (if exists)
- research: aidd/docs/research/$1.md
- test_policy: aidd/.cache/test-policy.env (if exists)

## What to do now
- Refine AIDD:SPEC_PACK/TEST_* and produce executable NEXT_3.

## User note
- $ARGUMENTS

## Git snapshot (optional)
- branch: <git rev-parse --abbrev-ref HEAD>
- diffstat: <git diff --stat>
```

## Пошаговый план
1. Команда (до subagent): зафиксируй стадию `tasklist` через `${CLAUDE_PLUGIN_ROOT}/tools/set-active-stage.sh tasklist` и активную фичу через `${CLAUDE_PLUGIN_ROOT}/tools/set-active-feature.sh "$1"`.
2. Команда (до subagent): создай/открой tasklist; при отсутствии скопируй `aidd/docs/tasklist/template.md`.
3. Команда (до subagent): если секций `AIDD:SPEC_PACK`/`AIDD:TEST_STRATEGY`/`AIDD:TEST_EXECUTION`/`AIDD:ITERATIONS_FULL` нет — добавь их из шаблона.
4. Команда (до subagent): собери Context Pack `aidd/reports/context/$1.tasklist.pack.md` по шаблону W79-10.
5. Команда → subagent: **Use the feature-dev-aidd:tasklist-refiner subagent. First action: Read `aidd/reports/context/$1.tasklist.pack.md`.**
6. Subagent: обновляет `AIDD:SPEC_PACK`, `AIDD:TEST_STRATEGY`, `AIDD:TEST_EXECUTION`, `AIDD:ITERATIONS_FULL` (чекбоксы + iteration_id/parent_iteration_id) и `AIDD:NEXT_3` (pointer list с `ref: iteration_id|id`).

## Fail-fast и вопросы
- Нет plan/Plan Review/PRD Review READY — остановись и попроси завершить `/feature-dev-aidd:review-spec`.
- Если есть UI/API/DATA/E2E изменения и spec отсутствует — `Status: BLOCKED` и запросить `/feature-dev-aidd:spec-interview`.
- Если непонятны владельцы/сроки — запроси уточнения.

## Ожидаемый вывод
- Актуальный `aidd/docs/tasklist/$1.md` с `AIDD:SPEC_PACK`, `AIDD:TEST_STRATEGY`, `AIDD:TEST_EXECUTION`, `AIDD:ITERATIONS_FULL`, `AIDD:NEXT_3` и `AIDD:HANDOFF_INBOX`.
- Если данных недостаточно — `Status: BLOCKED` и рекомендация повторить `/feature-dev-aidd:spec-interview`, затем `/feature-dev-aidd:tasks-new`.
- Ответ содержит `Checkbox updated`, `Status`, `Artifacts updated`, `Next actions`.

## Примеры CLI
- `/feature-dev-aidd:tasks-new ABC-123`
