# Anchor: tasklist

## Goals
- Tasklist — единственный источник для implement/review/qa.
- Спека хранится в `aidd/docs/spec/<ticket>.spec.yaml` (если есть), tasklist содержит краткий `AIDD:SPEC_PACK`.
- Чекбоксы однозначны (DoD/Boundaries/Tests) и не требуют дополнительных догадок.

## MUST READ FIRST
- aidd/docs/tasklist/<ticket>.md:
  - AIDD:CONTEXT_PACK
  - AIDD:SPEC_PACK
  - AIDD:TEST_STRATEGY
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
  - AIDD:ITERATIONS_FULL
  - AIDD:NEXT_3
  - AIDD:HANDOFF_INBOX
  - AIDD:CHECKLIST

## MUST NOT
- Оставлять tasklist без AIDD:NEXT_3 или AIDD:SPEC_PACK.
- Задавать очевидные вопросы (ответ уже в plan/PRD/research/tasklist).
- Начинать реализацию кода.

## Definition of Done
- `AIDD:SPEC_PACK` и `AIDD:TEST_STRATEGY` заполнены.
- `AIDD:ITERATIONS_FULL` подробен и детальнее плана (DoD/Boundaries/Tests/Dependencies/Risks).
- Каждый implement‑чекбокс содержит DoD + Boundaries + Tests.

## Output contract
- Tasklist готов к /implement.
- Если данных недостаточно для DoD/Boundaries/Tests — запусти `/spec-interview`, затем `/tasks-new` для синхронизации.
- (Опционально) preflight: `claude-workflow tasklist-check --ticket <ticket>`.
