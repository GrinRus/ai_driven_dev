---
description: "Сформировать чеклист задач (`aidd/docs/tasklist/<ticket>.md`) для фичи"
argument-hint: "<TICKET> [note...]"
lang: ru
prompt_version: 1.0.6
source_version: 1.0.6
allowed-tools:
  - Read
  - Edit
  - Write
  - Glob
  - "Bash(rg:*)"
  - "Bash(${CLAUDE_PLUGIN_ROOT:-./aidd}/tools/set_active_stage.py:*)"
  - "Bash(${CLAUDE_PLUGIN_ROOT:-./aidd}/tools/set_active_feature.py:*)"
model: inherit
disable-model-invocation: false
---

## Контекст
Команда `/tasks-new` создаёт или пересобирает `aidd/docs/tasklist/<ticket>.md` на основе плана, PRD и ревью. Tasklist — основной источник для `/implement`, `/review`, `/qa`. Свободный ввод после тикета включи как примечание в чеклист.

## Входные артефакты
- `@aidd/docs/plan/<ticket>.md` — итерации и DoD.
- `@aidd/docs/prd/<ticket>.prd.md` + `## PRD Review`.
- `@aidd/docs/research/<ticket>.md` — reuse и риски.
- Шаблон `@aidd/docs/tasklist/template.md` (если файл создаётся с нуля).

## Когда запускать
- После `/review-spec`, перед `/implement`.
- Повторно — если план/PRD изменились.

## Автоматические хуки и переменные
- `${CLAUDE_PLUGIN_ROOT:-./aidd}/tools/set_active_stage.py tasklist` фиксирует стадию `tasklist`.
- `gate-workflow` проверяет наличие tasklist и новых `- [x]`.

## Что редактируется
- `aidd/docs/tasklist/<ticket>.md` — фронт-маттер + секции `Next 3`, `Handoff inbox`, чеклисты по этапам.

## Пошаговый план
1. Зафиксируй стадию `tasklist`: `${CLAUDE_PLUGIN_ROOT:-./aidd}/tools/set_active_stage.py tasklist`.
2. Создай/открой tasklist; при отсутствии скопируй `aidd/docs/tasklist/template.md`.
3. Обнови фронт-маттер (Ticket/Slug/Status/PRD/Plan/Research/Updated).
4. Перенеси шаги из плана в чеклист, добавь action items из PRD Review.
5. Заполни `Next 3` (первые три пункта фокуса) и `Handoff inbox`.
6. При необходимости добавь типовые задачи вручную (без пресетов).

## Fail-fast и вопросы
- Нет plan/Plan Review/PRD Review READY — остановись и попроси завершить `/review-spec`.
- Если непонятны владельцы/сроки — запроси уточнения.

## Ожидаемый вывод
- Актуальный `aidd/docs/tasklist/<ticket>.md` с `Next 3` и `Handoff inbox`.
- Ответ содержит `Checkbox updated`, `Status`, `Artifacts updated`, `Next actions`.

## Примеры CLI
- `/tasks-new ABC-123`
