---
description: "Сформировать чеклист задач (`aidd/docs/tasklist/<ticket>.md`) для фичи"
argument-hint: "<TICKET> [note...]"
lang: ru
prompt_version: 1.0.4
source_version: 1.0.4
allowed-tools:
  - Read
  - Edit
  - Write
  - Glob
  - "Bash(rg:*)"
  - "Bash(${CLAUDE_PLUGIN_ROOT:-./aidd}/tools/set_active_stage.py:*)"
model: inherit
disable-model-invocation: false
---

## Контекст
Команда `/tasks-new` создаёт или пересобирает `aidd/docs/tasklist/<ticket>.md` на основе плана, PRD и ревью. Tasklist — основной источник для `/implement`, `/review`, `/qa`. Свободный ввод после тикета включи как примечание в чеклист.

## Входные артефакты
- `@aidd/docs/plan/<ticket>.md` — итерации и DoD.
- `@aidd/docs/prd/<ticket>.prd.md` + `## PRD Review`.
- `@aidd/docs/research/<ticket>.md` — reuse и риски.
- Шаблон `@templates/tasklist.md` (если файл создаётся с нуля).

## Когда запускать
- После `review-plan` и `review-prd`, перед `/implement`.
- Повторно — если план/PRD изменились.

## Автоматические хуки и переменные
- `${CLAUDE_PLUGIN_ROOT:-./aidd}/tools/set_active_stage.py tasklist` фиксирует стадию `tasklist`.
- `gate-workflow` проверяет наличие tasklist и новых `- [x]`.
- Пресет `feature-impl` может заполнить типовые задачи.

## Что редактируется
- `aidd/docs/tasklist/<ticket>.md` — фронт-маттер + секции `Next 3`, `Handoff inbox`, чеклисты по этапам.

## Пошаговый план
1. Зафиксируй стадию `tasklist`: `${CLAUDE_PLUGIN_ROOT:-./aidd}/tools/set_active_stage.py tasklist`.
2. Создай/открой tasklist; при отсутствии скопируй `templates/tasklist.md`.
3. Обнови фронт-маттер (Ticket/Slug/Status/PRD/Plan/Research/Updated).
4. Перенеси шаги из плана в чеклист, добавь action items из PRD Review.
5. Заполни `Next 3` (первые три пункта фокуса) и `Handoff inbox`.
6. При необходимости разверни `feature-impl`.

## Fail-fast и вопросы
- Нет plan/review-plan/review-prd READY — остановись и попроси завершить предыдущие шаги.
- Если непонятны владельцы/сроки — запроси уточнения.

## Ожидаемый вывод
- Актуальный `aidd/docs/tasklist/<ticket>.md` с `Next 3` и `Handoff inbox`.
- Ответ содержит `Checkbox updated`, `Status`, `Artifacts updated`, `Next actions`.

## Примеры CLI
- `/tasks-new ABC-123`
- `!bash -lc 'claude-workflow preset feature-impl --ticket "ABC-123"'`
