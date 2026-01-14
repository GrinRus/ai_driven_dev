# Anchor: review

## Goals
- Сверить diff с plan/PRD и DoD.
- Вернуть замечания в tasklist (handoff).
- Управлять обязательностью тестов через reviewer marker (если используется).

## MUST READ FIRST
- git diff / PR diff
- aidd/docs/tasklist/<ticket>.md: AIDD:CONTEXT_PACK, AIDD:CHECKLIST_REVIEW
- aidd/docs/plan/<ticket>.md: AIDD:FILES_TOUCHED, AIDD:ITERATIONS

## MUST UPDATE
- aidd/docs/tasklist/<ticket>.md: замечания + handoff
- aidd/reports/reviewer/<ticket>.json (если это маркер/summary)

## MUST NOT
- Рефакторинг “ради красоты”.
- Игнорировать тест‑требования при рисковых изменениях.

## Output contract
- Status: READY|WARN|BLOCKED
