# Anchor: review-plan

## Цели
- Проверить исполнимость плана и блокеры до PRD review.

## MUST KNOW FIRST
- `aidd/docs/plan/<ticket>.md`.
- `aidd/docs/research/<ticket>.md`.

## Inputs
- План, research, PRD.

## Outputs/Contract
- Раздел `## Plan Review` в плане со статусом `READY|BLOCKED|PENDING`.

## MUST UPDATE
- `aidd/docs/plan/<ticket>.md` (секция Plan Review).
- `aidd/docs/.active_stage`.

## MUST NOT
- Пропускать проверку DoD, тест‑стратегии и границ модулей.

## Blockers
- Критичные пробелы в планировании, отсутствующие артефакты.
