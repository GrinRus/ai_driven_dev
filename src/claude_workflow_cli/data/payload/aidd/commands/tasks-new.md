---
description: "Сформировать чеклист задач (`aidd/docs/tasklist/<ticket>.md`) для фичи"
argument-hint: "<TICKET> [note...]"
lang: ru
prompt_version: 1.0.7
source_version: 1.0.7
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
Команда `/tasks-new` создаёт или пересобирает `aidd/docs/tasklist/<ticket>.md` на основе плана, PRD и ревью. Tasklist — основной источник для `/implement`, `/review`, `/qa`. Свободный ввод после тикета включи как примечание в чеклист.
Следуй attention‑policy из `aidd/AGENTS.md` и начни с `aidd/docs/anchors/tasklist.md`.

## Входные артефакты
- `@aidd/docs/plan/<ticket>.md` — итерации и DoD.
- `@aidd/docs/prd/<ticket>.prd.md` + `## PRD Review`.
- `@aidd/docs/research/<ticket>.md` — reuse и риски.
- Шаблон `@aidd/docs/tasklist/template.md` (если файл создаётся с нуля).

## Когда запускать
- После `/review-spec`, перед `/implement`.
- Повторно — если план/PRD изменились.

## Автоматические хуки и переменные
- `claude-workflow set-active-stage tasklist` фиксирует стадию `tasklist`.
- `gate-workflow` проверяет наличие tasklist и новых `- [x]`.

## Что редактируется
- `aidd/docs/tasklist/<ticket>.md` — фронт-маттер + секции `AIDD:NEXT_3`, `AIDD:CONTEXT_PACK`, `AIDD:HANDOFF_INBOX`.

## Пошаговый план
1. Зафиксируй стадию `tasklist`: `claude-workflow set-active-stage tasklist`.
2. Создай/открой tasklist; при отсутствии скопируй `aidd/docs/tasklist/template.md`.
3. Обнови фронт-маттер (Ticket/Slug/Status/PRD/Plan/Research/Updated).
4. Перенеси шаги из плана в чеклист, добавь action items из PRD Review.
5. Заполни `AIDD:NEXT_3` (первые три пункта фокуса).
6. Заполни первичный `AIDD:CONTEXT_PACK` из плана (`AIDD:FILES_TOUCHED`, `AIDD:ITERATIONS`) и первого пункта `AIDD:NEXT_3`.
7. Если есть handoff‑задачи — помести их в `AIDD:HANDOFF_INBOX`.

## Fail-fast и вопросы
- Нет plan/Plan Review/PRD Review READY — остановись и попроси завершить `/review-spec`.
- Если непонятны владельцы/сроки — запроси уточнения.

## Ожидаемый вывод
- Актуальный `aidd/docs/tasklist/<ticket>.md` с `AIDD:NEXT_3` и `AIDD:HANDOFF_INBOX`.
- Ответ содержит `Checkbox updated`, `Status`, `Artifacts updated`, `Next actions`.

## Примеры CLI
- `/tasks-new ABC-123`
