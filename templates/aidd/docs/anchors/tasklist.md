# Anchor: tasklist

## Goals
- Tasklist — единственный источник для implement/review/qa.
- Спека хранится в `aidd/docs/spec/<ticket>.spec.yaml` (если есть), tasklist содержит краткий `AIDD:SPEC_PACK`.
- Чекбоксы однозначны (iteration_id/DoD/Boundaries/Steps/Tests) и не требуют дополнительных догадок.

## MUST READ FIRST
- aidd/docs/tasklist/<ticket>.md:
  - AIDD:CONTEXT_PACK
  - AIDD:SPEC_PACK
  - AIDD:TEST_STRATEGY
  - AIDD:TEST_EXECUTION
  - AIDD:ITERATIONS_FULL
  - AIDD:NEXT_3
- aidd/docs/spec/<ticket>.spec.yaml (status, contracts, risks, test strategy) if exists
- aidd/docs/plan/<ticket>.md: AIDD:FILES_TOUCHED, AIDD:ITERATIONS, AIDD:TEST_STRATEGY
- aidd/docs/prd/<ticket>.prd.md: AIDD:ACCEPTANCE, AIDD:ROLL_OUT
- aidd/docs/research/<ticket>.md: AIDD:INTEGRATION_POINTS, AIDD:RISKS
- aidd/reports/context/latest_working_set.md (если есть)

## MUST UPDATE
- aidd/docs/tasklist/<ticket>.md:
  - AIDD:SPEC_PACK
  - AIDD:TEST_STRATEGY
  - AIDD:TEST_EXECUTION
  - AIDD:ITERATIONS_FULL
  - AIDD:NEXT_3
  - AIDD:HANDOFF_INBOX
  - AIDD:CHECKLIST
  - AIDD:QA_TRACEABILITY (если был QA)

## MUST NOT
- Оставлять tasklist без AIDD:NEXT_3 или AIDD:SPEC_PACK.
- Задавать очевидные вопросы (ответ уже в plan/PRD/research/tasklist).
- Начинать реализацию кода.

## Spec required policy
- Spec обязателен, если есть изменения UI/UX, API‑контрактов, данных/миграций, или e2e на стенде.
- Spec опционален для рефакторинга без изменения поведения, фикса багов без изменения контракта, docs‑only.

## Definition of Done
- `AIDD:SPEC_PACK`, `AIDD:TEST_STRATEGY`, `AIDD:TEST_EXECUTION` заполнены.
- `AIDD:ITERATIONS_FULL` подробен и детальнее плана (iteration_id/DoD/Boundaries/Steps/Tests/Dependencies/Risks).
- Каждый implement‑чекбокс содержит iteration_id + DoD + Boundaries + Steps + Tests + Acceptance mapping.

## Output contract
- Tasklist готов к /implement.
- Если данных недостаточно для DoD/Boundaries/Tests — запусти `/spec-interview`, затем `/tasks-new` для синхронизации.
- (Опционально) preflight: `PYTHONPATH=${CLAUDE_PLUGIN_ROOT:-.} python3 -m aidd_runtime.cli tasklist-check --ticket <ticket>`.
