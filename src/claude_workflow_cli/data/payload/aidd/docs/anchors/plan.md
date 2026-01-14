# Anchor: plan

## Goals
- План на уровне milestones (macro), не tasklist.
- Итерации с `iteration_id` и измеримым DoD.
- Явный Files/Modules touched.
- Test strategy per iteration + миграции/флаги + observability.

## MUST READ FIRST
- aidd/docs/prd/<ticket>.prd.md: AIDD:ACCEPTANCE, AIDD:ROLL_OUT
- aidd/docs/research/<ticket>.md: AIDD:INTEGRATION_POINTS, AIDD:REUSE_CANDIDATES, AIDD:RISKS

## MUST UPDATE
- aidd/docs/plan/<ticket>.md:
  - AIDD:ARCHITECTURE
  - AIDD:FILES_TOUCHED
  - AIDD:ITERATIONS
  - AIDD:TEST_STRATEGY
  - AIDD:RISKS

## MUST NOT
- Over-engineering без обоснования (KISS/YAGNI).
- Пропускать тест‑стратегию и миграции/флаги (если есть).
- Чекбоксы `- [ ]`, execution‑команды и микрошаги по файлам/функциям в итерациях.
- Конкретные команды тестов/CLI (это уровень tasklist).

## Output contract
- План готов к validator и /review-spec.
