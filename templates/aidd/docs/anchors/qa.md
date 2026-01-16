# Anchor: qa

## Goals
- Проверить фичу против AIDD:ACCEPTANCE.
- Findings с severity и traceability.
- Обновить QA чекбоксы, отчёт и handoff‑задачи.

## MUST READ FIRST
- aidd/docs/prd/<ticket>.prd.md: AIDD:ACCEPTANCE
- aidd/docs/tasklist/<ticket>.md: AIDD:CHECKLIST_QA + AIDD:HANDOFF_INBOX + AIDD:TEST_EXECUTION
- aidd/docs/spec/<ticket>.spec.yaml (если существует)
- aidd/reports/tests/* и diff (если есть)

## MUST UPDATE
- aidd/docs/tasklist/<ticket>.md: QA чекбоксы + known issues + AIDD:QA_TRACEABILITY
- aidd/reports/qa/<ticket>.json
- AIDD:HANDOFF_INBOX через `PYTHONPATH=${CLAUDE_PLUGIN_ROOT:-.} python3 -m aidd_runtime.cli tasks-derive --source qa --append`.
- AIDD:CONTEXT_PACK → Blockers summary (если есть blocking handoff)

## MUST NOT
- READY при blocker/critical.
- Прятать gaps — перечислять явно.
- Придумывать тест‑команды вне `AIDD:TEST_EXECUTION`.

## Repeat runs
- Повторные запуски QA/`tasks-derive` должны обновлять задачи по стабильному `id` без дублей.

## Output contract
- Status: READY|WARN|BLOCKED
