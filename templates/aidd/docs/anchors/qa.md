# Anchor: qa

## Goals
- Проверить фичу против AIDD:ACCEPTANCE.
- Findings с severity и traceability.
- Обновить QA чекбоксы, отчёт и handoff‑задачи.

## RLM Read Policy
- MUST: читать `aidd/reports/research/<ticket>-rlm.pack.*` first.
- PREFER: использовать `rlm-slice` pack для узких запросов.
- MUST NOT: читать `*-rlm.nodes.jsonl` или `*-rlm.links.jsonl` целиком; только spot‑check через `rg`.

## MUST READ FIRST
- aidd/docs/prd/<ticket>.prd.md: AIDD:ACCEPTANCE
- aidd/docs/tasklist/<ticket>.md: AIDD:CHECKLIST_QA (или QA‑подсекция в AIDD:CHECKLIST) + AIDD:HANDOFF_INBOX + AIDD:TEST_EXECUTION
- aidd/docs/spec/<ticket>.spec.yaml (если существует)
- aidd/reports/tests/* и diff (если есть)

## MUST UPDATE
- aidd/docs/tasklist/<ticket>.md: QA чекбоксы + known issues + AIDD:QA_TRACEABILITY
- aidd/reports/qa/<ticket>.json
- AIDD:HANDOFF_INBOX через `${CLAUDE_PLUGIN_ROOT}/tools/tasks-derive.sh --source qa --append`.
- AIDD:CONTEXT_PACK → Blockers summary (если есть blocking handoff)
- Каждый finding оформляй как handoff‑задачу в `AIDD:HANDOFF_INBOX` (scope/DoD/Boundaries/Tests).
- Формат finding: `scope=iteration_id|n/a`, `blocking: true|false`, DoD/Boundaries/Tests как часть handoff.
- Write surface (разрешено):
  - front‑matter: `Status`, `Updated` (и `Stage`, если есть)
  - `AIDD:CHECKLIST_QA` (или QA‑подсекция в `AIDD:CHECKLIST`)
  - `AIDD:QA_TRACEABILITY`
  - `AIDD:HANDOFF_INBOX` (через derive)
  - `AIDD:CONTEXT_PACK` (только Status/Stage/Blockers summary)

## MUST NOT
- READY при blocker/critical.
- Прятать gaps — перечислять явно.
- Придумывать тест‑команды вне `AIDD:TEST_EXECUTION`.
- Любые правки кода/конфигов/тестов/CI. QA фиксирует только задачи в tasklist.
- Любые изменения вне `aidd/docs/tasklist/<ticket>.md` (кроме автогенерируемых отчётов в `aidd/reports/**`).
- Переписывать `AIDD:ITERATIONS_FULL`, `AIDD:SPEC_PACK`, `AIDD:TEST_EXECUTION`, `AIDD:NEXT_3`.

## Repeat runs
- Повторные запуски QA/`tasks-derive` должны обновлять задачи по стабильному `id` без дублей.

## Output contract
- Status: READY|WARN|BLOCKED (source‑of‑truth: front‑matter Status, mirror in AIDD:CONTEXT_PACK)
