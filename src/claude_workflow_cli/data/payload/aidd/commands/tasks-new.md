---
description: "Tasklist: scaffold + интервью-агент для спецификации"
argument-hint: "<TICKET> [note...]"
lang: ru
prompt_version: 1.0.8
source_version: 1.0.8
allowed-tools:
  - Read
  - Edit
  - Write
  - Glob
  - "Bash(rg:*)"
  - "Bash(claude-workflow set-active-stage:*)"
  - "Bash(claude-workflow set-active-feature:*)"
model: inherit
disable-model-invocation: false
---

## Контекст
Команда `/tasks-new` готовит `aidd/docs/tasklist/<ticket>.md` (шаблон + anchors) и передаёт управление саб-агенту **tasklist-refiner**.
Agent проводит глубокое интервью по plan/PRD/research, фиксирует решения в `AIDD:SPEC`/`AIDD:SPEC_PACK` и доводит чекбоксы до однозначных DoD/Boundaries/Tests.
Следуй attention‑policy из `aidd/AGENTS.md` и начни с `aidd/docs/anchors/tasklist.md`.

## Входные артефакты
- `@aidd/docs/plan/<ticket>.md` — итерации и DoD.
- `@aidd/docs/prd/<ticket>.prd.md` + `## PRD Review`.
- `@aidd/docs/research/<ticket>.md` — reuse и риски.
- Шаблон `@aidd/docs/tasklist/template.md` (если файл создаётся с нуля).

## Когда запускать
- После `/review-spec`, перед `/implement`.
- Повторно — пока `AIDD:SPEC Status` не READY или изменились вводные.

## Автоматические хуки и переменные
- `claude-workflow set-active-stage tasklist` фиксирует стадию `tasklist`.
- `claude-workflow set-active-feature --target . <ticket>` фиксирует активную фичу.
- Команда должна запускать саб-агента **tasklist-refiner** (Claude: Run agent → tasklist-refiner).
- `gate-workflow` проверяет наличие tasklist и новых `- [x]`.

## Что редактируется
- `aidd/docs/tasklist/<ticket>.md` — фронт-маттер + секции `AIDD:SPEC`, `AIDD:SPEC_PACK`, `AIDD:INTERVIEW`, `AIDD:NEXT_3`, `AIDD:HANDOFF_INBOX`.

## Пошаговый план
1. Зафиксируй стадию `tasklist`: `claude-workflow set-active-stage tasklist`.
2. Зафиксируй активную фичу: `claude-workflow set-active-feature --target . "$1"`.
3. Создай/открой tasklist; при отсутствии скопируй `aidd/docs/tasklist/template.md`.
4. Если секций `AIDD:SPEC`/`AIDD:SPEC_PACK`/`AIDD:INTERVIEW`/`AIDD:TASKLIST_REFINEMENT` нет — добавь их из шаблона.
5. Запусти саб-агента **tasklist-refiner** и передай примечания из свободного ввода.
6. Убедись, что обновлены `AIDD:SPEC_PACK`, `AIDD:INTERVIEW`, `AIDD:NEXT_3` и чекбоксы refinement.

## Fail-fast и вопросы
- Нет plan/Plan Review/PRD Review READY — остановись и попроси завершить `/review-spec`.
- Если непонятны владельцы/сроки — запроси уточнения.

## Ожидаемый вывод
- Актуальный `aidd/docs/tasklist/<ticket>.md` с `AIDD:SPEC_PACK`, `AIDD:INTERVIEW`, `AIDD:NEXT_3` и `AIDD:HANDOFF_INBOX`.
- Ответ содержит `Checkbox updated`, `Status`, `Artifacts updated`, `Next actions`.

## Примеры CLI
- `/tasks-new ABC-123`
