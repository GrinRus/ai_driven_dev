---
description: "Tasklist: scaffold + refiner (детализация по plan/PRD/spec)"
argument-hint: "<TICKET> [note...]"
lang: ru
prompt_version: 1.1.2
source_version: 1.1.2
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
  - "Bash(${CLAUDE_PLUGIN_ROOT}/tools/graph-slice.sh:*)"
model: inherit
disable-model-invocation: false
---

## Контекст
Команда `/feature-dev-aidd:tasks-new` готовит `aidd/docs/tasklist/<ticket>.md` (шаблон + anchors), затем запускает саб-агента **feature-dev-aidd:tasklist-refiner** для детальной разбивки задач по plan/PRD/spec.
Интервью проводится командой `/feature-dev-aidd:spec-interview` (опционально), которая пишет `aidd/docs/spec/<ticket>.spec.yaml`. Tasklist обновляется только через `/feature-dev-aidd:tasks-new`.
Следуй attention‑policy из `aidd/AGENTS.md` и начни с `aidd/docs/anchors/tasklist.md`.

## Входные артефакты
- `@aidd/docs/plan/<ticket>.md` — итерации и DoD.
- `@aidd/docs/prd/<ticket>.prd.md` + `## PRD Review`.
- `@aidd/docs/research/<ticket>.md` — reuse и риски.
- `@aidd/docs/spec/<ticket>.spec.yaml` — итоговая спецификация (если есть).
- Шаблон `@aidd/docs/tasklist/template.md` (если файл создаётся с нуля).

## Когда запускать
- После `/feature-dev-aidd:review-spec`, перед `/feature-dev-aidd:implement`.
- При наличии spec‑интервью — для синхронизации tasklist.
- Повторно — если поменялась спецификация.

## Автоматические хуки и переменные
- `${CLAUDE_PLUGIN_ROOT}/tools/set-active-stage.sh tasklist` фиксирует стадию `tasklist`.
- `${CLAUDE_PLUGIN_ROOT}/tools/set-active-feature.sh <ticket>` фиксирует активную фичу.
- `gate-workflow` проверяет наличие tasklist и новых `- [x]`.

## Что редактируется
- `aidd/docs/tasklist/<ticket>.md` — фронт-маттер + секции `AIDD:SPEC_PACK`, `AIDD:TEST_STRATEGY`, `AIDD:TEST_EXECUTION`, `AIDD:ITERATIONS_FULL`, `AIDD:NEXT_3`, `AIDD:HANDOFF_INBOX`.

## Пошаговый план
1. Зафиксируй стадию `tasklist`: `${CLAUDE_PLUGIN_ROOT}/tools/set-active-stage.sh tasklist`.
2. Зафиксируй активную фичу: `${CLAUDE_PLUGIN_ROOT}/tools/set-active-feature.sh "$1"`.
3. Создай/открой tasklist; при отсутствии скопируй `aidd/docs/tasklist/template.md`.
4. Если секций `AIDD:SPEC_PACK`/`AIDD:TEST_STRATEGY`/`AIDD:TEST_EXECUTION`/`AIDD:ITERATIONS_FULL` нет — добавь их из шаблона.
5. Запусти саб-агента **feature-dev-aidd:tasklist-refiner** (без AskUserQuestionTool).
6. Убедись, что обновлены `AIDD:SPEC_PACK`, `AIDD:TEST_STRATEGY`, `AIDD:TEST_EXECUTION`, `AIDD:ITERATIONS_FULL`, `AIDD:NEXT_3` (с iteration_id/DoD/Boundaries/Steps/Tests).

## Fail-fast и вопросы
- Нет plan/Plan Review/PRD Review READY — остановись и попроси завершить `/feature-dev-aidd:review-spec`.
- Если есть UI/API/DATA/E2E изменения и spec отсутствует — `Status: BLOCKED` и запросить `/feature-dev-aidd:spec-interview`.
- Если непонятны владельцы/сроки — запроси уточнения.

## Ожидаемый вывод
- Актуальный `aidd/docs/tasklist/<ticket>.md` с `AIDD:SPEC_PACK`, `AIDD:TEST_STRATEGY`, `AIDD:TEST_EXECUTION`, `AIDD:ITERATIONS_FULL`, `AIDD:NEXT_3` и `AIDD:HANDOFF_INBOX`.
- Если данных недостаточно — `Status: BLOCKED` и рекомендация повторить `/feature-dev-aidd:spec-interview`, затем `/feature-dev-aidd:tasks-new`.
- Ответ содержит `Checkbox updated`, `Status`, `Artifacts updated`, `Next actions`.

## Примеры CLI
- `/feature-dev-aidd:tasks-new ABC-123`
