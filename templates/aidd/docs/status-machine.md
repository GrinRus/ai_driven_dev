# Status Machine (AIDD)

Единый словарь статусов и правил переходов для артефактов SDLC.

> Формат статуса в документах: `Status: READY|BLOCKED|PENDING` (регистр неважен, рекомендуем UPPERCASE).

## PRD (`aidd/docs/prd/<ticket>.prd.md`)

Статусы:
- `draft` — автосозданный шаблон, диалог не заполнен.
- `PENDING` — есть вопросы к пользователю, ответы не получены.
- `BLOCKED` — есть блокеры (нужны данные/решения).
- `READY` — все ответы получены, критичные секции заполнены.

Кто выставляет: `analyst` (через `/feature-dev-aidd:idea-new`).

Переходы:
- `draft → PENDING/BLOCKED` после первичной аналитики.
- `PENDING/BLOCKED → READY` только после ответов пользователя; research проверяется отдельно перед планом (`research-check`).

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

Кто выставляет: `plan-reviewer` (через `/feature-dev-aidd:review-spec`).

## PRD Review (`## PRD Review` + report)

Статусы:
- `PENDING` — проверка не завершена.
- `BLOCKED` — есть критичные замечания.
- `READY` — PRD готов к реализации.

Кто выставляет: `prd-reviewer` (через `/feature-dev-aidd:review-spec`).

## Spec Interview (`aidd/docs/spec/<ticket>.spec.yaml`)

Статусы:
- `draft` — интервью не закрыто, есть блокеры/дыры.
- `ready` — интервью закрыто, решения зафиксированы.
- `deprecated` — спеку заменили/устарела.

Кто выставляет: `/feature-dev-aidd:spec-interview` и агент `spec-interview-writer`.

Примечание:
- Spec‑интервью опционален; отсутствие spec не блокирует implement.

## Tasklist (`aidd/docs/tasklist/<ticket>.md`)

Статусы tasklist (front matter):
- `PENDING` — создан, но не синхронизирован с планом.
- `BLOCKED` — есть блокеры в plan/tasklist или отсутствуют входные артефакты.
- `READY` — tasklist готов к implement.
- `WARN` — готов, но с предупреждениями.

Кто выставляет: `/feature-dev-aidd:tasks-new` + `tasklist-refiner`.

Готовность:
- `Tasklist READY` требует заполненные `AIDD:SPEC_PACK` + `AIDD:TEST_STRATEGY` + `AIDD:TEST_EXECUTION`.

## Review / QA Reports

Статусы:
- `READY` — нет блокеров.
- `WARN` — есть предупреждения (minor/major).
- `BLOCKED` — есть блокеры (blocker/critical).

Кто выставляет: `reviewer` и `qa`.

## Review Pack verdict (`aidd/reports/loops/<ticket>/<scope_key>/review.latest.pack.md`)

Verdict:
- `SHIP` — работа принята, итерация закрыта.
- `REVISE` — есть замечания, требуется следующая итерация.

## Stage Result (loop‑gating)

Файл: `aidd/reports/loops/<ticket>/<scope_key>/stage.<stage>.result.json`

Result:
- `blocked` — остановка loop (нужен handoff/данные/команды).
- `continue` — следующая итерация.
- `done` — стадия закрыта.

Mapping (по стадиям):
- implement: `READY → continue`, `BLOCKED → blocked`
- review: `SHIP → done`, `REVISE → continue`, `BLOCKED → blocked`
- qa: `READY/WARN → done`, `BLOCKED → blocked`

## Scope (work_item vs ticket)

- `implement/review`: `scope_key = sanitize(work_item_key)`
- `qa`: `scope_key = ticket`

## Инварианты

- Без `PRD READY` и успешного `research-check` нельзя переходить к планированию.
- Без `Plan READY` и `Plan Review READY` нельзя начинать `tasks`.
- Без `PRD Review READY` и `Tasklist READY` нельзя менять код (`implement/review/qa`).
