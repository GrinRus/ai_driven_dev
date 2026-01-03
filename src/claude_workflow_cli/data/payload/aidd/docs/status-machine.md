# Status Machine (AIDD)

Единый словарь статусов и правил переходов для артефактов SDLC.

> Формат статуса в документах: `Status: READY|BLOCKED|PENDING` (регистр неважен, рекомендуем UPPERCASE).

## PRD (`aidd/docs/prd/<ticket>.prd.md`)

Статусы:
- `draft` — автосозданный шаблон, диалог не заполнен.
- `PENDING` — есть вопросы к пользователю, ответы не получены.
- `BLOCKED` — есть блокеры (нужны данные/решения).
- `READY` — все ответы получены, критичные секции заполнены.

Кто выставляет: `analyst` (через `/idea-new`).

Переходы:
- `draft → PENDING/BLOCKED` после первичной аналитики.
- `PENDING/BLOCKED → READY` только после ответов пользователя и свежего research.

## Research (`aidd/docs/research/<ticket>.md`)

Статусы:
- `pending` — контекст не подтверждён.
- `reviewed` — найдено достаточно точек интеграции/рисков.

Кто выставляет: `researcher`.

Переходы:
- `pending → reviewed` после заполнения обязательных секций и фиксации команд/путей.

## Plan (`aidd/docs/plan/<ticket>.md`)

Статусы:
- `PENDING` — план сформирован, но есть вопросы.
- `BLOCKED` — validator нашёл критичные пробелы.
- `READY` — validator подтвердил исполняемость.

Кто выставляет: `planner` + `validator`.

Переходы:
- `PENDING/BLOCKED → READY` после ответов и обновления плана.

## Plan Review (`## Plan Review` в плане)

Статусы:
- `PENDING` — проверка не завершена.
- `BLOCKED` — план требует доработки.
- `READY` — план прошёл ревью.

Кто выставляет: `plan-reviewer` (через `/review-plan` или `/review-spec`).

## PRD Review (`## PRD Review` + report)

Статусы:
- `PENDING` — проверка не завершена.
- `BLOCKED` — есть критичные замечания.
- `READY` — PRD готов к реализации.

Кто выставляет: `prd-reviewer` (через `/review-prd` или `/review-spec`).

## Tasklist (`aidd/docs/tasklist/<ticket>.md`)

Статусы:
- `draft` — создан, но не синхронизирован с планом.
- `READY` — отражает plan/review/qa handoff.

Кто выставляет: `/tasks-new` и агент‑исполнитель.

## Review / QA Reports

Статусы:
- `READY` — нет блокеров.
- `WARN` — есть предупреждения (minor/major).
- `BLOCKED` — есть блокеры (blocker/critical).

Кто выставляет: `reviewer` и `qa`.

## Инварианты

- Без `PRD READY` и `Research reviewed` нельзя переходить к планированию.
- Без `Plan READY` и `Plan Review READY` нельзя начинать `review-prd` (или `/review-spec`) и `tasks`.
- Без `PRD Review READY` и `Tasklist READY` нельзя менять код (`implement/review/qa`).
