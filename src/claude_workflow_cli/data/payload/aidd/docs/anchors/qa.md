# Anchor: qa

## Цели
- Провести финальную проверку и выпустить QA report.

## MUST KNOW FIRST
- `aidd/docs/tasklist/<ticket>.md` (QA‑секция + AIDD anchors).
- `aidd/docs/prd/<ticket>.prd.md` (acceptance criteria).

## Inputs
- Diff, tasklist, результаты гейтов/тестов.

## Outputs/Contract
- `aidd/reports/qa/<ticket>.json` со статусом READY/WARN/BLOCKED.
- Обновлённый tasklist с QA traceability.

## MUST UPDATE
- `aidd/docs/tasklist/<ticket>.md`.
- `aidd/reports/qa/<ticket>.json`.
- `aidd/docs/.active_stage`.

## MUST NOT
- Пропускать блокеры/critical в QA отчёте.

## Blockers
- Отсутствует tasklist или не пройдены обязательные проверки.

## Test defaults
- QA запускает `claude-workflow qa --gate` и фиксирует логи.
