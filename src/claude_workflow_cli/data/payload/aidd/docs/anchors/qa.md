# Anchor: qa

## Goals
- Проверить фичу против AIDD:ACCEPTANCE.
- Findings с severity и traceability.
- Обновить QA чекбоксы, отчёт и handoff‑задачи.

## MUST READ FIRST
- aidd/docs/prd/<ticket>.prd.md: AIDD:ACCEPTANCE
- aidd/docs/tasklist/<ticket>.md: AIDD:CHECKLIST_QA + AIDD:HANDOFF_INBOX
- aidd/reports/tests/* и diff (если есть)

## MUST UPDATE
- aidd/docs/tasklist/<ticket>.md: QA чекбоксы + known issues
- aidd/reports/qa/<ticket>.json
- AIDD:HANDOFF_INBOX через `claude-workflow tasks-derive --source qa --append`.

## MUST NOT
- READY при blocker/critical.
- Прятать gaps — перечислять явно.

## Repeat runs
- Повторные запуски QA/`tasks-derive` должны обновлять задачи по стабильному `id` без дублей.

## Output contract
- Status: READY|WARN|BLOCKED
