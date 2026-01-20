# Anchor: qa

## Goals
- Проверить фичу против AIDD:ACCEPTANCE.
- Findings с severity и traceability.
- Обновить QA чекбоксы, отчёт и handoff‑задачи.

## Graph Read Policy
- MUST: читать `aidd/reports/research/<ticket>-call-graph.pack.*` или `graph-slice` pack.
- MUST: точечный `rg` по `aidd/reports/research/<ticket>-call-graph.edges.jsonl`.
- MUST NOT: `Read` full `*-call-graph-full.json` или `*.cjson`.

## MUST READ FIRST
- aidd/docs/prd/<ticket>.prd.md: AIDD:ACCEPTANCE
- aidd/docs/tasklist/<ticket>.md: AIDD:CHECKLIST_QA + AIDD:HANDOFF_INBOX + AIDD:TEST_EXECUTION
- aidd/docs/spec/<ticket>.spec.yaml (если существует)
- aidd/reports/tests/* и diff (если есть)

## MUST UPDATE
- aidd/docs/tasklist/<ticket>.md: QA чекбоксы + known issues + AIDD:QA_TRACEABILITY
- aidd/reports/qa/<ticket>.json
- AIDD:HANDOFF_INBOX через `${CLAUDE_PLUGIN_ROOT}/tools/tasks-derive.sh --source qa --append`.
- AIDD:CONTEXT_PACK → Blockers summary (если есть blocking handoff)
- Каждый finding оформляй как handoff‑задачу в `AIDD:HANDOFF_INBOX` (scope/DoD/Boundaries/Tests).
- Формат finding: `scope=iteration_id|n/a`, `blocking: true|false`, DoD/Boundaries/Tests как часть handoff.

## MUST NOT
- READY при blocker/critical.
- Прятать gaps — перечислять явно.
- Придумывать тест‑команды вне `AIDD:TEST_EXECUTION`.
- Любые правки кода/конфигов/тестов/CI. QA фиксирует только задачи в tasklist.
- Любые изменения вне `aidd/docs/tasklist/<ticket>.md` (кроме автогенерируемых отчётов в `aidd/reports/**`).

## Repeat runs
- Повторные запуски QA/`tasks-derive` должны обновлять задачи по стабильному `id` без дублей.

## Output contract
- Status: READY|WARN|BLOCKED
