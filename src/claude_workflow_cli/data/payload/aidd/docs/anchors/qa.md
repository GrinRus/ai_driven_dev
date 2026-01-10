# Anchor: qa

## Goals
- Проверить фичу против AIDD:ACCEPTANCE.
- Findings с severity и traceability.
- Обновить QA чекбоксы и отчёт.

## MUST READ FIRST
- aidd/docs/prd/<ticket>.prd.md: AIDD:ACCEPTANCE
- aidd/docs/tasklist/<ticket>.md: AIDD:CHECKLIST_QA + AIDD:HANDOFF_INBOX
- aidd/reports/tests/* и diff (если есть)

## MUST UPDATE
- aidd/docs/tasklist/<ticket>.md: QA чекбоксы + known issues
- aidd/reports/qa/<ticket>.json

## MUST NOT
- READY при blocker/critical.
- Прятать gaps — перечислять явно.

## Output contract
- Status: READY|WARN|BLOCKED
