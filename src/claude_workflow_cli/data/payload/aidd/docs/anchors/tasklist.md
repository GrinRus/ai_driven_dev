# Anchor: tasklist

## Goals
- Tasklist — единственный источник для implement/review/qa.
- Спека живёт внутри tasklist: `AIDD:SPEC` + `AIDD:SPEC_PACK`.
- Интервью закрыто, чекбоксы однозначны (DoD/Boundaries/Tests).

## MUST READ FIRST
- aidd/docs/tasklist/<ticket>.md:
  - AIDD:CONTEXT_PACK
  - AIDD:SPEC_PACK
  - AIDD:INTERVIEW
  - AIDD:NEXT_3
- aidd/docs/plan/<ticket>.md: AIDD:FILES_TOUCHED, AIDD:ITERATIONS, AIDD:TEST_STRATEGY
- aidd/docs/prd/<ticket>.prd.md: AIDD:ACCEPTANCE, AIDD:ROLL_OUT
- aidd/docs/research/<ticket>.md: AIDD:INTEGRATION_POINTS, AIDD:RISKS
- aidd/reports/context/latest_working_set.md (если есть)

## MUST UPDATE
- aidd/docs/tasklist/<ticket>.md:
  - AIDD:SPEC
  - AIDD:SPEC_PACK
  - AIDD:INTERVIEW
  - AIDD:DECISIONS
  - AIDD:TEST_POLICY
  - AIDD:OPEN_QUESTIONS
  - AIDD:TASKLIST_REFINEMENT
  - AIDD:NEXT_3
  - AIDD:HANDOFF_INBOX
  - AIDD:CHECKLIST

## MUST NOT
- Оставлять tasklist без AIDD:NEXT_3 или AIDD:SPEC_PACK.
- Задавать очевидные вопросы (ответ уже в plan/PRD/research/tasklist).
- Начинать реализацию кода.

## Interview rules (non-obvious)
Вопрос допустим только если:
- ответа нет в plan/PRD/research/tasklist;
- меняет решение по UI/UX, контрактам, данным, тест-матрице, rollout или observability;
- содержит `Зачем` + `Варианты` + `Default`.

## Definition of Done
- `AIDD:SPEC Status: READY`.
- Coverage checklist в `AIDD:INTERVIEW` закрыт, blocker-вопросов нет.
- Каждый implement‑чекбокс содержит DoD + Boundaries + Tests.

## Output contract
- Tasklist готов к /implement.
- (Опционально) preflight: `claude-workflow tasklist-check --ticket <ticket>`.
