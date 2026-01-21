# Anchor: tasklist

## Goals
- Tasklist — единственный источник для implement/review/qa.
- Спека хранится в `aidd/docs/spec/<ticket>.spec.yaml` (если есть), tasklist содержит краткий `AIDD:SPEC_PACK`.
- Чекбоксы однозначны (iteration_id/DoD/Boundaries/Steps/Tests) и не требуют дополнительных догадок.
- `AIDD:NEXT_3` — pointer list (1–2 строки + ref), без истории и без `[x]`.

## Graph Read Policy
- MUST: читать `aidd/reports/research/<ticket>-call-graph.pack.*` или `graph-slice` pack.
- MUST: точечный `rg` по `aidd/reports/research/<ticket>-call-graph.edges.jsonl`.
- MUST NOT: `Read` full `*-call-graph-full.json` или `*.cjson`.

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
  - AIDD:PROGRESS_LOG

## MUST NOT
- Оставлять tasklist без AIDD:NEXT_3 или AIDD:SPEC_PACK.
- Задавать очевидные вопросы (ответ уже в plan/PRD/research/tasklist).
- Начинать реализацию кода.
- Создавать дубли `## AIDD:*` секций.
- Копировать подробности DoD/Steps/Tests в `AIDD:NEXT_3`.

## Budgets (soft, unless stage=review/qa)
- `AIDD:CONTEXT_PACK` TL;DR <= 12 bullets.
- `Blockers summary` <= 8 строк.
- `AIDD:NEXT_3` item <= 12 строк.
- `AIDD:HANDOFF_INBOX` item <= 20 строк.

## Spec required policy
- Spec обязателен, если есть изменения UI/UX, API‑контрактов, данных/миграций, или e2e на стенде.
- Spec опционален для рефакторинга без изменения поведения, фикса багов без изменения контракта, docs‑only.

## Definition of Done
- `AIDD:SPEC_PACK`, `AIDD:TEST_STRATEGY`, `AIDD:TEST_EXECUTION` заполнены.
- `AIDD:ITERATIONS_FULL` подробен и детальнее плана (iteration_id/DoD/Boundaries/Steps/Tests/Dependencies/Risks).
- Каждая итерация в `AIDD:ITERATIONS_FULL` размечена state (чекбокс или `State:`).
- `AIDD:NEXT_3` содержит только ref‑строки на open items (iterations + handoff) и отсортирован по Blocking/Priority.
- Каждый implement‑чекбокс содержит iteration_id + DoD + Boundaries + Steps + Tests + Acceptance mapping.

## Output contract
- Tasklist готов к /feature-dev-aidd:implement.
- Если данных недостаточно для DoD/Boundaries/Tests — запусти `/feature-dev-aidd:spec-interview`, затем `/feature-dev-aidd:tasks-new` для синхронизации.
- (Опционально) preflight: `${CLAUDE_PLUGIN_ROOT}/tools/tasklist-check.sh --ticket <ticket>`.
