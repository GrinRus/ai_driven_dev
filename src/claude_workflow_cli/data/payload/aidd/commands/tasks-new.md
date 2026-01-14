---
description: "Tasklist: scaffold (+ optional spec sync)"
argument-hint: "<TICKET> [note...]"
lang: ru
prompt_version: 1.1.0
source_version: 1.1.0
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
Команда `/tasks-new` готовит `aidd/docs/tasklist/<ticket>.md` (шаблон + anchors) и, если есть готовая спецификация, синхронизирует `AIDD:SPEC_PACK`/`AIDD:TEST_STRATEGY`.
Интервью проводится командой `/spec-interview` (опционально), которая пишет `aidd/docs/spec/<ticket>.spec.yaml`.
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
- `aidd/docs/tasklist/<ticket>.md` — фронт-маттер + секции `AIDD:SPEC_PACK`, `AIDD:TEST_STRATEGY`, `AIDD:NEXT_3`, `AIDD:HANDOFF_INBOX`.

## Пошаговый план
1. Зафиксируй стадию `tasklist`: `claude-workflow set-active-stage tasklist`.
2. Зафиксируй активную фичу: `claude-workflow set-active-feature --target . "$1"`.
3. Создай/открой tasklist; при отсутствии скопируй `aidd/docs/tasklist/template.md`.
4. Если секций `AIDD:SPEC_PACK`/`AIDD:TEST_STRATEGY` нет — добавь их из шаблона.
5. Если есть spec и он актуален — синхронизируй `AIDD:SPEC_PACK`/`AIDD:TEST_STRATEGY`; иначе оставь placeholders и отметь, что `/spec-interview` опционален.
6. Убедись, что обновлены `AIDD:SPEC_PACK`, `AIDD:TEST_STRATEGY`, `AIDD:NEXT_3`.

## Fail-fast и вопросы
- Нет plan/Plan Review/PRD Review READY — остановись и попроси завершить `/review-spec`.
- Если непонятны владельцы/сроки — запроси уточнения.

## Ожидаемый вывод
- Актуальный `aidd/docs/tasklist/<ticket>.md` с `AIDD:SPEC_PACK`, `AIDD:TEST_STRATEGY`, `AIDD:NEXT_3` и `AIDD:HANDOFF_INBOX`.
- Ответ содержит `Checkbox updated`, `Status`, `Artifacts updated`, `Next actions`.

## Примеры CLI
- `/tasks-new ABC-123`
