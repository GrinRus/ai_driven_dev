# Anchor: review-prd

## Цели
- Проверить качество PRD и готовность к tasks/implement.

## MUST KNOW FIRST
- `aidd/docs/prd/<ticket>.prd.md`.
- `aidd/docs/plan/<ticket>.md`.
- `aidd/docs/research/<ticket>.md`.

## Inputs
- PRD, план, research, ADR (если есть).

## Outputs/Contract
- Раздел `## PRD Review` в PRD со статусом `READY|BLOCKED|PENDING`.
- Отчёт `aidd/reports/prd/<ticket>.json`.

## MUST UPDATE
- `aidd/docs/prd/<ticket>.prd.md` (секция PRD Review).
- `aidd/reports/prd/<ticket>.json`.
- `aidd/docs/.active_stage`.

## MUST NOT
- Пропускать блокирующие замечания и action items.

## Blockers
- PRD неполный, отсутствуют acceptance criteria или риски.
