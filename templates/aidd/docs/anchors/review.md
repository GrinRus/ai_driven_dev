# Anchor: review

## Goals
- Сверить diff с plan/PRD и DoD.
- Вернуть замечания в tasklist (handoff).
- Управлять обязательностью тестов через reviewer marker (если используется).

## MUST READ FIRST
- git diff / PR diff
- aidd/docs/tasklist/<ticket>.md: AIDD:CONTEXT_PACK, AIDD:CHECKLIST_REVIEW, AIDD:HANDOFF_INBOX
- aidd/docs/spec/<ticket>.spec.yaml (если существует)
- aidd/docs/plan/<ticket>.md: AIDD:FILES_TOUCHED, AIDD:ITERATIONS

## MUST UPDATE
- aidd/docs/tasklist/<ticket>.md: замечания + handoff
- aidd/reports/reviewer/<ticket>.json (review report + маркер тестов)
- AIDD:CONTEXT_PACK → Blockers summary (если есть blocking handoff)

## MUST NOT
- Рефакторинг “ради красоты”.
- Игнорировать тест‑требования при рисковых изменениях.
- Пропускать проверку исполнимости tasklist (NEXT_3/ITERATIONS_FULL/TEST_EXECUTION).

## Repeat runs
- Повторные `/review` должны обновлять handoff‑задачи по `id` без дублей (`tasks-derive --source review --append`).

## Output contract
- Status: READY|WARN|BLOCKED
