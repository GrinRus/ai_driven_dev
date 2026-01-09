# Anchor: plan

## Цели
- Подготовить исполнимый план с итерациями, DoD и тест‑стратегией.
- Зафиксировать границы изменений и риски.

## MUST KNOW FIRST
- `aidd/docs/prd/<ticket>.prd.md`.
- `aidd/docs/research/<ticket>.md`.
- `aidd/docs/plan/template.md`.

## Inputs
- PRD со статусом `READY`.
- Research со статусом `reviewed`.

## Outputs/Contract
- `aidd/docs/plan/<ticket>.md` со статусом `PENDING|BLOCKED|READY`.
- Заполненные `AIDD:*` секции плана (архитектура, файлы, итерации, тесты).

## MUST UPDATE
- `aidd/docs/plan/<ticket>.md`.
- `aidd/docs/.active_stage`.

## MUST NOT
- Пропускать `research-check` перед планом.
- Планировать без границ модулей/файлов.

## Blockers
- Отсутствует `PRD READY` или `research reviewed`.
- Не определены риски/границы изменений.
