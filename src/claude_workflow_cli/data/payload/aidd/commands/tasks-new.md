---
description: "Tasklist: scaffold + refiner (детализация по plan/PRD/spec)"
argument-hint: "<TICKET> [note...]"
lang: ru
prompt_version: 1.1.1
source_version: 1.1.1
allowed-tools:
  - Read
  - Edit
  - Write
  - Glob
  - "Bash(rg:*)"
  - "Bash(sed:*)"
  - "Bash(cat:*)"
  - "Bash(claude-workflow set-active-stage:*)"
  - "Bash(claude-workflow set-active-feature:*)"
model: inherit
disable-model-invocation: false
---

## Контекст
Команда `/tasks-new` готовит `aidd/docs/tasklist/<ticket>.md` (шаблон + anchors), затем запускает саб-агента **tasklist-refiner** для детальной разбивки задач по plan/PRD/spec.
Интервью проводится командой `/spec-interview` (опционально), которая пишет `aidd/docs/spec/<ticket>.spec.yaml`. Tasklist обновляется только через `/tasks-new`.
Следуй attention‑policy из `aidd/AGENTS.md` и начни с `aidd/docs/anchors/tasklist.md`.

## Входные артефакты
- `@aidd/docs/plan/<ticket>.md` — итерации и DoD.
- `@aidd/docs/prd/<ticket>.prd.md` + `## PRD Review`.
- `@aidd/docs/research/<ticket>.md` — reuse и риски.
- `@aidd/docs/spec/<ticket>.spec.yaml` — итоговая спецификация (если есть).
- Шаблон `@aidd/docs/tasklist/template.md` (если файл создаётся с нуля).

## Когда запускать
- После `/review-spec`, перед `/implement`.
- При наличии spec‑интервью — для синхронизации tasklist.
- Повторно — если поменялась спецификация.

## Автоматические хуки и переменные
- `claude-workflow set-active-stage tasklist` фиксирует стадию `tasklist`.
- `claude-workflow set-active-feature --target . <ticket>` фиксирует активную фичу.
- `gate-workflow` проверяет наличие tasklist и новых `- [x]`.

## Что редактируется
- `aidd/docs/tasklist/<ticket>.md` — фронт-маттер + секции `AIDD:SPEC_PACK`, `AIDD:TEST_STRATEGY`, `AIDD:ITERATIONS_FULL`, `AIDD:NEXT_3`, `AIDD:HANDOFF_INBOX`.

## Пошаговый план
1. Зафиксируй стадию `tasklist`: `claude-workflow set-active-stage tasklist`.
2. Зафиксируй активную фичу: `claude-workflow set-active-feature --target . "$1"`.
3. Создай/открой tasklist; при отсутствии скопируй `aidd/docs/tasklist/template.md`.
4. Если секций `AIDD:SPEC_PACK`/`AIDD:TEST_STRATEGY`/`AIDD:ITERATIONS_FULL` нет — добавь их из шаблона.
5. Запусти саб-агента **tasklist-refiner** (без AskUserQuestionTool).
6. Убедись, что обновлены `AIDD:SPEC_PACK`, `AIDD:TEST_STRATEGY`, `AIDD:ITERATIONS_FULL`, `AIDD:NEXT_3` (с DoD/Boundaries/Tests).

## Fail-fast и вопросы
- Нет plan/Plan Review/PRD Review READY — остановись и попроси завершить `/review-spec`.
- Если непонятны владельцы/сроки — запроси уточнения.

## Ожидаемый вывод
- Актуальный `aidd/docs/tasklist/<ticket>.md` с `AIDD:SPEC_PACK`, `AIDD:TEST_STRATEGY`, `AIDD:ITERATIONS_FULL`, `AIDD:NEXT_3` и `AIDD:HANDOFF_INBOX`.
- Если данных недостаточно — `Status: BLOCKED` и рекомендация повторить `/spec-interview`, затем `/tasks-new`.
- Ответ содержит `Checkbox updated`, `Status`, `Artifacts updated`, `Next actions`.

## Примеры CLI
- `/tasks-new ABC-123`
